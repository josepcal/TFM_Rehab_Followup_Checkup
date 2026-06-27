# Tasks: Follow-up Check-up (UC-09, FR-07, AC-14)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 520–650 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1 Backend · PR2 Frontend |
| Delivery strategy | stacked-to-main |
| Chain strategy | stacked-to-main |

Decision needed before apply: No (split already defined below)
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | PR | Notes |
|------|------|----|-------|
| 1 | Alembic corrective migration | PR1 | Foundation for ORM; idempotent IF EXISTS guard |
| 2 | ORM models | PR1 | Depends on migration intent being clear |
| 3 | Pydantic schemas | PR1 | Parallel with ORM |
| 4 | Router (5 endpoints) | PR1 | Depends on ORM + schemas |
| 5 | main.py registration | PR1 | Depends on router |
| 6 | Tests | PR1 | Depends on router |
| 7 | API module (TS types + factory) | PR2 | Independent from backend once PR1 merged |
| 8 | DiagnosticFeatureApi intersection | PR2 | Depends on task 7 |
| 9 | React Query hooks | PR2 | Depends on tasks 7 + 8 |
| 10 | FollowupCheckupPanel component | PR2 | Depends on tasks 8 + 9 |
| 11 | RehabProgramPanel mount toggle | PR2 | Depends on task 10 |

---

## PR1 — Backend

### Phase 1: Alembic Corrective Migration

- [x] **1.1** Create `bbdd_dev_setup/alembic/migrations/versions/0010_followup_checkup.py`.
  - **Context verified**: `clinical.followup_checkup` and `clinical.followup_checkup_report` do NOT exist in any of the 9 existing `bbdd_dev_setup` migrations (`0001`–`0009`). They are defined in the canonical DDL (`ftm_schema.sql`) but never ported to a migration version. The legacy `reporting.followup_checkup` (wrong shape: `report_ids uuid[]`, no link table) exists only in `api/migrations/versions/0001_init.py` — a separate API migration tree.
  - `upgrade()` must:
    1. Create `clinical.followup_checkup` — columns: `followup_checkup_id uuid PK DEFAULT gen_random_uuid()`, `rehab_program_id uuid NOT NULL REFERENCES clinical.rehab_program`, `patient_id uuid NOT NULL`, `period_start date NOT NULL`, `period_end date NOT NULL`, `summary text`, `created_by uuid REFERENCES clinical.doctor`, `created_at timestamptz DEFAULT now()`, `CHECK (period_end >= period_start)`.
    2. Create `clinical.followup_checkup_report` link table — `followup_checkup_id uuid NOT NULL REFERENCES clinical.followup_checkup ON DELETE CASCADE`, `exercise_report_id uuid NOT NULL REFERENCES clinical.exercise_report`, `PRIMARY KEY (followup_checkup_id, exercise_report_id)`.
    3. Create indexes `idx_checkup_program ON clinical.followup_checkup(rehab_program_id)` and `idx_checkup_patient ON clinical.followup_checkup(patient_id)`.
    4. Enable RLS and create policies mirroring `ftm_schema.sql:598–611`: `fchk_staff` (FOR ALL TO `ftm_gp`, `ftm_medical_specialist`), `fchk_self` (FOR SELECT TO `ftm_patient` USING `patient_id = clinical.current_patient_id()`), `fcr_staff`, `fcr_self`.
  - `downgrade()` must drop `clinical.followup_checkup_report` then `clinical.followup_checkup` (CASCADE).
  - Use `op.execute("""...""")` raw SQL, same style as `0009_uc17_delete_exercise_report.py`.
  - **Files**: `bbdd_dev_setup/alembic/migrations/versions/0010_followup_checkup.py`
  - **Depends on**: nothing — first task.
  - **Acceptance**: `alembic upgrade head` creates both tables with correct schema, constraints, indexes, and RLS policies; `alembic downgrade -1` drops them cleanly; re-running upgrade on an already-migrated DB raises no error.

---

### Phase 2: ORM Models

- [x] **2.1** Create `api/app/followup/__init__.py` (empty package marker).
  - **Files**: `api/app/followup/__init__.py`
  - **Depends on**: nothing — can run in parallel with 1.1.
  - **Acceptance**: `from app.followup import models` resolves without ImportError.

- [x] **2.2** Create `api/app/followup/models.py` with `FollowupCheckup` ORM class.
  - `__tablename__ = "followup_checkup"`, `__table_args__ = {"schema": "clinical"}`.
  - Columns: `followup_checkup_id` (UUID PK, `gen_random_uuid()`), `rehab_program_id` (UUID FK → `clinical.rehab_program.rehab_program_id`, NOT NULL), `patient_id` (UUID, NOT NULL — derived server-side, never caller-supplied), `period_start` (Date, NOT NULL), `period_end` (Date, NOT NULL), `summary` (Text, nullable), `created_by` (UUID FK → `clinical.doctor.doctor_id`, nullable), `created_at` (DateTime timezone=True, server_default `now()`).
  - **Files**: `api/app/followup/models.py`
  - **Depends on**: 2.1.
  - **Acceptance**: `FollowupCheckup.__table_args__["schema"] == "clinical"`; no reference to `reporting` schema.

- [x] **2.3** Add `FollowupCheckupReport` ORM class to `api/app/followup/models.py`.
  - `__tablename__ = "followup_checkup_report"`, schema `clinical`.
  - Composite PK: `(followup_checkup_id, exercise_report_id)`.
  - `followup_checkup_id`: UUID FK → `clinical.followup_checkup.followup_checkup_id` with `ondelete="CASCADE"`.
  - `exercise_report_id`: UUID FK → `clinical.exercise_report.exercise_report_id`.
  - **Files**: `api/app/followup/models.py`
  - **Depends on**: 2.2.
  - **Acceptance**: composite PK declared via `PrimaryKeyConstraint`; model importable without errors; `ondelete="CASCADE"` present.

---

### Phase 3: Pydantic Schemas

- [x] **3.1** Create `api/app/followup/schemas.py` with `CheckupIn(BaseModel)`.
  - Fields: `rehab_program_id: uuid.UUID`, `exercise_report_ids: list[uuid.UUID]`, `period_start: date`, `period_end: date`, `summary: str | None = None`.
  - `@field_validator("exercise_report_ids")` that raises `ValueError` if list is empty.
  - `@model_validator(mode="after")` that raises `ValueError` if `period_end < period_start`.
  - **Files**: `api/app/followup/schemas.py`
  - **Depends on**: 2.1 (package must exist).
  - **Acceptance**: `CheckupIn(..., exercise_report_ids=[])` raises `ValidationError`; `CheckupIn(..., period_end=d0, period_start=d1)` where `d0 < d1` raises `ValidationError`.

- [x] **3.2** Add `CheckupCreatedOut`, `CheckupPatchIn`, `CheckupListItem`, `LinkedReportItem`, `CheckupDetailOut` to `api/app/followup/schemas.py`.
  - `CheckupCreatedOut`: `followup_checkup_id: uuid.UUID`.
  - `CheckupPatchIn`: `summary: str | None = None`.
  - `CheckupListItem`: `followup_checkup_id`, `rehab_program_id`, `period_start`, `period_end`, `summary`, `created_by`, `created_by_name: str | None`, `report_count: int`; `model_config = ConfigDict(from_attributes=True)`.
  - `LinkedReportItem`: `exercise_report_id`, `period_start`, `period_end`, `summary`.
  - `CheckupDetailOut`: all `CheckupListItem` fields minus `report_count`, plus `reports: list[LinkedReportItem]`; `from_attributes=True`.
  - **Files**: `api/app/followup/schemas.py`
  - **Depends on**: 3.1.
  - **Acceptance**: all five classes importable; `CheckupListItem.model_config` has `from_attributes=True`.

---

### Phase 4: Router

- [x] **4.1** Create `api/app/followup/router.py` with router boilerplate and guard helpers.
  - `router = APIRouter(tags=["followup"])`.
  - `_require_medical(principal)` → raises `HTTPException(403)` if not `medical` role.
  - `_require_not_technician(principal)` → raises `HTTPException(403)` if `technician`.
  - Import `FollowupCheckup`, `FollowupCheckupReport` from `.models`; import all schemas from `.schemas`; import `RehabProgram`, `Diagnostic`, `Doctor`, `ExerciseReport` from `app.clinical.models` and `app.reporting.models`.
  - **Files**: `api/app/followup/router.py`
  - **Depends on**: 2.3, 3.2.
  - **Acceptance**: file imports cleanly; router object instantiated.

- [x] **4.2** Implement `POST /followup-checkups` (status 201).
  - Auth: `require_role("medical")` + `_require_medical`.
  - Steps:
    1. Validate schema (Pydantic raises 422 automatically on period/empty-list violations).
    2. `SELECT RehabProgram WHERE id == body.rehab_program_id` → 404 if None.
    3. `SELECT Diagnostic WHERE id == program.diagnostic_id` → derive `patient_id`.
    4. `SELECT Doctor WHERE identity_id == db.info["identity_id"]` → derive `created_by`.
    5. For each `report_id` in `body.exercise_report_ids`: fetch `ExerciseReport` → 404 if None; 422 if `report.rehab_program_id != body.rehab_program_id` (message: `"exercise_report {id} does not belong to rehab_program {program_id}"`).
    6. Insert `FollowupCheckup` with derived fields; `db.flush()`.
    7. Bulk-insert `FollowupCheckupReport` link rows.
    8. Return `CheckupCreatedOut`, 201.
  - **Files**: `api/app/followup/router.py`
  - **Depends on**: 4.1.
  - **Acceptance**: spec scenarios for POST all pass — 201 created, 403 non-medical, 404 unknown program/report, 422 invalid period, 422 empty list, 422 cross-program.

- [x] **4.3** Implement `GET /programs/{program_id}/followup-checkups` (status 200).
  - Auth: `require_role("medical", "patient")` + `_require_not_technician`.
  - Aggregate SELECT: `FollowupCheckup` fields + `func.count(FollowupCheckupReport.exercise_report_id).label("report_count")` via `outerjoin` + optional doctor name from `Doctor`.
  - Filter `WHERE followup_checkup.rehab_program_id == program_id`.
  - RLS filters rows transparently; return empty list if none.
  - Return `list[CheckupListItem]`, 200.
  - **Files**: `api/app/followup/router.py`
  - **Depends on**: 4.1.
  - **Acceptance**: 200 with `report_count` per item; empty list for no check-ups; 403 for technician.

- [x] **4.4** Implement `GET /followup-checkups/{followup_checkup_id}` (status 200).
  - Auth: `require_role("medical", "patient")` + `_require_not_technician`.
  - `SELECT FollowupCheckup WHERE id == followup_checkup_id` → 404 if None.
  - Fetch linked `ExerciseReport` rows via `followup_checkup_report` join.
  - Build `CheckupDetailOut` with `reports` array.
  - **Files**: `api/app/followup/router.py`
  - **Depends on**: 4.1.
  - **Acceptance**: 200 with `reports` array; 404 for missing/hidden id; 403 for technician.

- [x] **4.5** Implement `PATCH /followup-checkups/{followup_checkup_id}` (status 204).
  - Auth: `require_role("medical")` + `_require_medical`.
  - Fetch check-up → 404 if None.
  - Set `checkup.summary = body.summary`; no explicit commit needed.
  - Return 204.
  - **Files**: `api/app/followup/router.py`
  - **Depends on**: 4.1.
  - **Acceptance**: 204 on valid patch; summary updated; 403 non-medical; 404 not found.

- [x] **4.6** Implement `DELETE /followup-checkups/{followup_checkup_id}` (status 204).
  - Auth: `require_role("medical")` + `_require_medical`.
  - Fetch check-up → 404 if None.
  - `db.delete(checkup)` — DB `ON DELETE CASCADE` removes link rows; underlying `exercise_report` rows untouched.
  - Return 204.
  - **Files**: `api/app/followup/router.py`
  - **Depends on**: 4.1.
  - **Acceptance**: 204; `followup_checkup_report` rows gone; `exercise_report` rows intact; 403 non-medical; 404 not found.

---

### Phase 5: Router Registration

- [x] **5.1** Register `followup_router` in `api/app/main.py`.
  - Add `from app.followup.router import router as followup_router`.
  - Add `followup_router` to the `include_router` loop (after `reporting_router`).
  - **Files**: `api/app/main.py`
  - **Depends on**: 4.2–4.6 complete.
  - **Acceptance**: all five follow-up paths appear in `app.routes`; no import errors on startup.

---

### Phase 6: Tests

- [x] **6.1** Create `api/tests/test_followup.py`. Add unit tests for Pydantic schema validators.
  - Cases: `period_end == period_start` → valid; `period_end < period_start` → `ValidationError`; `exercise_report_ids=[]` → `ValidationError`; valid body → no error.
  - **Files**: `api/tests/test_followup.py`
  - **Depends on**: 3.1, 3.2.
  - **Acceptance**: 4 schema-only assertions pass without DB.

- [x] **6.2** Add `POST /followup-checkups` endpoint tests using `FakeSession` pattern (mirror `test_reporting.py`).
  - Cases: valid body → 201 + `followup_checkup_id`; `period_end < period_start` → 422; empty `exercise_report_ids` → 422; unknown `rehab_program_id` → 404; non-medical role → 403; cross-program report → 422 with message identifying offending report.
  - Assert `patient_id` equals `diagnostic.patient_id` (derived correctly).
  - **Files**: `api/tests/test_followup.py`
  - **Depends on**: 4.2, 6.1.
  - **Acceptance**: 6 cases pass.

- [x] **6.3** Add `GET /programs/{program_id}/followup-checkups` tests.
  - Cases: 200 list with `report_count`; empty list when no check-ups; 403 technician; patient sees only own check-ups (RLS simulated via FakeSession row filtering).
  - **Files**: `api/tests/test_followup.py`
  - **Depends on**: 4.3.
  - **Acceptance**: 4 cases pass.

- [x] **6.4** Add `GET /followup-checkups/{id}` tests.
  - Cases: 200 full detail with `reports` array; 404 not found; 403 technician.
  - **Files**: `api/tests/test_followup.py`
  - **Depends on**: 4.4.
  - **Acceptance**: 3 cases pass.

- [x] **6.5** Add `PATCH /followup-checkups/{id}` tests.
  - Cases: 204 updates summary; verify row after patch; 403 non-medical; 404 not found.
  - **Files**: `api/tests/test_followup.py`
  - **Depends on**: 4.5.
  - **Acceptance**: 4 cases pass.

- [x] **6.6** Add `DELETE /followup-checkups/{id}` tests.
  - Cases: 204 + verify `followup_checkup_report` link rows removed + `exercise_report` rows intact; 403 non-medical; 404 not found.
  - **Files**: `api/tests/test_followup.py`
  - **Depends on**: 4.6.
  - **Acceptance**: 3 cases pass.

---

## PR2 — Frontend

> Prerequisite: PR1 merged to main and backend endpoints are live in the dev environment.

### Phase 7: API Module

- [ ] **7.1** Create `web/src/api/followupCheckups.ts`.
  - Export types: `CheckupIn`, `CheckupListItem`, `LinkedReportItem`, `CheckupDetailOut`.
    - `CheckupDetailOut = Omit<CheckupListItem, "report_count"> & { reports: LinkedReportItem[] }`.
  - Export `FollowupCheckupsApi` interface with methods: `createCheckup(body: CheckupIn): Promise<{ followup_checkup_id: string }>`, `listProgramCheckups(programId: string): Promise<CheckupListItem[]>`, `getCheckupDetail(checkupId: string): Promise<CheckupDetailOut>`, `updateCheckup(checkupId: string, summary: string | null): Promise<void>`, `deleteCheckup(checkupId: string): Promise<void>`.
  - Implement `createFollowupCheckupsApi(http: HttpClient): FollowupCheckupsApi`. Map to: `POST /followup-checkups`, `GET /programs/{id}/followup-checkups`, `GET /followup-checkups/{id}`, `PATCH /followup-checkups/{id}`, `DELETE /followup-checkups/{id}`.
  - **Files**: `web/src/api/followupCheckups.ts`
  - **Depends on**: nothing in this PR — first task.
  - **Acceptance**: file imports cleanly; `FollowupCheckupsApi` exports all five methods with correct signatures.

- [ ] **7.2** Add `FollowupCheckupsApi` to `DiagnosticFeatureApi` intersection in `web/src/features/diagnostics/api.ts`.
  - Import `FollowupCheckupsApi` from `../../api/followupCheckups`.
  - Append `& FollowupCheckupsApi` to the `DiagnosticFeatureApi` type.
  - **Files**: `web/src/features/diagnostics/api.ts`
  - **Depends on**: 7.1.
  - **Acceptance**: `DiagnosticFeatureApi` includes `createCheckup`, `listProgramCheckups`, `getCheckupDetail`, `updateCheckup`, `deleteCheckup`; project builds without type errors.

- [ ] **7.3** Wire `createFollowupCheckupsApi(http)` into the `api` object in `web/src/App.tsx`.
  - Follow the same spread/Object.assign pattern used for `createReportsApi`.
  - **Files**: `web/src/App.tsx`
  - **Depends on**: 7.2.
  - **Acceptance**: app builds; `api.listProgramCheckups` is callable at runtime.

---

### Phase 8: React Query Hooks

- [ ] **8.1** Add `useProgramCheckups(api, programId?: string)` to `web/src/features/diagnostics/hooks.ts`.
  - `useQuery` with key `["followup-checkups", programId]`, calls `api.listProgramCheckups(programId!)`, enabled when `Boolean(programId)`.
  - **Files**: `web/src/features/diagnostics/hooks.ts`
  - **Depends on**: 7.2.
  - **Acceptance**: hook returns `{ data, isLoading, error }`; disabled when `programId` is undefined.

- [ ] **8.2** Add `useCheckupDetail(api, checkupId?: string)` to `web/src/features/diagnostics/hooks.ts`.
  - `useQuery` with key `["followup-checkups", "detail", checkupId]`, calls `api.getCheckupDetail(checkupId!)`, enabled when `Boolean(checkupId)`.
  - **Files**: `web/src/features/diagnostics/hooks.ts`
  - **Depends on**: 7.2.
  - **Acceptance**: hook returns query object; disabled when `checkupId` is undefined.

- [ ] **8.3** Add `useCreateCheckup(api, programId: string)` mutation to `web/src/features/diagnostics/hooks.ts`.
  - `useMutation` calling `api.createCheckup(body)`.
  - On success: `queryClient.invalidateQueries({ queryKey: ["followup-checkups", programId] })`.
  - **Files**: `web/src/features/diagnostics/hooks.ts`
  - **Depends on**: 7.2.
  - **Acceptance**: mutation callable; success invalidates the list query for the program.

---

### Phase 9: FollowupCheckupPanel Component

- [ ] **9.1** Create `web/src/features/diagnostics/components/FollowupCheckupPanel.tsx` with component skeleton.
  - Props: `{ api: DiagnosticFeatureApi; programId: string }`.
  - State: `showCreateForm`, `periodStart`, `periodEnd`, `selectedReportIds: string[]`, `summary`, `formError`, `editingCheckupId: string | null`, `editingSummary`, `expandedCheckupId: string | null`, `deleteError`, `saveError`.
  - Use `useProgramCheckups(api, programId)` for the list.
  - Render: section header with "Follow-up Check-ups" h3 + "New Check-up" button (hidden when form open); loading/error state; empty state ("No follow-up check-ups yet") when list is empty.
  - Use existing CSS classes: `.detail-card`, `.v0-outline-button`, `.ghost-button`, `.section-heading`, `.state-card` — no new styles.
  - **Files**: `web/src/features/diagnostics/components/FollowupCheckupPanel.tsx`
  - **Depends on**: 8.1, 8.2, 8.3.
  - **Acceptance**: component renders without errors in Vitest + jsdom; shows loading state.

- [ ] **9.2** Implement the inline create form inside `FollowupCheckupPanel`.
  - Fields: `period_start` date input, `period_end` date input, optional `summary` textarea.
  - Report multi-select: fetch `api.listProgramReports(programId)` (UC-08 reports API); render a checkbox list showing each report's `period_start`–`period_end` and `recording_count`.
  - Auto-selection: when both period inputs have values, auto-check all reports whose `period_start` and `period_end` fall within `[periodStart, periodEnd]` (client-side filter). Doctor may uncheck any or check others.
  - Submit validation:
    1. `period_end >= period_start` — inline error if not.
    2. At least one report selected — inline error "Select at least one report" if not.
  - On valid submit: call `useCreateCheckup.mutate(...)`. On success: reset form, close. On 422: show API error message inline.
  - Cancel button resets and closes form.
  - **Files**: `web/src/features/diagnostics/components/FollowupCheckupPanel.tsx`
  - **Depends on**: 9.1.
  - **Acceptance**: period auto-selects matching reports; validation errors shown inline without API call; successful submit invalidates list query and closes form.

- [ ] **9.3** Implement check-up cards list inside `FollowupCheckupPanel`.
  - Each card shows: period range (`period_start – period_end`), `report_count` badge, summary excerpt (truncated), "Expand" / "Collapse" toggle, "Edit Summary" button, "Delete" button.
  - Expand: sets `expandedCheckupId`; renders `useCheckupDetail(api, id)` as a table of linked reports with columns: `period_start`–`period_end`, `recording_count`.
  - Edit summary: clicking "Edit Summary" sets `editingCheckupId` and populates `editingSummary`. Save calls `api.updateCheckup(id, editingSummary)` then invalidates `["followup-checkups", programId]` and clears editing state. Cancel resets.
  - **Files**: `web/src/features/diagnostics/components/FollowupCheckupPanel.tsx`
  - **Depends on**: 9.2.
  - **Acceptance**: cards render with correct data; expand shows linked report table; edit summary updates and refreshes.

- [ ] **9.4** Implement delete flow inside `FollowupCheckupPanel`.
  - "Delete" button triggers `window.confirm()`. On confirmation: call `api.deleteCheckup(id)`, on success invalidate `["followup-checkups", programId]`, on failure set `deleteError` and show `<p role="alert">` inside the card.
  - On dismiss: no API call, no state change.
  - **Files**: `web/src/features/diagnostics/components/FollowupCheckupPanel.tsx`
  - **Depends on**: 9.3.
  - **Acceptance**: confirmed delete removes card from list; dismissed delete makes no API call; failure shows inline error.

---

### Phase 10: RehabProgramPanel Mount Toggle

- [ ] **10.1** Add `FollowupCheckupPanel` toggle to `web/src/features/diagnostics/components/RehabProgramPanel.tsx`.
  - Import `FollowupCheckupPanel` from `./FollowupCheckupPanel`.
  - Add `const [showCheckups, setShowCheckups] = useState(false)` alongside the existing `showReports` state.
  - Render toggle button (`"Show Follow-up Check-ups"` / `"Hide Follow-up Check-ups"`, class `v0-outline-button`) alongside the existing Exercise Reports toggle.
  - Mount `<FollowupCheckupPanel programId={program.id} api={api} />` when `showCheckups` is true.
  - **Files**: `web/src/features/diagnostics/components/RehabProgramPanel.tsx`
  - **Depends on**: 9.4.
  - **Acceptance**: toggle button visible in program detail view; clicking shows/hides the panel; existing Exercise Reports toggle is unaffected.

---

### Phase 11: Frontend Tests

- [ ] **11.1** Create `web/src/api/followupCheckups.test.ts`. Test `createFollowupCheckupsApi`:
  - `listProgramCheckups` calls `GET /programs/{id}/followup-checkups`.
  - `createCheckup` calls `POST /followup-checkups` with correct body.
  - `getCheckupDetail` calls `GET /followup-checkups/{id}`.
  - `updateCheckup` calls `PATCH /followup-checkups/{id}` with `{ summary }`.
  - `deleteCheckup` calls `DELETE /followup-checkups/{id}`.
  - Use same mock `http` pattern as `web/src/api/programs.test.ts`.
  - **Files**: `web/src/api/followupCheckups.test.ts`
  - **Depends on**: 7.1.
  - **Acceptance**: 5 tests pass.

- [ ] **11.2** Create `web/src/features/diagnostics/components/FollowupCheckupPanel.test.tsx`.
  - Use Vitest + React Testing Library (same setup as `DiagnosticWorkspace.test.tsx`).
  - Cases:
    1. Shows loading state when `listProgramCheckups` is pending.
    2. Shows empty state when list returns `[]`.
    3. Shows check-up cards when list returns data (period, report_count, summary excerpt visible).
    4. "New Check-up" button opens create form.
    5. Form validates date range → shows inline error without API call.
    6. Form validates empty report selection → shows "Select at least one report".
    7. Period auto-selection: reports within range are pre-checked.
  - Mock `api` with `vi.fn()` stubs.
  - **Files**: `web/src/features/diagnostics/components/FollowupCheckupPanel.test.tsx`
  - **Depends on**: 9.4.
  - **Acceptance**: 7 tests pass without hitting real HTTP.

---

## Dependency Map

```
PR1 (Backend)
──────────────────────────────────────────
1.1 (migration) ──────────────────────────────────────────► 5.1 (schema unit tests)
2.1 (__init__)  ──┐
                  ├──► 2.2 (FollowupCheckup ORM) ──► 2.3 (FollowupCheckupReport ORM)
                  └──► 3.1 (CheckupIn schema) ──► 3.2 (remaining schemas)

2.3 + 3.2 ──► 4.1 (router boilerplate)
              ├──► 4.2 (POST) ──► 6.2
              ├──► 4.3 (GET list) ──► 6.3
              ├──► 4.4 (GET detail) ──► 6.4
              ├──► 4.5 (PATCH) ──► 6.5
              └──► 4.6 (DELETE) ──► 6.6

4.2–4.6 complete ──► 5.1 (registration)

PR2 (Frontend)  [starts after PR1 merged]
──────────────────────────────────────────
7.1 (TS types + factory) ──► 7.2 (DiagnosticFeatureApi) ──► 7.3 (App.tsx wire)
7.1 ──► 11.1 (API factory tests)

7.2 ──► 8.1 (useProgramCheckups)
     ──► 8.2 (useCheckupDetail)
     ──► 8.3 (useCreateCheckup)

8.1 + 8.2 + 8.3 ──► 9.1 (panel skeleton)
                     ──► 9.2 (create form)
                         ──► 9.3 (cards list + expand + edit summary)
                             ──► 9.4 (delete flow)
                                 ──► 10.1 (RehabProgramPanel mount)
                                 ──► 11.2 (panel tests)
```

Parallel opportunities inside PR1:
- Tasks 1.1, 2.1 can run simultaneously.
- Tasks 2.2 and 3.1 can run simultaneously after 2.1.
- Tasks 4.2–4.6 can run simultaneously after 4.1.
- Test tasks 6.2–6.6 can run simultaneously after their respective endpoint tasks.

Parallel opportunities inside PR2:
- Tasks 7.1 and any exploratory reading can run simultaneously.
- Tasks 8.1, 8.2, 8.3 can run simultaneously after 7.2.
- Task 11.1 can run after 7.1 independently of hooks.

Sequential bottlenecks:
- 2.1 → 2.2 → 2.3 (ORM chain): must be ordered.
- 3.1 → 3.2 (schema chain): must be ordered.
- 4.1 (router boilerplate) blocks all endpoint tasks.
- 9.2 → 9.3 → 9.4 → 10.1 (component chain): each builds on the prior.
