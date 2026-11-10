# Architecture and relationships

SafeOps is a local monorepo. The Next.js App Router renders six operational views. Same-origin `/api` requests are proxied to FastAPI. Pydantic validates requests; SQLAlchemy transactions write PostgreSQL. Alembic creates the schema and immutable-history triggers. The shared generator has no database or wall-clock dependency. No Docker, external AI service, queue server or cloud account is required.

```mermaid
flowchart LR
    Browser[Six Next.js views] --> Proxy[Same-origin API proxy]
    Proxy --> API[FastAPI and role checks]
    API --> PG[(PostgreSQL)]
    API --> Worker[One background generation worker]
    Worker --> Generator[Seeded NumPy generator]
    Generator --> Rules[Operational rule engine]
    Rules --> Evaluation[Validation and label evaluation]
    Evaluation --> PG
    Generator --> Export[CSV / JSON / PostgreSQL SQL]
```

```mermaid
erDiagram
    PLANT ||--o{ MACHINE : contains
    PLANT ||--o{ SAFETY_ZONE : defines
    MACHINE ||--o{ MACHINE_SAFETY_ZONE : assigned
    SAFETY_ZONE ||--o{ MACHINE_SAFETY_ZONE : protects
    MACHINE ||--o{ INTERLOCK : requires
    SAFETY_ZONE ||--o{ INTERLOCK : constrains
    MACHINE ||--o{ ALARM_DEFINITION : configures
    MACHINE ||--o{ MACHINE_STATE_EVENT : records
    INTERLOCK ||--o{ INTERLOCK_STATE_EVENT : records
    MACHINE_STATE_EVENT ||--o{ INTERLOCK_STATE_EVENT : contextualizes
    ALARM_DEFINITION ||--o{ ALARM_EVENT : explains
    MACHINE_STATE_EVENT ||--o{ ALARM_EVENT : contextualizes
    PLANT ||--o{ OPERATOR_SHIFT : schedules
    APPLICATION_USER ||--o{ OPERATOR_SHIFT : works
    OPERATOR_SHIFT ||--o{ ALARM_EVENT : covers
    ALARM_EVENT ||--o| ACKNOWLEDGEMENT : receives
    APPLICATION_USER ||--o{ ACKNOWLEDGEMENT : records
    MACHINE ||--o{ INCIDENT : affects
    INCIDENT ||--o{ INCIDENT_ALARM : links
    ALARM_EVENT ||--o{ INCIDENT_ALARM : triggers
    INCIDENT ||--o{ CORRECTIVE_ACTION : requires
    APPLICATION_USER ||--o{ CORRECTIVE_ACTION : owns
    INCIDENT ||--o{ INCIDENT_STATUS_HISTORY : appends
    CORRECTIVE_ACTION ||--o{ CORRECTIVE_ACTION_STATUS_HISTORY : appends
    DATASET_GENERATION_RUN ||--o{ VALIDATION_RESULT : evaluates
```

An alarm has zero or one acknowledgement (a database unique constraint prevents competing responses). Machines and zones, and incidents and alarms, are many-to-many through explicit bridges. Other relationships are one-to-many. There are no required one-to-one relationships.

Every operational entity carries a `workspace_id`: `manual` or a deterministic simulation ID. Dataset generation creates a new namespace, or reuses an identical completed configuration. There is no destructive replacement endpoint. The UI includes manual records in operational lists; validation resolves references such as manual acting users without importing unrelated datasets. This prevents regeneration from overwriting manual records. Failed background generations roll back all data and retain a failed run with the error. The administrator may retry the same failed configuration. Restarting the API marks interrupted jobs failed rather than falsely reporting completion.

Configuration revisions close the old `[effective_from, effective_to)` interval and create a new immutable reference. Historical alarm definitions, state events and interlock evidence continue pointing to the original version. Restriction text describes the supported rule: mandatory guards must be closed and interlocks engaged during operation. It is not an arbitrary executable policy language.

Event occurrence, ingestion, acknowledgement, completion and verification are distinct timestamp fields. All use PostgreSQL timestamp with time zone. Timeline ordering uses occurrence time followed by canonical ID. Database triggers reject updates/deletes on alarms, acknowledgements, state events, lifecycle histories and audits. Current incident/action status is mutable only with an accompanying history event. A database owner can alter triggers; this is auditable application history, not tamper-proof regulatory storage.

Pagination, SQL window-based source deduplication and server-side SQL aggregates keep 50,000-event datasets out of browser memory. Source and filtering columns are indexed. Database writes are bulked in batches of 2,000. The single-process background executor is appropriate for this local demonstration; durable multi-worker scheduling is an explicit future deployment concern.
