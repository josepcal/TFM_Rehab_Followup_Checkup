---
name: sqlalchemy-alembic
description: "Trigger: SQLAlchemy model, Alembic migration, ORM query, database session. Use for FTM ORM and migration conventions."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## Plan

Use this skill for ORM and migration mechanics. Use `add-schema-and-rls` for concrete RLS policies, grants and schema access rules.

## When this applies

Use for SQLAlchemy 2.0 models, typed queries, DB sessions, Alembic revisions, schema mapping and DB integration tests.

## Steps

1. Confirm the owning schema from `Architecture.md` and SDD §7.
2. Use SQLAlchemy 2.0 style declarative models and typed `select()` queries.
3. Keep one DB session per request/job boundary.
4. Use Alembic for schema changes; never use `create_all()` for production schema.
5. Handwrite DDL for views, roles, grants, RLS and functions because autogenerate will not cover them (ADR-0017).
6. Add or update PostgreSQL-backed tests when behavior depends on real schema/RLS.

## Minimal pattern

```python
stmt = select(Diagnostic).where(Diagnostic.doctor_id == doctor_id)
diagnostics = db.scalars(stmt).all()
```

## Files and paths

- `api/app/**/models.py` — SQLAlchemy mappings.
- `bbdd_dev_setup/alembic/` — SQL-first migrations and models.
- `.github/skills/add-schema-and-rls/SKILL.md` — RLS-specific workflow.

## Validation checklist

- [ ] Migration and model agree on schema, table and column names.
- [ ] RLS/grants/views/functions are handled manually when needed.
- [ ] App DB is separate from Keycloak DB.
- [ ] App code does not connect as DB owner.
- [ ] Integration tests run against real PostgreSQL for schema-sensitive changes.

## Common mistakes

- Relying on Alembic autogenerate for RLS policies.
- Mixing legacy simplified ORM columns with the SQL-first schema without adapters.
- Adding cross-schema shortcuts that bypass module services.
