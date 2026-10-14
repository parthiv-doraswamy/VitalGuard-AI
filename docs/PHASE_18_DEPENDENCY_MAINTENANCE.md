# Phase 18 — Dependency maintenance

Dependabot is configured to open weekly grouped updates for the frontend npm dependencies and backend Python dependencies.

## Current known issue

Recent frontend CI installation logs reported 15 npm audit findings: 7 moderate, 6 high, and 2 critical. These have not yet been remediated. Do not run `npm audit fix --force` blindly because it may introduce breaking upgrades. Review the audit report, update affected direct/transitive dependencies in controlled batches, run the complete frontend test/build suite, and review the resulting lockfile before merging.

Dependency automation is not a substitute for reviewing advisories, testing updates, or a security assessment. The demo has no authentication and must not receive real patient information.
