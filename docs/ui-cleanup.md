# UI cleanup and administrator-only data access

The existing application architecture, database schema and generator are unchanged. The update focuses on presentation and access control.

## Changes

- Disabled the Next.js development indicator with `devIndicators: false` in `frontend/next.config.ts`.
- Removed database connection/environment badges from the shared header and the local-demo suffix from the signed-in profile. Backend health checks and environment configuration remain active. The login still accurately discloses demonstration authentication.
- Filtered Data & Validation out of non-admin navigation. Server-side `/data` authentication uses the existing HttpOnly session and the backend's current user record. Unauthorized visits redirect to Overview. Client-side logout clears the view and redirects too.
- Restricted every dataset administration endpoint, including job listings, to admin. Other users receive minimal operational selector entries from `/api/workspaces`. Ground truth and export downloads require admin on every request.
- Reorganized Data & Validation into Dataset Generation, Dataset Integrity, Detection Evaluation, and Exports & Reproducibility. Generation history, advanced parameters, detailed counts and validation details are collapsed by default.
- Kept a six-entity summary and distinct counts for labelled anomaly instances versus related validation findings.
- Replaced visible serialized evidence with named fields, local dates, expected conditions, readable explanations and working record links. Evidence remains structured in saved reports and exports. Findings and validation results paginate ten at a time without nested vertical scrolling.
- Added separate CSV, JSON, SQL, validation-report and ground-truth-report download controls; kept the full bundle and reproducibility check.

## Files

Application: `frontend/next.config.ts`, `frontend/app/[section]/page.tsx`, `frontend/app/workspace.tsx`, `frontend/app/data-page.tsx`, `frontend/app/ui.tsx`, `frontend/app/globals.css`, `backend/safeops/api.py`.

Regression tests: `backend/tests/test_api.py`, `frontend/tests/workflows.spec.ts`. Documentation: README, progress, API overview and this report.

## Preserved behavior

The full preset still generates four plants, 60 machines, 200 alarm definitions and 50,000 alarm events over 30 days. Stable identifiers, fixed seeds, all five injected anomaly categories, referential integrity, timestamp rules, immutable event histories, operational workflows, incident traceability, SQL/CSV/JSON exports and reproducibility are preserved. No existing records were deleted or migrated for this update.

## Verification

Backend regression suite: **22 tests passed**, including every non-admin role receiving 403 for all administration/download operations, administrator export contents in all six formats, and all five anomaly detections. Existing persistence/lifecycle/constraint/generator checks remain included.

Nine browser workflows passed in development and against the production build (20.9 seconds). Coverage checks all four roles, direct `/data` requests, refresh, logout and switching from administrator to engineer, hidden development/environment indicators, readable evidence without raw JSON, collapsed detailed counts, all download controls, responsive layouts and the existing acknowledgement/action workflows. TypeScript, ESLint and the production build passed. Both frontend and backend health checks returned HTTP 200. The updated local preview is left running for inspection, as requested.

Known limitation remains unchanged: shared local demonstration authentication is not an enterprise identity provider. One existing upstream Starlette TestClient deprecation warning remains; no warnings are suppressed.
