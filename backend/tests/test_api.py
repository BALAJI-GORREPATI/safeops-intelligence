import os
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select, func, text
from sqlalchemy.orm import Session as ORMSession
from sqlalchemy.exc import IntegrityError, DBAPIError
from safeops.api import app
from safeops.auth import token
from safeops.db import engine, get_db
from safeops.models import *
from safeops.generator import GeneratorConfig, generate

pytestmark = pytest.mark.integration


@pytest.fixture
def env():
    connection = engine.connect()
    transaction = connection.begin()
    db = ORMSession(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    for role in ["admin", "engineer", "operator", "planner"]:
        if not db.get(ApplicationUser, f"USR-DEMO-{role}"):
            db.add(ApplicationUser(id=f"USR-DEMO-{role}", workspace_id="manual", name=role, role=role))
    db.flush()
    data = generate(GeneratorConfig(seed=31337, events=200, days=2))
    db.add(DatasetGenerationRun(id=data['plants'][0]['workspace_id'], status='COMPLETED', progress=100,
        config=GeneratorConfig(seed=31337, events=200, days=2).model_dump(), counts={}))
    db.flush()
    for table in Base.metadata.sorted_tables:
        if data.get(table.name): db.execute(insert(table), data[table.name])
    db.commit()
    def override(): yield db
    app.dependency_overrides[get_db] = override
    client = TestClient(app)
    client.cookies.set("safeops_session", token("USR-DEMO-admin"))
    yield client, db, data
    client.close()
    app.dependency_overrides.clear()
    db.close(); transaction.rollback(); connection.close()


def test_authentication_and_roles(env):
    client, db, data = env
    alarm = data["alarm_events"][0]
    client.cookies.clear()
    assert client.post(f"/api/alarms/{alarm['id']}/acknowledge", json={"note": "checked machine"}).status_code == 401
    client.cookies.set("safeops_session", token("USR-DEMO-planner"))
    assert client.post(f"/api/alarms/{alarm['id']}/acknowledge", json={"note": "checked machine"}).status_code == 403
    assert client.post("/api/datasets", json=GeneratorConfig().model_dump()).status_code == 403
    client.cookies.set("safeops_session", token("USR-DEMO-operator"))
    assert client.post("/api/config/plants", json={"name": "Test plant", "location": "Pune"}).status_code == 403


def test_acknowledgement_persists_and_original_event_is_immutable(env):
    client, db, data = env
    acked = {r["alarm_id"] for r in data["acknowledgements"]}
    alarm = next(a for a in data["alarm_events"] if a["id"] not in acked)
    before = dict(alarm)
    r = client.post(f"/api/alarms/{alarm['id']}/acknowledge", json={"note": "Guard inspected; safe stop confirmed"})
    assert r.status_code == 201, r.text
    stored = db.scalar(select(Acknowledgement).where(Acknowledgement.alarm_id == alarm["id"]))
    assert stored.user_id == "USR-DEMO-admin"
    fresh = client.get(f"/api/alarms/{alarm['id']}").json()
    assert fresh["acknowledgement"]["id"] == stored.id
    assert fresh["alarm"]["source_event_id"] == before["source_event_id"]
    assert client.post(f"/api/alarms/{alarm['id']}/acknowledge", json={"note": "Second acknowledgement"}).status_code == 409
    with pytest.raises(DBAPIError):
        with db.begin_nested(): db.execute(text("UPDATE alarm_events SET message='changed' WHERE id=:id"), {"id": alarm["id"]})


def test_incident_trace_chain(env):
    client, db, data = env
    incident = next(i for i in data["incidents"] if any(l["incident_id"] == i["id"] for l in data["incident_alarms"]))
    response = client.get('/api/incidents/'+incident["id"])
    assert response.status_code == 200, response.text
    detail = response.json()
    alarm = detail["alarm_details"][0]
    assert alarm["definition"] and alarm["zones"] and alarm["interlocks"] and alarm["state"] and alarm["shift"]
    assert detail["actions"] and detail["timeline"]
    machine = client.get('/api/machines/'+incident["machine_id"])
    assert machine.status_code == 200, machine.text
    assert machine.json()["states"]


def test_action_lifecycle_verification_and_history(env):
    client, db, data = env
    incident = next(i for i in data["incidents"] if i["status"] == "OPEN" and i["rule_id"] == "HAZARD_ESCALATION")
    result = client.post('/api/actions', json={"incident_id": incident["id"], "assignee_id": "USR-DEMO-engineer", "priority": "HIGH", "description": "Replace guard sensor and verify restart", "due_at": (utcnow()+timedelta(days=2)).isoformat()})
    assert result.status_code == 201, result.text
    id = result.json()["id"]
    assert client.post(f'/api/actions/{id}/transition', json={"status": "CLOSED", "note": "Attempt invalid closure"}).status_code == 409
    for status in ["IN_PROGRESS", "COMPLETED"]:
        assert client.post(f'/api/actions/{id}/transition', json={"status": status, "note": "Repair work recorded"}).status_code == 200
    client.cookies.set("safeops_session", token("USR-DEMO-engineer"))
    assert client.post(f'/api/actions/{id}/transition', json={"status": "VERIFIED", "note": "Self verification attempt", "verification_evidence": "Guard cycle test passed"}).status_code == 409
    client.cookies.set("safeops_session", token("USR-DEMO-admin"))
    assert client.post(f'/api/actions/{id}/transition', json={"status": "VERIFIED", "note": "Independent test performed", "verification_evidence": "Guard cycles and supervised safe restart passed"}).status_code == 200
    assert client.post(f'/api/actions/{id}/transition', json={"status": "CLOSED", "note": "Evidence reviewed and accepted"}).status_code == 200
    detail = client.get('/api/actions/'+id).json()
    assert [h["to_status"] for h in detail["history"]] == ["OPEN", "IN_PROGRESS", "COMPLETED", "VERIFIED", "CLOSED"]
    assert detail["action"]["verification_evidence"]


def test_database_constraints_and_invalid_inputs(env):
    client, db, data = env
    assert client.post('/api/config/machines', json={"plant_id": "missing", "name": "Machine", "kind": "Press"}).status_code == 404
    assert client.post('/api/config/plants', json={"name": "", "location": "X"}).status_code == 422
    assert client.get('/api/alarms?limit=10000').status_code == 422
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(Machine(id="BROKEN-FK", workspace_id="test", plant_id="MISSING", name="Broken", kind="Press")); db.flush()


def test_analytics_match_independent_sql(env):
    client, db, data = env
    workspace = data["plants"][0]["workspace_id"]
    result = client.get('/api/dashboard?workspace='+workspace)
    assert result.status_code == 200, result.text
    dashboard = result.json()
    expected = db.execute(text("SELECT COUNT(DISTINCT (machine_id, source_event_id)) FROM alarm_events WHERE workspace_id=:w"), {"w": workspace}).scalar_one()
    assert dashboard["total_alarms"] == expected
    critical = db.execute(text("SELECT COUNT(DISTINCT (a.machine_id,a.source_event_id)) FROM alarm_events a JOIN alarm_definitions d ON a.definition_id=d.id WHERE a.workspace_id=:w AND d.severity='CRITICAL'"), {"w": workspace}).scalar_one()
    assert dashboard["critical_alarms"] == critical
    assert sum(s["value"] for s in dashboard["severity"]) == dashboard["total_alarms"]
    assert sum(s["alarms"] for s in dashboard["trends"]) == dashboard["total_alarms"]
    assert all('2026-10-01' <= day['date'] <= '2026-10-02' for day in dashboard['trends'])
    assert dashboard['rate_period_days'] == 2
    assert all(item['alarms_per_day'] == round(item['alarms']/2, 2) for item in dashboard['top_machines']+dashboard['by_plant'])


def test_effective_configuration_retains_old_definition(env):
    client, db, data = env
    old = data["alarm_definitions"][0]
    values = {k: old[k] for k in ["machine_id", "name", "severity", "ack_deadline_seconds", "source"]}
    values["ack_deadline_seconds"] = 600
    result = client.post(f"/api/config/definitions/{old['id']}/version", json=values)
    assert result.status_code == 201, result.text
    db.expire_all()
    assert db.get(AlarmDefinition, old["id"]).ack_deadline_seconds == old["ack_deadline_seconds"]
    assert db.get(AlarmDefinition, old["id"]).effective_to
    assert result.json()["id"] != old["id"]


def test_manual_configuration_and_safe_machine_state(env):
    client, db, data = env
    p = client.post('/api/config/plants', json={"name": "Integration plant", "location": "Pune"})
    assert p.status_code == 201, p.text
    m = client.post('/api/config/machines', json={"plant_id": p.json()["id"], "name": "Guarded test press", "kind": "Hydraulic press"})
    assert m.status_code == 201, m.text
    mid = m.json()["id"]
    z = client.post('/api/config/zones', json={"plant_id": p.json()["id"], "machine_id": mid, "name": "Test perimeter", "restriction": "Closed guard required while running"})
    assert z.status_code == 201, z.text
    lock = client.post('/api/config/interlocks', json={"machine_id": mid, "zone_id": z.json()["id"], "name": "Guard test lock", "mandatory": True})
    assert lock.status_code == 201, lock.text
    definition = client.post('/api/config/definitions', json={"machine_id": mid, "name": "Guard state alarm", "severity": "CRITICAL", "ack_deadline_seconds": 120})
    assert definition.status_code == 201, definition.text
    invalid = {"state": "RUNNING", "interlock_state": "BYPASSED", "guard_state": "OPEN", "reason": "Unsafe start attempt"}
    assert client.post(f'/api/machines/{mid}/state', json=invalid).status_code == 409
    valid = {**invalid, "interlock_state": "ENGAGED", "guard_state": "CLOSED", "reason": "Guard closed; supervised safe start"}
    assert client.post(f'/api/machines/{mid}/state', json=valid).status_code == 201
    detail = client.get('/api/machines/'+mid).json()
    assert detail["states"][0]["state"] == "RUNNING"
    assert detail["interlocks"][0]["guard_state"] == "CLOSED"


@pytest.mark.parametrize('role', ['operator', 'engineer', 'planner'])
def test_dataset_administration_is_forbidden_for_every_non_admin(env, role):
    client, db, data = env
    workspace = data['plants'][0]['workspace_id']
    client.cookies.set('safeops_session', token(f'USR-DEMO-{role}'))
    assert client.get('/api/datasets').status_code == 403
    assert client.post('/api/datasets', json=GeneratorConfig().model_dump()).status_code == 403
    for suffix, method in [('report', 'get'), ('validate', 'post'), ('reproduce', 'post')]:
        assert getattr(client, method)(f'/api/datasets/{workspace}/{suffix}').status_code == 403
    for format in ['bundle', 'csv', 'json', 'sql', 'validation', 'ground-truth']:
        assert client.get(f'/api/datasets/{workspace}/export?format={format}').status_code == 403
    public = client.get('/api/workspaces')
    assert public.status_code == 200
    for item in public.json():
        assert set(item) == {'id', 'status', 'config'}
        assert set(item['config']) == {'preset', 'seed', 'events'}
    assert client.get(f'/exports/{workspace}/evaluation/ground_truth.json').status_code == 404


def test_admin_report_preserves_isolated_labels_and_all_download_formats(env):
    import io
    import json
    import zipfile
    from safeops.services import analyse_workspace
    from safeops.generator import canonical
    client, db, data = env
    workspace = data['plants'][0]['workspace_id']
    _, _, report = analyse_workspace(db, workspace)
    db.add(ValidationResult(id='VAL-FORMAT-TEST', run_id=workspace, report=json.loads(canonical(report))))
    db.commit()
    result = client.get(f'/api/datasets/{workspace}/report')
    assert result.status_code == 200
    assert len(result.json()['report']['ground_truth']) == 5
    assert result.json()['report']['evaluation']['overall']['tp'] == 5
    assert 'ground_truth' not in result.json()['report']['detections'][0]
    for format in ['csv', 'json', 'sql', 'bundle']:
        result = client.get(f'/api/datasets/{workspace}/export?format={format}')
        assert result.status_code == 200, result.text
        assert 'attachment;' in result.headers['content-disposition']
        with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
            names = archive.namelist()
            assert 'source-manifest.json' in names
            if format == 'csv':
                assert 'csv/alarm_events.csv' in names and 'evaluation/ground_truth.csv' in names
                assert not any(n.startswith('sql/') for n in names)
            if format == 'json':
                assert 'json/alarm_events.json' in names and 'evaluation/ground_truth.json' in names
                assert 'anomaly_type' not in json.loads(archive.read('json/alarm_events.json'))[0]
            if format == 'sql': assert 'sql/seed.sql' in names and 'sql/schema.sql' in names
            if format == 'bundle': assert 'evaluation/detection_results.json' in names
    validation = client.get(f'/api/datasets/{workspace}/export?format=validation')
    assert validation.status_code == 200
    assert validation.json()['validation']['counts']['UNEXPECTED_FAILURE'] == 0
    truth = client.get(f'/api/datasets/{workspace}/export?format=ground-truth')
    assert truth.status_code == 200
    assert len(truth.json()) == 5
