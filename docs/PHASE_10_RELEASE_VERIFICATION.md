# Phase 10 — Release verification

Run the live synthetic API checks with:

```bash
npm run smoke:api
```

Optionally set `VITALGUARD_API_URL` to test a staging backend.

The script verifies:
- Health and model metadata/disclaimers
- CORS preflight for the deployed frontend
- Synthetic holdout evaluation endpoint
- Prediction response validation and persistence
- Model contribution explanation endpoint
- Observation history and data-quality endpoints
- Elevated synthetic prediction -> persistent alert -> acknowledge -> resolve -> audit trail

The test writes synthetic records to the configured demo database. It never uses real patient information. Run it only against a demo/staging deployment whose database is intended for test records.

This smoke test does not establish clinical validity or safety.
