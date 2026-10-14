# Phase 17 — NEWS2 UI regression tests

Frontend tests cover:
- Submitting the default Scale 1 example and rendering the returned component scores.
- Blocking Scale 2 submission until the user checks the explicit acknowledgement box.
- Confirming the authorization assertion is included in the submitted payload after acknowledgement.

The acknowledgement is not verified identity or proof of clinical authorization. The backend independently validates the authorization assertion. Synthetic demo only.
