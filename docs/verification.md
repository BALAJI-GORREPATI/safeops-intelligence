# Executed verification

Verified locally on Windows on **10 November 2026**, with Node 22.23.4, Python 3.13, PostgreSQL 17.11 and the installed lockfile dependencies. These are observed results; there is no claim of regulatory certification or real-world detection accuracy.

| Check | Observed result |
|---|---|
| Backend generator/rules/PostgreSQL/API/export tests | 22 passed |
| Playwright Chromium end-to-end tests | 23 passed (current browser-reload behavior) |
| TypeScript | passed |
| ESLint | passed, no warnings |
| Next.js production build | passed |
| npm install audit | zero vulnerabilities |
| Starter/full FK and integrity validation | zero unexpected failures |
| Starter/full canonical reproduction | identical |
| Independent export/file reproduction | identical across 47 files for each preset |
| PostgreSQL SQL seed round trip | passed in isolated rolled-back schema |
| Full persisted analytics vs independent SQL | matched |

Backend scenarios cover deterministic starter/full counts, separate-label detection, corrupted FK/required/enums/keys, response deadlines, replay exclusion, exported byte identity, minimum custom scale, role rejection, acknowledgement persistence, duplicate response prevention, database immutability triggers, incident trace chains, action verification rules, constraints/invalid input, independent SQL aggregation, effective definition revisions, manual plant/machine/zone/interlock/definition creation and safe-state validation.

Browser scenarios cover real forms and API mutations, critical/unacknowledged filters, response persistence after refresh, incident evidence and chronological timeline, action creation and every lifecycle stage, independent verification, invalid closure rejection, dataset validation/reproduction, ZIP export download, prohibited planner mutation and actual background dataset generation with UI progress polling. All six pages were checked at widths 1,440, 768 and 390 pixels for horizontal overflow. Charts were checked for rendered SVG output. Screenshots and retained-failure traces are written under ignored `frontend/test-results`; HTML report under `frontend/playwright-report`.

## Fixed-seed dataset results (generator 1.1.0)

| Entity | Starter | Full |
|---|---:|---:|
| Plants | 2 | 4 |
| Machines | 8 | 60 |
| Alarm definitions | 24 | 200 |
| Alarm events / ingestions | 800 | 50,000 |
| Physical alarms (source deduplicated) | 799 | 49,950 |
| Zones / interlocks, each | 8 | 60 |
| Machine states / interlock states, each | 168 | 5,400 |
| Operator shifts | 42 | 360 |
| Acknowledgements | 684 | 42,814 |
| Incidents | 31 | 2,051 |
| Corrective actions | 30 | 2,001 |
| Ground-truth anomaly instances | 5 | 250 |
| Expected validation findings | 6 | 288 |
| Unexpected validation failures | 0 | 0 |

Validation findings may outnumber labels because imported unverified closure can also violate lifecycle ordering. Live browser acknowledgements increase current PostgreSQL acknowledgement totals; manual actions are additionally persisted. Table above describes the pristine deterministic exports, not a frozen live dashboard.

Full labelled evaluation: TP **250**, FP **0**, TN **102,016**, FN **0**; precision, recall and F1 **1.0** on the five explicitly injected categories. Starter: TP **5**, FP **0**, TN **1,708**, FN **0**. These are rule-row decisions on synthetic fixtures. Detector output is generated before labels are loaded. Flood, nuisance and recurrence findings are operational findings outside this five-category labelled evaluation.

Checksums:

```text
starter a4542e8bbb80f5cd1d1d562147cb9fd1a1d526a866c4ff6c0a65755dfd4967be
full    5cdf47e16959ee7fe11fff24de32800f13be2e8f36e0855342c31881f7a93cbd
```

Observed final full-dataset HTTP dashboard query: approximately **2.41 seconds**, **8,126 bytes**; paginated 25-alarm query approximately **0.18 seconds**, **15.5 KB**. Timing varies with local load and saved rule evidence. Database validation and fresh-generation checksums are independent. Exact measured evidence is saved in [database-verification.json](database-verification.json); independent per-preset file comparison and counts are in [reproducibility-results.json](reproducibility-results.json).

The documented PowerShell stop/build/start sequence was executed successfully. The final five Chromium workflows also passed against the production frontend (20.9 seconds observed). Final servers are stopped for handoff; the one-command launcher restarts workspace PostgreSQL and the application without altering saved records.

One upstream Starlette warning is emitted by backend tests: its current TestClient deprecates the installed httpx adapter. Tests execute successfully; the runtime uses normal ASGI/uvicorn and does not use that adapter. This warning has not been suppressed.

The subsequent Refresh and operational-label cleanup passed all 25 production browser workflows (39.1 seconds), 22 backend tests, lint, type checks and build. Refresh tests cover every page/detail API, an actual saved machine-state change, all alarm filters and page two, loading/duplicate-click protection, failed refresh/retry, stale-request cancellation and session/role changes. See [the implementation report](refresh-and-origin-cleanup.md). The current preview is left running at the user's request.

The newer user-requested [browser reload behavior](browser-reload-behavior.md) supersedes manual Refresh controls and their obsolete tests. All 23 current browser workflows passed against production (40.9 seconds), verifying no Refresh controls, reload-to-Overview defaults, preserved sessions/storage/data, direct links, normal sidebar navigation, server-side role restrictions and automatic post-save updates. The backend suite passed 22 tests; lint, type checking, production build and health checks passed. The updated preview is left running for inspection.
