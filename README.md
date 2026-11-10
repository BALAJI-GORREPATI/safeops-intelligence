# SafeOps Intelligence

A locally runnable industrial safety application connecting machine states, protective systems, alarms, operator responses, incidents and verified corrective actions.

**Stack:** Next.js App Router, TypeScript, Tailwind CSS, Lucide and Recharts; Python FastAPI/Pydantic; SQLAlchemy/Alembic; PostgreSQL; seeded NumPy generation. Six primary views: Overview, Machines, Alarms, Incidents, Corrective actions, Data & validation. No Docker or cloud account required.

## Repository and Project Structure

```
safeops-intelligence/
├── backend/                             # FastAPI application & safety analytics engine
│   ├── safeops/                         # Core Python package
│   │   ├── api.py                       # FastAPI application, route handlers & endpoints
│   │   ├── artifacts.py                 # Export bundle packager (ZIP, CSV, JSON, SQL)
│   │   ├── auth.py                      # Session cookies, role-based RBAC & demo auth
│   │   ├── cli.py                       # SafeOps CLI (seed, generate, validate, evaluate)
│   │   ├── db.py                        # Database session management & engine setup
│   │   ├── generator.py                 # Synthetic dataset generator & deterministic seeding
│   │   ├── models.py                    # SQLAlchemy ORM models & immutable constraints
│   │   ├── rules.py                     # Industrial safety business rules & anomaly engine
│   │   ├── schemas.py                   # Pydantic request/response validation schemas
│   │   ├── services.py                  # Domain service layer & query orchestration
│   │   └── validation.py                # Ground truth evaluation & data integrity auditing
│   ├── tests/                           # Backend test suite (pytest)
│   │   ├── test_api.py                  # API endpoints, authentication & RBAC tests
│   │   ├── test_generator.py            # Dataset generation, rules & anomalies test
│   │   └── test_sql_export.py           # SQL round-trip & integrity tests
│   ├── requirements.txt                 # Backend Python package dependencies
│   └── requirements.lock.txt            # Locked Python dependencies
├── database/                            # Database migrations (Alembic)
│   ├── env.py                           # Alembic environment runner
│   └── versions/                        # Migration scripts
│       └── 0001_schema.py               # Initial PostgreSQL schema definition & indexes
├── frontend/                            # Next.js App Router frontend application
│   ├── app/                             # Next.js pages, layouts & routing
│   │   ├── layout.tsx                   # Root HTML layout & fonts
│   │   ├── page.tsx                     # Main dashboard page
│   │   ├── [section]/page.tsx           # Dynamic section router (machines, alarms, etc.)
│   │   ├── data-page.tsx                # Admin-only Data & Validation interface
│   │   ├── ui.tsx                       # Reusable UI components, modals, filters & tables
│   │   ├── workspace.tsx                # Workspace context, role selector & state
│   │   ├── resources.tsx                # API fetch helpers & state hooks
│   │   ├── browser-reload-boundary.tsx  # F5 browser reload handler
│   │   └── globals.css                  # Tailwind styles & theme variables
│   ├── tests/                           # End-to-end browser tests (Playwright)
│   │   ├── browser-navigation.spec.ts   # Navigation & reload tests
│   │   └── workflows.spec.ts            # Role workflows, acknowledgments & actions
│   ├── next.config.ts                   # Next.js config with dynamic backend proxy
│   ├── package.json                     # Frontend npm scripts & dependencies
│   ├── playwright.config.ts             # Playwright test configuration
│   ├── postcss.config.mjs               # PostCSS configuration
│   ├── tsconfig.json                    # TypeScript compiler options
│   └── AGENTS.md                        # Frontend design & safety workflow rules
├── docs/                                # Technical specifications & architecture guides
│   ├── api.md                           # REST API specifications & endpoint reference
│   ├── architecture.md                  # System architecture & Entity-Relationship diagram
│   ├── browser-reload-behavior.md       # Session preservation & navigation spec
│   ├── business-rules.md                # Safety rules, metric definitions & formulas
│   ├── data-dictionary.md               # Human-readable database schema dictionary
│   ├── data-dictionary.json             # Machine-readable schema dictionary
│   ├── database-verification.json       # Database integrity audit evidence
│   ├── generation-and-evaluation.md     # Synthetic generator & ground-truth evaluation
│   ├── refresh-and-origin-cleanup.md    # UI cleanup guidelines
│   ├── reproducibility-results.json     # Reproducibility checksum audit evidence
│   ├── ui-cleanup.md                    # Access control & role visibility guide
│   └── verification.md                  # Comprehensive verification report
├── exports/                             # Seeded dataset exports & evaluation reports
│   ├── starter/                         # Starter dataset (seed 20261022, 5 edge cases)
│   │   ├── csv/                         # Normalized CSV tables
│   │   ├── json/                        # JSON structured tables
│   │   ├── sql/                         # Schema & seed SQL scripts
│   │   └── evaluation/                  # Detection results & ground truth records
│   └── full/                            # Full 50k-event dataset exports
├── scripts/                             # Development, operations & verification scripts
│   ├── Start-SafeOps.ps1                # One-click startup script for local environment
│   ├── Stop-SafeOps.ps1                 # Clean shutdown script
│   ├── bootstrap_db.py                  # Local PostgreSQL cluster bootstrapper
│   ├── verify_artifacts.py              # Export bundle reproducibility checker
│   └── verify_database.py               # Comprehensive database integrity verifier
├── alembic.ini                          # Alembic database migration config
├── netlify.toml                         # Netlify frontend deployment configuration
├── render.yaml                          # Render backend deployment configuration
├── PROGRESS.md                          # Project progress & verification history
└── README.md                            # Main project overview & instructions
```

## Run the installed application in this workspace

Dependencies, workspace-local PostgreSQL, migrations, starter and full datasets have been installed/generated here. From PowerShell in the project root:

```powershell
.\scripts\Start-SafeOps.ps1
```

Open **http://127.0.0.1:3000**. Choose **OT / IT administrator** and use the local demonstration password **`SafeOps-local-demo`**, unless changed in your ignored `.env`. Choose the desired dataset in the top selector. Other roles expose their permitted workflows.

Stop the application with ` .\scripts\Stop-SafeOps.ps1`. This preserves PostgreSQL and all data. To stop the workspace database explicitly:

```powershell
.\.runtime\pgsql\bin\pg_ctl.exe stop -D .runtime\pgdata -m fast
```

The local database listens only on `127.0.0.1:55432`, uses SCRAM password authentication, and stores data under `.runtime/pgdata`. No Windows service, system PATH or registry settings were changed. Startup logs live under `.runtime`. Never delete `.runtime/pgdata` to resolve an application error: it contains persisted safety records.

Only administrators see or can open **Data & Validation**. Direct non-admin visits to `/data` redirect to Overview; administrator APIs and downloads return 403 for other roles. The page provides four sections for generation, integrity, readable detection evidence, and exports/reproducibility. CSV, JSON and SQL exports are multi-table ZIP archives; validation and ground truth are downloadable reports. [Cleanup and access-control details](docs/ui-cleanup.md).

There are no manual Refresh buttons. Browser Reload (F5 / Ctrl+R) preserves the session and opens Overview with the existing defaults: Manual operations, All plants and All recorded activity. Searches, filters, details and pagination reset; saved records remain in PostgreSQL. Sidebar navigation and valid direct links work normally. Automatic updates after saves remain active. Normal operational pages omit data-origin badges; the administrator interface and exports retain accurate simulation provenance. [Browser reload behavior and verification](docs/browser-reload-behavior.md).

## Fresh Windows setup

Prerequisites: Node.js 22+, Python 3.13+, Git, and PostgreSQL 16+ (17 tested). VS Code is optional. Run from PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm.cmd --prefix frontend ci
Copy-Item .env.example .env
```

If `.env` already exists, keep it; do not overwrite its credentials. For a standard PostgreSQL installation, create a dedicated development role/database using psql as your local database administrator:

```sql
CREATE ROLE safeops LOGIN PASSWORD 'choose-a-local-password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE DATABASE safeops OWNER safeops;
```

Edit ignored `.env`:

```dotenv
DATABASE_URL=postgresql+psycopg://safeops:URL_ENCODED_PASSWORD@127.0.0.1:5432/safeops
SESSION_SECRET=replace-with-a-random-secret-of-at-least-32-characters
DEMO_PASSWORD=choose-your-local-demo-password
CORS_ORIGIN=http://localhost:3000
```

Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Use a URL-encoded database password. Supabase-compatible PostgreSQL URLs are supported through `DATABASE_URL`; use the provider's connection details, `postgresql+psycopg://` dialect and `?sslmode=require` for remote TLS. No Supabase account is needed or accessed by this project.

Optional portable alternative: download the ZIP from the [official EDB binaries page](https://www.enterprisedb.com/download-postgresql-binaries), place it at `.runtime/postgres-portable.zip`, then run ` .\.venv\Scripts\python.exe scripts\bootstrap_db.py`. This initializes a new loopback-only PostgreSQL 17 cluster, creates the database, and writes a new `.env` **only if none exists**. It refuses to reset existing role credentials. It does not install a Windows service. The bootstrap administrator password remains in ignored `.runtime/bootstrap-password`; protect this directory like a development database backup.

Migrate and load datasets:

```powershell
$env:PYTHONPATH = 'backend'
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m safeops.cli seed --preset starter
.\.venv\Scripts\python.exe -m safeops.cli seed --preset full
```

Identical configurations reuse their dataset namespace; seed never deletes/replaces existing records. Generation versions/configurations create isolated namespaces. Background UI generation is available to administrators and reports progress, completion or errors.

## Start servers individually

Backend, root PowerShell terminal:

```powershell
$env:PYTHONPATH = 'backend'
.\.venv\Scripts\python.exe -m uvicorn safeops.api:app --host 127.0.0.1 --port 8000
```

Frontend, second terminal:

```powershell
Set-Location frontend
npm.cmd run dev
```

API documentation: http://127.0.0.1:8000/docs. Database health: http://127.0.0.1:8000/api/health. For a production frontend build: `npm.cmd --prefix frontend run build`, then ` .\scripts\Start-SafeOps.ps1 -Production` after stopping existing application processes. The backend remains the explicitly local demonstration deployment.

## Generate, validate, evaluate and export

All commands below run in the root with `$env:PYTHONPATH = 'backend'`:

```powershell
.\.venv\Scripts\python.exe -m safeops.cli generate --preset starter --output exports/starter
.\.venv\Scripts\python.exe -m safeops.cli generate --preset full --output exports/full
.\.venv\Scripts\python.exe -m safeops.cli validate --preset full
.\.venv\Scripts\python.exe -m safeops.cli evaluate --preset full
.\.venv\Scripts\python.exe -m safeops.cli reproduce --preset full --output exports/full
.\.venv\Scripts\python.exe -m safeops.cli dictionary
.\.venv\Scripts\python.exe scripts/verify_artifacts.py
```

Default seed is `20261022`; override with `--seed`. Generator CLI outputs deterministic CSV, JSON and PostgreSQL SQL, isolated ground truth, dictionary, manifest, checksums, validation and reproduction report. `generate` compares two independently generated datasets. `verify_artifacts.py` additionally exports both runs and compares every file for starter and full. Generated CLI artifacts are separate from live edits in PostgreSQL. The Data & validation view can validate current stored simulation records, test fresh generation reproduction, and download a ZIP export.

## Verification

Backend tests use transactions that roll back; they require the designated database to be migrated and the ignored `.env` configured:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
Set-Location frontend
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

Start both servers before browser tests. `DEMO_PASSWORD` can be passed as a test environment variable if you changed the default. Browser tests create identifiable operational evidence and actions rather than deleting safety history. The SQL export round-trip test creates an isolated schema inside a rolled-back transaction. `scripts/verify_database.py` checks persisted starter/full validation, independent SQL totals, response sizes and timings while the backend is running.

Results, counts and checksums: [verification report](docs/verification.md), [database evidence](docs/database-verification.json), [file reproducibility](docs/reproducibility-results.json).

## Demonstration walkthrough

1. Sign in as administrator and choose the latest starter dataset. Overview shows live database-derived counts, trends, priority incidents and explainable findings. Physical alarms and source replays are reported separately.
2. Open **Alarms**, filter critical/unacknowledged, inspect the guard/state/shift context, enter an operator note and acknowledge. Browser Reload returns to Overview; select the dataset and return to the alarm to confirm its response and acting user persist.
3. Open an **Incident**. Follow the triggering alarm to its definition, machine, zone, interlock, shift and acknowledgement. Switch to its chronological timeline. Imported incidents without evidence are visibly flagged.
4. Create a **Corrective action**, assign the engineer and a future due date. Move it through IN_PROGRESS and COMPLETED. Administrator can independently verify an engineer-assigned action using recorded evidence, then close it. Attempting to skip verification is rejected.
5. In **Machines**, add a plant/machine, inspect state history, configure a zone/interlock/definition and record a safe state change. Configuration revisions retain effective dates and old references.
6. Open **Data & validation**, select/generate full, inspect exception counts and per-category precision/recall/F1, run reproduction, filter rule evidence and download the export bundle.

## Architecture and documentation

`frontend/app` contains the six routed views and reusable interaction components; `backend/safeops` holds schema, typed requests, authentication, API, generation, rules, validation and artifact export; `database` holds Alembic migration; `backend/tests` and `frontend/tests` cover data and workflows; `scripts` contains local lifecycle/verification tools; `exports` contains generated delivery artifacts.

- [Architecture and ER diagram](docs/architecture.md)
- [Data dictionary](docs/data-dictionary.md) / [machine-readable dictionary](docs/data-dictionary.json)
- [Business rules and metric formulas](docs/business-rules.md)
- [Generation, anomalies, evaluation and validation](docs/generation-and-evaluation.md)
- [API overview](docs/api.md)
- [Progress and handoff](PROGRESS.md)

## Limits and deployment considerations

This is a local, production-minded demonstration, not a certified safety controller. Authentication uses shared local demo credentials and role selection; it has no enterprise identity, TLS termination, rate limiting or account recovery. Keep the servers on loopback. No real PLC connection, external safety data or industrial personal data is used. Detection results on synthetic fixtures do not establish real-world accuracy.

Generation uses a single-process background executor. Interrupted jobs are marked failed at restart and can be retried. Rule-based flood/nuisance/recurrence summaries are from the latest saved analysis (timestamp shown); operational KPI/lifecycle values query current database records. Reopening/cancelling closed records is intentionally unsupported. The machine panel shows the latest 100 states, ten alarms and 25 incidents; list views paginate. Configuration selectors list at most 100 machines, while API configuration/operational lists support the full specified dataset. Graphs group UTC days; displayed timestamps use the browser timezone. Previously generated development versions remain isolated rather than being deleted. PostgreSQL owner privileges can alter immutability triggers, so regulatory tamper resistance requires additional deployment controls.
