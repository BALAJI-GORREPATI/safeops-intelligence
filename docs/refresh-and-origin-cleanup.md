# Refresh behavior and operational UI cleanup

Historical implementation report: the later user-requested [browser reload behavior](browser-reload-behavior.md) supersedes the manual controls described below. Those controls and their success cards have been removed; automatic post-save revalidation and the operational-label cleanup are preserved.

## Changes

Removed the operational source chip (`Synthetic activity + manual records`) and its operational-records alternative without adding a placeholder. Removed the decorative snapshot dot and changed the login phrase `Live evidence` to `Evidence history` so the application makes no real-equipment/live-feed claim. The operational dataset selector remains functional. The administrator's generation section explicitly describes a synthetic safety simulation; accurate provenance is retained in PostgreSQL, documentation, ground truth, validation reports and exports. Authentication disclosures remain accurate.

Refresh now uses a small shared coordinator and the existing native-fetch API helper, with no new dependencies. Every mounted page resource registers a reload function: workspace/job metadata, users, plants, dashboard aggregates, paginated record lists, alarm machine options, administrator reports and open investigation details. The page header and detail drawers use the same Refresh button.

- Every refresh sends uncached requests and waits for all relevant responses.
- Buttons show **Refreshing…**, expose busy state and reject repeat clicks while a refresh is running.
- Success appears only after requests complete successfully. Failures show an actionable error and retain previous records where available. Retry restores normal behavior.
- Request cancellation and sequence checks prevent superseded responses from replacing current filters or records.
- Refresh does not reload the browser, navigate, remount the page, reset filters/search/plant/date range, reset pagination, or switch investigation tabs.
- Successful writes use the same revalidation flow. If a write completes during a refresh, another read is queued after it so the completed write is included.
- Expired sessions return to sign-in. A permission failure rechecks the authenticated identity; a non-admin is removed from `/data`. Existing backend roles and route guards remain unchanged.

## Files modified

- `frontend/app/refresh.tsx`: shared coordinator, registered resource hook and loading-aware button.
- `frontend/app/ui.tsx`: uncached requests, abort support and structured HTTP/network errors.
- `frontend/app/workspace.tsx`: operational chip removal, shared resource revalidation across pages and details, feedback and session handling.
- `frontend/app/data-page.tsx`: administrator report revalidation without resetting its filters/pages, accurate simulation provenance.
- `frontend/app/globals.css`: compact dialog tools, refresh feedback and reduced-motion-aware loading indicator.
- `frontend/tests/refresh.spec.ts`: targeted browser regression coverage using actual backend responses.
- `PROGRESS.md`, `docs/verification.md`, README and this report: verification and handoff updates.

No database schema, safety rule, generated identifier, source label, existing event or history record was changed by the implementation. Browser verification creates identifiable `Refresh verification press ...` equipment and appends supervised state events to verify real persistence. These records are preserved rather than deleting safety history.

## Verification

The backend regression suite passed **22 tests**, including the full deterministic dataset, mandatory anomaly categories, integrity, exports, role checks and persistent workflows. All **25 browser workflows passed against the production build** (39.1 seconds). Coverage verifies fresh requests on every page and all four detail panels, a database-backed state change, retained search/plant and alarm page-two filters, loading/single-flight behavior, failure/recovery, request races, expired sessions and role changes. TypeScript, ESLint (without warnings), and the production build passed. PostgreSQL health returned HTTP 200. The updated preview is left running for inspection.

Known limitation: local demonstration authentication remains intentional. The existing upstream Starlette TestClient deprecation warning remains documented and unsuppressed.
