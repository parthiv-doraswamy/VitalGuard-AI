# Phase 7 — Dataset Governance and Access

## Status and scope

This phase establishes the governance rules that must be satisfied before any non-synthetic dataset is acquired, copied, transformed, or used for model development. It is a policy and engineering-readiness deliverable; it does not claim that external clinical datasets have been obtained, approved, or loaded.

VitalGuard AI currently uses generated synthetic observations for its demonstration classifier. The model is not clinically validated and must not be used for diagnosis, triage, treatment, or real patient monitoring.

## Data-source approval gate

Before enabling a dataset or source, the project owner must document and approve all of the following:

1. **Purpose and necessity** — intended research question, intended population, required fields, and why each field is needed.
2. **Authority and access** — dataset owner, official access process, named accountable person, approval status, applicable data-use agreement (DUA), and any institutional/ethics approval required by the provider or institution.
3. **Permitted use** — license and terms covering research, model training, derived features, redistribution, publication, commercial use, and deployment. Do not infer permission from public discoverability.
4. **Privacy and identifiability** — classification of direct identifiers, quasi-identifiers, free text, dates, linkage keys, and re-identification risk. Public repositories must not contain row-level patient data, secrets, access tokens, or private credentials.
5. **Security and location** — approved storage location, least-privilege access, encryption in transit and at rest, access logging, backup handling, and transfer restrictions.
6. **Quality and semantics** — data dictionary, units, coding systems, measurement methods, missingness, duplicates, timestamp/time-zone conventions, cohort definitions, and known collection bias.
7. **Retention and exit** — retention period, deletion/return obligations, handling of backups and derived artifacts, and an owner responsible for executing the plan.
8. **Approval record** — reviewer, date, evidence links stored in an access-controlled location, review date, and explicit decision: approved, rejected, or pending.

**Default rule: pending means prohibited.** No ingestion or model training may start until the required approvals are recorded.

## Source-specific notes

- **MIMIC-IV**: access is governed by the dataset provider's credentialing, training, and data-use requirements. Follow the official PhysioNet process and the specific dataset terms. Do not download or redistribute restricted data without authorization.
- **eICU Collaborative Research Database**: follow the provider's access, training, credentialing, and data-use requirements for the exact resource.
- **Hospital, EHR, device, HL7, or FHIR feeds**: require explicit organizational authorization, a defined controller/processor relationship where applicable, approved interfaces, source-system mapping, security review, and a documented clinical governance pathway.
- **Other open datasets**: review the exact license, version, provenance, intended population, collection process, and redistribution restrictions rather than treating “open” as unrestricted.

These are governance reminders, not confirmation that any source has been approved or integrated. Verify current provider requirements at the point of access.

## Dataset registry template

Maintain one registry entry per dataset or source. Store sensitive approval evidence in a restricted system and link to it using a non-secret reference.

| Field | Required content |
| --- | --- |
| Dataset/source name and version | Exact provider name, release/version, and official URL |
| Data owner and accountable project owner | Organization/provider and responsible contact/role |
| Intended purpose | Approved question, cohort, and permitted use |
| Access status | Pending / approved / rejected / expired |
| Access evidence | Restricted reference to approval, DUA, license, and required training |
| Ethics/privacy review | Status, reviewer, date, and reference where applicable |
| Data classification | Synthetic / de-identified / identifiable / unknown; justify classification |
| Data elements and units | Fields, units, coding, timestamp semantics, and transformations |
| Population and limitations | Inclusion/exclusion criteria, provenance, bias, missingness, known caveats |
| Storage and access controls | Approved environment, roles, encryption, audit, and transfer restrictions |
| Retention/deletion | Deadline, deletion method, backup treatment, and responsible owner |
| Model usage | Training/validation/test/none; permitted derived artifacts |
| Review date and decision | Reviewer, decision, date, and next review date |

Do not place patient-level examples or credentials in the registry stored in this repository.

## Separation of data roles

- Keep training, validation, and test cohorts distinct at the patient level where applicable to avoid leakage.
- Record dataset version, cohort-building code version, preprocessing configuration, feature definitions, and random seeds where relevant.
- Fit preprocessing and feature selection only on the training partition; apply frozen transformations to validation/test data.
- Preserve source provenance and transformation lineage for derived datasets.
- Do not combine datasets or link records across sources unless the approvals and agreements explicitly permit it.
- Evaluate subgroup coverage, missingness, temporal drift, and site/source differences before interpreting performance.
- Treat de-identification as risk reduction, not proof that re-identification is impossible.

## Dataset intake checklist

- [ ] Source owner, version, official access path, and purpose recorded.
- [ ] License/DUA and required credentialing/training reviewed and approved.
- [ ] Ethics and privacy requirements assessed and satisfied where applicable.
- [ ] Data classification and permitted storage location documented.
- [ ] Data dictionary, units, timestamp semantics, and quality profile reviewed.
- [ ] Access controls, audit trail, retention, and deletion plan assigned.
- [ ] Patient-level split and leakage controls defined before modeling.
- [ ] Provenance and transformation lineage are reproducible.
- [ ] Dataset-specific limitations and population mismatch are documented.
- [ ] Responsible reviewer has recorded an explicit approval.

## Implementation boundary for this release

The current ingestion API intentionally accepts only synthetic-demo records with `DEMO-` patient IDs and `source_system: synthetic-demo`. Do not loosen these checks to accommodate real clinical sources as part of this documentation phase. A future source adapter must be separately designed, authorized, threat-modeled, tested, and reviewed. It must define identity resolution, unit/code mapping, timestamp handling, retries, idempotency, quarantine of invalid records, audit provenance, and failure/replay behavior.

## Exit criteria

Phase 7 documentation is complete when the governance policy, registry template, intake checklist, and source-specific access caveats are committed and reviewed. This does **not** imply clinical dataset access, data ingestion, model validation, or Phase 5 database verification. Phase 5's PostgreSQL migration and persistence checks remain a separate prerequisite for production-oriented data workflows.
