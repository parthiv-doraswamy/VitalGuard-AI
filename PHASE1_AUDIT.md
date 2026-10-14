# VitalGuard AI — Phase 1 Stabilisation Report

Date: 2026-10-10

## Scope

Phase 1 covers repository hygiene, reproducible setup documentation, script correctness, and a baseline check. This report does not claim clinical validation, end-to-end API integration, or successful browser testing.

## Changes made

- Added `.gitignore` rules for dependencies, build output, TypeScript build metadata, local environment files, logs, editor files, and test artifacts.
- Added `.env.example` with the three non-secret Vite configuration values used by the current app.
- Removed the local `.env` file from the distributable working copy. It contained only the current demo flag, localhost API URL, and version label; use `.env.example` to recreate local configuration.
- Removed `node_modules`, `dist`, and TypeScript build metadata from the distributable working copy. These are generated/local files and should be recreated on install/build.
- Updated the README to document setup, verification commands, architecture, current limitations, and the synthetic-data / non-clinical-use boundary.
- Corrected the `lint` script: the previous `tsc --noEmit` ran against a root tsconfig containing only project references, so it could exit successfully without type-checking the referenced source projects. The script now explicitly type-checks both app and Vite config projects.
- Kept the existing source implementation and visual design unchanged in this phase.

## Verification attempts

| Command/check | Result |
| --- | --- |
| Initial `npm run lint` before script correction | Exit 0, but the root project-reference config meant this was not a reliable source type-check. |
| `npm test` against the ZIP's bundled dependencies | Failed at Vitest startup because the Rollup Linux x64 optional native package was missing. |
| `npm run build` against the ZIP's bundled dependencies | Failed for the same missing Rollup Linux x64 optional package. |
| Fresh `npm ci --no-audit --no-fund` | Did not complete in this environment; it timed out while attempting dependency installation. The incomplete `node_modules` was removed from the deliverable. |
| Explicit TypeScript check after correcting `lint` | Could not complete because the timed-out install left dependencies incomplete (including `vite/client`, `vitest/globals`, and React type definitions). |

**Conclusion:** the code and project configuration were inspected, but fresh tests and build are not yet verified. Run `npm ci`, `npm run lint`, `npm test`, and `npm run build` in a network-enabled local environment before treating the baseline as green.

## Existing issues intentionally deferred to later phases

- Risk score is scenario-driven independently of vital readings.
- NEWS2-like output is not a verified NEWS2 calculation.
- Explanatory risk factors are illustrative demo data.
- The API client is not the source of truth for the main simulation state, and API failure fallback is not clearly surfaced throughout the UI.
- Browser workflows and responsive layout have not yet been verified in a real browser.

These are recorded as follow-up work, rather than being silently represented as fixed in Phase 1.
