"""Persisted full-scale validation, independent SQL totals and API timings."""
from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter
import httpx
from sqlalchemy import select, text
from safeops.db import Session
from safeops.models import DatasetGenerationRun
from safeops.auth import token
from safeops.services import analyse_workspace

results = {}
with Session() as db:
    runs = list(db.scalars(select(DatasetGenerationRun).where(DatasetGenerationRun.status == "COMPLETED").order_by(DatasetGenerationRun.created_at.desc())))
    for preset in ("starter", "full"):
        run = next(r for r in runs if r.config["preset"] == preset and r.config["seed"] == 20261022)
        _, _, report = analyse_workspace(db, run.id)
        assert report["validation"]["counts"]["UNEXPECTED_FAILURE"] == 0, report["validation"]["findings"][-10:]
        with httpx.Client(base_url="http://127.0.0.1:8000", cookies={"safeops_session": token("USR-DEMO-admin")}, timeout=90) as client:
            started = perf_counter()
            response = client.get('/api/dashboard', params={"workspace": run.id})
            elapsed = perf_counter()-started
            response.raise_for_status()
            dashboard = response.json()
            physical = db.execute(text("SELECT count(DISTINCT (machine_id, source_event_id)) FROM alarm_events WHERE workspace_id=:w"), {"w": run.id}).scalar_one()
            assert dashboard["total_alarms"] == physical
            started = perf_counter()
            alarms = client.get('/api/alarms', params={"workspace": run.id, "limit": 25})
            alarms.raise_for_status()
            list_elapsed = perf_counter()-started
            assert len(alarms.json()["items"]) == 25
            results[preset] = {"workspace": run.id, "stored_counts": run.counts, "physical_alarms": physical,
                "dashboard_seconds": round(elapsed, 4), "alarm_page_seconds": round(list_elapsed, 4),
                "dashboard_response_bytes": len(response.content), "alarm_page_response_bytes": len(alarms.content),
                "validation_counts": report["validation"]["counts"], "evaluation": report["evaluation"]["overall"]}
results["verified_at"] = datetime.now(timezone.utc).isoformat()
Path("docs/database-verification.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print(json.dumps(results, indent=2))
