# Phase 14 — NEWS2 scoring demonstration

## Endpoint

`POST /api/v1/scores/news2`

Accepts a fictional adult observation with respiratory rate, oxygen saturation, systolic blood pressure, pulse, temperature, consciousness, supplemental oxygen status, and SpO2 scale. Returns the per-parameter points and total.

## Source

Scoring bands are based on the Royal College of Physicians' NEWS2 chart and report:
- Official RCP resource: https://www.rcp.ac.uk/resources/national-early-warning-score-news-2/
- RCP NEWS2 report: https://www.rcp.ac.uk/media/a4ibkkbf/news2-final-report_0_0.pdf

The RCP identifies six physiological parameters and an additional 2 points for supplemental oxygen. SpO2 Scale 2 is reserved for patients with a prescribed 88–92% target range and must only be used under direction of a qualified clinician. The API therefore rejects Scale 2 unless the request explicitly asserts authorization.

## Important limitations

- This is a software implementation for synthetic demonstrations and is not approved or clinically validated.
- It does not generate escalation, diagnosis, or treatment advice and does not replace local clinical policy or a clinician's judgement.
- It does not establish that all deployment, documentation, rounding, or workflow requirements of a clinical NEWS2 implementation are satisfied.
- Test this against the official chart and a qualified clinical reviewer before any clinical context.
- Never send real patient data to this demo.
