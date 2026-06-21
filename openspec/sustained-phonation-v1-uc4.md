# Explore: Sustained Phonation Analysis Function (`sustained_phonation_v1`, UC-04)

## User Need

Per the FTM implementation plan (D9) and ADR-0008, the system needs its **first real technician-authored audio-analysis function**: `sustained_phonation_v1`, covering exercise #1 (fonación sostenida). The function must turn a patient's WAV recording into two acoustic metrics — maximum phonation duration and F0 (pitch) stability — and flow end-to-end through the registry/worker infrastructure built in D8 (`analysis-registry-worker-uc6`) into `metric_result`/`recording_metric`, tagged by pseudonym.

This is the first time the D8 worker actually executes something non-trivial. Until now the registry has been empty (per the D8 implementation checkpoint, "existing reference functions were preserved" as placeholders); this slice replaces that placeholder with a clinically meaningful function and proves the full pipeline (`WAV in object storage → worker → registry → metrics in DB`) with real signal processing.

## Current State

- D8 delivered the registry (`app/analysis/registry.py`), the job queue (`metrics.analysis_job`, `SKIP LOCKED`), the worker loop (dequeue → resolve pseudonym → resolve function → timeout/error capture → persist), and the API surface (`POST /recordings/{id}/run`, `GET /recordings/{id}/metrics`) — all already merged per the D8 tasks checkpoint.
- `app/analysis/functions/__init__.py` exists as the deploy-time import point but registers no real function yet.
- Exercise #1 seed (D1 migration, per FTM plan §12) already wires `analysis_setup` for "Fonación sostenida" to reference this function by name — **terminology note:** ADR-0008 names the column `metric_api_endpoint`, while the D8 design doc refers to the same concept as `analysis_setup.function_name`. Both describe "the registered name the worker resolves," but the exact column name needs reconciling against the actual `ftm_schema.sql`/`models.py` before this slice ships (see Open Questions).
- ADR-0008 also establishes `metric_definition` as part of the implemented data layer — it declares which metrics a function returns, "con composición ponderada" (weighted composition). No function has populated it with real rows yet; `sustained_phonation_v1` will be the first.
- No audio fixtures exist yet in the test suite (`tests/fixtures/audio/` does not exist).

## Constraints

- The function must return a plain `dict`; the system does not interpret or validate its semantic content (ADR-0008) — `metric_definition` is descriptive metadata for UI/reporting, not a runtime schema gate.
- Traceability fields (`function_name`, `function_version`, `code_sha`, `status`, `error_detail`) are already handled generically by the D8 worker; this slice only needs to declare a `FUNCTION_VERSION` constant for the function itself (ADR-0009).
- Reanalysis overwrites the single `metric_result` row for the recording; no history is created (ADR-0010, accepted debt).
- The function runs inside the existing worker timeout (ADR-0007); it must not perform its own retries or background I/O beyond reading the WAV.
- No PII may appear in the returned dict or in logs emitted by the function (ADR-0013) — it receives only a `wav_path` and a `params` dict, never patient identity.
- Upstream SNR/duration validation ("nivel mínimo de SNR", per the FTM plan D10 task) is explicitly **out of scope** for this slice — D10 owns that gate. This function must still fail safely (raise, not crash the worker or silently fabricate a result) on degenerate input, since D10 lands after D9.

## Options Considered

| Concern | Option | Pros | Cons |
|---|---|---|---|
| Voiced-segment detection (for phonation duration) | `librosa.effects.split` (energy/top_db threshold) | No new dependency; matches the FTM plan §6.1 reference snippet; simple to reason about and tune | Sensitive to background noise; a single `top_db` threshold may not generalize across microphones |
| Voiced-segment detection | WebRTC VAD / ML-based VAD | More robust to noise | New dependency, more tuning surface, disproportionate for a single MVP exercise |
| Pitch tracking (for F0 stability) | `librosa.pyin` (probabilistic YIN) | Built into librosa (already a dependency); handles voiced/unvoiced detection natively (`voiced_flag`), robust to mild noise | Slower than plain autocorrelation; needs an `fmin`/`fmax` range tuned to human voice |
| Pitch tracking | Plain autocorrelation / `librosa.yin` | Faster | No native voiced/unvoiced flag — would need a separate VAD pass, duplicating work `pyin` already does |
| Stability metric definition | Coefficient of variation (`1 - std/mean` of voiced F0 frames, clipped to [0,1]) | Scale-invariant across patients with different baseline pitch (matches the FTM plan §6.1 sketch) | Undefined when there are zero voiced frames — must be handled explicitly, not divided-by-zero |

## Decision

Implement `sustained_phonation_v1` per the FTM plan's §6.1 reference sketch, hardened for real input: `librosa.effects.split` for voiced-segment duration, `librosa.pyin` (bounded to a human-voice `fmin`/`fmax` range) for F0 tracking, and the coefficient-of-variation formula for stability — with an explicit guard that raises (rather than returns degenerate zeros) when no voiced frames are detected, since "zero seconds of phonation" and "no usable signal" are clinically different outcomes and must not be conflated in `metric_result`.

Register two `metric_definition` rows for this function (`phonation_seconds`, `f0_stability`) with placeholder equal weighting (0.5/0.5) for the "composición ponderada" ADR-0008 describes, pending real clinical weighting guidance (see Open Questions) — this keeps the data model populated and correct in shape without inventing a clinical scoring formula that hasn't been signed off.

## Out of Scope

- `breathing_cadence_v1` and `ddk_rate_v1` — FTM plan D13, same registration pattern.
- SNR/duration validation gate before a recording is eligible for analysis — FTM plan D10.
- The LLM insight call and its prompt/contract — ADR-0013, FTM plan D11–D12, `app/ai/`.
- Reanalysis history/versioning — ADR-0010, explicit accepted debt, not re-litigated here.
- Calibrating clinical thresholds (target phonation seconds, what counts as "stable" F0) — that lives in the LLM `criteria` payload (FTM plan §6.2), not in this function.

## Open Questions

- **Schema field reconciliation:** does `analysis_setup` actually expose `metric_api_endpoint` (per ADR-0008) or `function_name` (per the D8 design doc)? Needs a quick check against the live `ftm_schema.sql`/`models.py` before wiring the seed row for exercise #1 — naming this wrong silently breaks the resolver.
- **`metric_definition` weighting:** are the 0.5/0.5 placeholder weights acceptable to ship, or does this need clinical sign-off before D9 closes? If a composite "exercise score" already consumes these weights downstream (UC-07/UC-08), shipping placeholders could leak into a report before they're correct.
- **Degenerate-input contract:** should "zero voiced frames detected" surface as `metric_result.status=error` (this slice's current decision) or as a valid `phonation_seconds=0.0` result? Affects how UC-07 reports render a patient's failed attempt vs. a recording problem.
- **`top_db` / `fmin`/`fmax` defaults:** are the values lifted from the FTM plan §6.1 sketch (`top_db=30`, voice range `C2`–`C7`) good enough for MVP, or do they need tuning against real patient recordings before D10's hardening pass?
