# Design: Analysis Function Registry + Worker (UC-06 infra)

## Technical Approach

Two new pieces sit behind the existing `recording` slice: (1) an in-process **function registry** (`app/analysis/registry.py`) that technicians populate at deploy time via a decorator, and (2) a **worker** (`app/worker.py`) that consumes a job queue, resolves the requested function by name, executes it with a timeout, and persists the result — success or error — without ever inspecting what the returned metrics mean. The API only ever enqueues `{recording_id, function_name}`; it never executes analysis inline.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|---|---|---|---|
| Registry shape | In-process `dict[str, callable]` populated by a `@register_analysis(name)` decorator | Plugin discovery via entry points / dynamic import by string path | Matches the FTM plan reference implementation (§6.1); keeps "no runtime code upload" trivially true — everything is imported at process start. |
| Job source | Postgres table with `FOR UPDATE SKIP LOCKED` (default), interface-compatible with Redis+RQ | Celery + broker | ADR-0007 scopes this to a "cola ligera"; Postgres avoids a new IaC component for the MVP. |
| Execution isolation | In-process call with a hard timeout inside the worker container | Spawn a subprocess per job | Worker container is already the isolation boundary (ADR-0007); subprocess-per-job adds startup latency the 20-day MVP doesn't need. |
| Result cardinality | `metric_result.recording_id` UNIQUE (1:1); reanalysis overwrites | Append-only history table | ADR-0010 — explicit MVP debt, not re-litigated here. |
| Trigger authorization | `POST /recordings/{id}/run` requires patient/medical role; RLS denies technician | Allow technician to trigger their own functions | ADR-0011 — technician writes code, doesn't operate on patient data. |
| Traceability | `function_name` + `function_version` + `code_sha` + `status` + `error_detail` on every `metric_result` row | Digital signature per function | ADR-0009 — git is the chain of custody, no signing infra needed. |
| Pseudonym handling | Worker resolves `pseudonym_id` via the `ftm_worker` role before writing metrics; never calls the LLM | API resolves pseudonym before enqueueing | ADR-0013 — keeps the worker as the single point that crosses the identified/pseudonymized boundary. |

## Data Flow

```text
Doctor/Patient UI
  -> POST /recordings/{id}/run { function_name? }
  -> API checks RLS (patient/medical only; technician denied)
  -> API resolves function_name (request override, else analysis_setup.function_name for the exercise)
  -> API enqueues job { recording_id, function_name } (Postgres jobs table or RQ)
  -> API returns immediately (job accepted, not yet executed)

Worker (separate container, polling loop)
  -> Dequeues one job (SELECT ... FOR UPDATE SKIP LOCKED, or RQ pop)
  -> Resolves recording's pseudonym_id (role ftm_worker)
  -> Looks up function_name in REGISTRY
  -> Reads WAV from object storage
  -> Executes function(wav_path, params) with a timeout
  -> On success: writes metric_result(status=success, raw_json, function_version, code_sha) + flattened recording_metric rows
  -> On timeout/exception: writes metric_result(status=error, error_detail), no metrics rows
  -> Marks job done (delete row / RQ ack)

GET /recordings/{id}/metrics
  -> Returns the current metric_result for the recording (success or error state)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `api/app/analysis/registry.py` | Create | `REGISTRY` dict, `register_analysis(name)` decorator, `run(name, wav_path, params)` resolver raising `UnknownAnalysisFunction`. |
| `api/app/analysis/functions/__init__.py` | Create | Import point where technician-authored functions register themselves at process start (empty in this slice; D9/D13 add real functions here). |
| `api/app/jobs.py` | Modify | Job row model (`recording_id`, `function_name`, `status`, `attempts`, `created_at`, `locked_at`) and `SKIP LOCKED` dequeue helper. |
| `api/app/worker.py` | Modify | Polling loop: dequeue → resolve pseudonym → resolve function → execute with timeout → persist result → mark job done. |
| `api/app/metrics/models.py` | Create/Modify | `MetricResult` (`recording_id` UNIQUE, `pseudonym_id`, `function_name`, `function_version`, `code_sha`, `status`, `error_detail`, `raw_json`) and `RecordingMetric` (flattened rows) per ADR-0009/ADR-0010. |
| `api/app/recording/router.py` | Modify | Add `POST /recordings/{id}/run` (enqueue, RLS-checked) and `GET /recordings/{id}/metrics`. |
| `api/migrations/` | Create | Alembic migration for the jobs table and `metric_result`/`recording_metric` if not already present. |
| `api/tests/test_analysis_registry.py` | Create | Registry resolution, unknown-function rejection. |
| `api/tests/test_worker.py` | Create | Timeout handling, exception capture, success persistence, `SKIP LOCKED` concurrency (two workers, one job). |
| `api/tests/test_recording_run.py` | Create | `POST /recordings/{id}/run` RLS coverage (patient/medical allowed, technician denied). |

## Interfaces / Contracts

```python
# app/analysis/registry.py
REGISTRY: dict[str, Callable[[str, dict], dict]] = {}

def register_analysis(name: str):
    def deco(fn):
        REGISTRY[name] = fn
        return fn
    return deco

def run(name: str, wav_path: str, params: dict) -> dict:
    if name not in REGISTRY:
        raise UnknownAnalysisFunction(name)
    return REGISTRY[name](wav_path, params)


# app/metrics/models.py
class MetricResult(Base):
    recording_id: UUID            # UNIQUE — 1:1 with the recording (ADR-0010)
    pseudonym_id: UUID            # no FK — deleting the pseudonym map anonymizes this row (ADR-0013)
    function_name: str
    function_version: str
    code_sha: str
    status: Literal["success", "error"]
    error_detail: str | None
    raw_json: dict | None         # CHECK (status='success' => raw_json IS NOT NULL)
    extracted_at: datetime


class RunIn(BaseModel):
    function_name: str | None = None   # override; else taken from analysis_setup
```

## Authorization Rules

| Principal | Allowed |
|-----------|---------|
| Patient | Trigger run / read metrics for their own recordings only. |
| Medical | Trigger run / read metrics for recordings within their clinic's patients. |
| Technician | No access — excluded by RLS (ADR-0011); their contribution is code (registered functions), not runtime triggering. |
| Worker (`ftm_worker`) | Reads recording + resolves pseudonym; writes `metric_result`/`recording_metric`; never calls the LLM (ADR-0013). |
| AI (`ftm_ai`) | No access in this slice — reads pseudonymized metrics only via `metrics.v_ai_payload`, out of scope here. |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|--------------|----------|
| Registry | Resolution by name, unknown name raises | Unit test, no DB. |
| Worker — timeout | Function exceeding the configured timeout is marked `error` and the worker keeps processing other jobs | Unit test with a deliberately slow fake function. |
| Worker — exception | Function raising an exception is captured as `error` with `error_detail`, no crash propagates | Unit test with a fake function that raises. |
| Worker — success | Successful execution persists `metric_result` + flattened `recording_metric` under the right `pseudonym_id` | Unit test with a fake function returning a known dict. |
| Concurrency | Two worker processes against one job row never double-process it | Integration test against real PostgreSQL (`FOR UPDATE SKIP LOCKED`). |
| API — RLS | Patient/medical can trigger and read; technician is denied | API test client with seeded role fixtures. |
| Reanalysis | Re-triggering `run` on the same recording overwrites the prior `metric_result` (no history row created) | API test asserting row count stays 1 after two runs. |

## Migration / Rollout

Add the jobs table and `metric_result`/`recording_metric` via a SQL-first Alembic migration if they aren't already in `ftm_schema.sql` (ADR-0017). Deploy the worker as its own container behind the existing IaC (ADR-0018) — it has no public port. Roll out the `POST /recordings/{id}/run` endpoint behind existing JWT/RLS auth; nothing downstream depends on it until D9 registers a real function, so this can ship inert (registry empty) without breaking anything.
