# API overview

Interactive OpenAPI: `http://127.0.0.1:8000/docs`. Health: `/api/health` checks PostgreSQL. Frontend proxies `/api` to loopback port 8000, so browser cookies stay same-origin.

| Resource | Endpoints |
|---|---|
| Demo session | POST `/api/auth/login`, POST `/logout`, GET `/me` under `/api/auth` |
| Users | GET `/api/users` |
| Plants | GET `/api/plants` |
| Machines | GET `/api/machines`, GET `/{id}`, POST `/{id}/state` |
| Alarms | GET `/api/alarms`, GET `/{id}`, POST `/{id}/acknowledge` |
| Incidents | GET/POST `/api/incidents`, GET `/{id}`, POST `/{id}/transition`, POST `/{id}/evidence` |
| Corrective actions | GET/POST `/api/actions`, GET `/{id}`, POST `/{id}/transition`, POST `/{id}/assign` |
| Configuration | GET/POST `/api/config/{plants,machines,zones,interlocks,definitions}`, POST `/{resource}/{id}/version` for effective configurations |
| Analytics | GET `/api/dashboard` |
| Operational workspaces | GET `/api/workspaces` (authenticated, completed selector entries only) |
| Dataset jobs | GET/POST `/api/datasets`, GET `/{id}/report`, POST `/{id}/validate`, POST `/{id}/reproduce`, GET `/{id}/export` |

List filters: `workspace`, `plant_id`, relevant `machine_id`, `severity`, `status`, `q`, `page>=1`, `1<=limit<=100`. Alarms support ISO timestamp `start` inclusive / `end` exclusive, plus `sort=newest|oldest`. Dashboard uses the same plant and date scope. Lists return `items,total,page,limit`. Status filters include ACTIVE incidents, OVERDUE actions, LATE/INVALID acknowledgements. Dataset and configuration master lists are bounded to the local supported scale.

POST requests use JSON. Request schemas forbid unknown properties. Validation errors return HTTP 422 and `error.message` plus field paths. Unauthorized requests return 401, prohibited roles 403, missing records 404, competing writes/invalid transitions 409. Transactions roll back when validation or a database constraint fails. Row locks serialize acknowledgement/lifecycle updates. Audit/history rows commit with the operational change. Referential errors return a structured 409 rather than leaking SQL details.

Example action transition:

```json
{"status":"VERIFIED","note":"Independent check completed","verification_evidence":"Guard cycle and supervised safe restart passed"}
```

The verifier must differ from the assigned engineer. Every GET that exposes operational data requires a valid local session. All `/api/datasets` routes, including job history, labelled reports, generation, validation, reproduction and exports, require administrator permission; authenticated non-admins receive HTTP 403. `/api/workspaces` exposes only completed IDs, preset, seed and alarm count so operators can select operational records without receiving administrator reports or labels. There is no destructive dataset-replacement API.

`GET /api/datasets/{id}/export?format=...` supports `bundle` (default), `csv`, `json`, `sql`, `validation`, and `ground-truth`. Multi-table CSV/JSON/SQL downloads are ZIP archives; the last two are downloadable JSON reports. Structured evidence and isolated ground truth remain available in technical exports. The administrator report response includes evaluation labels after detection has completed; labels never become detection inputs.

Next.js verifies the existing signed session through the backend before rendering `/data`. Unauthenticated or non-admin navigation redirects to `/`. The client also hides the sidebar item and clears the administrator view on logout. This route protection supplements, rather than replaces, backend permissions.
