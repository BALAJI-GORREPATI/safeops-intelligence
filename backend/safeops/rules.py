"""Transparent rules. This module never imports or queries GroundTruth."""
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import os

FLOOD_WINDOW_SECONDS = int(os.getenv("FLOOD_WINDOW_SECONDS", "600"))
FLOOD_THRESHOLD = int(os.getenv("FLOOD_THRESHOLD", "20"))
NUISANCE_THRESHOLD = int(os.getenv("NUISANCE_THRESHOLD", "8"))
INCIDENT_PATH = ["OPEN", "INVESTIGATING", "ACTION_PENDING", "RESOLVED", "CLOSED"]
ACTION_PATH = ["OPEN", "IN_PROGRESS", "COMPLETED", "VERIFIED", "CLOSED"]
ANOMALY_ENTITIES = {"ACK_BEFORE_ALARM": "acknowledgements", "IMPOSSIBLE_INTERLOCK_STATE": "interlock_state_events",
    "INCIDENT_MISSING_CONTEXT": "incidents", "DUPLICATE_ALARM_REPLAY": "alarm_events", "ACTION_CLOSED_UNVERIFIED": "corrective_actions"}


def aware(t):
    if isinstance(t, str):
        t = datetime.fromisoformat(t)
    return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t


def ack_status(alarm, acknowledgement, definition, now=None):
    now = now or datetime.now(timezone.utc)
    if not acknowledgement:
        return {"status": "UNACKNOWLEDGED", "delay_seconds": None,
                "overdue": (now-aware(alarm["occurred_at"])).total_seconds() > definition["ack_deadline_seconds"]}
    delay = (aware(acknowledgement["acknowledged_at"])-aware(alarm["occurred_at"])).total_seconds()
    return {"status": "INVALID_ACKNOWLEDGEMENT" if delay < 0 else "ACKNOWLEDGED_LATE" if delay > definition["ack_deadline_seconds"] else "ACKNOWLEDGED_ON_TIME",
            "delay_seconds": delay, "overdue": delay > definition["ack_deadline_seconds"]}


def detect(data):
    result = []
    index = {table: {r["id"]: r for r in rows} for table, rows in data.items()}

    def emit(rule, table, row, explanation, evidence, severity="HIGH", related=None):
        result.append(dict(rule_id=rule, severity=severity, target_entity=table, target_record_id=row["id"],
            affected_record_ids=[row["id"]]+(related or []), explanation=explanation,
            occurred_at=row.get("occurred_at", row.get("acknowledged_at", row.get("due_at", row.get("created_at")))), evidence=evidence))

    alarms = index.get("alarm_events", {})
    definitions = index.get("alarm_definitions", {})
    for ack in data.get("acknowledgements", []):
        alarm = alarms.get(ack["alarm_id"])
        if alarm and aware(ack["acknowledged_at"]) < aware(alarm["occurred_at"]):
            emit("ACK_BEFORE_ALARM", "acknowledgements", ack, "Acknowledgement predates the source alarm",
                 {"alarm_at": alarm["occurred_at"], "acknowledged_at": ack["acknowledged_at"]}, related=[alarm["id"]])
    for state in data.get("interlock_state_events", []):
        machine_state = index.get("machine_state_events", {}).get(state["machine_state_id"])
        lock = index.get("interlocks", {}).get(state["interlock_id"])
        if machine_state and lock and lock["mandatory"] and aware(lock["effective_from"]) <= aware(state["occurred_at"]) and (
                not lock.get("effective_to") or aware(state["occurred_at"]) < aware(lock["effective_to"])):
            if machine_state["state"] == "RUNNING" and (state["guard_state"] == "OPEN" or state["state"] != "ENGAGED"):
                emit("IMPOSSIBLE_INTERLOCK_STATE", "interlock_state_events", state,
                     "Running machine violates its effective mandatory interlock restriction",
                     {"machine_state": "RUNNING", "guard": state["guard_state"], "interlock": state["state"], "machine_id": machine_state["machine_id"]}, "CRITICAL", [machine_state["id"], lock["id"]])
    linked = defaultdict(list)
    for link in data.get("incident_alarms", []):
        if link["alarm_id"] in alarms:
            linked[link["incident_id"]].append(alarms[link["alarm_id"]])
    for inc in data.get("incidents", []):
        evidence = linked[inc["id"]]
        if not evidence or not any(a.get("machine_state_id") in index.get("machine_state_events", {}) and a["machine_id"] == inc["machine_id"] for a in evidence):
            emit("INCIDENT_MISSING_CONTEXT", "incidents", inc, "No linked triggering alarm and machine-state evidence", {"triggering_alarm_count": len(evidence)})
    seen, physical = {}, []
    for alarm in sorted(alarms.values(), key=lambda a: (aware(a["created_at"]), a["id"])):
        identity = (alarm["machine_id"], alarm["source_event_id"])
        if identity in seen:
            emit("DUPLICATE_ALARM_REPLAY", "alarm_events", alarm, "Previously ingested physical source event was replayed",
                 {"source_event_id": alarm["source_event_id"], "original_record_id": seen[identity]}, related=[seen[identity]])
        else:
            seen[identity] = alarm["id"]
            physical.append(alarm)
    for action in data.get("corrective_actions", []):
        if action["status"] in ("VERIFIED", "CLOSED") and not (action.get("completed_at") and action.get("verified_at") and action.get("verified_by") and action.get("verification_evidence")):
            emit("ACTION_CLOSED_UNVERIFIED", "corrective_actions", action,
                 "Closed or verified action lacks mandatory completion, verifier or evidence",
                 {"status": action["status"], "verified_at": action.get("verified_at"), "evidence": action.get("verification_evidence")})
    # Deduplicate first; one flood episode ends when the rolling count drops below threshold.
    by_machine = defaultdict(list)
    nuisance = defaultdict(list)
    for alarm in physical:
        by_machine[alarm["machine_id"]].append(alarm)
        definition = definitions.get(alarm["definition_id"], {})
        if definition.get("severity") == "LOW" and "chatter" in definition.get("name", "").lower():
            nuisance[(alarm["machine_id"], alarm["definition_id"], aware(alarm["occurred_at"]).date())].append(alarm)
    for mid, events in by_machine.items():
        events.sort(key=lambda a: (aware(a["occurred_at"]), a["id"]))
        left, in_flood = 0, False
        for right, event in enumerate(events):
            while (aware(event["occurred_at"])-aware(events[left]["occurred_at"])).total_seconds() > FLOOD_WINDOW_SECONDS:
                left += 1
            count = right-left+1
            if count >= FLOOD_THRESHOLD and not in_flood:
                emit("ALARM_FLOOD", "alarm_events", event, f"{count} distinct physical alarms in {FLOOD_WINDOW_SECONDS} seconds",
                     {"machine_id": mid, "count": count, "window_seconds": FLOOD_WINDOW_SECONDS}, "HIGH", [a["id"] for a in events[left:right]])
            in_flood = count >= FLOOD_THRESHOLD
    for (mid, definition, day), events in nuisance.items():
        if len(events) >= NUISANCE_THRESHOLD:
            emit("NUISANCE_ALARM", "alarm_events", events[0], "Repeated low-severity sensor chatter during one UTC day",
                 {"machine_id": mid, "definition_id": definition, "day": str(day), "count": len(events)}, "LOW", [a["id"] for a in events[1:]])
    # Recurrence requires the same machine AND hazard rule after a verified remediation.
    incident_index = index.get("incidents", {})
    by_hazard = defaultdict(list)
    for incident in data.get("incidents", []):
        by_hazard[(incident["machine_id"], incident["rule_id"])].append(incident)
    for items in by_hazard.values():
        items.sort(key=lambda r: aware(r["occurred_at"]))
    for action in data.get("corrective_actions", []):
        incident = incident_index.get(action["incident_id"])
        if incident and action.get("verified_at"):
            items = by_hazard[(incident["machine_id"], incident["rule_id"])]
            times = [aware(i["occurred_at"]) for i in items]
            pos = bisect_right(times, aware(action["verified_at"]))
            if pos < len(items):
                later = items[pos]
                emit("RECURRENT_HAZARD", "incidents", later, "Hazard recurred on the same machine after verified remediation",
                     {"machine_id": incident["machine_id"], "previous_incident_id": incident["id"], "action_id": action["id"], "verified_at": action["verified_at"]}, related=[incident["id"], action["id"]])
    return result


def evaluate(operational, truth, detections):
    """One (rule, target row) decision per eligible row; negatives included for each rule."""
    expected = {(r["rule_id"], r["target_record_id"]) for r in truth if r["expected_decision"]}
    predicted = {(r["rule_id"], r["target_record_id"]) for r in detections if r["rule_id"] in ANOMALY_ENTITIES}
    per_type = {}
    for rule, table in ANOMALY_ENTITIES.items():
        universe = {(rule, row["id"]) for row in operational.get(table, [])}
        e, p = expected & universe, predicted & universe
        tp, fp, fn, tn = len(e & p), len(p-e), len(e-p), len(universe-(e | p))
        per_type[rule] = metric(tp, fp, tn, fn)
    total = {key: sum(v[key] for v in per_type.values()) for key in ("tp", "fp", "tn", "fn")}
    return {"unit": "(rule ID, target record ID); replay evaluated per extra ingestion; normal eligible rows are negatives",
            "overall": metric(total["tp"], total["fp"], total["tn"], total["fn"]), "per_type": per_type}


def metric(tp, fp, tn, fn):
    precision, recall = tp/(tp+fp) if tp+fp else 0, tp/(tp+fn) if tp+fn else 0
    return dict(tp=tp, fp=fp, tn=tn, fn=fn, precision=precision, recall=recall,
                f1=2*precision*recall/(precision+recall) if precision+recall else 0)
