# Explore: Analysis Function Registry + Worker (UC-06 infra)

## User Need

Per the FTM implementation plan (D8) and ADR-0007/ADR-0008, the system needs infrastructure that lets a technician-authored audio-analysis function be invoked by name, asynchronously, without the API thread blocking and without the core system needing to understand what the function measures. A doctor or patient must be able to trigger this from a recording (UC-05 output) and later read back the resulting metrics (feeding UC-07 reports and UC-08 follow-up).

This is infrastructure-only: it does not include writing the audio-analysis functions themselves (`sustained_phonation_v1` and friends, D9/D13) or the LLM insight call (D11-D12, `app/ai/`).

## Current State

- UC-05 recording upload/registration exists; `ExerciseRecording` rows reference object-storage media (see `api-recording-ejercicio-uc5`).
- `analysis_setup` (per the data model in the FTM plan §5.2) is expected to hold `function_name`/`function_params` per exercise but is not yet wired to anything that executes.
- The repo already has placeholders for this slice per `init-report.md`: `api/app/analysis/` (functions & models), `api/app/jobs.py` (background job model), `api/app/worker.py` (background worker) — none implement registry resolution, queueing or timeout/error handling yet.
- No queue backend (Redis or a Postgres jobs table) is wired into the app yet.

## Constraints

- The system must not interpret metric semantics — it persists whatever the registered function returns (ADR-0008).
- No runtime code upload / no sandboxing: functions are deployed with the codebase via PR + review (ADR-0008, ADR-0009).
- Traceability is via git, not digital signature: every result must carry `function_name`, `function_version`, `code_sha` (ADR-0009).
- `metric_result` is 1:1 with the recording; reanalysis overwrites, it does not version (ADR-0010) — no retry/backoff policy is in scope.
- Only the patient or an authorized medical user may trigger analysis; the technician is excluded by RLS (ADR-0011).
- The worker may resolve the patient's pseudonym to tag metrics, but must never call the LLM itself — that boundary belongs to the `ai` module (ADR-0013).
- Must not block the API process (ADR-0007); heavy/slow work happens in a separate worker container.

## Options Considered

| Option | Summary | Pros | Cons |
|--------|---------|------|------|
| Redis + RQ | Dedicated lightweight queue, separate Redis container | Mature client, simple retry/inspection tooling | One more moving part in the IaC for a 20-day MVP |
| Postgres jobs table (`SKIP LOCKED`) | Reuse `postgres-app`, poll with `FOR UPDATE SKIP LOCKED` | No new infra component; jobs visible via SQL; transactional with the metric write | Worker must implement its own polling loop |
| Celery + broker | Full task framework | Battle-tested, rich features (retries, scheduling) | Disproportionate for a single job type in a 20-day MVP; ADR-0007 explicitly scopes this to a "cola ligera" |

## Decision

Build the registry as a plain in-process dict + decorator (per the FTM plan §6.1 reference implementation), and the worker as a separate container that polls a job source. Both Redis+RQ and the Postgres jobs table remain valid per ADR-0007; this slice should keep the **dequeue mechanism behind a small interface** so the choice is a config switch, not a code fork — but for the 20-day MVP, default to the **Postgres `SKIP LOCKED` table**, since it avoids adding Redis to the IaC before it's proven necessary.

## Out of Scope

- The actual audio-analysis functions (`sustained_phonation_v1`, etc.) — D9/D13.
- The `POST /recordings/{id}/insight` LLM call and `metrics.v_ai_payload` — ADR-0013, D11-D12.
- Reanalysis history/versioning — explicitly deferred per ADR-0010.

## Open Questions

- Final pick between Redis+RQ and Postgres-jobs for production (ADR-0007 leaves both open) — revisit once real load/throughput is known.
- Should `code_sha` be captured automatically at deploy time (CI writes it into an env var the worker reads) or computed at runtime via `git rev-parse`? Needs a CI decision outside this slice.
