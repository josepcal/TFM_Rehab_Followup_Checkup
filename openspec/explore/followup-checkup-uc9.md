# Explore: UC-09 Follow-up Check-up

**Date**: 2026-06-27 · **Scope**: UC-09 (Follow-up Check-up) · **Reference**: UC-08 Exercise Report

---

## Current State

### Database (canonical — already designed, NOT yet in the API runtime)

The follow-up data model already exists in the canonical DDL and the dev SQLAlchemy models, matching the SDD exactly:

- `doc/bbdd/ftm_schema.sql` and `bbdd_dev_setup/alembic/migrations/ftm_schema.sql` define:
  - `clinical.followup_checkup` (`followup_checkup_id`, `rehab_program_id`, `patient_id`, `period_start`, `period_end`, `summary`, `created_by`, `created_at`, `CHECK (period_end >= period_start)`)
  - `clinical.followup_checkup_report` link table (`followup_checkup_id`, `exercise_report_id`, PK both, `ON DELETE CASCADE` on the checkup side)
  - Indexes `idx_checkup_program`, `idx_checkup_patient`
- RLS policies already written: `fchk_staff` (FOR ALL to `ftm_gp`, `ftm_medical_specialist`), `fchk_self` (FOR SELECT to `ftm_patient` where `patient_id = current_patient_id()`), plus link-table policies `fcr_staff` / `fcr_self`. **Identical pattern to UC-08 `report_staff` / `report_self`.**
- ORM exists in `bbdd_dev_setup/alembic/models.py` (`FollowupCheckup`, `FollowupCheckupReport`) with relationships to `RehabProgram`, `Patient`, and `ExerciseReport`.

### Schema-drift hazard (CRITICAL)

`api/migrations/versions/0001_init.py` contains an OBSOLETE table: `reporting.followup_checkup (id, patient_id, doctor_id, periodo text, report_ids uuid[], ...)`. This is the WRONG shape — denormalized `report_ids uuid[]` array, wrong schema `reporting` instead of `clinical`, no link table. This is the same class of bug UC-08 had to correct (non-existent `reporting.exercise_report`). UC-09 **must** target `clinical.followup_checkup` + `clinical.followup_checkup_report`, NOT this legacy table.

### API runtime

No follow-up code exists in `api/app/`. No ORM, no schema, no router; `app/main.py` does not register any follow-up router. UC-08 lives in `api/app/reporting/` (`router.py`, `models.py`, `schemas.py`).

### UI

No follow-up code in `web/src/`. UC-08 lives in `web/src/api/reports.ts`, `web/src/features/diagnostics/components/ExerciseReportsPanel.tsx`, wired through `features/diagnostics/api.ts` (`DiagnosticFeatureApi`), with hooks in `hooks.ts`, mounted via toggle in `RehabProgramPanel.tsx`.

---

## Reference Pattern (UC-08 — reuse verbatim)

**Backend** (`api/app/reporting/`):
- `models.py`: plain `Column`-style ORM in `clinical` schema, `server_default=text("gen_random_uuid()")` for PK, junction table with `PrimaryKeyConstraint` + `ondelete="CASCADE"`.
- `router.py`:
  - `POST /reports` → `require_role("medical")` guard; resolves `created_by` doctor from `db.info.get("identity_id")` → `Doctor.identity_id`; `db.flush()` to materialize PK; bulk-inserts junction rows; returns `{exercise_report_id}` with `201`.
  - `GET /programs/{program_id}/reports` → `require_role("medical","patient")`; RLS filters rows transparently.
  - `GET /reports/{id}`, `PATCH /reports/{id}` (summary only, `204`), `DELETE /reports/{id}` (`204`, cascade removes junction).
  - Guards: `_require_medical` → 403 if not medical; `_require_not_technician` → 403 for technician.
- `schemas.py`: Pydantic v2; `@field_validator` (recording_ids non-empty), `@model_validator(mode="after")` for `period_end >= period_start`, `ConfigDict(from_attributes=True)`.
- Auth: `require_role(*allowed)` dependency. GP + Medical Specialist + Technical Specialist all collapse to realm role `medical` at the API layer.

**Frontend**:
- `web/src/api/reports.ts`: typed `XxxApi` type + `createXxxApi(http)` factory.
- Intersect the new API into `DiagnosticFeatureApi` in `features/diagnostics/api.ts`.
- Hooks in `hooks.ts` via `@tanstack/react-query`, query keys like `["reports", programId]`, invalidate on mutation.
- Panel component + toggle mount inside `RehabProgramPanel`. Plain CSS, no Tailwind/shadcn.

---

## Gap Analysis

| Layer | Status | What to build |
|-------|--------|---------------|
| DB schema | ✅ Canonical DDL exists | Verify live migration; add corrective migration if legacy `reporting` table is deployed |
| API ORM | ❌ Missing in `api/app/` | New module `api/app/followup/models.py` |
| API schemas | ❌ Missing | New `api/app/followup/schemas.py` |
| API router | ❌ Missing | New `api/app/followup/router.py` + register in `main.py` |
| UI API client | ❌ Missing | `web/src/api/followupCheckups.ts` |
| UI hooks | ❌ Missing | Extend `features/diagnostics/hooks.ts` |
| UI panel | ❌ Missing | `FollowupCheckupPanel.tsx` mounted in `RehabProgramPanel` |

---

## Open Design Decisions

1. **Report selection**: explicit multi-select of `exercise_report_id`s vs. auto-collect all reports within `[period_start, period_end]`? **Recommend explicit selection** (deterministic, mirrors UC-08's explicit `recording_ids`).
2. **SUMMARY generation**: manual free-text only vs. AI-assisted aggregation of report insights? AC-14 only requires creation. **Recommend manual for v1.**
3. **Cross-program validation**: enforce that all selected reports share the checkup's `rehab_program_id`? **Recommend yes** — FR-07 requires "del mismo rehab program".
4. **Module placement**: new `api/app/followup/` vs. extending `api/app/reporting/`. **Recommend new module** for separation.
5. **Mutability**: create + read only vs. full PATCH/DELETE parity with UC-08? AC-14 only mentions create. **Recommend create + read for v1**, add PATCH/DELETE if scope allows.
6. **Patient-facing read**: RLS `fchk_self` already permits patient SELECT. Expose to patient portal in v1?
7. **Legacy table migration**: confirm what is actually deployed before writing the ORM.

---

## Recommended Approach

Copy the UC-08 vertical slice into a parallel `followup` slice. **Backend first** (ORM → schemas → router → main wiring → tests), then the UI panel mounted alongside Exercise Reports.

**Key differences from UC-08:**
- Links target `exercise_report_id` (not `recording_id`)
- `patient_id` in the checkup must be **derived** via `RehabProgram → Diagnostic.patient_id` (RehabProgram has no direct `patient_id`)
- Treat the legacy `reporting.followup_checkup` the same way UC-08 treated `reporting.exercise_report`: ignore it, target `clinical.*`, add a corrective migration if the legacy shape is live

**Effort**: Medium — DB already designed; API + UI are mechanical clones of an existing tested pattern. Likely splits into two PRs (~250 lines each): API slice and UI slice.

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Legacy `reporting.followup_checkup` in `0001_init.py` may be deployed → runtime/ORM mismatch | Verify live migration before coding; add corrective migration if needed |
| `RehabProgram` has no `patient_id`; forgetting the `Diagnostic` join breaks `NOT NULL` inserts | Document in spec; verify in review |
| RLS uses `ftm_gp`/`ftm_medical_specialist` Postgres roles while API uses one `medical` realm role | Confirm DB session role mapping (via `db.info`) is correct — same as UC-08 |

---

## Status

**Ready for Proposal**: Yes. Pattern is well-established by UC-08 and the data model is fully designed. Resolve open decisions 1, 3, and 7 before writing the spec.

**Next recommended**: `sdd-propose` → `sdd-spec` → `sdd-tasks` → `sdd-apply`
