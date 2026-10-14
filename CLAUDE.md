# VitalGuard AI — Claude Code instructions

Before making any changes in this repository, read:
1. [Phase 0 baseline audit](docs/PHASE_0_BASELINE_AUDIT.md)
2. [Render release runbook](docs/RENDER_RELEASE_RUNBOOK.md)
3. [Delivery roadmap](docs/REALTIME_DEMO_ROADMAP.md)

## Required next task

The next implementation task after Phase 0 is **Phase 1 — Database persistence and migrations**, as defined in `docs/PHASE_0_BASELINE_AUDIT.md`. Implement Phase 1 only. Do not begin Phase 2 or unrelated UI, alert, push, or ML work until Phase 1 acceptance criteria are verified or explicitly blocked.

## Safety and repository rules

- VitalGuard AI is a synthetic-data demonstration, not clinically validated and not for clinical use. Never use real patient data.
- Preserve the existing `main` branch and deployed backend branch.
- Render frontend service tracks `main`; backend service tracks `phase-3-risk-engine`. Both auto-deploy on commits.
- The Phase 0 audit found that `main` and `phase-3-risk-engine` have no common ancestor according to GitHub's compare API. Do not merge, rebase, reset, force-push or synchronize these branches blindly.
- For backend work, create a feature branch based on `phase-3-risk-engine`; do not commit directly to that live auto-deploy branch. Open a reviewed pull request targeting it.
- Inspect current branch, working tree, deployed commit SHAs and open PRs at the start of every phase. This audit may become stale.
- Use a disposable test database for migration tests. Never reset or overwrite production data.
- Keep the hosted PostgreSQL network private. Never commit database URLs, VAPID keys, tokens or other secrets.
- Do not enable `VITALGUARD_REQUIRE_POSTGRES=true` until the intended `DATABASE_URL` and successful connection are verified.
- Do not claim a test passed unless it was actually run. Do not claim deployment, restart durability, backup/restore or push delivery without evidence.
- Reuse existing services and architecture; avoid parallel state stores and broad refactors.
- Report concrete files changed, commands run, test results, blockers and whether a deployment was actually verified.
