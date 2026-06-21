# Tasks: API Analysis Registry + Worker (UC-06 infra)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 550-850 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR #1 registry + models/migration → PR #2 job queue + worker loop → PR #3 API endpoints (run/metrics) + RLS → PR #4 tests/integration |
| Delivery strategy | ask-on-risk |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Registry + metric models + migration | PR 1 | `registry.py`, `MetricResult`/`RecordingMetric`, Alembic migration. No execution logic yet. |
| 2 | Job queue + worker loop | PR 2 | `jobs.py` dequeue (`SKIP LOCKED`), `worker.py` polling/timeout/error capture. |
| 3 | API endpoints + RLS | PR 3 | `POST /recordings/{id}/run`, `GET /recordings/{id}/metrics`, technician denial. |
| 4 | Tests / integration | PR 4 | Unit + concurrency + RLS coverage; fold into PR 3 if diff stays small. |

## Implementation Checkpoint

**Phase 1 completed**: 2026-06-21

- The canonical SQL-first baseline already owns `metrics.metric_result` and
  `metrics.recording_metric`. Migration `0006_analysis_worker` validates those
  tables, gives the success/raw-JSON CHECK a stable name, and creates the
  `metrics.analysis_job` queue with grants and RLS.
- `analysis/functions/__init__.py` remains the deploy-time import point. Existing
  reference functions were preserved rather than deleted; adding or changing
  those functions remains outside this phase.
- Phase 1 is the autonomous PR 1 boundary in the feature-branch chain. Worker
  dequeue/execution and API endpoints remain in Phases 2 and 3.

## Phase 1: Registry + Models Foundation

- [x] 1.1 Create `api/app/analysis/registry.py` with `REGISTRY`, `register_analysis(name)` decorator and `run(name, wav_path, params)` resolver raising `UnknownAnalysisFunction`.
- [x] 1.2 Create `api/app/analysis/functions/__init__.py` as the import point for technician-authored functions (empty for this slice).
- [x] 1.3 Add/confirm `MetricResult` model (`recording_id` UNIQUE, `pseudonym_id` no-FK, `function_name`, `function_version`, `code_sha`, `status`, `error_detail`, `raw_json`, `extracted_at`) in `api/app/metrics/models.py`.
- [x] 1.4 Add `RecordingMetric` flattened-row model in `api/app/metrics/models.py`.
- [x] 1.5 Write the SQL-first Alembic migration for the jobs table and `metric_result`/`recording_metric`, including the `status='success' => raw_json IS NOT NULL` CHECK constraint (ADR-0009).

## Phase 2: Job Queue and Worker Loop

- [x] 2.1 Define the job row shape in `api/app/jobs.py` (`recording_id`, `function_name`, `status`, `attempts`, `created_at`, `locked_at`).
- [x] 2.2 Implement `SKIP LOCKED` dequeue helper (`SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1`).
- [x] 2.3 Implement the worker polling loop in `api/app/worker.py`: dequeue → resolve `pseudonym_id` (role `ftm_worker`) → resolve `function_name` against `REGISTRY` → read WAV from object storage.
- [x] 2.4 Add execution timeout enforcement around the function call.
- [x] 2.5 Add exception capture around the function call; never let a single job crash the worker process.
- [x] 2.6 Persist `metric_result` (success: `raw_json` + flattened `recording_metric`; error: `status=error` + `error_detail`) and mark the job done.
- [x] 2.7 Implement reanalysis-overwrites behavior (no new row, no history) per ADR-0010.


**Phase 2 completed**: 2026-06-21

- `api/app/jobs.py` now matches the SQL-first `metrics.analysis_job` queue shape, including `attempts`, `locked_at`, `error_detail`, and a `FOR UPDATE SKIP LOCKED` claim helper.
- `api/app/worker.py` now performs the complete dequeue → pseudonym resolution → registry execution → timeout/error isolation → result persistence flow.
- Successful reanalysis upserts the single current `metric_result` row and replaces flattened `recording_metric` rows; failed jobs persist `status=error` and clear stale flattened metrics.

## Phase 3: API Endpoints and Authorization

- [x] 3.1 Add `POST /recordings/{id}/run` to `api/app/recording/router.py`: resolve `function_name` (request override, else `analysis_setup.function_name`), enqueue job, return immediately.
- [x] 3.2 Restrict `POST /recordings/{id}/run` to patient/medical roles; confirm technician is denied via RLS (ADR-0011).
- [x] 3.3 Add `GET /recordings/{id}/metrics` returning the current `metric_result` (success or error state) for an authorized recording.
- [x] 3.4 Confirm the worker's DB session uses the `ftm_worker` role and cannot read outside what it needs to resolve the pseudonym and write metrics (ADR-0013, ADR-0014).



**Phase 3 completed**: 2026-06-21

- `api/app/recording/router.py` now owns the UC-06 API boundary: `POST /recordings/{recording_id}/run` enqueues a job with HTTP 202, resolving `function_name` from the request override or from the exercise `analysis_setup`.
- The run endpoint uses the same patient/medical recording access check as UC-05 and excludes technicians at the FastAPI role dependency before any queue write.
- `GET /recordings/{recording_id}/metrics` returns the current `metrics.metric_result` for an authorized recording, including success/error status, raw JSON, traceability fields, and error detail.
- Legacy duplicate handlers were removed from `api/app/metrics/router.py`; the worker continues to use `system_session()` with `SET LOCAL ROLE ftm_worker` for pseudonym resolution and metric writes.

## Phase 4: Testing / Verification

- [x] 4.1 Add registry unit tests: resolution by name, unknown-name rejection.
- [x] 4.2 Add worker unit tests: timeout handling with a deliberately slow fake function.
- [x] 4.3 Add worker unit tests: exception capture with a fake function that raises.
- [x] 4.4 Add worker unit tests: successful execution persists `raw_json` + flattened metrics under the correct `pseudonym_id`.
- [ ] 4.5 Add a real PostgreSQL integration test for `SKIP LOCKED` concurrency (two workers, one job, processed exactly once) when available.
- [x] 4.6 Add API tests for `POST /recordings/{id}/run` RLS: patient/medical allowed, technician denied.
- [x] 4.7 Add API test/assertion coverage for current-result overwrite behavior via worker persistence helpers.
- [x] 4.8 Run `PYTHONPATH=api pytest api/tests -q` locally for this workspace.
- [ ] 4.9 If PostgreSQL is available, run `RUN_INTEGRATION=1 ... pytest api/tests/integration -q`.
