# Data dictionary

Generated from SQLAlchemy metadata. All event timestamps are UTC. Identifiers are immutable strings.

## application_users

| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |
|---|---|---|---|---|---|---|---|---|
| name | VARCHAR(120) | True | ["role IN ('operator','engineer','planner','admin')"] | — | — | False | [] | Name |
| role | VARCHAR(20) | True | ["role IN ('operator','engineer','planner','admin')"] | — | — | False | [] | Role |
| id | VARCHAR(160) | True | ["role IN ('operator','engineer','planner','admin')"] | — | — | True | [] | Immutable canonical identifier |
| workspace_id | VARCHAR(80) | True | ["role IN ('operator','engineer','planner','admin')"] | — | — | False | [] | Dataset run identifier or manual |
| created_at | DATETIME | True | ["role IN ('operator','engineer','planner','admin')"] | UTC | UTC now | False | [] | UTC record ingestion time |

Composite uniqueness: []

## dataset_generation_runs

| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |
|---|---|---|---|---|---|---|---|---|
| id | VARCHAR(80) | True | [] | — | — | True | [] | Id |
| status | VARCHAR(20) | True | [] | — | — | False | [] | Status |
| progress | INTEGER | True | [] | — | 0 | False | [] | Progress |
| config | JSON | True | [] | — | — | False | [] | Config |
| counts | JSON | True | [] | — | UTC now | False | [] | Counts |
| checksum | VARCHAR(64) | False | [] | — | — | False | [] | Checksum |
| error | TEXT | False | [] | — | — | False | [] | Error |
| created_at | DATETIME | True | [] | UTC | UTC now | False | [] | Created at |

Composite uniqueness: []

## ground_truth

| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |
|---|---|---|---|---|---|---|---|---|
| id | VARCHAR(160) | True | [] | — | — | True | [] | Id |
| workspace_id | VARCHAR(80) | True | [] | — | — | False | [] | Workspace id |
| target_entity | VARCHAR(80) | True | [] | — | — | False | [] | Target entity |
| target_record_id | VARCHAR(160) | True | [] | — | — | False | [] | Target record id |
| anomaly_type | VARCHAR(80) | True | [] | — | — | False | [] | Anomaly type |
| expected_decision | BOOLEAN | True | [] | — | True | False | [] | Expected decision |
| rule_id | VARCHAR(80) | True | [] | — | — | False | [] | Rule id |
| explanation | TEXT | True | [] | — | — | False | [] | Explanation |
| related_record_ids | JSON | True | [] | — | — | False | [] | Related record ids |

Composite uniqueness: []

## plants

| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |
|---|---|---|---|---|---|---|---|---|
| name | VARCHAR(120) | True | [] | — | — | False | [] | Name |
| location | VARCHAR(120) | True | [] | — | — | False | [] | Location |
| timezone | VARCHAR(80) | True | [] | — | Asia/Kolkata | False | [] | Timezone |
| active | BOOLEAN | True | [] | — | True | False | [] | Active |
| id | VARCHAR(160) | True | [] | — | — | True | [] | Immutable canonical identifier |
| workspace_id | VARCHAR(80) | True | [] | — | — | False | [] | Dataset run identifier or manual |
| created_at | DATETIME | True | [] | UTC | UTC now | False | [] | UTC record ingestion time |

Composite uniqueness: [['workspace_id', 'name']]

## audit_events

| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |
|---|---|---|---|---|---|---|---|---|
| entity | VARCHAR(80) | True | [] | — | — | False | [] | Entity |
| record_id | VARCHAR(160) | True | [] | — | — | False | [] | Record id |
| user_id | VARCHAR(160) | True | [] | — | — | False | ['application_users.id'] | User id |
| operation | VARCHAR(80) | True | [] | — | — | False | [] | Operation |
| occurred_at | DATETIME | True | [] | UTC | — | False | [] | Occurred at |
| evidence | JSON | True | [] | — | — | False | [] | Evidence |
| id | VARCHAR(160) | True | [] | — | — | True | [] | Immutable canonical identifier |
| workspace_id | VARCHAR(80) | True | [] | — | — | False | [] | Dataset run identifier or manual |
| created_at | DATETIME | True | [] | UTC | UTC now | False | [] | UTC record ingestion time |

Composite uniqueness: []

## machines

| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |
|---|---|---|---|---|---|---|---|---|
| plant_id | VARCHAR(160) | True | [] | — | — | False | ['plants.id'] | Plant id |
| name | VARCHAR(120) | True | [] | — | — | False | [] | Name |
| kind | VARCHAR(80) | True | [] | — | — | False | [] | Kind |
| active | BOOLEAN | True | [] | — | True | False | [] | Active |
| id | VARCHAR(160) | True | [] | — | — | True | [] | Immutable canonical identifier |
| workspace_id | VARCHAR(80) | True | [] | — | — | False | [] | Dataset run identifier or manual |
| created_at | DATETIME | True | [] | UTC | UTC now | False | [] | UTC record ingestion time |

Composite uniqueness: [['plant_id', 'name']]

## operator_shifts

| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |
|---|---|---|---|---|---|---|---|---|
| plant_id | VARCHAR(160) | True | ['ends_at > starts_at'] | — | — | False | ['plants.id'] | Plant id |
| user_id | VARCHAR(160) | True | ['ends_at > starts_at'] | — | — | False | ['application_users.id'] | User id |
| starts_at | DATETIME | True | ['ends_at > starts_at'] | UTC | — | False | [] | Starts at |
| ends_at | DATETIME | True | ['ends_at > starts_at'] | UTC | — | False | [] | Ends at |
| id | VARCHAR(160) | True | ['ends_at > starts_at'] | — | — | True | [] | Immutable canonical identifier |
| workspace_id | VARCHAR(80) | True | ['ends_at > starts_at'] | — | — | False | [] | Dataset run identifier or manual |
| created_at | DATETIME | True | ['ends_at > starts_at'] | UTC | UTC now | False | [] | UTC record ingestion time |

Composite uniqueness: []

## safety_zones

| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |
|---|---|---|---|---|---|---|---|---|
| plant_id | VARCHAR(160) | True | [] | — | — | False | ['plants.id'] | Plant id |
| name | VARCHAR(120) | True | [] | — | — | False | [] | Name |
| restriction | VARCHAR(240) | True | [] | — | Guard must be closed during operation | False | [] | Restriction |
| effective_from | DATETIME | True | [] | UTC | — | False | [] | Effective from |
| effective_to | DATETIME | False | [] | UTC | — | False | [] | Effective to |
| id | VARCHAR(160) | True | [] | — | — | True | [] | Immutable canonical identifier |
| workspace_id | VARCHAR(80) | True | [] | — | — | False | [] | Dataset run identifier or manual |
| created_at | DATETIME | True | [] | UTC | UTC now | False | [] | UTC record ingestion time |

Composite uniqueness: []

## validation_results

| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |
|---|---|---|---|---|---|---|---|---|
| id | VARCHAR(100) | True | [] | — | — | True | [] | Id |
| run_id | VARCHAR(80) | True | [] | — | — | False | ['dataset_generation_runs.id'] | Run id |
| report | JSON | True | [] | — | — | False | [] | Report |
| created_at | DATETIME | True | [] | UTC | UTC now | False | [] | Created at |

Composite uniqueness: []

## alarm_definitions

| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |
|---|---|---|---|---|---|---|---|---|
| machine_id | VARCHAR(160) | True | ['ack_deadline_seconds > 0', "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')"] | — | — | False | ['machines.id'] | Machine id |
| name | VARCHAR(160) | True | ['ack_deadline_seconds > 0', "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')"] | — | — | False | [] | Name |
| severity | VARCHAR(16) | True | ['ack_deadline_seconds > 0', "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')"] | — | — | False | [] | Severity |
| source | VARCHAR(80) | True | ['ack_deadline_seconds > 0', "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')"] | — | PLC | False | [] | Source |
| ack_deadline_seconds | INTEGER | True | ['ack_deadline_seconds > 0', "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')"] | seconds | — | False | [] | Project demo response deadline in seconds |
| effective_from | DATETIME | True | ['ack_deadline_seconds > 0', "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')"] | UTC | — | False | [] | Effective from |
| effective_to | DATETIME | False | ['ack_deadline_seconds > 0', "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')"] | UTC | — | False | [] | Effective to |
| id | VARCHAR(160) | True | ['ack_deadline_seconds > 0', "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')"] | — | — | True | [] | Immutable canonical identifier |
| workspace_id | VARCHAR(80) | True | ['ack_deadline_seconds > 0', "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')"] | — | — | False | [] | Dataset run identifier or manual |
| created_at | DATETIME | True | ['ack_deadline_seconds > 0', "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')"] | UTC | UTC now | False | [] | UTC record ingestion time |

Composite uniqueness: []

## incidents

| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |
|---|---|---|---|---|---|---|---|---|
| machine_id | VARCHAR(160) | True | ["severity IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','INVESTIGATING','ACTION_PENDING','RESOLVED','CLOSED')"] | — | — | False | ['machines.id'] | Machine id |
| title | VARCHAR(240) | True | ["severity IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','INVESTIGATING','ACTION_PENDING','RESOLVED','CLOSED')"] | — | — | False | [] | Title |
| severity | VARCHAR(16) | True | ["severity IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','INVESTIGATING','ACTION_PENDING','RESOLVED','CLOSED')"] | — | — | False | [] | Severity |
| status | VARCHAR(24) | True | ["severity IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','INVESTIGATING','ACTION_PENDING','RESOLVED','CLOSED')"] | — | OPEN | False | [] | Status |
| occurred_at | DATETIME | True | ["severity IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','INVESTIGATING','ACTION_PENDING','RESOLVED','CLOSED')"] | UTC | — | False | [] | Occurred at |
| rule_id | VARCHAR(80) | True | ["severity IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','INVESTIGATING','ACTION_PENDING','RESOLVED','CLOSED')"] | — | — | False | [] | Rule id |
| id | VARCHAR(160) | True | ["severity IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','INVESTIGATING','ACTION_PENDING','RESOLVED','CLOSED')"] | — | — | True | [] | Immutable canonical identifier |
| workspace_id | VARCHAR(80) | True | ["severity IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','INVESTIGATING','ACTION_PENDING','RESOLVED','CLOSED')"] | — | — | False | [] | Dataset run identifier or manual |
| created_at | DATETIME | True | ["severity IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','INVESTIGATING','ACTION_PENDING','RESOLVED','CLOSED')"] | UTC | UTC now | False | [] | UTC record ingestion time |

Composite uniqueness: []

## interlocks

| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |
|---|---|---|---|---|---|---|---|---|
| machine_id | VARCHAR(160) | True | [] | — | — | False | ['machines.id'] | Machine id |
| zone_id | VARCHAR(160) | True | [] | — | — | False | ['safety_zones.id'] | Zone id |
| name | VARCHAR(120) | True | [] | — | — | False | [] | Name |
| mandatory | BOOLEAN | True | [] | — | True | False | [] | Mandatory |
| effective_from | DATETIME | True | [] | UTC | — | False | [] | Effective from |
| effective_to | DATETIME | False | [] | UTC | — | False | [] | Effective to |
| id | VARCHAR(160) | True | [] | — | — | True | [] | Immutable canonical identifier |
| workspace_id | VARCHAR(80) | True | [] | — | — | False | [] | Dataset run identifier or manual |
| created_at | DATETIME | True | [] | UTC | UTC now | False | [] | UTC record ingestion time |

Composite uniqueness: []

## machine_safety_zones

| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |
|---|---|---|---|---|---|---|---|---|
| machine_id | VARCHAR(160) | True | [] | — | — | False | ['machines.id'] | Machine id |
| zone_id | VARCHAR(160) | True | [] | — | — | False | ['safety_zones.id'] | Zone id |
| id | VARCHAR(160) | True | [] | — | — | True | [] | Immutable canonical identifier |
| workspace_id | VARCHAR(80) | True | [] | — | — | False | [] | Dataset run identifier or manual |
| created_at | DATETIME | True | [] | UTC | UTC now | False | [] | UTC record ingestion time |

Composite uniqueness: [['machine_id', 'zone_id']]

## machine_state_events

| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |
|---|---|---|---|---|---|---|---|---|
| machine_id | VARCHAR(160) | True | ["state IN ('RUNNING','STOPPED','MAINTENANCE','FAULT')"] | — | — | False | ['machines.id'] | Machine id |
| state | VARCHAR(20) | True | ["state IN ('RUNNING','STOPPED','MAINTENANCE','FAULT')"] | — | — | False | [] | State |
| occurred_at | DATETIME | True | ["state IN ('RUNNING','STOPPED','MAINTENANCE','FAULT')"] | UTC | — | False | [] | Occurred at |
| reason | VARCHAR(240) | True | ["state IN ('RUNNING','STOPPED','MAINTENANCE','FAULT')"] | — | — | False | [] | Reason |
| id | VARCHAR(160) | True | ["state IN ('RUNNING','STOPPED','MAINTENANCE','FAULT')"] | — | — | True | [] | Immutable canonical identifier |
| workspace_id | VARCHAR(80) | True | ["state IN ('RUNNING','STOPPED','MAINTENANCE','FAULT')"] | — | — | False | [] | Dataset run identifier or manual |
| created_at | DATETIME | True | ["state IN ('RUNNING','STOPPED','MAINTENANCE','FAULT')"] | UTC | UTC now | False | [] | UTC record ingestion time |

Composite uniqueness: []

## alarm_events

| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |
|---|---|---|---|---|---|---|---|---|
| machine_id | VARCHAR(160) | True | [] | — | — | False | ['machines.id'] | Machine id |
| definition_id | VARCHAR(160) | True | [] | — | — | False | ['alarm_definitions.id'] | Definition id |
| machine_state_id | VARCHAR(160) | True | [] | — | — | False | ['machine_state_events.id'] | Machine state id |
| shift_id | VARCHAR(160) | True | [] | — | — | False | ['operator_shifts.id'] | Shift id |
| source_event_id | VARCHAR(160) | True | [] | — | — | False | [] | Physical source identity; repeats indicate replay |
| occurred_at | DATETIME | True | [] | UTC | — | False | [] | Occurred at |
| message | VARCHAR(240) | True | [] | — | — | False | [] | Message |
| value | FLOAT | False | [] | — | — | False | [] | Sensor reading, degrees C for temperature definitions |
| id | VARCHAR(160) | True | [] | — | — | True | [] | Immutable canonical identifier |
| workspace_id | VARCHAR(80) | True | [] | — | — | False | [] | Dataset run identifier or manual |
| created_at | DATETIME | True | [] | UTC | UTC now | False | [] | UTC record ingestion time |

Composite uniqueness: []

## corrective_actions

| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |
|---|---|---|---|---|---|---|---|---|
| incident_id | VARCHAR(160) | True | ["priority IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','IN_PROGRESS','COMPLETED','VERIFIED','CLOSED')"] | — | — | False | ['incidents.id'] | Incident id |
| assignee_id | VARCHAR(160) | True | ["priority IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','IN_PROGRESS','COMPLETED','VERIFIED','CLOSED')"] | — | — | False | ['application_users.id'] | Assignee id |
| priority | VARCHAR(16) | True | ["priority IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','IN_PROGRESS','COMPLETED','VERIFIED','CLOSED')"] | — | — | False | [] | Priority |
| description | TEXT | True | ["priority IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','IN_PROGRESS','COMPLETED','VERIFIED','CLOSED')"] | — | — | False | [] | Description |
| due_at | DATETIME | True | ["priority IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','IN_PROGRESS','COMPLETED','VERIFIED','CLOSED')"] | UTC | — | False | [] | Due at |
| status | VARCHAR(20) | True | ["priority IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','IN_PROGRESS','COMPLETED','VERIFIED','CLOSED')"] | — | OPEN | False | [] | Status |
| completed_at | DATETIME | False | ["priority IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','IN_PROGRESS','COMPLETED','VERIFIED','CLOSED')"] | UTC | — | False | [] | Completed at |
| verified_at | DATETIME | False | ["priority IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','IN_PROGRESS','COMPLETED','VERIFIED','CLOSED')"] | UTC | — | False | [] | Verified at |
| verified_by | VARCHAR(160) | False | ["priority IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','IN_PROGRESS','COMPLETED','VERIFIED','CLOSED')"] | — | — | False | ['application_users.id'] | Verified by |
| verification_evidence | TEXT | False | ["priority IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','IN_PROGRESS','COMPLETED','VERIFIED','CLOSED')"] | — | — | False | [] | Verification evidence |
| id | VARCHAR(160) | True | ["priority IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','IN_PROGRESS','COMPLETED','VERIFIED','CLOSED')"] | — | — | True | [] | Immutable canonical identifier |
| workspace_id | VARCHAR(80) | True | ["priority IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','IN_PROGRESS','COMPLETED','VERIFIED','CLOSED')"] | — | — | False | [] | Dataset run identifier or manual |
| created_at | DATETIME | True | ["priority IN ('LOW','MEDIUM','HIGH','CRITICAL')", "status IN ('OPEN','IN_PROGRESS','COMPLETED','VERIFIED','CLOSED')"] | UTC | UTC now | False | [] | UTC record ingestion time |

Composite uniqueness: []

## incident_status_history

| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |
|---|---|---|---|---|---|---|---|---|
| incident_id | VARCHAR(160) | True | [] | — | — | False | ['incidents.id'] | Incident id |
| from_status | VARCHAR(24) | False | [] | — | — | False | [] | From status |
| to_status | VARCHAR(24) | True | [] | — | — | False | [] | To status |
| user_id | VARCHAR(160) | True | [] | — | — | False | ['application_users.id'] | User id |
| occurred_at | DATETIME | True | [] | UTC | — | False | [] | Occurred at |
| note | TEXT | True | [] | — | — | False | [] | Note |
| id | VARCHAR(160) | True | [] | — | — | True | [] | Immutable canonical identifier |
| workspace_id | VARCHAR(80) | True | [] | — | — | False | [] | Dataset run identifier or manual |
| created_at | DATETIME | True | [] | UTC | UTC now | False | [] | UTC record ingestion time |

Composite uniqueness: []

## interlock_state_events

| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |
|---|---|---|---|---|---|---|---|---|
| interlock_id | VARCHAR(160) | True | ["state IN ('ENGAGED','RELEASED','BYPASSED','FAILED')", "guard_state IN ('OPEN','CLOSED')"] | — | — | False | ['interlocks.id'] | Interlock id |
| machine_state_id | VARCHAR(160) | True | ["state IN ('ENGAGED','RELEASED','BYPASSED','FAILED')", "guard_state IN ('OPEN','CLOSED')"] | — | — | False | ['machine_state_events.id'] | Machine state id |
| state | VARCHAR(20) | True | ["state IN ('ENGAGED','RELEASED','BYPASSED','FAILED')", "guard_state IN ('OPEN','CLOSED')"] | — | — | False | [] | State |
| guard_state | VARCHAR(12) | True | ["state IN ('ENGAGED','RELEASED','BYPASSED','FAILED')", "guard_state IN ('OPEN','CLOSED')"] | — | — | False | [] | Guard state |
| occurred_at | DATETIME | True | ["state IN ('ENGAGED','RELEASED','BYPASSED','FAILED')", "guard_state IN ('OPEN','CLOSED')"] | UTC | — | False | [] | Occurred at |
| id | VARCHAR(160) | True | ["state IN ('ENGAGED','RELEASED','BYPASSED','FAILED')", "guard_state IN ('OPEN','CLOSED')"] | — | — | True | [] | Immutable canonical identifier |
| workspace_id | VARCHAR(80) | True | ["state IN ('ENGAGED','RELEASED','BYPASSED','FAILED')", "guard_state IN ('OPEN','CLOSED')"] | — | — | False | [] | Dataset run identifier or manual |
| created_at | DATETIME | True | ["state IN ('ENGAGED','RELEASED','BYPASSED','FAILED')", "guard_state IN ('OPEN','CLOSED')"] | UTC | UTC now | False | [] | UTC record ingestion time |

Composite uniqueness: []

## acknowledgements

| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |
|---|---|---|---|---|---|---|---|---|
| alarm_id | VARCHAR(160) | True | [] | — | — | True | ['alarm_events.id'] | Alarm id |
| user_id | VARCHAR(160) | True | [] | — | — | False | ['application_users.id'] | User id |
| acknowledged_at | DATETIME | True | [] | UTC | — | False | [] | Acknowledged at |
| note | TEXT | True | [] | — | — | False | [] | Note |
| id | VARCHAR(160) | True | [] | — | — | True | [] | Immutable canonical identifier |
| workspace_id | VARCHAR(80) | True | [] | — | — | False | [] | Dataset run identifier or manual |
| created_at | DATETIME | True | [] | UTC | UTC now | False | [] | UTC record ingestion time |

Composite uniqueness: []

## corrective_action_status_history

| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |
|---|---|---|---|---|---|---|---|---|
| action_id | VARCHAR(160) | True | [] | — | — | False | ['corrective_actions.id'] | Action id |
| from_status | VARCHAR(24) | False | [] | — | — | False | [] | From status |
| to_status | VARCHAR(24) | True | [] | — | — | False | [] | To status |
| user_id | VARCHAR(160) | True | [] | — | — | False | ['application_users.id'] | User id |
| occurred_at | DATETIME | True | [] | UTC | — | False | [] | Occurred at |
| note | TEXT | True | [] | — | — | False | [] | Note |
| id | VARCHAR(160) | True | [] | — | — | True | [] | Immutable canonical identifier |
| workspace_id | VARCHAR(80) | True | [] | — | — | False | [] | Dataset run identifier or manual |
| created_at | DATETIME | True | [] | UTC | UTC now | False | [] | UTC record ingestion time |

Composite uniqueness: []

## incident_alarms

| Field | Type | Required | Allowed / validation | Units | Default | Unique | Reference | Description |
|---|---|---|---|---|---|---|---|---|
| incident_id | VARCHAR(160) | True | [] | — | — | False | ['incidents.id'] | Incident id |
| alarm_id | VARCHAR(160) | True | [] | — | — | False | ['alarm_events.id'] | Alarm id |
| id | VARCHAR(160) | True | [] | — | — | True | [] | Immutable canonical identifier |
| workspace_id | VARCHAR(80) | True | [] | — | — | False | [] | Dataset run identifier or manual |
| created_at | DATETIME | True | [] | UTC | UTC now | False | [] | UTC record ingestion time |

Composite uniqueness: [['incident_id', 'alarm_id']]
