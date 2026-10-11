# Phase 20 — Pilot-readiness and clinical-validation gates

## Current status

VitalGuard AI is a software demonstration using generated synthetic data. Its risk classifier and NEWS2-style demonstration are **not clinically validated**, are not medical devices by virtue of this repository, and must not be used to diagnose, triage, monitor, or treat real people. Do not enter real patient data into this demo.

This phase documents prerequisites; it does not conduct clinical research, establish safety or efficacy, or authorize a pilot.

## Gates before any real-world clinical evaluation

### 1. Intended use and governance
- Define the intended population, setting, user, workflow, and exact decision the system may support.
- Name a clinical owner, safety owner, data-protection owner, and accountable deployment owner.
- Complete institutional ethics/IRB review and applicable regulatory/legal review before collecting or using health data.
- Establish consent/waiver, retention, access, incident reporting, and data deletion procedures.

### 2. Dataset and labels
- Use appropriately authorized, representative data with documented provenance, licensing, consent/legal basis, and permitted uses.
- Predefine outcomes, observation windows, exclusion criteria, missingness handling, and adjudication procedures.
- Split by person/site/time as appropriate to avoid leakage; keep the final test set locked until the evaluation plan is approved.
- Document subgroup coverage and limitations; synthetic test performance is not evidence of real-world performance.

### 3. Evaluation protocol
- Pre-register the intended-use evaluation protocol and analysis plan before examining the locked test set.
- Compare against an appropriate baseline and current workflow.
- Report discrimination, calibration, sensitivity/specificity at prespecified thresholds, PPV/NPV at the target prevalence, confidence intervals, missing-data behavior, and subgroup performance.
- Assess alert burden, false alarms, missed events, workflow impact, and human-factors usability.
- Set acceptance thresholds with clinical and statistical owners before evaluation; do not choose thresholds after seeing results.

### 4. Safety and human oversight
- Keep the system in silent/shadow mode initially, with no automated clinical action.
- Require qualified human review and a documented override/escalation process.
- Define stop criteria for safety signals, data drift, reliability failures, subgroup harms, or unexpected alert burden.
- Validate downtime behavior, stale data handling, monitoring, rollback, and incident response.

### 5. Security and operations
- Complete independent security/privacy review, threat modeling, least-privilege access, managed identity/MFA, audit review, encrypted backups, restore tests, and retention controls.
- Use a managed database plan with tested backup and recovery; do not rely on an expiring free database for important records.
- Verify the deployed commit, migrations, health/readiness, authenticated end-to-end smoke tests, persistence after restart, and rollback procedure.
- Establish versioned model/data releases, monitoring ownership, change control, and a post-deployment review process.

## Release decision

The project remains **demo-only / not clinically validated** until every applicable gate is approved by the responsible clinical, statistical, privacy, security, regulatory, and operational owners. A passing software CI run does not satisfy these gates.

## What this repository can currently claim

- The API and frontend have automated CI checks.
- Automated tests exercise generated synthetic records, validation, authentication, and selected persistence/restart behavior.
- Synthetic evaluation and diagnostics are development tools only.

It cannot currently claim prospective clinical validation, clinical effectiveness, regulatory clearance, production-grade reliability, or suitability for patient care.
