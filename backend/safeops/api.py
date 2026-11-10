from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hmac
import json
import os
import shutil
import uuid
import logging
import zipfile
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException, Query, Response, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, or_, and_, case, distinct
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session as DBSession
from .db import Session, engine, get_db, ROOT
from .models import *
from .schemas import *
from .auth import actor, permit, token
from .generator import GeneratorConfig, VERSION, digest, checksums, generate, canonical
from .rules import ack_status, aware, INCIDENT_PATH, ACTION_PATH, detect
from .services import generate_and_store, analyse_workspace
from .artifacts import export_dataset

jobs = ThreadPoolExecutor(max_workers=1, thread_name_prefix="safeops-generator")


@asynccontextmanager
async def lifespan(app):
    with Session.begin() as db:
        for role, name in [("operator", "Asha · Operator"), ("engineer", "Dev · Engineer"), ("planner", "Mira · Planner"), ("admin", "Administrator")]:
            id = f"USR-DEMO-{role}"
            if not db.get(ApplicationUser, id):
                db.add(ApplicationUser(id=id, workspace_id="manual", name=name, role=role))
        for run in db.scalars(select(DatasetGenerationRun).where(DatasetGenerationRun.status.in_(["RUNNING", "QUEUED"]))):
            run.status, run.error = "FAILED", "Server restarted before generation completed; submit a new configuration to retry"
    yield
    jobs.shutdown(wait=False)


app = FastAPI(title="SafeOps Intelligence", version=VERSION, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[os.getenv("CORS_ORIGIN", "http://localhost:3000")],
                   allow_credentials=True, allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type"])


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse({"error": {"message": exc.detail, "status": exc.status_code}}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse({"error": {"message": "Check the submitted fields", "fields": json.loads(json.dumps(exc.errors(), default=str))}}, status_code=422)


@app.exception_handler(IntegrityError)
async def integrity_error(request, exc):
    return JSONResponse({"error": {"message": "This record conflicts with existing data or a required relationship", "status": 409}}, status_code=409)


@app.exception_handler(OperationalError)
async def database_error(request, exc):
    logging.getLogger(__name__).error("PostgreSQL request failed", exc_info=exc)
    return JSONResponse({"error": {"message": "PostgreSQL is unavailable. Check the local database and retry.", "status": 503}}, status_code=503)


def row(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def uid(prefix): return prefix+"-MAN-"+uuid.uuid4().hex[:16]


def get(db, model, id, lock=False):
    obj = db.scalar(select(model).where(model.id == id).with_for_update()) if lock else db.get(model, id)
    if not obj: raise HTTPException(404, f"{model.__name__} not found")
    return obj


def scope(model, workspace):
    return model.workspace_id.in_([workspace, "manual"])


def audit(db, user, entity, record_id, operation, evidence):
    db.add(AuditEvent(id=uid("AUD"), workspace_id="manual", entity=entity, record_id=record_id,
        user_id=user.id, operation=operation, occurred_at=utcnow(), evidence=json.loads(canonical(evidence))))


@app.get("/api/health")
def health(db: DBSession = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "database": "PostgreSQL", "version": VERSION}


@app.post("/api/auth/login")
def login(body: Login, response: Response):
    password = os.getenv("DEMO_PASSWORD", "")
    if not password: raise HTTPException(503, "Configure DEMO_PASSWORD in .env")
    if not hmac.compare_digest(body.password, password): raise HTTPException(401, "Incorrect demonstration password")
    response.set_cookie("safeops_session", token(f"USR-DEMO-{body.role}"), httponly=True, samesite="strict", max_age=28800)
    return {"role": body.role}


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie("safeops_session")
    return {"ok": True}


@app.get("/api/auth/me")
def me(user=Depends(actor)): return row(user)


@app.get("/api/users")
def users(db: DBSession = Depends(get_db), user=Depends(actor)):
    return [row(u) for u in db.scalars(select(ApplicationUser).where(ApplicationUser.workspace_id == "manual").order_by(ApplicationUser.name))]


@app.get("/api/datasets")
def datasets(db: DBSession = Depends(get_db), user=Depends(permit("admin"))):
    return [row(r) for r in db.scalars(select(DatasetGenerationRun).order_by(DatasetGenerationRun.created_at.desc()).limit(100))]


@app.get("/api/workspaces")
def workspaces(db: DBSession = Depends(get_db), user=Depends(actor)):
    """Operational dataset selector; no labels, validation reports or job internals."""
    return [{"id": r.id, "status": "COMPLETED", "config": {k: r.config[k] for k in ("preset", "seed", "events")}}
            for r in db.scalars(select(DatasetGenerationRun).where(DatasetGenerationRun.status == "COMPLETED")
                                .order_by(DatasetGenerationRun.created_at.desc()).limit(100))]


def evaluation_labels(db, workspace):
    return [row(r) for r in db.scalars(select(GroundTruth).where(GroundTruth.workspace_id == workspace).order_by(GroundTruth.id))]


@app.post("/api/datasets", status_code=202)
def new_dataset(body: GeneratorConfig, db: DBSession = Depends(get_db), user=Depends(permit("admin"))):
    id = "sim-"+digest({"version": VERSION, **body.model_dump()})[:10]
    existing = db.get(DatasetGenerationRun, id)
    if existing and existing.status == "FAILED":
        # Transactional generation never committed rows for a failed run; retry is safe.
        existing.status, existing.progress, existing.error = "QUEUED", 0, None
    elif existing: return row(existing)
    else:
        existing = DatasetGenerationRun(id=id, status="QUEUED", progress=0, config=body.model_dump(), counts={})
        db.add(existing)
    db.commit()
    jobs.submit(generate_and_store, id, body)
    return row(existing)


@app.get("/api/datasets/{id}/report")
def dataset_report(id: str, db: DBSession = Depends(get_db), user=Depends(permit("admin"))):
    run = get(db, DatasetGenerationRun, id)
    report = db.scalar(select(ValidationResult).where(ValidationResult.run_id == id).order_by(ValidationResult.created_at.desc()))
    return {"run": row(run), "report": {**report.report, "ground_truth": evaluation_labels(db, id)} if report else None}


@app.post("/api/datasets/{id}/validate")
def validate_dataset(id: str, db: DBSession = Depends(get_db), user=Depends(permit("admin"))):
    get(db, DatasetGenerationRun, id)
    _, _, report = analyse_workspace(db, id)
    db.add(ValidationResult(id=uid("VAL"), run_id=id, report=json.loads(canonical(report))))
    db.commit()
    return {**report, "ground_truth": evaluation_labels(db, id)}


@app.get("/api/datasets/{id}/export")
def export(id: str, format: Literal["bundle", "csv", "json", "sql", "validation", "ground-truth"] = "bundle",
           db: DBSession = Depends(get_db), user=Depends(permit("admin"))):
    run = get(db, DatasetGenerationRun, id)
    if run.status != "COMPLETED": raise HTTPException(409, "Wait for generation to finish")
    operational, truth, report = analyse_workspace(db, id)
    config = GeneratorConfig(**run.config)
    # Compare immutable generated output; operational acknowledgements and edits are exported as currently stored.
    first, second = generate(config), generate(config)
    a, b = checksums(first), checksums(second)
    repro = {"tested": True, "identical": a == b, "first": a, "second": b,
             "scope": "Fresh generator runs; live operational changes intentionally excluded from reproduction comparison"}
    path = ROOT/"exports"/id
    export_dataset({**operational, "ground_truth": truth}, config, report, path, repro)
    if format == "validation":
        return FileResponse(path/"validation-summary.json", filename=f"safeops-{id}-validation.json", media_type="application/json")
    if format == "ground-truth":
        return FileResponse(path/"evaluation"/"ground_truth.json", filename=f"safeops-{id}-ground-truth.json", media_type="application/json")
    if format != "bundle":
        archive = ROOT/"exports"/f"{id}-{format}.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
            for file in sorted(path.rglob("*")):
                if not file.is_file(): continue
                relative = file.relative_to(path)
                if relative.parts[0] == format or (relative.parts[0] == "evaluation" and file.suffix == f".{format}"):
                    zipped.write(file, relative.as_posix())
            for name in ("source-manifest.json", "generation-config.json", "data-dictionary.json", "reproducibility-report.json"):
                zipped.write(path/name, name)
        return FileResponse(archive, filename=f"safeops-{id}-{format}.zip", media_type="application/zip")
    archive = shutil.make_archive(str(path), "zip", path)
    return FileResponse(archive, filename=f"safeops-{id}.zip", media_type="application/zip")


@app.post("/api/datasets/{id}/reproduce")
def reproduce_dataset(id: str, db: DBSession = Depends(get_db), user=Depends(permit("admin"))):
    run = get(db, DatasetGenerationRun, id)
    config = GeneratorConfig(**run.config)
    first, second = checksums(generate(config)), checksums(generate(config))
    result = {"tested": True, "identical": first == second, "first": first, "second": second}
    path = ROOT/"exports"/id
    path.mkdir(parents=True, exist_ok=True)
    (path/"reproducibility-report.json").write_text(canonical(result), encoding="utf-8")
    return result


@app.get("/api/plants")
def plants(workspace: str = "manual", db: DBSession = Depends(get_db), user=Depends(actor)):
    return [row(p) for p in db.scalars(select(Plant).where(scope(Plant, workspace)).order_by(Plant.name))]


@app.get("/api/machines")
def machines(workspace: str = "manual", plant_id: str | None = None, q: str = "", page: int = Query(1, ge=1),
             limit: int = Query(25, ge=1, le=100), db: DBSession = Depends(get_db), user=Depends(actor)):
    stmt = select(Machine, Plant.name.label("plant_name")).join(Plant, Plant.id == Machine.plant_id).where(scope(Machine, workspace))
    if plant_id: stmt = stmt.where(Machine.plant_id == plant_id)
    if q: stmt = stmt.where(or_(Machine.name.ilike(f"%{q}%"), Machine.id.ilike(f"%{q}%")))
    count = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = []
    for m, plant in db.execute(stmt.order_by(Machine.name).offset((page-1)*limit).limit(limit)):
        state = db.scalar(select(MachineStateEvent).where(MachineStateEvent.machine_id == m.id).order_by(MachineStateEvent.occurred_at.desc(), MachineStateEvent.id.desc()).limit(1))
        items.append({**row(m), "plant_name": plant, "current_state": state.state if state else "UNKNOWN"})
    return {"items": items, "total": count, "page": page, "limit": limit}


def alarm_query(workspace, plant_id=None, machine_id=None, severity=None, start=None, end=None, status=None, q=""):
    stmt = select(AlarmEvent, AlarmDefinition, Machine.name, Acknowledgement).join(AlarmDefinition, AlarmDefinition.id == AlarmEvent.definition_id).join(Machine, Machine.id == AlarmEvent.machine_id).outerjoin(Acknowledgement, Acknowledgement.alarm_id == AlarmEvent.id).where(scope(AlarmEvent, workspace))
    if plant_id: stmt = stmt.where(Machine.plant_id == plant_id)
    if machine_id: stmt = stmt.where(AlarmEvent.machine_id == machine_id)
    if severity: stmt = stmt.where(AlarmDefinition.severity == severity)
    if start: stmt = stmt.where(AlarmEvent.occurred_at >= start)
    if end: stmt = stmt.where(AlarmEvent.occurred_at < end)
    if status == "UNACKNOWLEDGED": stmt = stmt.where(Acknowledgement.id.is_(None))
    if status == "ACKNOWLEDGED": stmt = stmt.where(Acknowledgement.id.is_not(None))
    if status in ("LATE", "INVALID", "DELAYED"):
        seconds = func.extract("epoch", Acknowledgement.acknowledged_at-AlarmEvent.occurred_at)
        if status == "DELAYED":
            stmt = stmt.where(or_(seconds > AlarmDefinition.ack_deadline_seconds, and_(Acknowledgement.id.is_(None), func.extract("epoch", func.now()-AlarmEvent.occurred_at) > AlarmDefinition.ack_deadline_seconds)))
        else:
            stmt = stmt.where(seconds > AlarmDefinition.ack_deadline_seconds if status == "LATE" else seconds < 0)
    if q: stmt = stmt.where(or_(AlarmEvent.message.ilike(f"%{q}%"), Machine.name.ilike(f"%{q}%"), AlarmEvent.id.ilike(f"%{q}%")))
    return stmt


@app.get("/api/alarms")
def alarms(workspace: str = "manual", plant_id: str | None = None, machine_id: str | None = None, severity: str | None = None,
           start: datetime | None = None, end: datetime | None = None, status: str | None = None, q: str = "",
           page: int = Query(1, ge=1), limit: int = Query(25, ge=1, le=100), sort: str = Query("newest", pattern="^(newest|oldest)$"),
           db: DBSession = Depends(get_db), user=Depends(actor)):
    stmt = alarm_query(workspace, plant_id, machine_id, severity, start, end, status, q)
    count = db.scalar(select(func.count()).select_from(stmt.subquery()))
    order = AlarmEvent.occurred_at.asc() if sort == "oldest" else AlarmEvent.occurred_at.desc()
    latest_analysis = db.scalar(select(ValidationResult).where(ValidationResult.run_id == workspace).order_by(ValidationResult.created_at.desc()).limit(1))
    nuisance_ids, flood_ids = set(), set()
    for finding in latest_analysis.report.get("detections", []) if latest_analysis else []:
        if finding["rule_id"] == "NUISANCE_ALARM": nuisance_ids.update(finding["affected_record_ids"])
        if finding["rule_id"] == "ALARM_FLOOD": flood_ids.update(finding["affected_record_ids"])
    items = []
    for a, definition, machine_name, ack in db.execute(stmt.order_by(order, AlarmEvent.id).offset((page-1)*limit).limit(limit)):
        original = db.scalar(select(AlarmEvent.id).where(AlarmEvent.source_event_id == a.source_event_id, AlarmEvent.machine_id == a.machine_id).order_by(AlarmEvent.created_at, AlarmEvent.id).limit(1))
        items.append({**row(a), "severity": definition.severity, "machine_name": machine_name,
            "definition_name": definition.name, "is_replay": original != a.id, "is_nuisance": a.id in nuisance_ids,
            "in_flood": a.id in flood_ids, **ack_status(row(a), row(ack) if ack else None, row(definition))})
    return {"items": items, "total": count, "page": page, "limit": limit}


@app.post("/api/alarms/{id}/acknowledge", status_code=201)
def acknowledge(id: str, body: Acknowledge, db: DBSession = Depends(get_db), user=Depends(permit("operator", "engineer", "admin"))):
    a = get(db, AlarmEvent, id, lock=True)
    if db.scalar(select(Acknowledgement).where(Acknowledgement.alarm_id == id)): raise HTTPException(409, "This alarm is already acknowledged")
    now = utcnow()
    if now < aware(a.occurred_at): raise HTTPException(422, "Cannot acknowledge an alarm before it occurs")
    ack = Acknowledgement(id=f"ACK-{id}-01", workspace_id=a.workspace_id, alarm_id=id, user_id=user.id, acknowledged_at=now, note=body.note)
    db.add(ack)
    audit(db, user, "alarm_events", id, "ACKNOWLEDGE", {"note": body.note})
    db.commit()
    return row(ack)


@app.get("/api/incidents")
def incidents(workspace: str = "manual", severity: str | None = None, status: str | None = None, plant_id: str | None = None,
              machine_id: str | None = None, q: str = "", page: int = Query(1, ge=1), limit: int = Query(25, ge=1, le=100),
              db: DBSession = Depends(get_db), user=Depends(actor)):
    stmt = select(Incident, Machine.name).join(Machine, Machine.id == Incident.machine_id).where(scope(Incident, workspace))
    if severity: stmt = stmt.where(Incident.severity == severity)
    if status == "ACTIVE": stmt = stmt.where(Incident.status.not_in(["RESOLVED", "CLOSED"]))
    elif status: stmt = stmt.where(Incident.status == status)
    if plant_id: stmt = stmt.where(Machine.plant_id == plant_id)
    if machine_id: stmt = stmt.where(Incident.machine_id == machine_id)
    if q: stmt = stmt.where(Incident.title.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = []
    for i, machine in db.execute(stmt.order_by(Incident.occurred_at.desc(), Incident.id).offset((page-1)*limit).limit(limit)):
        links = db.scalar(select(func.count()).select_from(IncidentAlarm).where(IncidentAlarm.incident_id == i.id))
        items.append({**row(i), "machine_name": machine, "missing_context": links == 0})
    return {"items": items, "total": total, "page": page, "limit": limit}


@app.post("/api/incidents", status_code=201)
def create_incident(body: IncidentCreate, db: DBSession = Depends(get_db), user=Depends(permit("engineer", "admin"))):
    a = get(db, AlarmEvent, body.alarm_id)
    d = get(db, AlarmDefinition, a.definition_id)
    i = Incident(id=uid("INC-2026"), workspace_id="manual", machine_id=a.machine_id, title=body.title, severity=d.severity, status="OPEN", occurred_at=a.occurred_at, rule_id="MANUAL_INVESTIGATION")
    db.add(i); db.flush()
    db.add(IncidentAlarm(id=uid("IA"), workspace_id="manual", incident_id=i.id, alarm_id=a.id))
    db.add(IncidentStatusHistory(id=uid("IH"), workspace_id="manual", incident_id=i.id, from_status=None, to_status="OPEN", user_id=user.id, occurred_at=utcnow(), note="Investigation opened from alarm evidence"))
    audit(db, user, "incidents", i.id, "CREATE", body.model_dump())
    db.commit(); return row(i)


@app.post("/api/incidents/{id}/transition")
def transition_incident(id: str, body: Transition, db: DBSession = Depends(get_db), user=Depends(permit("engineer", "admin"))):
    i = get(db, Incident, id, lock=True)
    if i.status == "CLOSED" or body.status not in INCIDENT_PATH or INCIDENT_PATH.index(body.status) != INCIDENT_PATH.index(i.status)+1:
        raise HTTPException(409, "Follow OPEN → INVESTIGATING → ACTION_PENDING → RESOLVED → CLOSED")
    links = db.scalar(select(func.count()).select_from(IncidentAlarm).where(IncidentAlarm.incident_id == id))
    if not links: raise HTTPException(409, "Incident lacks triggering evidence; attach evidence before progressing")
    actions = list(db.scalars(select(CorrectiveAction).where(CorrectiveAction.incident_id == id)))
    if body.status == "ACTION_PENDING" and not actions: raise HTTPException(409, "Create a corrective action first")
    if body.status in ("RESOLVED", "CLOSED") and (not actions or any(a.status not in ("VERIFIED", "CLOSED") or not a.verification_evidence or not a.verified_at for a in actions)):
        raise HTTPException(409, "Every corrective action must be independently verified before resolution")
    old, i.status = i.status, body.status
    db.add(IncidentStatusHistory(id=uid("IH"), workspace_id=i.workspace_id, incident_id=id, from_status=old,
        to_status=body.status, user_id=user.id, occurred_at=utcnow(), note=body.note))
    audit(db, user, "incidents", id, "TRANSITION", body.model_dump())
    db.commit(); return row(i)


@app.post("/api/incidents/{id}/evidence", status_code=201)
def attach_evidence(id: str, values: dict, db: DBSession = Depends(get_db), user=Depends(permit("engineer", "admin"))):
    i = get(db, Incident, id, lock=True)
    if i.status in ("RESOLVED", "CLOSED"): raise HTTPException(409, "Resolved evidence is immutable")
    if set(values) != {"alarm_id"} or not isinstance(values["alarm_id"], str): raise HTTPException(422, "Supply alarm_id only")
    a = get(db, AlarmEvent, values["alarm_id"])
    if a.machine_id != i.machine_id: raise HTTPException(422, "Triggering alarm must belong to the incident machine")
    db.add(IncidentAlarm(id=uid("IA"), workspace_id=i.workspace_id, incident_id=id, alarm_id=a.id))
    audit(db, user, "incidents", id, "ATTACH_EVIDENCE", values)
    db.commit(); return {"ok": True}


@app.get("/api/actions")
def actions(workspace: str = "manual", status: str | None = None, severity: str | None = None, plant_id: str | None = None,
            q: str = "", page: int = Query(1, ge=1), limit: int = Query(25, ge=1, le=100), db: DBSession = Depends(get_db), user=Depends(actor)):
    stmt = select(CorrectiveAction, Incident.title, ApplicationUser.name).join(Incident, Incident.id == CorrectiveAction.incident_id).join(Machine, Machine.id == Incident.machine_id).join(ApplicationUser, ApplicationUser.id == CorrectiveAction.assignee_id).where(scope(CorrectiveAction, workspace))
    if status == "OVERDUE": stmt = stmt.where(CorrectiveAction.due_at < utcnow(), CorrectiveAction.status.not_in(["VERIFIED", "CLOSED"]))
    elif status: stmt = stmt.where(CorrectiveAction.status == status)
    if severity: stmt = stmt.where(CorrectiveAction.priority == severity)
    if plant_id: stmt = stmt.where(Machine.plant_id == plant_id)
    if q: stmt = stmt.where(CorrectiveAction.description.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = [{**row(a), "incident_title": title, "assignee_name": name, "overdue": aware(a.due_at) < utcnow() and a.status not in ("VERIFIED", "CLOSED"),
        "unverified_closure": a.status == "CLOSED" and not a.verification_evidence}
        for a, title, name in db.execute(stmt.order_by(CorrectiveAction.due_at, CorrectiveAction.id).offset((page-1)*limit).limit(limit))]
    return {"items": items, "total": total, "page": page, "limit": limit}


@app.post("/api/actions", status_code=201)
def create_action(body: ActionCreate, db: DBSession = Depends(get_db), user=Depends(permit("engineer", "admin"))):
    incident = get(db, Incident, body.incident_id)
    if incident.status in ("RESOLVED", "CLOSED"): raise HTTPException(409, "Cannot add an action to a resolved incident")
    assignee = get(db, ApplicationUser, body.assignee_id)
    if assignee.role not in ("engineer", "admin"): raise HTTPException(422, "Assign to an engineer or administrator")
    if body.due_at <= utcnow(): raise HTTPException(422, "Due date must be in the future")
    a = CorrectiveAction(id=uid("ACT-"+incident.id), workspace_id="manual", status="OPEN", **body.model_dump())
    db.add(a); db.flush()
    db.add(CorrectiveActionStatusHistory(id=uid("AH"), workspace_id="manual", action_id=a.id, from_status=None, to_status="OPEN", user_id=user.id, occurred_at=utcnow(), note="Action created and assigned"))
    audit(db, user, "corrective_actions", a.id, "CREATE", body.model_dump())
    db.commit(); return row(a)


@app.post("/api/actions/{id}/assign")
def assign_action(id: str, body: Assignment, db: DBSession = Depends(get_db), user=Depends(permit("engineer", "admin"))):
    a = get(db, CorrectiveAction, id, lock=True)
    if a.status in ("VERIFIED", "CLOSED"): raise HTTPException(409, "Verified actions cannot be reassigned")
    target = get(db, ApplicationUser, body.assignee_id)
    if target.role not in ("engineer", "admin"): raise HTTPException(422, "Choose an engineer or administrator")
    old, a.assignee_id = a.assignee_id, target.id
    audit(db, user, "corrective_actions", id, "ASSIGN", {"from": old, "to": target.id, "note": body.note})
    db.commit(); return row(a)


@app.post("/api/actions/{id}/transition")
def transition_action(id: str, body: Transition, db: DBSession = Depends(get_db), user=Depends(permit("engineer", "admin"))):
    a = get(db, CorrectiveAction, id, lock=True)
    if a.status == "CLOSED" or body.status not in ACTION_PATH or ACTION_PATH.index(body.status) != ACTION_PATH.index(a.status)+1:
        raise HTTPException(409, "Follow OPEN → IN_PROGRESS → COMPLETED → VERIFIED → CLOSED; verification is mandatory")
    now = utcnow()
    if body.status == "COMPLETED": a.completed_at = now
    if body.status == "VERIFIED":
        if user.id == a.assignee_id: raise HTTPException(409, "Verification requires a different engineer or administrator")
        if not a.completed_at or not body.verification_evidence or len(body.verification_evidence.strip()) < 10:
            raise HTTPException(422, "Record completion and at least 10 characters of verification evidence")
        a.verified_at, a.verified_by, a.verification_evidence = now, user.id, body.verification_evidence
    if body.status == "CLOSED" and not (a.verified_at and a.verified_by and a.verification_evidence):
        raise HTTPException(409, "Closure requires verification")
    old, a.status = a.status, body.status
    db.add(CorrectiveActionStatusHistory(id=uid("AH"), workspace_id=a.workspace_id, action_id=id, from_status=old,
        to_status=body.status, user_id=user.id, occurred_at=now, note=body.note))
    audit(db, user, "corrective_actions", id, "TRANSITION", body.model_dump())
    db.commit(); return row(a)


CONFIG_MODELS = {"plants": Plant, "machines": Machine, "zones": SafetyZone, "interlocks": Interlock, "definitions": AlarmDefinition}
CONFIG_SCHEMAS = {"plants": PlantCreate, "machines": MachineCreate, "zones": ZoneCreate, "interlocks": InterlockCreate, "definitions": DefinitionCreate}


@app.get("/api/config/{resource}")
def configuration(resource: str, workspace: str = "manual", machine_id: str | None = None,
                  db: DBSession = Depends(get_db), user=Depends(actor)):
    model = CONFIG_MODELS.get(resource)
    if not model: raise HTTPException(404, "Unknown configuration resource")
    stmt = select(model).where(scope(model, workspace))
    if machine_id and hasattr(model, "machine_id"): stmt = stmt.where(model.machine_id == machine_id)
    if hasattr(model, "effective_to"): stmt = stmt.where(model.effective_to.is_(None))
    return [row(r) for r in db.scalars(stmt.order_by(model.id).limit(2000))]


def config_payload(resource, values):
    schema = CONFIG_SCHEMAS.get(resource)
    if not schema: raise HTTPException(404, "Unknown configuration resource")
    try: return schema.model_validate(values).model_dump()
    except Exception as exc: raise HTTPException(422, str(exc))


def check_config_refs(db, resource, values):
    if "plant_id" in values: get(db, Plant, values["plant_id"])
    if "machine_id" in values:
        m = get(db, Machine, values["machine_id"])
        if "plant_id" in values and m.plant_id != values["plant_id"]:
            raise HTTPException(422, "Machine and safety zone must belong to the same plant")
    if "zone_id" in values:
        zone = get(db, SafetyZone, values["zone_id"])
        m = get(db, Machine, values["machine_id"])
        if zone.plant_id != m.plant_id: raise HTTPException(422, "Interlock and zone must belong to the same plant")
        bridge = db.scalar(select(MachineSafetyZone).where(MachineSafetyZone.machine_id == m.id, MachineSafetyZone.zone_id == zone.id))
        if not bridge: raise HTTPException(422, "Zone must be assigned to this machine")


@app.post("/api/config/{resource}", status_code=201)
def create_config(resource: str, values: dict, db: DBSession = Depends(get_db), user=Depends(permit("admin"))):
    values = config_payload(resource, values)
    check_config_refs(db, resource, values)
    machine_id = values.pop("machine_id") if resource == "zones" else None
    if resource in ("zones", "interlocks", "definitions"): values |= {"effective_from": utcnow(), "effective_to": None}
    obj = CONFIG_MODELS[resource](id=uid({"plants": "PLT", "machines": "MAC", "zones": "SAFE", "interlocks": "INT", "definitions": "DEF"}[resource]), workspace_id="manual", **values)
    db.add(obj); db.flush()
    if machine_id:
        db.add(MachineSafetyZone(id=uid("MZ"), workspace_id="manual", machine_id=machine_id, zone_id=obj.id))
    audit(db, user, obj.__tablename__, obj.id, "CREATE_CONFIGURATION", values)
    db.commit(); return row(obj)


@app.post("/api/config/{resource}/{id}/version", status_code=201)
def version_config(resource: str, id: str, values: dict, db: DBSession = Depends(get_db), user=Depends(permit("admin"))):
    if resource not in ("interlocks", "definitions", "zones"): raise HTTPException(422, "Use new entities for plants and machines")
    values = config_payload(resource, values)
    check_config_refs(db, resource, values)
    old = get(db, CONFIG_MODELS[resource], id, lock=True)
    if old.effective_to: raise HTTPException(409, "This configuration version is already superseded")
    now = utcnow()
    if aware(old.effective_from) >= now: raise HTTPException(409, "Effective interval would be empty")
    old.effective_to = now
    machine_id = values.pop("machine_id") if resource == "zones" else None
    new = CONFIG_MODELS[resource](id=uid("CFG"), workspace_id="manual", effective_from=now, effective_to=None, **values)
    db.add(new); db.flush()
    if machine_id: db.add(MachineSafetyZone(id=uid("MZ"), workspace_id="manual", machine_id=machine_id, zone_id=new.id))
    audit(db, user, old.__tablename__, id, "SUPERSEDE_CONFIGURATION", {"previous": row(old), "new": row(new)})
    db.commit(); return row(new)


@app.post("/api/machines/{id}/state", status_code=201)
def machine_state(id: str, body: MachineStateCreate, db: DBSession = Depends(get_db), user=Depends(permit("engineer", "admin"))):
    machine = get(db, Machine, id, lock=True)
    now = utcnow()
    locks = list(db.scalars(select(Interlock).where(Interlock.machine_id == id, Interlock.effective_to.is_(None))))
    if body.state == "RUNNING" and any(l.mandatory for l in locks) and (body.guard_state != "CLOSED" or body.interlock_state != "ENGAGED"):
        raise HTTPException(409, "Running requires every mandatory guard CLOSED and interlock ENGAGED")
    state = MachineStateEvent(id=uid("MSE"), workspace_id="manual", machine_id=id, state=body.state, occurred_at=now, reason=body.reason)
    db.add(state); db.flush()
    for lock in locks:
        db.add(InterlockStateEvent(id=uid("ISE"), workspace_id="manual", interlock_id=lock.id, machine_state_id=state.id,
            state=body.interlock_state, guard_state=body.guard_state, occurred_at=now))
    audit(db, user, "machines", id, "STATE_CHANGE", body.model_dump())
    db.commit(); return row(state)


def alarm_detail(db, id):
    a = get(db, AlarmEvent, id)
    definition = get(db, AlarmDefinition, a.definition_id)
    machine = get(db, Machine, a.machine_id)
    state = get(db, MachineStateEvent, a.machine_state_id)
    ack = db.scalar(select(Acknowledgement).where(Acknowledgement.alarm_id == id))
    interlock_states = list(db.scalars(select(InterlockStateEvent).where(InterlockStateEvent.machine_state_id == state.id)))
    interlocks = [get(db, Interlock, s.interlock_id) for s in interlock_states]
    zone_ids = set(l.zone_id for l in interlocks)
    incidents = list(db.scalars(select(Incident).join(IncidentAlarm, IncidentAlarm.incident_id == Incident.id).where(IncidentAlarm.alarm_id == id)))
    source_records = list(db.scalars(select(AlarmEvent).where(AlarmEvent.source_event_id == a.source_event_id, AlarmEvent.machine_id == a.machine_id).order_by(AlarmEvent.created_at, AlarmEvent.id)))
    return {"alarm": {**row(a), "severity": definition.severity, **ack_status(row(a), row(ack) if ack else None, row(definition))},
        "definition": row(definition), "machine": row(machine), "plant": row(get(db, Plant, machine.plant_id)),
        "state": row(state), "shift": row(get(db, OperatorShift, a.shift_id)),
        "acknowledgement": {**row(ack), "user_name": get(db, ApplicationUser, ack.user_id).name} if ack else None,
        "interlock_states": [row(s) for s in interlock_states], "interlocks": [row(i) for i in interlocks],
        "zones": [row(get(db, SafetyZone, id)) for id in sorted(zone_ids)], "incidents": [row(i) for i in incidents],
        "source_records": [row(s) for s in source_records]}


@app.get("/api/alarms/{id}")
def get_alarm(id: str, db: DBSession = Depends(get_db), user=Depends(actor)):
    return alarm_detail(db, id)


@app.get("/api/machines/{id}")
def get_machine(id: str, db: DBSession = Depends(get_db), user=Depends(actor)):
    machine = get(db, Machine, id)
    states = list(db.scalars(select(MachineStateEvent).where(MachineStateEvent.machine_id == id).order_by(MachineStateEvent.occurred_at.desc(), MachineStateEvent.id.desc()).limit(100)))
    locks = list(db.scalars(select(Interlock).where(Interlock.machine_id == id).order_by(Interlock.effective_from.desc())))
    zone_ids = set(db.scalars(select(MachineSafetyZone.zone_id).where(MachineSafetyZone.machine_id == id)))
    latest_lock_states = []
    for lock in locks:
        s = db.scalar(select(InterlockStateEvent).where(InterlockStateEvent.interlock_id == lock.id).order_by(InterlockStateEvent.occurred_at.desc(), InterlockStateEvent.id.desc()).limit(1))
        latest_lock_states.append({**row(lock), "state": s.state if s else "UNKNOWN", "guard_state": s.guard_state if s else "UNKNOWN"})
    return {"machine": row(machine), "plant": row(get(db, Plant, machine.plant_id)), "states": [row(s) for s in states],
        "zones": [row(get(db, SafetyZone, z)) for z in sorted(zone_ids)], "interlocks": latest_lock_states,
        "definitions": [row(d) for d in db.scalars(select(AlarmDefinition).where(AlarmDefinition.machine_id == id).order_by(AlarmDefinition.id))],
        "alarms": alarms(workspace=machine.workspace_id, machine_id=id, page=1, limit=10, sort="newest", db=db, user=user)["items"],
        "incidents": [row(i) for i in db.scalars(select(Incident).where(Incident.machine_id == id).order_by(Incident.occurred_at.desc()).limit(25))]}


@app.get("/api/incidents/{id}")
def get_incident(id: str, db: DBSession = Depends(get_db), user=Depends(actor)):
    incident = get(db, Incident, id)
    links = list(db.scalars(select(IncidentAlarm).where(IncidentAlarm.incident_id == id)))
    details = [alarm_detail(db, link.alarm_id) for link in links]
    actions = list(db.scalars(select(CorrectiveAction).where(CorrectiveAction.incident_id == id)))
    timeline = []
    def event(id, t, kind, description, reference=None):
        timeline.append(dict(id=id, occurred_at=t, kind=kind, description=description, reference=reference))
    for detail in details:
        a, state = detail["alarm"], detail["state"]
        event(state["id"], state["occurred_at"], "Machine state", state["state"]+" · "+state["reason"])
        event(a["id"], a["occurred_at"], "Alarm occurred", a["message"], a["id"])
        event(a["id"]+"-ingestion", a["created_at"], "Alarm ingested", "Source record received")
        for lock in detail["interlock_states"]:
            event(lock["id"], lock["occurred_at"], "Interlock", f"{lock['state']} · guard {lock['guard_state']}")
        ack = detail["acknowledgement"]
        if ack: event(ack["id"], ack["acknowledged_at"], "Acknowledgement", ack["user_name"]+" · "+ack["note"])
    for h in db.scalars(select(IncidentStatusHistory).where(IncidentStatusHistory.incident_id == id)):
        event(h.id, h.occurred_at, "Incident lifecycle", f"{h.from_status or 'Created'} → {h.to_status} · {h.note}")
    for a in actions:
        for h in db.scalars(select(CorrectiveActionStatusHistory).where(CorrectiveActionStatusHistory.action_id == a.id)):
            event(h.id, h.occurred_at, "Corrective action", f"{h.from_status or 'Created'} → {h.to_status} · {h.note}", a.id)
        if a.verified_at: event(a.id+"-verification", a.verified_at, "Verification", a.verification_evidence, a.id)
    unique = {e["id"]: e for e in timeline}
    return {"incident": row(incident), "machine": row(get(db, Machine, incident.machine_id)), "alarm_details": details,
        "actions": [row(a) for a in actions], "missing_context": not details,
        "timeline": sorted(unique.values(), key=lambda e: (aware(e["occurred_at"]), e["id"]))}


@app.get("/api/actions/{id}")
def get_action(id: str, db: DBSession = Depends(get_db), user=Depends(actor)):
    a = get(db, CorrectiveAction, id)
    return {"action": {**row(a), "assignee_name": get(db, ApplicationUser, a.assignee_id).name},
        "incident": row(get(db, Incident, a.incident_id)),
        "history": [row(h) for h in db.scalars(select(CorrectiveActionStatusHistory).where(CorrectiveActionStatusHistory.action_id == id).order_by(CorrectiveActionStatusHistory.occurred_at, CorrectiveActionStatusHistory.id))],
        "audit": [row(e) for e in db.scalars(select(AuditEvent).where(AuditEvent.record_id == id).order_by(AuditEvent.occurred_at, AuditEvent.id))]}


@app.get("/api/dashboard")
def dashboard(workspace: str = "manual", plant_id: str | None = None, start: datetime | None = None, end: datetime | None = None,
              db: DBSession = Depends(get_db), user=Depends(actor)):
    # Aggregate in PostgreSQL; the browser never downloads the source dataset.
    base = select(AlarmEvent.id, AlarmEvent.machine_id, AlarmEvent.definition_id, AlarmEvent.occurred_at,
        func.row_number().over(partition_by=(AlarmEvent.machine_id, AlarmEvent.source_event_id), order_by=(AlarmEvent.created_at, AlarmEvent.id)).label("rn")).join(Machine, Machine.id == AlarmEvent.machine_id).where(scope(AlarmEvent, workspace))
    if plant_id: base = base.where(Machine.plant_id == plant_id)
    ranked = base.subquery()
    physical = select(ranked).where(ranked.c.rn == 1)
    raw = select(func.count()).select_from(ranked)
    if start:
        physical = physical.where(ranked.c.occurred_at >= start)
        raw = raw.where(ranked.c.occurred_at >= start)
    if end:
        physical = physical.where(ranked.c.occurred_at < end)
        raw = raw.where(ranked.c.occurred_at < end)
    p = physical.subquery()
    totals = dict(db.execute(select(AlarmDefinition.severity, func.count()).select_from(p).join(AlarmDefinition, AlarmDefinition.id == p.c.definition_id).group_by(AlarmDefinition.severity)).all())
    day_bucket = func.date_trunc("day", p.c.occurred_at)
    trends = [{"date": str(day.date()), "alarms": count} for day, count in db.execute(select(day_bucket, func.count()).group_by(day_bucket).order_by(day_bucket))]
    top = [{"id": mid, "name": name, "alarms": count} for mid, name, count in db.execute(select(Machine.id, Machine.name, func.count()).select_from(p).join(Machine, Machine.id == p.c.machine_id).group_by(Machine.id, Machine.name).order_by(func.count().desc(), Machine.id).limit(5))]
    by_plant = [{"name": name, "alarms": count} for name, count in db.execute(select(Plant.name, func.count()).select_from(p).join(Machine, Machine.id == p.c.machine_id).join(Plant, Plant.id == Machine.plant_id).group_by(Plant.name).order_by(Plant.name))]
    dataset_run = db.get(DatasetGenerationRun, workspace)
    first_event, last_event = db.execute(select(func.min(p.c.occurred_at), func.max(p.c.occurred_at))).one()
    period_start = aware(start) if start else datetime(2026, 10, 1, tzinfo=timezone.utc) if dataset_run else aware(first_event) if first_event else utcnow()
    period_end = aware(end) if end else datetime(2026, 10, 1, tzinfo=timezone.utc)+timedelta(days=dataset_run.config["days"]) if dataset_run else aware(last_event) if last_event else utcnow()
    period_days = max((period_end-period_start).total_seconds()/86400, 1/86400)
    for item in top+by_plant: item["alarms_per_day"] = round(item["alarms"]/period_days, 2)
    delay = func.extract("epoch", Acknowledgement.acknowledged_at-p.c.occurred_at)
    response = select(p.c.id, AlarmDefinition.severity, delay.label("delay"), AlarmDefinition.ack_deadline_seconds.label("deadline"), Acknowledgement.id.label("ack_id"), p.c.occurred_at).select_from(p).join(AlarmDefinition, AlarmDefinition.id == p.c.definition_id).outerjoin(Acknowledgement, Acknowledgement.alarm_id == p.c.id).subquery()
    valid_delay = case((response.c.delay >= 0, response.c.delay), else_=None)
    late = or_(response.c.delay > response.c.deadline, and_(response.c.ack_id.is_(None), func.extract("epoch", func.now()-response.c.occurred_at) > response.c.deadline))
    late_count, mean, median, acked, on_time_critical, critical = db.execute(select(func.count().filter(late), func.avg(valid_delay), func.percentile_cont(0.5).within_group(valid_delay), func.count().filter(response.c.delay >= 0), func.count().filter(and_(response.c.severity == "CRITICAL", response.c.delay >= 0, response.c.delay <= response.c.deadline)), func.count().filter(response.c.severity == "CRITICAL")).select_from(response)).one()
    inc_filters = [scope(Incident, workspace)]
    if plant_id: inc_filters.append(Machine.plant_id == plant_id)
    if start: inc_filters.append(Incident.occurred_at >= start)
    if end: inc_filters.append(Incident.occurred_at < end)
    inc_base = select(Incident).join(Machine, Machine.id == Incident.machine_id).where(*inc_filters)
    open_count = db.scalar(select(func.count()).select_from(inc_base.where(Incident.status.not_in(["RESOLVED", "CLOSED"])).subquery()))
    priority = [row(i) for i in db.scalars(inc_base.where(Incident.status.not_in(["RESOLVED", "CLOSED"])).order_by(case((Incident.severity == "CRITICAL", 0), else_=1), Incident.occurred_at.desc()).limit(5))]
    inc_ids = inc_base.with_only_columns(Incident.id)
    action_total, verified, overdue = db.execute(select(func.count(), func.count().filter(CorrectiveAction.verified_at.is_not(None)), func.count().filter(and_(CorrectiveAction.due_at < utcnow(), CorrectiveAction.status.not_in(["VERIFIED", "CLOSED"])))).where(CorrectiveAction.incident_id.in_(inc_ids))).one()
    report = db.scalar(select(ValidationResult).where(ValidationResult.run_id == workspace).order_by(ValidationResult.created_at.desc()).limit(1))
    machine_ids = set(db.scalars(select(Machine.id).where(scope(Machine, workspace), *([Machine.plant_id == plant_id] if plant_id else []))))
    detections = report.report.get("detections", []) if report else []
    def relevant(d):
        evidence = d.get("evidence", {})
        mid = evidence.get("machine_id")
        if mid and mid not in machine_ids: return False
        if plant_id and not mid: return False
        t = d.get("occurred_at")
        if t and start and aware(t) < aware(start): return False
        if t and end and aware(t) >= aware(end): return False
        return True
    detections = [d for d in detections if relevant(d)]
    recurring = [d for d in detections if d["rule_id"] in ("RECURRENT_HAZARD", "IMPOSSIBLE_INTERLOCK_STATE")]
    unique_recurrent = len({d["target_record_id"] for d in detections if d["rule_id"] == "RECURRENT_HAZARD"})
    incident_total = db.scalar(select(func.count()).select_from(inc_base.subquery()))
    total = sum(totals.values())
    return {"total_alarms": total, "ingested_records": db.scalar(raw), "critical_alarms": totals.get("CRITICAL", 0), "open_incidents": open_count,
        "delayed_acknowledgements": late_count, "severity": [{"name": k, "value": totals.get(k, 0)} for k in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]],
        "trends": trends, "top_machines": top, "by_plant": by_plant, "rate_period_days": round(period_days, 3), "priority_incidents": priority, "recurring": recurring[:8],
        "average_ack_seconds": float(mean or 0), "median_ack_seconds": float(median or 0), "late_percentage": late_count/total*100 if total else 0,
        "critical_on_time_percentage": on_time_critical/critical*100 if critical else 0, "overdue_actions": overdue,
        "verification_percentage": verified/action_total*100 if action_total else 0, "recurrence_rate": unique_recurrent/incident_total*100 if incident_total else 0,
        "floods": sum(d["rule_id"] == "ALARM_FLOOD" for d in detections), "nuisance_patterns": sum(d["rule_id"] == "NUISANCE_ALARM" for d in detections),
        "acknowledged_count": acked, "repeated_unsafe_count": len(recurring), "rule_analysis_at": report.created_at if report else None}
