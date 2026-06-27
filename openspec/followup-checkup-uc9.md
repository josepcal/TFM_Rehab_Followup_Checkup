# Proposal: UC-09 Follow-up Check-up

## Intent

Doctors (GP, Medical Specialist) currently have no way to summarize patient progress across a rehabilitation period. UC-09 introduces the Follow-up Check-up: a period-bounded, structured summary that aggregates Exercise Reports from a single Rehab Program. This satisfies AC-14 and FR-07 and closes the only remaining gap in the clinical review workflow.

## Scope

### In Scope
- `POST /followup-checkups` — create a check-up with explicit report selection (defaults to all reports in `[period_start, period_end]`, doctor can deselect)
- `GET /programs/{program_id}/followup-checkups` — list check-ups for a program
- `GET /followup-checkups/{id}` — retrieve single check-up with linked reports
- `PATCH /followup-checkups/{id}` — update `summary` text (full parity with UC-08)
- `DELETE /followup-checkups/{id}` — delete with cascade on link table (full parity with UC-08)
- Cross-program validation: 422 if any `exercise_report_id` does not belong to the checkup's `rehab_program_id`
- `patient_id` derived server-side via `RehabProgram → Diagnostic.patient_id` (not caller-supplied)
- UI panel `FollowupCheckupPanel` mounted in `RehabProgramPanel` alongside Exercise Reports
- Corrective Alembic migration if legacy `reporting.followup_checkup` is live

### Out of Scope
- AI-assisted summary generation (manual free-text only for v1)
- Patient-portal read endpoint (RLS permits it; UI exposure deferred)
- Notifications or PDF export

## Capabilities

### New Capabilities
- `followup-checkup`: Full CRUD for follow-up check-ups; period-scoped aggregation of exercise reports per rehab program; cross-program report validation; manual summary authoring.

### Modified Capabilities
- None

## Approach

Mirror the UC-08 vertical slice into a new `api/app/followup/` module (ORM → schemas → router → `main.py` wiring → tests), then add the UI panel. Backend first; UI second. Two PRs expected (~250 lines each).

**Key differences from UC-08:**

| Concern | UC-08 | UC-09 |
|---------|-------|-------|
| Link target | `recording_id` | `exercise_report_id` |
| Patient resolution | `Diagnostic.patient_id` directly | `RehabProgram → Diagnostic.patient_id` join |
| Selection default | explicit list required | auto-select all reports in period; doctor may deselect |
| Cross-entity validation | recordings must belong to report | reports must belong to program (422 on mismatch) |

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `api/app/followup/models.py` | New | SQLAlchemy ORM for `clinical.followup_checkup` + `clinical.followup_checkup_report` |
| `api/app/followup/schemas.py` | New | Pydantic v2 request/response schemas; `period_end >= period_start` validator |
| `api/app/followup/router.py` | New | 5 endpoints; `require_role("medical")` guard; `_require_medical` / `_require_not_technician` guards |
| `api/app/main.py` | Modified | Register follow-up router |
| `api/migrations/versions/` | New | Corrective migration if legacy `reporting.followup_checkup` is deployed |
| `web/src/api/followupCheckups.ts` | New | Typed API factory |
| `web/src/features/diagnostics/api.ts` | Modified | Add `followupCheckupApi` to `DiagnosticFeatureApi` |
| `web/src/features/diagnostics/hooks.ts` | Modified | Add react-query hooks; invalidate on mutation |
| `web/src/features/diagnostics/components/FollowupCheckupPanel.tsx` | New | Panel with create form, list, and summary edit; plain CSS |
| `web/src/features/diagnostics/components/RehabProgramPanel.tsx` | Modified | Mount `FollowupCheckupPanel` toggle |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Legacy `reporting.followup_checkup` in `0001_init.py` is live — causes ORM/runtime mismatch | Med | Verify live migration before writing ORM; add corrective migration if present |
| `RehabProgram` has no direct `patient_id` — missing join causes NOT NULL insert failure | Med | Document required join in spec; enforce in code review |
| RLS uses `ftm_gp`/`ftm_medical_specialist` Postgres roles while API uses one `medical` realm role | Low | Same mapping as UC-08; confirm `db.info["identity_id"]` path is unchanged |

## Rollback Plan

- API: remove router registration from `main.py`; drop `api/app/followup/`; reverse corrective migration with `alembic downgrade`.
- UI: remove `FollowupCheckupPanel` toggle from `RehabProgramPanel`; delete panel and API client files.
- DB canonical schema is untouched (tables already exist); rollback does not affect other features.

## Dependencies

- UC-08 Exercise Report must be deployed (check-ups link to `exercise_report_id`)
- Live migration state must be confirmed before implementation starts

## Success Criteria

- [ ] `POST /followup-checkups` creates a check-up with correct `patient_id` derived from `RehabProgram → Diagnostic`
- [ ] Cross-program report validation returns 422 when reports do not belong to the checkup's program
- [ ] `PATCH` updates summary; `DELETE` removes check-up and link rows via cascade
- [ ] `GET /programs/{id}/followup-checkups` returns only check-ups for that program, filtered by RLS
- [ ] `FollowupCheckupPanel` renders create form, list, and summary editor inside `RehabProgramPanel`
- [ ] All backend endpoints covered by tests mirroring UC-08 test structure
- [ ] No regression in UC-08 endpoints
