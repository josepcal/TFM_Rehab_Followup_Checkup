---
name: add-schema-and-rls
description: "Trigger: RLS, policy, access rule, new table, schema, migration, claims in DB session. Use for every FTM data-access change."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## Plan

Use this workflow skill to add or change tables with access rules. Pair with `sqlalchemy-alembic` for ORM and migration mechanics.

## When this applies

Use for new tables, schemas, RLS policies, grants, identity helpers, role access matrices and isolation tests.

## Steps

1. Choose the source-of-truth schema from `Architecture.md`: `clinical`, `recording`, `metrics`, `setup`, `audit`, or `reference` (ADR-0005).
2. Define SQLAlchemy model and Alembic migration together.
3. Add handwritten SQL for grants, RLS policies and helper functions; do not rely on autogenerate (ADR-0017).
4. Feed policies from Keycloak-derived identity: DB session must set `app.identity_id` (ADR-0014).
5. Ensure `clinical` and `recording` are never accessible by AI roles (ADR-0013).
6. Add PostgreSQL-backed tests for patient/doctor/technician/AI isolation.

## Minimal checklist query

```sql
-- TODO (verify): exact role names and helper functions in current migration.
SELECT clinical.current_patient_id();
SELECT clinical.current_doctor_id();
```

## Files and paths

- `bbdd_dev_setup/alembic/` — SQL-first migrations.
- `api/app/**/models.py` — ORM mappings.
- `api/tests/integration/` — real PostgreSQL isolation tests.

## Validation checklist

- [ ] Correct schema selected from SDD/ADR.
- [ ] RLS enabled for patient-data tables.
- [ ] Grants exclude AI from `clinical` and `recording`.
- [ ] Session identity is set before patient-data queries.
- [ ] Integration test proves forbidden role cannot read rows.

## Common mistakes

- Inventing a new schema when an existing SDD schema owns the data.
- Testing RLS with the owner role, which bypasses policies.
- Forgetting that per-doctor patient partitioning is accepted debt in MVP.
