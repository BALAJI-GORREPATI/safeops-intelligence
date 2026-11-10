from collections import Counter
from .models import OPERATIONAL
from .rules import aware, detect, ANOMALY_ENTITIES, INCIDENT_PATH, ACTION_PATH


def validate(data, truth=()):
    findings = []
    expected = {(r["rule_id"], r["target_record_id"]) for r in truth}
    indexes = {t: {r["id"]: r for r in rows} for t, rows in data.items()}

    def issue(check, table, id, description, rule=None):
        findings.append(dict(check=check, table=table, record_id=id, description=description,
            category="EXPECTED_ANOMALY" if (rule or check, id) in expected else "UNEXPECTED_FAILURE"))

    checks = 0
    for name, table in OPERATIONAL.items():
        rows = data.get(name, [])
        for constraint in table.constraints:
            if constraint.__class__.__name__ == "UniqueConstraint":
                fields = list(constraint.columns.keys())
                groups = {}
                for r in rows:
                    key = tuple(r.get(f) for f in fields)
                    if None not in key:
                        if key in groups: issue("UNIQUE_CONSTRAINT", name, r["id"], f"Duplicate unique fields: {fields}")
                        groups[key] = r["id"]
        ids = Counter(r["id"] for r in rows)
        for id, count in ids.items():
            checks += 1
            if count != 1:
                issue("PRIMARY_KEY", name, id, "Duplicate canonical primary key")
        for row in rows:
            for column in table.columns:
                checks += 1
                value = row.get(column.name)
                if value is None and not column.nullable:
                    issue("REQUIRED_FIELD", name, row["id"], f"Missing {column.name}")
                for fk in column.foreign_keys:
                    if value is not None and value not in indexes.get(fk.column.table.name, {}):
                        issue("FOREIGN_KEY", name, row["id"], f"Broken reference {column.name}: {value}")
            if row.get("effective_to") and aware(row["effective_to"]) <= aware(row["effective_from"]):
                issue("EFFECTIVE_DATES", name, row["id"], "Empty or reversed configuration interval")
            if name == "operator_shifts" and aware(row["ends_at"]) <= aware(row["starts_at"]):
                issue("SHIFT_ORDER", name, row["id"], "Shift ends before it starts")
            allowed = {"severity": "LOW MEDIUM HIGH CRITICAL", "priority": "LOW MEDIUM HIGH CRITICAL", "role": "operator engineer planner admin"}
            if name == "incidents": allowed["status"] = " ".join(INCIDENT_PATH)
            if name == "corrective_actions": allowed["status"] = " ".join(ACTION_PATH)
            if name == "machine_state_events": allowed["state"] = "RUNNING STOPPED MAINTENANCE FAULT"
            if name == "interlock_state_events": allowed |= {"state": "ENGAGED RELEASED BYPASSED FAILED", "guard_state": "OPEN CLOSED"}
            for field, values in allowed.items():
                if field in row and row[field] not in values.split():
                    issue("ENUM", name, row["id"], f"Invalid {field}")
            if name == "alarm_events":
                if aware(row["created_at"]) < aware(row["occurred_at"]):
                    issue("INGESTION_ORDER", name, row["id"], "Ingestion cannot precede occurrence")
                definition = indexes.get("alarm_definitions", {}).get(row["definition_id"])
                state = indexes.get("machine_state_events", {}).get(row["machine_state_id"])
                shift = indexes.get("operator_shifts", {}).get(row["shift_id"])
                machine = indexes.get("machines", {}).get(row["machine_id"])
                if definition and (definition["machine_id"] != row["machine_id"] or aware(definition["effective_from"]) > aware(row["occurred_at"]) or (definition.get("effective_to") and aware(row["occurred_at"]) >= aware(definition["effective_to"]))):
                    issue("ALARM_CONTEXT", name, row["id"], "Definition not effective for this machine at event time")
                if state and (state["machine_id"] != row["machine_id"] or aware(state["occurred_at"]) > aware(row["occurred_at"])):
                    issue("STATE_CONTEXT", name, row["id"], "Machine state belongs to another machine or the future")
                if shift and machine and not (shift["plant_id"] == machine["plant_id"] and aware(shift["starts_at"]) <= aware(row["occurred_at"]) < aware(shift["ends_at"])):
                    issue("SHIFT_CONTEXT", name, row["id"], "Alarm outside assigned operator shift")
            if name == "corrective_actions" and row.get("verified_at") and (not row.get("completed_at") or aware(row["verified_at"]) < aware(row["completed_at"])):
                issue("ACTION_TIME_ORDER", name, row["id"], "Verification before completion")
    detections = detect({k: v for k, v in data.items() if k != "ground_truth"})
    for d in detections:
        if d["rule_id"] in ANOMALY_ENTITIES:
            issue(d["rule_id"], d["target_entity"], d["target_record_id"], d["explanation"])
    # Reconcile materialized lifecycle summaries with the final immutable history event.
    for table, history, field, path in [("incidents", "incident_status_history", "incident_id", INCIDENT_PATH),
                                       ("corrective_actions", "corrective_action_status_history", "action_id", ACTION_PATH)]:
        grouped = {}
        for h in data.get(history, []): grouped.setdefault(h[field], []).append(h)
        for row in data.get(table, []):
            items = sorted(grouped.get(row["id"], []), key=lambda r: (aware(r["occurred_at"]), r["id"]))
            if not items or items[-1]["to_status"] != row["status"]:
                issue("HISTORY_RECONCILIATION", table, row["id"], "Status disagrees with final history")
            previous = None
            for h in items:
                if h["from_status"] != previous or (previous and (previous not in path or h["to_status"] not in path or path.index(h["to_status"]) != path.index(previous)+1)):
                    issue("LIFECYCLE", table, row["id"], "Invalid historical lifecycle transition", "ACTION_CLOSED_UNVERIFIED" if table == "corrective_actions" else "LIFECYCLE")
                previous = h["to_status"]
    counts = Counter(f["category"] for f in findings)
    return dict(status="FAIL" if counts["UNEXPECTED_FAILURE"] else "PASS", checks=checks,
        counts={"PASS": checks-len(findings), "EXPECTED_ANOMALY": counts["EXPECTED_ANOMALY"], "UNEXPECTED_FAILURE": counts["UNEXPECTED_FAILURE"]}, findings=findings)
