# Phase 31 — Dependency audit visibility

The Dependency audit report workflow prints npm audit severity counts and advisory metadata (package, severity, affected range, and whether npm reports a fix) without making the existing test/build CI silently fail due to known advisories.

This is a reporting step, not remediation. Review each fix, upgrade in controlled batches, and run the full test/build and live smoke suites. Avoid `npm audit fix --force` unless the breaking changes have been deliberately migrated and reviewed.
