"""Canonical, portable artifacts and schema-derived dictionary."""
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from .generator import VERSION, canonical, checksums
from .models import Base, OPERATIONAL


def dictionary():
    tables = {}
    for table in Base.metadata.sorted_tables:
        fields = []
        constraints = [str(c.sqltext) for c in table.constraints if hasattr(c, "sqltext")]
        for c in table.columns:
            fields.append(dict(name=c.name, type=str(c.type), required=not c.nullable,
                allowed_values=[v for v in constraints if c.name in v], units="seconds" if c.name.endswith("seconds") else "UTC" if "TIME" in str(c.type) else None,
                default=str(c.default.arg) if c.default and not c.default.is_callable else "UTC now" if c.default else None,
                unique=bool(c.primary_key or c.unique), foreign_key=[str(f.target_fullname) for f in c.foreign_keys],
                validation=constraints, description=c.comment or c.name.replace("_", " ").capitalize()))
        tables[table.name] = dict(fields=fields, unique_constraints=[list(c.columns.keys()) for c in table.constraints if c.__class__.__name__ == "UniqueConstraint"])
    return dict(schema_version="0001", tables=tables)


def write_dictionary(path):
    path.mkdir(parents=True, exist_ok=True)
    doc = dictionary()
    (path/"data-dictionary.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    lines = ["# Data dictionary", "", "Generated from SQLAlchemy metadata. All event timestamps are UTC. Identifiers are immutable strings.", ""]
    for table, info in doc["tables"].items():
        lines += [f"## {table}", "", "| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |", "|---|---|---|---|---|---|---|---|---|"]
        for f in info["fields"]:
            lines.append("| " + " | ".join(str(f[k] if f[k] is not None else "—").replace("|", "/") for k in ["name", "type", "required", "validation", "units", "default", "unique", "foreign_key", "description"]) + " |")
        lines += ["", f"Composite uniqueness: {info['unique_constraints']}", ""]
    (path/"data-dictionary.md").write_text("\n".join(lines), encoding="utf-8")


def literal(value):
    if value is None: return "NULL"
    if isinstance(value, bool): return "TRUE" if value else "FALSE"
    if isinstance(value, (float, int)): return str(value)
    if isinstance(value, (dict, list)): value = canonical(value)
    if isinstance(value, datetime): value = value.isoformat()
    return "'" + str(value).replace("'", "''") + "'"


def export_dataset(data, config, report, path, reproducibility=None):
    path = Path(path)
    for folder in ("csv", "json", "sql", "evaluation"):
        (path/folder).mkdir(parents=True, exist_ok=True)
    for table in sorted(set(data) | set(OPERATIONAL)):
        rows = data.get(table, [])
        target = path/"evaluation" if table == "ground_truth" else path/"json"
        (target/f"{table}.json").write_text(canonical(rows)+"\n", encoding="utf-8")
        csv_target = path/"evaluation" if table == "ground_truth" else path/"csv"
        with (csv_target/f"{table}.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else [c.name for c in Base.metadata.tables[table].columns])
            writer.writeheader()
            for row in rows:
                writer.writerow({k: canonical(v) if isinstance(v, (dict, list)) else v.isoformat() if isinstance(v, datetime) else v for k, v in row.items()})
    detections = report.get("detections", [])
    (path/"evaluation"/"detection_results.json").write_text(canonical(detections)+"\n", encoding="utf-8")
    with (path/"evaluation"/"detection_results.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["rule_id", "severity", "target_entity", "target_record_id", "affected_record_ids", "explanation", "occurred_at", "evidence"])
        writer.writeheader()
        for detection in detections:
            writer.writerow({k: canonical(v) if isinstance(v, (dict, list)) else v.isoformat() if isinstance(v, datetime) else v for k, v in detection.items()})
    with (path/"sql"/"seed.sql").open("w", encoding="utf-8") as f:
        f.write("-- Synthetic data; apply to an empty migrated database. No destructive statements.\nBEGIN;\n")
        for table in Base.metadata.sorted_tables:
            for row in data.get(table.name, []):
                columns = ', '.join('"'+c+'"' for c in row)
                f.write(f'INSERT INTO "{table.name}" ({columns}) VALUES ({", ".join(literal(v) for v in row.values())});\n')
        f.write("COMMIT;\n")
    (path/"sql"/"schema.sql").write_text("\n".join(str(CreateTable(t).compile(dialect=postgresql.dialect()))+";" for t in Base.metadata.sorted_tables), encoding="utf-8")
    write_dictionary(path)
    (path/"validation-summary.json").write_text(canonical(report)+"\n", encoding="utf-8")
    (path/"generation-config.json").write_text(canonical(config.model_dump())+"\n", encoding="utf-8")
    (path/"reproducibility-report.json").write_text(canonical(reproducibility or {"tested": False})+"\n", encoding="utf-8")
    sums = checksums(data)
    manifest = dict(provenance="Entirely synthetic; no private or external industrial data", generator_version=VERSION,
        schema_version="0001", seed=config.seed, config=config.model_dump(), period_start="2026-10-01T00:00:00+00:00",
        period_days=config.days, **sums)
    manifest["files"] = {str(p.relative_to(path)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(path.rglob("*")) if p.is_file() and p.name != "source-manifest.json"}
    (path/"source-manifest.json").write_text(canonical(manifest)+"\n", encoding="utf-8")
    return manifest
