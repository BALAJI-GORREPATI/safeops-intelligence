from copy import deepcopy
from pathlib import Path
import pytest
from safeops.generator import GeneratorConfig, generate, checksums
from safeops.rules import detect, evaluate, ack_status, ANOMALY_ENTITIES
from safeops.validation import validate
from safeops.artifacts import export_dataset


@pytest.fixture(scope="module")
def starter(): return generate(GeneratorConfig())


@pytest.mark.parametrize("preset", ["starter", "full"])
def test_counts_integrity_and_reproducibility(preset):
    config = GeneratorConfig.preset_config(preset)
    a, b = generate(config), generate(config)
    assert checksums(a) == checksums(b)
    assert len(a["alarm_events"]) == config.events
    assert len(a["plants"]) == config.plants
    assert len(a["machines"]) == config.machines
    assert len(a["alarm_definitions"]) == config.definitions
    report = validate(a, a["ground_truth"])
    assert report["counts"]["UNEXPECTED_FAILURE"] == 0, report["findings"][-10:]
    assert {r["anomaly_type"] for r in a["ground_truth"]} == set(ANOMALY_ENTITIES)


def test_detector_does_not_consume_labels(starter):
    ops = {k: v for k, v in starter.items() if k != "ground_truth"}
    detections = detect(ops)
    evaluation = evaluate(ops, starter["ground_truth"], detections)
    assert evaluation["overall"]["tp"] == 5
    assert evaluation["overall"]["fn"] == 0
    assert evaluation["overall"]["fp"] == 0
    assert evaluation["overall"]["tn"] > 0
    assert detect(ops) == detections
    assert "ground_truth" not in ops


def test_validation_rejects_unexpected_defects(starter):
    data = deepcopy(starter)
    data["alarm_events"][0]["machine_id"] = "NONEXISTENT"
    data["machines"][0]["kind"] = None
    data["machines"].append(data["machines"][0].copy())
    data["alarm_definitions"][0]["severity"] = "BANANA"
    report = validate(data, data["ground_truth"])
    assert report["status"] == "FAIL"
    assert {"FOREIGN_KEY", "REQUIRED_FIELD", "PRIMARY_KEY", "ENUM"} <= {f["check"] for f in report["findings"]}


def test_exports_are_identical_and_include_labels_separately(tmp_path, starter):
    config = GeneratorConfig()
    a = export_dataset(starter, config, {}, tmp_path/"a", {"identical": True})
    b = export_dataset(starter, config, {}, tmp_path/"b", {"identical": True})
    assert a["files"] == b["files"]
    assert (tmp_path/"a/evaluation/ground_truth.csv").exists()
    assert not (tmp_path/"a/csv/ground_truth.csv").exists()
    assert "BEGIN;" in (tmp_path/"a/sql/seed.sql").read_text()


def test_seed_changes_data(starter):
    assert checksums(starter)["overall"] != checksums(generate(GeneratorConfig(seed=123)))["overall"]


def test_replays_are_excluded_from_flood_count(starter):
    ops = {k: deepcopy(v) for k, v in starter.items() if k != "ground_truth"}
    before = [d for d in detect(ops) if d["rule_id"] == "ALARM_FLOOD"]
    original = ops["alarm_events"][0]
    for n in range(100):
        ops["alarm_events"].append(dict(original, id=f"REPLAY-{n:04}"))
    after = [d for d in detect(ops) if d["rule_id"] == "ALARM_FLOOD"]
    assert len(before) == len(after)


def test_response_deadline_boundaries(starter):
    from datetime import timedelta
    a = starter["alarm_events"][0]
    deadline = {"ack_deadline_seconds": 120}
    assert ack_status(a, {"acknowledged_at": a["occurred_at"]+timedelta(seconds=120)}, deadline)["status"] == "ACKNOWLEDGED_ON_TIME"
    assert ack_status(a, {"acknowledged_at": a["occurred_at"]+timedelta(seconds=121)}, deadline)["status"] == "ACKNOWLEDGED_LATE"
    assert ack_status(a, {"acknowledged_at": a["occurred_at"]-timedelta(seconds=1)}, deadline)["status"] == "INVALID_ACKNOWLEDGEMENT"


def test_minimum_custom_scale_still_has_all_anomaly_categories():
    data = generate(GeneratorConfig(plants=1, machines=1, definitions=1, events=100, days=1))
    assert {r["anomaly_type"] for r in data["ground_truth"]} == set(ANOMALY_ENTITIES)
    assert validate(data, data["ground_truth"])["counts"]["UNEXPECTED_FAILURE"] == 0
