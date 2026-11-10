"""Deterministic causal generator; no database or wall-clock dependency."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Literal
import numpy as np
from pydantic import BaseModel, Field, model_validator

VERSION = "1.1.0"
START = datetime(2026, 10, 1, tzinfo=timezone.utc)
DEADLINES = {"LOW": 1800, "MEDIUM": 900, "HIGH": 300, "CRITICAL": 120}


class GeneratorConfig(BaseModel):
    preset: Literal["starter", "full"] = "starter"
    seed: int = Field(default=20261022, ge=0, le=2**32-1)
    plants: int = Field(default=2, ge=1, le=20)
    machines: int = Field(default=8, ge=1, le=500)
    definitions: int = Field(default=24, ge=1, le=2000)
    events: int = Field(default=800, ge=100, le=200000)
    days: int = Field(default=7, ge=1, le=90)
    anomaly_rate: float = Field(default=0.005, ge=0.001, le=0.05)

    @model_validator(mode="before")
    @classmethod
    def apply_preset_defaults(cls, value):
        if isinstance(value, dict) and value.get("preset") == "full":
            return {"plants": 4, "machines": 60, "definitions": 200, "events": 50000, "days": 30, **value}
        return value

    @model_validator(mode="after")
    def consistent(self):
        if self.machines < self.plants or self.definitions < self.machines:
            raise ValueError("Require at least one machine per plant and one definition per machine")
        return self

    @classmethod
    def preset_config(cls, preset="starter", **overrides):
        values = dict(preset=preset)
        if preset == "full":
            values.update(plants=4, machines=60, definitions=200, events=50000, days=30)
        return cls(**(values | overrides))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      default=lambda v: v.isoformat() if isinstance(v, datetime) else str(v))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def generate(config: GeneratorConfig, progress=lambda value: None):
    rng = np.random.default_rng(config.seed)
    key = digest({"version": VERSION, **config.model_dump()})[:10]
    workspace = f"sim-{key}"
    counter_base = int(key, 16) * 1000000
    data = defaultdict(list)

    def add(table, id, **fields):
        ingestion = fields.pop("created_at", fields.get("occurred_at", fields.get("acknowledged_at", START)))
        row = dict(id=id, workspace_id=workspace, created_at=ingestion, **fields)
        data[table].append(row)
        return row

    def label(kind, table, row, explanation, related=None):
        data["ground_truth"].append(dict(id=f"GT-{key}-{len(data['ground_truth'])+1:06}", workspace_id=workspace,
            target_entity=table, target_record_id=row["id"], anomaly_type=kind, rule_id=kind,
            expected_decision=True, explanation=explanation, related_record_ids=related or []))

    users = [add("application_users", f"USR-{key}-{i:03}", name=name, role=role)
             for i, (name, role) in enumerate([("Asha Rao", "operator"), ("Dev Shah", "engineer"),
                 ("Mira Sen", "planner"), ("Local administrator", "admin")], 1)]
    plant_names = ["Pune · Assembly", "Chennai · Machining", "Vadodara · Fabrication", "Hosur · Finishing"]
    plants = [add("plants", f"PLT-{key}-{i+1:03}", name=plant_names[i] if i < 4 else f"Plant {i+1}",
                  location=["Pune", "Chennai", "Vadodara", "Hosur"][i % 4], timezone="Asia/Kolkata", active=True)
              for i in range(config.plants)]
    machines, zones, locks = [], [], []
    kinds = ["Hydraulic press", "CNC machining centre", "Robotic weld cell", "Conveyor", "Injection moulder"]
    for i in range(config.machines):
        plant = plants[i % len(plants)]
        machine = add("machines", f"MAC-{key}-{i+1:03}", plant_id=plant["id"],
                      name=f"{kinds[i % 5]} {i+1:02}", kind=kinds[i % 5], active=True)
        machines.append(machine)
        zone = add("safety_zones", f"SAFE-{plant['id']}-{i+1:03}", plant_id=plant["id"],
                   name=f"Cell {i+1:02} perimeter", restriction="Guard must be closed while RUNNING",
                   effective_from=START, effective_to=None)
        zones.append(zone)
        add("machine_safety_zones", f"MZ-{key}-{i+1:03}", machine_id=machine["id"], zone_id=zone["id"])
        locks.append(add("interlocks", f"INT-{key}-{i+1:03}", machine_id=machine["id"], zone_id=zone["id"],
                         name="Perimeter guard interlock", mandatory=True, effective_from=START, effective_to=None))
    definitions = defaultdict(list)
    for i in range(config.definitions):
        machine = machines[i % len(machines)]
        # Alternate severity by definition rather than random event outcomes.
        severity = ["LOW", "MEDIUM", "HIGH", "CRITICAL"][(i // len(machines) + i) % 4]
        definitions[machine["id"]].append(add("alarm_definitions", f"DEF-{key}-{i+1:04}",
            machine_id=machine["id"], name={"LOW": "Sensor chatter", "MEDIUM": "Cycle deviation",
                "HIGH": "High temperature", "CRITICAL": "Emergency safety trip"}[severity], severity=severity,
            source="PLC / safety controller", ack_deadline_seconds=DEADLINES[severity],
            effective_from=START, effective_to=None))
    shifts = {}
    for p in plants:
        for s in range(config.days * 3):
            start = START + timedelta(hours=s*8)
            shifts[p["id"], s] = add("operator_shifts", f"SHF-{p['id']}-{s+1:04}", plant_id=p["id"],
                user_id=users[0]["id"], starts_at=start, ends_at=start+timedelta(hours=8))
    states, interlock_states = {}, {}
    for i, m in enumerate(machines):
        for s in range(config.days * 3):
            t = START + timedelta(hours=s*8)
            state = "MAINTENANCE" if (s+i) % 17 == 0 else "STOPPED" if s % 3 == 2 else "RUNNING"
            states[m["id"], s] = add("machine_state_events", f"MSE-{m['id']}-{s+1:04}", machine_id=m["id"],
                state=state, occurred_at=t, reason="Scheduled maintenance" if state == "MAINTENANCE" else "Shift schedule")
            interlock_states[m["id"], s] = add("interlock_state_events", f"ISE-{m['id']}-{s+1:04}",
                interlock_id=locks[i]["id"], machine_state_id=states[m["id"], s]["id"],
                state="ENGAGED" if state == "RUNNING" else "RELEASED", guard_state="CLOSED" if state == "RUNNING" else "OPEN", occurred_at=t)
    progress(20)
    # A skewed machine distribution and a fault burst each day produce genuine floods.
    weights = np.array([1/(i+1)**0.55 for i in range(config.machines)])
    machine_choices = rng.choice(config.machines, config.events, p=weights/weights.sum())
    seconds = np.sort(rng.integers(1, config.days*86400-3600, config.events))
    physical_events = config.events - max(1, int(config.events*config.anomaly_rate/5))
    machine_counters = defaultdict(int)
    for i in range(physical_events):
        mi = int(machine_choices[i])
        m = machines[mi]
        sec = int(seconds[i])
        # Dedicated clustered events with distinct source IDs are legitimate repeats.
        if i < min(40, physical_events):
            mi, m, sec = 0, machines[0], 3600+i*3
        t = START + timedelta(seconds=sec)
        shift_index = min(sec//28800, config.days*3-1)
        definition = definitions[m["id"]][i % len(definitions[m["id"]])]
        machine_counters[m["id"]] += 1
        a = add("alarm_events", f"ALM-{m['id']}-{machine_counters[m['id']]:06}", machine_id=m["id"],
            definition_id=definition["id"], machine_state_id=states[m["id"], shift_index]["id"],
            shift_id=shifts[m["plant_id"], shift_index]["id"], source_event_id=f"SRC-{key}-{i+1:06}",
            occurred_at=t, message=definition["name"], value=round(float(rng.normal(92, 4)), 2) if definition["severity"] == "HIGH" else None)
        # Higher operational load increases response time. A deterministic subset remains open.
        if i % 7:
            delay = int(rng.lognormal(4.2 + (0.8 if mi == 0 else 0), 0.8))
            add("acknowledgements", f"ACK-{a['id']}-01", alarm_id=a["id"], user_id=users[0]["id"],
                acknowledged_at=t+timedelta(seconds=delay), note="Operator reviewed controller and machine context")
        # Escalation based on hazardous severity + temporal separation, never random incident flags.
        if (definition["severity"] in ("HIGH", "CRITICAL") and i % 13 == 0) or i == 19:
            n = len(data["incidents"])+1
            status = "RESOLVED" if n % 4 == 0 else "ACTION_PENDING" if n % 3 == 0 else "OPEN"
            incident = add("incidents", f"INC-2026-{counter_base+n:018}", machine_id=m["id"],
                title=f"{definition['name']} on {m['name']}" if i != 19 else f"Alarm flood on {m['name']}", severity=definition["severity"] if i != 19 else "HIGH", status=status,
                occurred_at=t, rule_id="HAZARD_ESCALATION" if i != 19 else "ALARM_FLOOD")
            add("incident_alarms", f"IA-{incident['id']}-01", incident_id=incident["id"], alarm_id=a["id"])
            action_status = "VERIFIED" if status == "RESOLVED" else "IN_PROGRESS" if status == "ACTION_PENDING" else "OPEN"
            action = add("corrective_actions", f"ACT-{incident['id']}-01", incident_id=incident["id"], assignee_id=users[1]["id"],
                priority=definition["severity"], description=f"Inspect {m['name']}; isolate fault, repair and verify safe operation.",
                due_at=t+timedelta(hours=48), status=action_status, created_at=t,
                completed_at=t+timedelta(hours=2) if action_status == "VERIFIED" else None,
                verified_at=t+timedelta(hours=3) if action_status == "VERIFIED" else None,
                verified_by=users[3]["id"] if action_status == "VERIFIED" else None,
                verification_evidence="Guard cycle test and supervised restart passed" if action_status == "VERIFIED" else None)
            incident_path = ["OPEN", "INVESTIGATING", "ACTION_PENDING", "RESOLVED"]
            for j, st in enumerate(incident_path[:incident_path.index(status)+1]):
                add("incident_status_history", f"IH-{incident['id']}-{j+1:02}", incident_id=incident["id"],
                    from_status=incident_path[j-1] if j else None, to_status=st, user_id=users[1]["id"],
                    occurred_at=t+timedelta(hours=j+1) if j else t, note="Rule escalation" if j == 0 else "Engineering review")
            path = ["OPEN", "IN_PROGRESS", "COMPLETED", "VERIFIED"]
            for j, st in enumerate(path[:path.index(action_status)+1]):
                add("corrective_action_status_history", f"AH-{action['id']}-{j+1:02}", action_id=action["id"],
                    from_status=path[j-1] if j else None, to_status=st, user_id=users[3 if st == "VERIFIED" else 1]["id"],
                    occurred_at=t+timedelta(hours=j), note="Engineering remediation and verification")
    progress(65)
    # Baseline is complete. Inject labelled contradictions with all primary/foreign keys intact.
    n_inject = max(1, int(config.events*config.anomaly_rate/5))
    for ack in data["acknowledgements"][:n_inject]:
        alarm = next(a for a in data["alarm_events"] if a["id"] == ack["alarm_id"])
        ack["acknowledged_at"] = alarm["occurred_at"]-timedelta(seconds=30)
        label("ACK_BEFORE_ALARM", "acknowledgements", ack, "Acknowledgement occurs 30 seconds before its alarm", [alarm["id"]])
    alarms_by_state = {}
    for a in sorted(data["alarm_events"], key=lambda r: (r["occurred_at"], r["id"])):
        alarms_by_state.setdefault(a["machine_state_id"], a)
    unsafe = [x for (mid, s), x in interlock_states.items() if states[mid, s]["state"] == "RUNNING" and x["machine_state_id"] in alarms_by_state][:n_inject]
    for x in unsafe:
        x.update(state="BYPASSED", guard_state="OPEN")
        label("IMPOSSIBLE_INTERLOCK_STATE", "interlock_state_events", x, "Mandatory guard OPEN and interlock BYPASSED while machine RUNNING", [x["machine_state_id"]])
        # Unsafe evidence also escalates to an operational incident with a complete chain.
        alarm = alarms_by_state[x["machine_state_id"]]
        n = len(data["incidents"])+1
        incident = add("incidents", f"INC-2026-{counter_base+n:018}", machine_id=alarm["machine_id"],
            title="Mandatory guard violation during operation", severity="CRITICAL", status="OPEN",
            occurred_at=alarm["occurred_at"], rule_id="IMPOSSIBLE_INTERLOCK_STATE")
        add("incident_alarms", f"IA-{incident['id']}-01", incident_id=incident["id"], alarm_id=alarm["id"])
        add("incident_status_history", f"IH-{incident['id']}-01", incident_id=incident["id"], from_status=None,
            to_status="OPEN", user_id=users[1]["id"], occurred_at=incident["occurred_at"], note="Mandatory guard violation escalated from machine-state evidence")
        action = add("corrective_actions", f"ACT-{incident['id']}-01", incident_id=incident["id"], assignee_id=users[1]["id"],
            priority="CRITICAL", description="Restore guard interlock, remove bypass and verify safe operation before restart.",
            due_at=alarm["occurred_at"]+timedelta(hours=24), status="OPEN", created_at=alarm["occurred_at"], completed_at=None,
            verified_at=None, verified_by=None, verification_evidence=None)
        add("corrective_action_status_history", f"AH-{action['id']}-01", action_id=action["id"], from_status=None,
            to_status="OPEN", user_id=users[1]["id"], occurred_at=alarm["occurred_at"], note="Guard repair assigned")
    for i in range(n_inject):
        n = len(data["incidents"])+1
        incident = add("incidents", f"INC-2026-{counter_base+n:018}", machine_id=machines[i % len(machines)]["id"],
            title="Imported incident · triggering evidence absent", severity="HIGH", status="OPEN", occurred_at=START+timedelta(days=1), rule_id="IMPORTED_REVIEW")
        add("incident_status_history", f"IH-{incident['id']}-01", incident_id=incident["id"], from_status=None,
            to_status="OPEN", user_id=users[1]["id"], occurred_at=incident["occurred_at"], note="Imported record requires evidence")
        label("INCIDENT_MISSING_CONTEXT", "incidents", incident, "Incident has no triggering alarm evidence")
    for i in range(config.events-physical_events):
        original = data["alarm_events"][i]
        mid = original["machine_id"]
        machine_counters[mid] += 1
        replay = dict(original, id=f"ALM-{mid}-{machine_counters[mid]:06}", created_at=original["occurred_at"]+timedelta(minutes=10))
        data["alarm_events"].append(replay)
        label("DUPLICATE_ALARM_REPLAY", "alarm_events", replay, "Same source-event identity replayed with a distinct record identifier", [original["id"]])
    for action in data["corrective_actions"][:n_inject]:
        history = [h for h in data["corrective_action_status_history"] if h["action_id"] == action["id"]]
        action.update(status="CLOSED", completed_at=action["due_at"]-timedelta(hours=1), verified_at=None, verified_by=None, verification_evidence=None)
        add("corrective_action_status_history", f"AH-{action['id']}-99", action_id=action["id"], from_status=history[-1]["to_status"],
            to_status="CLOSED", user_id=users[1]["id"], occurred_at=action["due_at"], note="Imported unverified closure; deliberately preserved")
        label("ACTION_CLOSED_UNVERIFIED", "corrective_actions", action, "Closed without independent verification evidence")
    for table in data:
        data[table].sort(key=lambda r: r["id"])
    progress(85)
    return dict(data)


def checksums(data):
    entities = {k: digest(sorted(v, key=lambda r: r["id"])) for k, v in sorted(data.items())}
    return {"entities": entities, "overall": digest(entities), "counts": {k: len(v) for k, v in sorted(data.items())}}
