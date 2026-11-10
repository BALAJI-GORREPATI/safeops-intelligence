# Business rules and metric definitions

These are project-defined demonstration thresholds, not universal regulatory limits.

| Severity | Default acknowledgement deadline |
|---|---:|
| CRITICAL | 120 seconds |
| HIGH | 300 seconds |
| MEDIUM | 900 seconds |
| LOW | 1,800 seconds |

Each definition stores its effective deadline. An acknowledgement delay is `acknowledged_at - occurred_at`. Negative delay is INVALID_ACKNOWLEDGEMENT. A nonnegative delay up to and including the deadline is ACKNOWLEDGED_ON_TIME; a greater delay is ACKNOWLEDGED_LATE. No acknowledgement gives UNACKNOWLEDGED, with a separate overdue flag relative to current UTC. Acknowledgement writes the authenticated user and current UTC, rejects future alarms and duplicate acknowledgement, and never modifies the event.

Incident lifecycle is OPEN → INVESTIGATING → ACTION_PENDING → RESOLVED → CLOSED. Every advance needs triggering evidence; ACTION_PENDING needs an action; RESOLVED and CLOSED require all actions verified with evidence. Reopening is intentionally unsupported. Imported missing-context incidents can receive same-machine alarm evidence before progression.

Action lifecycle is OPEN → IN_PROGRESS → COMPLETED → VERIFIED → CLOSED. No skipped transitions. Completion records UTC. Verification needs completion, at least 10 characters of evidence and a different actor from the assigned engineer. Closure requires verification. Imported anomalous closures are preserved and flagged. Reassignment is audited and prohibited after verification.

| Rule | Evidence / threshold |
|---|---|
| ACK_BEFORE_ALARM | acknowledgement time earlier than linked alarm |
| IMPOSSIBLE_INTERLOCK_STATE | effective mandatory interlock, RUNNING machine and OPEN guard or interlock other than ENGAGED |
| INCIDENT_MISSING_CONTEXT | no linked alarm with same-machine state evidence |
| DUPLICATE_ALARM_REPLAY | same `(machine_id, source_event_id)` ingested again; earliest ingestion then ID is canonical |
| ACTION_CLOSED_UNVERIFIED | VERIFIED/CLOSED without completion, verifier, timestamp or evidence |
| ALARM_FLOOD | at least 20 distinct physical source events in a rolling 600-second event-time window per machine |
| NUISANCE_ALARM | at least eight LOW sensor-chatter signals for one machine/definition during one UTC day |
| RECURRENT_HAZARD | same machine and escalation rule recur after a prior action's verification time |

Flood episodes start on the threshold crossing; another episode requires the rolling count to fall below threshold first. Replayed ingestions never inflate flood or operational alarm counts. Repeated HIGH/CRITICAL hazards are not classified as nuisance. Flood window, threshold and nuisance threshold are configurable through `FLOOD_WINDOW_SECONDS`, `FLOOD_THRESHOLD`, `NUISANCE_THRESHOLD` before API/CLI start.

Each detection includes a rule ID, target entity and record, related IDs, event timestamp, severity, explanation and evidence. Detection runs never receive ground-truth rows. Dataset validation/evaluation can be rerun by an administrator. Dashboard rule summaries carry the last-analysis timestamp; acknowledgement and lifecycle KPIs are live SQL queries.

| Metric | Formula / scope |
|---|---|
| Physical alarms | unique `(machine_id, source_event_id)` in the selected event-time interval |
| Ingested records | all stored alarm rows including replays |
| Severity counts | physical alarms grouped by effective alarm definition |
| Alarm rate | distinct physical count / selected interval days, by machine/plant; unfiltered simulations use their configured duration; chart groups UTC days |
| Average / median response | valid nonnegative delays, excluding unacknowledged and invalid responses |
| Late acknowledgement percentage | late or currently overdue physical alarms / all physical alarms × 100 |
| Critical on time | critical physical alarms acknowledged within deadline / all critical physical alarms × 100 |
| Open incidents | incident status other than RESOLVED/CLOSED |
| Recurrence rate | distinct recurrent incident IDs / incidents in scope × 100 |
| Overdue actions | past due and status not VERIFIED/CLOSED |
| Verification completion | actions with verified timestamp / all actions in scope × 100 |
| Flood / nuisance frequency | number of detected episodes/patterns from latest analysis, filtered by event time/machine/plant |

The dashboard shows physical alarm counts and separate ingested/replay totals. The alarm workbench shows every stored ingestion for investigation. All timestamps display in the browser's local timezone; grouping days are explicitly UTC.

Roles: operator can acknowledge; engineer can acknowledge, investigate, attach evidence, manage actions and record safe machine states; planner can read operational views; administrator can additionally configure assets, generate data, evaluate ground truth and export datasets. API dependencies enforce these capabilities. All authenticated roles can inspect operational records. This is shared local demo authentication with signed, eight-hour HttpOnly SameSite cookies, not enterprise identity management.
