# Phase 25 — Pull request CI coverage

The main CI workflow now runs for pull requests targeting both `main` and `phase-3-risk-engine`. This ensures backend API changes are tested before they merge into the Render-tracked backend branch rather than relying only on a post-merge push workflow.

The workflow runs frontend lint/tests/build and backend pytest. The separate live API smoke workflow remains a deployment-level check and should be run after the corresponding Render backend deploy is Live.
