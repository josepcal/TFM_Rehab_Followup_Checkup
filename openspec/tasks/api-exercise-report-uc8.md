# Tasks: Exercise Report API (UC-07 / UC-08, D14)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 320–420 |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | ORM + schema models | PR 1 | Foundation; all other tasks depend on this |
| 2 | All 4 endpoints + schemas | PR 1 | Builds on Unit 1; single PR is viable |
| 3 | Tests | PR 1 | Completes the slice |

---

## Phase 1: ORM Fix — `reporting/models.py`

- [x] 1.1 **File**: `api/app/reporting/models.py`. Replace `ExerciseReport` with a model mapped to `clinical.exercise_report` columns: `exercise_report_id` (PK), `rehab_program_id` (FK), `program_exercise_id` (FK, nullable), `period_start` (Date), `period_end` (Date), `summary` (Text, nullable), `created_by` (UUID, FK to `clinical.doctor`), `attested_at` (DateTime, nullable), `content_hash` (Text, nullable), `created_at` (DateTime, server_default now()). Schema must be `clinical`. Remove the old fields (`recording_id`, `metrics_id`, `insight_id`, `resumen`). **Acceptance**: `ExerciseReport.__table_args__["schema"] == "clinical"` and no reference to `reporting.exercise_report`.

- [x] 1.2 **File**: `api/app/reporting/models.py`. Add `ExerciseReportRecording` model for `clinical.exercise_report_recording` junction table: columns `exercise_report_id` (UUID, FK to `clinical.exercise_report`, part of composite PK), `recording_id` (UUID, FK to `recording.exercise_recording`, part of composite PK). **Acceptance**: composite primary key declared; model importable without errors.

- [x] 1.3 **File**: `api/app/reporting/models.py`. Add `AiInsight` model for `metrics.ai_insight`: columns `ai_insight_id` (PK), `result_id` (UUID, FK unique to `metrics.metric_result`), `model_used` (Text, nullable), `insight_text` (Text), `generated_at` (DateTime). **Acceptance**: model importable; `__table_args__["schema"] == "metrics"`. NOTE: Re-exported from `app.analysis.models` (existing canonical ORM) to avoid duplicate table definition error.

- [x] 1.4 **File**: `api/app/reporting/router.py`. Remove all imports and references to the old `ExerciseReport`, `FollowupCheckup`, `ReportIn`, and `create_report`/`followups` handlers — they will be replaced in Phase 2. Keep the `router = APIRouter(tags=["reporting"])` line. **Acceptance**: file imports cleanly with no `NameError`; no reference to `reporting.exercise_report` schema.

---

## Phase 2: Pydantic Schemas — `reporting/schemas.py`

- [x] 2.1 **File**: `api/app/reporting/schemas.py` (new file). Define `ReportIn(BaseModel)`: `program_exercise_id: UUID`, `recording_ids: list[UUID]` (min length 1), `period_start: date`, `period_end: date`, `summary: str | None`. Add `@model_validator` that raises `ValueError` if `period_end < period_start`. **Acceptance**: `ReportIn(program_exercise_id=..., recording_ids=[uid], period_start=d1, period_end=d0)` raises `ValidationError`.

- [x] 2.2 **File**: `api/app/reporting/schemas.py`. Define `ReportCreatedOut(BaseModel)`: `exercise_report_id: UUID`. **Acceptance**: `ReportCreatedOut(exercise_report_id=uid)` serializes correctly.

- [x] 2.3 **File**: `api/app/reporting/schemas.py`. Define `ReportListItem(BaseModel)`: `exercise_report_id`, `program_exercise_id`, `period_start`, `period_end`, `summary`, `created_by`, `attested_at`, `recording_count: int`. **Acceptance**: all fields present; `model_config = ConfigDict(from_attributes=True)`.

- [x] 2.4 **File**: `api/app/reporting/schemas.py`. Define `RecordingInsightOut(BaseModel)`: `recording_id`, `recording_date`, `duration_seconds`, `media_status`, `metrics_status: str | None`, `raw_json: dict | None`, `insight_text: str | None`, `model_used: str | None`. Define `ReportDetailOut(BaseModel)`: all `ReportListItem` fields minus `recording_count`, plus `recordings: list[RecordingInsightOut]`. **Acceptance**: both models importable.

- [x] 2.5 **File**: `api/app/reporting/schemas.py`. Define `InsightOut(BaseModel)`: `insight_id: UUID`, `recording_id: UUID`, `insight_text: str`, `model_used: str | None`, `generated_at: datetime`. **Acceptance**: model importable.

---

## Phase 3: Endpoint Implementation — `reporting/router.py`

- [x] 3.1 **File**: `api/app/reporting/router.py`. Implement `POST /reports` (`status_code=201`). Auth: `require_role("medical")`. Steps: (1) look up `ProgramExercise` by `body.program_exercise_id` → 404 if missing; (2) for each `recording_id` in `body.recording_ids`, verify row exists in `ExerciseRecording` → 404 and abort if any missing; (3) insert `ExerciseReport` with `rehab_program_id = pe.program_id`, `created_by = db.info["identity_id"]`, period, summary; (4) flush to get PK; (5) bulk-insert `ExerciseReportRecording` rows; (6) return `ReportCreatedOut`. All writes in the single `get_db` transaction — no explicit `db.commit()` needed. **Acceptance**: REQ-2 scenarios all pass.

- [x] 3.2 **File**: `api/app/reporting/router.py`. Implement `GET /programs/{program_id}/reports`. Auth: `require_role("medical", "patient")`. Query: aggregate SELECT with `func.count` and LEFT JOIN on `exercise_report_recording`. Return `list[ReportListItem]`. RLS handles row filtering; return empty list when program has no reports. **Acceptance**: REQ-3 scenarios pass; technician gets 403.

- [x] 3.3 **File**: `api/app/reporting/router.py`. Implement `GET /reports/{report_id}`. Auth: `require_role("medical", "patient")`. Fetch `ExerciseReport` by PK → 404 if None. Fetch linked recordings via flat JOIN: `exercise_report_recording JOIN exercise_recording LEFT JOIN metric_result LEFT JOIN ai_insight`. Build `ReportDetailOut` with `recordings` array; set metric/insight fields to `None` when absent. **Acceptance**: REQ-4 scenarios pass including nulls for missing metrics/insight.

- [x] 3.4 **File**: `api/app/recording/router.py`. Add `GET /recordings/{recording_id}/insight` endpoint. Auth: `require_role("medical", "patient")`. Steps: (1) call `_require_authorized_recording`; (2) join `MetricResult` on `recording_id` → 404 if none; (3) join `AiInsight` on `result_id` → 404 if none; (4) return `InsightOut`. Import `AiInsight` from `app.reporting.models` (re-exports from `app.analysis.models`). **Acceptance**: REQ-5 scenarios pass; technician gets 403; another patient's insight returns 404.

---

## Phase 4: Router Registration

- [x] 4.1 **File**: `api/app/main.py`. Confirmed: `reporting_router` already registered. All 4 routes (`/reports`, `/programs/{id}/reports`, `/reports/{id}`, `/recordings/{id}/insight`) appear in the app. **Acceptance**: verified via `app.routes` inspection — all 4 paths present.

---

## Phase 5: Tests

- [x] 5.1 **File**: `api/tests/test_reporting.py` (new). Unit-test `POST /reports` using `FakeSession` pattern. Cases: valid body → 201 + `exercise_report_id`; `period_end < period_start` → 422 (Pydantic); unknown `program_exercise_id` → 404; non-medical role → 403. **Acceptance**: all 4 cases pass without DB.

- [x] 5.2 **File**: `api/tests/test_reporting.py`. Unit-test `GET /programs/{program_id}/reports`. Cases: returns list with `recording_count`; empty list for program with no reports; technician → 403. **Acceptance**: 3 cases pass.

- [x] 5.3 **File**: `api/tests/test_reporting.py`. Unit-test `GET /reports/{report_id}`. Cases: full detail with recordings array; recordings with null metrics/insight fields; report not found → 404; technician → 403. **Acceptance**: 4 cases pass.

- [x] 5.4 **File**: `api/tests/test_recording.py`. Add tests for `GET /recordings/{recording_id}/insight`. Cases: insight exists → 200 + all fields; no metric_result → 404; metric_result exists but no ai_insight → 404; technician → 403. **Acceptance**: 4 cases pass without DB.

- [x] 5.5 **File**: `api/tests/test_reporting.py`. Test `ReportIn` schema validator. Cases: `period_end == period_start` → valid; `period_end < period_start` → `ValidationError`; empty `recording_ids` → `ValidationError`. **Acceptance**: 3 schema-only assertions pass.

---

## Dependency Map

```
1.1 ──┐
1.2 ──┤──► 1.4 ──► 3.1, 3.2, 3.3
1.3 ──┘          ──► 3.4
2.1–2.5 (parallel with Phase 1, blocked only by 1.4 being clean)
3.1–3.4 depend on Phase 1 + Phase 2
4.1 depends on 3.1–3.3
5.1–5.5 depend on Phase 3
```

Tasks 1.1, 1.2, 1.3 can be written in parallel. Tasks 2.1–2.5 can be written in parallel with Phase 1. Phase 3 is sequential after both Phase 1 and 2 complete.
