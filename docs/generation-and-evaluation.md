# Synthetic generation, anomalies and validation

Generator version 1.1.0 uses NumPy's fixed-seed random generator, stable iteration and counters. Default seed: **20261022**. Simulation begins **2026-10-01 00:00 UTC**. Starter covers seven days and full covers 30. Counts are configurable with `GeneratorConfig`; both presets share the same implementation. Configuration validates at least one machine per plant and one definition per machine. Mandatory anomaly categories always have at least one eligible baseline record in supported presets; injection rate is a target capped by eligible evidence.

Order: users, plants, machines, zones/bridges, interlocks, definitions, shifts, machine/interlock states, alarms, acknowledgements, incidents, actions, histories, anomaly edits/labels, detection and validation. Master data and FK-safe histories are assembled before database insertion in topological table order.

Machines follow shift-based RUNNING/STOPPED/MAINTENANCE patterns. Alarm volumes follow unequal machine weights. A 40-event distinct-source burst creates a genuine fault flood. Definition severity controls escalation and response deadlines. Lognormal responses reflect longer delays at higher-load equipment; a stable subset is unacknowledged. HIGH/CRITICAL signals trigger spaced escalations. A fault burst triggers an incident. Verified historical remediations permit measurable recurrence. Injected unsafe guard/interlock combinations produce a linked critical incident and action. Baseline state histories obey guard restrictions before deliberate anomalies are introduced.

| Injected category | Exact mechanism |
|---|---|
| ACK_BEFORE_ALARM | move selected acknowledgement 30 seconds before its source alarm |
| IMPOSSIBLE_INTERLOCK_STATE | change an existing RUNNING context to guard OPEN/interlock BYPASSED; preserve keys and escalate with linked evidence |
| INCIDENT_MISSING_CONTEXT | create a valid machine-related incident and initial history, deliberately omit triggering-alarm bridge |
| DUPLICATE_ALARM_REPLAY | reserve alarm slots for new primary-key rows carrying an existing physical source identity; ingestion is 10 minutes after original occurrence |
| ACTION_CLOSED_UNVERIFIED | preserve original history, append imported CLOSED transition, clear verification evidence/time/actor, retain valid completion |

Identifier examples: `SAFE-<plant-id>-001`, `ALM-<machine-id>-000001`, `INC-2026-<zero-padded numeric counter>`, `ACK-<alarm-id>-01`, `ACT-<incident-id>-01`. PLT/MAC/DEF/USR/SHF/MSE/ISE/IA/IH/AH/GT prefixes identify other tables. The first ten hex characters of SHA-256 over generator version/config determine the simulation namespace. Incident numeric counters incorporate that namespace's integer value × 1,000,000, maintaining the required numeric pattern while avoiding collisions between development presets. Canonical references match across SQL, CSV, JSON and PostgreSQL. Manual identifiers use `-MAN-` plus a random UUID fragment and are outside seeded reproduction scope.

Ground truth is stored only in a separate database table and exported under `evaluation/ground_truth.csv` and `.json`. `rules.detect` sees operational tables only. Labels are read after detection. Rule decisions match on `(rule_id, target_record_id)`. Each of the five categories has a clearly defined eligible-table universe. Every unlabelled eligible row is a negative. A replay is evaluated per extra ingestion, not once per group. Multi-record evidence is attached to the target decision rather than counted as extra true positives. Operational flood/nuisance/recurrence detections are separate from the five labelled integrity categories.

Per rule: TP = predicted and labelled; FP = predicted but unlabelled; FN = labelled but undetected; TN = eligible rows in neither set. Precision = TP/(TP+FP), recall = TP/(TP+FN), F1 = 2PR/(P+R), with zero for empty denominators. Overall counts sum rule-level universes. Thus the overall denominator is eligible **rule-row pairs**, not all database rows.

Validation checks PKs, all metadata-defined unique keys, FKs, required fields, enums, shift/state/definition consistency, effective intervals, ingestion/event ordering, acknowledgement order, verification order, lifecycle continuity and final-history reconciliation. Materialized dashboard counters are independently reconciled against SQL in integration tests. Expected labels classify matching evidence as EXPECTED_ANOMALY; all other violations are UNEXPECTED_FAILURE. More than one finding can arise from one label (unverified closure and its skipped transition); counts are findings, not anomaly instances. Label presence never suppresses an unrelated structural failure. SQL constraints remain enabled during import.

Reproduction regenerates twice with identical seed, configuration, window and version. All rows sort by canonical ID; canonical JSON sorts keys. Entity SHA-256, row counts, dataset SHA-256 and exported file checksums are compared. Generated ingestion timestamps are deterministic; no generated metadata is excluded. Operational edits are separate from fresh-generator reproduction. `scripts/verify_artifacts.py` independently exports both runs for both presets and compares every output file. Source manifests record provenance, version, configuration, period, schema, counts and checksums. File manifests exclude their own self-referential checksum.

Export structure:

```text
exports/<preset-or-run>/
  csv/<operational-table>.csv
  json/<operational-table>.json
  evaluation/ground_truth.csv, ground_truth.json
  evaluation/detection_results.csv, detection_results.json
  sql/schema.sql, seed.sql
  data-dictionary.md, data-dictionary.json
  validation-summary.json
  generation-config.json
  reproducibility-report.json
  source-manifest.json
```

SQL seeds use dependency order, escaped literals, explicit canonical IDs and a transaction. They are intended for an empty migrated schema; no DROP, TRUNCATE, DELETE or conflict-overwrite commands are emitted. Apply Alembic migrations to retain immutable-history triggers. Never import into an occupied operational schema without reviewing collisions.
