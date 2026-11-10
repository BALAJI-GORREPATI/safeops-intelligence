# Browser reload reset and removal of manual Refresh controls

## Current behavior

No page or investigation panel has a manual Refresh button, icon, animation or refresh-success card. Ordinary initial data loading, generation-progress polling and automatic post-save revalidation remain active. Dataset validation and reproducibility controls still perform their original administrator operations.

An authenticated browser reload (F5, Ctrl+R or Reload) returns to the existing Overview route, `/`, with the application's original defaults:

- Dataset: **Manual operations** (the existing initial selection).
- Plant: **All plants**.
- Period: **All recorded activity**.
- Search, severity/status/machine filters and selected details: cleared.
- Pagination and sorting: first page and the API's existing default ordering.

The session cookie is preserved. Identity and role are read through the unchanged backend authentication endpoint. All page resources use uncached backend requests. Opening a valid direct detail URL or navigating with the sidebar continues to work normally, including after a reload.

## Implementation

`browser-reload-boundary.tsx` is a shared boundary around the existing Workspace component, after server page authorization has run. It reads the browser's `PerformanceNavigationTiming.type` once per document. A per-document window flag consumes that navigation decision so a document initially loaded through Reload does not redirect again during later client navigation. Browser-history and normal direct navigations are not classified as reloads.

On Reload, it removes only `localStorage['safeops-workspace']`, the application's one persisted temporary selection. It does not call `localStorage.clear`, `sessionStorage.clear`, or touch authentication cookies. Unrelated local/session storage remains unchanged. React state and the in-memory resource context start fresh in the new document. Deep routes use Next.js `router.replace('/')`; Overview's own temporary query/hash uses Next.js-integrated native history replacement before mounting the page. The boundary never bypasses the existing server-side `/data` guard or backend role checks.

The earlier refresh module was renamed to `resources.tsx` and reduced to automatic resource loading and invalidation. Manual-button state, success messages, public manual-refresh hook/button, callback argument and exclusive styling were removed. Failed automatic revalidation still reports an error instead of fabricating success.

## Files changed

- `frontend/app/browser-reload-boundary.tsx`: reload detection and temporary-state reset.
- `frontend/app/workspace.tsx`: shared boundary integration; page/detail controls and empty action containers removed; automatic invalidation retained.
- `frontend/app/resources.tsx`: automatic resource utility replacing `refresh.tsx`.
- `frontend/app/data-page.tsx`: updated utility import; validation uses a safety-check icon rather than a refresh icon.
- `frontend/app/globals.css`: removed exclusive manual-refresh styling.
- `frontend/tests/browser-navigation.spec.ts`: replaces obsolete manual-refresh tests with navigation/reset coverage.
- `frontend/tests/workflows.spec.ts`: persistence tests now expect Overview after Reload and explicitly return to the saved record.
- README, verification report and PROGRESS.md: current behavior and observed results.

## Verification

All **23 browser workflows passed** in development and against the production build (40.9 seconds). Tests check removal on six pages and four detail types, reload from every page, default filters, page-one reset, canonical URL cleanup, direct links, normal sidebar navigation, unchanged session cookies, unrelated browser storage, all four roles and rejection of restricted API requests. Requests observed during reload are reads only. Persistent alarm/action workflows and automatic machine-state updates are verified separately. All **22 backend tests**, TypeScript, ESLint without warnings, and the production build passed. Frontend and PostgreSQL health checks returned HTTP 200. No database migration or data reset is part of this implementation. The preview is left running for inspection.

This behavior requires client-side JavaScript and a browser supporting the standard Navigation Timing API, as do the application's existing interactive workflows. Backend unavailability is handled by the existing sign-in/data-loading error path. Existing local demonstration authentication remains unchanged.
