import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, insert
from .db import Session
from .models import Base, OPERATIONAL, DatasetGenerationRun, ValidationResult, GroundTruth
from .generator import generate, checksums, canonical, GeneratorConfig
from .rules import detect, evaluate
from .validation import validate
import json

log = logging.getLogger(__name__)


def load_operational(db, workspace):
    # Ground truth is intentionally absent from this data loading path.
    data = {name: [dict(r) for r in db.execute(select(table).where(table.c.workspace_id == workspace)).mappings()]
            for name, table in OPERATIONAL.items()}
    # Resolve referenced operational dependencies (for example a manual actor acknowledging
    # a simulated alarm) without importing unrelated workspaces or evaluation labels.
    changed = True
    while changed:
        changed = False
        for name, table in OPERATIONAL.items():
            for col in table.columns:
                for fk in col.foreign_keys:
                    target = fk.column.table.name
                    if target not in OPERATIONAL: continue
                    known = {r['id'] for r in data[target]}
                    missing = {r[col.name] for r in data[name] if r.get(col.name) is not None} - known
                    if missing:
                        extras = [dict(r) for r in db.execute(select(OPERATIONAL[target]).where(OPERATIONAL[target].c.id.in_(missing))).mappings()]
                        if extras: data[target].extend(extras); changed = True
    return data


def generate_and_store(id: str, config: GeneratorConfig):
    def progress(value):
        with Session.begin() as db:
            run = db.get(DatasetGenerationRun, id)
            run.status, run.progress = "RUNNING", value
    try:
        progress(1)
        data = generate(config, progress)
        operational = {k: v for k, v in data.items() if k != "ground_truth"}
        detections = detect(operational)
        report = dict(validation=validate(operational, data["ground_truth"]), evaluation=evaluate(operational, data["ground_truth"], detections),
                      detections=detections, checksums=checksums(data))
        if report["validation"]["status"] == "FAIL":
            raise ValueError("Unexpected integrity failures: "+canonical(report["validation"]["findings"][:5]))
        with Session.begin() as db:
            for table in Base.metadata.sorted_tables:
                rows = data.get(table.name, [])
                for offset in range(0, len(rows), 2000):
                    db.execute(insert(table), rows[offset:offset+2000])
            run = db.get(DatasetGenerationRun, id)
            run.status, run.progress = "COMPLETED", 100
            run.counts, run.checksum = report["checksums"]["counts"], report["checksums"]["overall"]
            db.add(ValidationResult(id=f"VAL-{uuid.uuid4().hex}", run_id=id, report=json.loads(canonical(report))))
    except Exception as exc:
        log.exception("Dataset generation failed: %s", id)
        with Session.begin() as db:
            run = db.get(DatasetGenerationRun, id)
            run.status, run.error = "FAILED", str(exc)


def analyse_workspace(db, workspace):
    operational = load_operational(db, workspace)
    detections = detect(operational)
    # Labels are loaded only after detection has completed.
    truth = [dict(r) for r in db.execute(select(GroundTruth.__table__).where(GroundTruth.workspace_id == workspace)).mappings()]
    return operational, truth, dict(validation=validate(operational, truth), evaluation=evaluate(operational, truth, detections), detections=detections)
