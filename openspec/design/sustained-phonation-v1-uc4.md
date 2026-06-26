# Design: Sustained Phonation Analysis Function (`sustained_phonation_v1`, UC-04)

> **Revised:** wraps the vendored `analyze_sustained_vowel` (Praat/parselmouth) instead of
> a librosa-only implementation. Registry, job queue, worker loop and API endpoints are
> unchanged from D8 — this revision only changes what runs *inside* the registered function.
>
> **Re-revised (post task 2.4):** the degenerate-input guard below reflects task 2.4's
> empirical characterization, not the original assumption. Silence does **not** raise
> `parselmouth.PraatError` — it returns `phonation_duration_sec=0.0` and NaN values.
> A short/quiet but technically-voiced sample returns cleanly with neither an exception
> nor a NaN — duration alone isn't a reliable enough signal, hence the added
> `MIN_VOICED_SECONDS` floor.

## Technical Approach

Vendor `dysarthria_analysis.py` unmodified as `app/analysis/vendor/dysarthria_analysis.py`. Add one new thin adapter module, `app/analysis/functions/voice.py`, that registers `sustained_phonation_v1` with the D8 registry and delegates the actual signal processing to the vendored `analyze_sustained_vowel`. The adapter's job is narrow: normalize the input file, call the vendored function, guard against degenerate/failed analysis, and return its dict untouched — it does not reinterpret or rescale any value.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|---|---|---|---|
| Source of the analysis logic | Vendor `analyze_sustained_vowel` from the uploaded `dysarthria_analysis.py` | Reimplement from the FTM plan §6.1 sketch | Clinically validated (jitter/shimmer/HNR are standard dysphonia/MDVP-style measures), already written for this exact patient population, and sets up D13's DDK exercise for free. |
| Vendoring granularity | Whole file, under `app/analysis/vendor/`, imported but not restyled | Extract only `analyze_sustained_vowel` + helpers into FTM-owned code | Keeps a single diffable source against future updates to the script; the unused portions (NORMS, scoring, tracker, CLI) cost nothing at runtime since nothing imports them. |
| What gets called from the vendored file | Only `analyze_sustained_vowel` + `ensure_pcm_wav` (this slice); `load_sound`/`_voiced_intensity_std` are internal to `analyze_sustained_vowel` already | Also wire in `score_domains`/`NORMS` for a composite score | Scoring/interpretation belongs to the LLM insight module (UC-06) and `metric_definition` metadata, not hardcoded into the agnostic extraction function (ADR-0008) — see the Explore doc's Decision. |
| Input normalization | Call `ensure_pcm_wav(wav_path)` before analysis | Trust the WAV as uploaded | UC-05 recordings are nominally WAV, but browsers/devices can produce non-standard headers (32-bit float, odd sample rates); `ensure_pcm_wav` is defensive and degrades gracefully (warns, returns original path) if `ffmpeg` is missing — no hard new failure mode introduced. |
| Degenerate-input guard | Adapter checks the returned dict (`phonation_duration_sec <= 0` or any NaN value) **and** catches `parselmouth.PraatError`, raising `InsufficientSignalError` in either case | Trust whatever `analyze_sustained_vowel` returns, including NaNs | Same rationale as the original design: a signal problem (silence, bad mic) must not be recorded as a clinical "zero/NaN" result. The vendored function has no such guard itself, so the adapter owns it. |
| `f0min`/`f0max` | Read from `params`, default to the vendored function's own defaults (`75`/`400` Hz) | Hardcode FTM-specific defaults | No clinical basis yet to override the vendored script's defaults (open question in Explore doc) — pass through `analysis_setup.function_params` unchanged. |
| New dependencies | `praat-parselmouth` (pip) added to backend requirements; `ffmpeg` added to the **worker** container image only | Skip `ffmpeg`, rely on the graceful fallback | `ffmpeg` is optional per the vendored code's own design, but shipping it removes a silent-degradation path for a one-line Dockerfile change — flagged as an open question on timing (D9 vs. D10), not contested on whether to do it. |

## Data Flow

Unchanged from D8 at the worker/queue level; only the inside of the function call changes:

```text
Worker (from D8, unchanged)
  -> Dequeues job { recording_id, function_name }
  -> Resolves pseudonym_id (role ftm_worker)
  -> registry.run("sustained_phonation_v1", wav_path, params)
       -> app/analysis/functions/voice.py: sustained_phonation(wav_path, params)
            -> ensure_pcm_wav(wav_path)                       [vendored]
            -> analyze_sustained_vowel(normalized_path,
                                        f0min=params.get("f0min", 75),
                                        f0max=params.get("f0max", 400))  [vendored]
            -> guard: raise InsufficientSignalError on
                      PraatError / phonation_duration_sec<=0 / NaNs
            -> returns {phonation_duration_sec, jitter_local_pct,
                        shimmer_local_pct, hnr_db, volume_std_db}
  -> On success: persists metric_result(raw_json=<dict above>, function_version="v1", ...)
                 + flattened recording_metric rows (5 rows now, not 2)
  -> On InsufficientSignalError (or any exception): persists metric_result(status=error, error_detail=...)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `api/app/analysis/vendor/dysarthria_analysis.py` | Create | Unmodified copy of the uploaded script. Treated as third-party; not restyled to FTM conventions. |
| `api/app/analysis/functions/voice.py` | Create | `sustained_phonation(wav_path, params) -> dict`, decorated `@register_analysis("sustained_phonation_v1")`; `FUNCTION_VERSION = "v1"`; calls into the vendored module; owns the `InsufficientSignalError` guard. |
| `api/app/analysis/functions/__init__.py` | Modify | Import `voice` so the decorator runs at process start. |
| `api/app/analysis/errors.py` | Create/Modify | Add `InsufficientSignalError` alongside the existing `UnknownAnalysisFunction` (D8). |
| `api/requirements.txt` (or `pyproject.toml`) | Modify | Add `praat-parselmouth`. |
| `worker/Dockerfile` (or shared base image) | Modify | Add `ffmpeg` via `apt-get install` — worker image only, not the API image. |
| `api/seed/metric_definitions.sql` | Create/Modify | Insert 5 `metric_definition` rows for `sustained_phonation_v1` (see below) — pending resolution of the Explore doc's "domain grouping" open question. |
| `api/tests/fixtures/audio/` | Create | Clear sustained vowel, silence-only, short/borderline, and noisy-background WAV fixtures. |
| `api/tests/test_sustained_phonation.py` | Create | Adapter tests against the fixtures, including the PraatError-vs-NaN determination (see Testing Strategy). |
| `api/tests/test_worker.py` | Modify | One real (non-fake) job against `sustained_phonation_v1`, asserting `metric_result` shape with 5 flattened metrics. |

## Interfaces / Contracts

```python
# app/analysis/functions/voice.py
import math
import parselmouth

from app.analysis.registry import register_analysis
from app.analysis.errors import InsufficientSignalError
from app.analysis.vendor.dysarthria_analysis import analyze_sustained_vowel, ensure_pcm_wav

FUNCTION_VERSION = "v1"

# Empirically determined (task 2.4): a silence-only WAV does NOT raise an exception —
# analyze_sustained_vowel returns phonation_duration_sec=0.0 and NaN for
# jitter/shimmer/hnr. A very short or very low-amplitude *voiced* sample also returns
# cleanly (no exception, no NaN), so duration/NaN checks alone don't catch it — hence
# the explicit minimum-duration floor below. PraatError is kept as a defensive catch
# for malformed/corrupt files, not as the primary degenerate-signal path.
MIN_VOICED_SECONDS = 1.0  # engineering default, not clinically validated — see Open Questions


@register_analysis("sustained_phonation_v1")
def sustained_phonation(wav_path: str, params: dict) -> dict:
    normalized_path = ensure_pcm_wav(wav_path)

    try:
        result = analyze_sustained_vowel(
            normalized_path,
            f0min=params.get("f0min", 75),
            f0max=params.get("f0max", 400),
        )
    except parselmouth.PraatError as e:
        # Defensive only — not observed for silence/short/quiet input in task 2.4's
        # characterization; covers malformed/corrupt audio instead.
        raise InsufficientSignalError(f"Praat analysis failed: {e}") from e

    min_duration = params.get("min_duration_sec", MIN_VOICED_SECONDS)
    duration = result.get("phonation_duration_sec", 0)

    if duration < min_duration or any(
        v is None or (isinstance(v, float) and math.isnan(v))
        for v in result.values()
    ):
        raise InsufficientSignalError(
            f"No usable voiced signal detected (duration={duration}s, "
            f"min required={min_duration}s)."
        )

    return result
    # -> {"phonation_duration_sec": ..., "jitter_local_pct": ...,
    #     "shimmer_local_pct": ..., "hnr_db": ..., "volume_std_db": ...}
```

```sql
-- metric_definition seed (illustrative; exact columns per the live ftm_schema.sql,
-- and pending the Explore doc's open question on domain grouping)
INSERT INTO setup.metric_definition (function_name, metric_key, label, unit, weight) VALUES
  ('sustained_phonation_v1', 'phonation_duration_sec', 'Tiempo máximo de fonación', 's',       0.2),
  ('sustained_phonation_v1', 'jitter_local_pct',       'Jitter (perturbación de F0)', '%',      0.2),
  ('sustained_phonation_v1', 'shimmer_local_pct',      'Shimmer (perturbación de amplitud)', '%', 0.2),
  ('sustained_phonation_v1', 'hnr_db',                 'Relación armónico-ruido (HNR)', 'dB',   0.2),
  ('sustained_phonation_v1', 'volume_std_db',          'Estabilidad de volumen', 'dB',          0.2);
```

> Equal placeholder weights again, same caveat as before — five metrics now instead of two, still pending clinical sign-off, and now additionally complicated by the fact that they span two different clinical constructs (respiratory support vs. voice stability) per the Explore doc's open question.

## Authorization Rules

Unchanged from D8 — no new endpoints, no new roles. The adapter runs inside the same `ftm_worker`-scoped execution path; it receives only a `wav_path` and `params`, never patient identity.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|--------------|----------|
| Adapter — happy path | Clear sustained-vowel fixture (~12s) yields all five metrics in clinically plausible ranges (cross-check loosely against the vendored script's own `NORMS` good/poor bounds, without importing `NORMS` into production code) | Unit test against a checked-in WAV fixture, range-based assertions. |
| Adapter — silence | Silence-only fixture: **first determine empirically** whether `analyze_sustained_vowel` raises `PraatError` or returns NaNs/zeros, then assert the adapter converts either outcome into `InsufficientSignalError` | Unit test; this also resolves the Explore doc's open question and should update this doc once known. |
| Adapter — too short | ~0.3s fixture must raise via the `MIN_VOICED_SECONDS` floor specifically — task 2.4's characterization confirmed the vendored function returns a real, non-NaN, non-zero result for short/quiet voiced input without raising, so the duration/NaN checks alone would *not* catch this case. Assert the error message attributes the failure to the duration floor, not to a NaN/exception path, to confirm the right guard fired. | Unit test. |
| Adapter — noisy | Fixture with background noise still returns a result without raising, with worse (higher jitter/shimmer, lower HNR) values than the clean fixture | Unit test, range-based. |
| Adapter — determinism | Same fixture processed twice yields identical output | Unit test. |
| Adapter — `ensure_pcm_wav` fallback | With `ffmpeg` unavailable (mock `shutil.which` to return `None`), the adapter still completes on a standard WAV fixture, using the original path | Unit test, confirms the graceful-degradation path doesn't break the pipeline. |
| Worker integration | A real job against `sustained_phonation_v1` produces `metric_result.status=success` with 5 `recording_metric` rows under the correct `pseudonym_id` | Extends `test_worker.py`. |
| `metric_definition` seed | 5 rows exist for `sustained_phonation_v1`; weights sum to `1.0` | Data assertion test. |

## Migration / Rollout

No change to the D8 worker/registry deployment story (ADR-0018) — this ships as a normal deploy with two additions: (1) a `praat-parselmouth` pip dependency in the API/worker image, and (2) an `ffmpeg` apt package in the **worker** image specifically (no need to bloat the API image, which never touches audio). Until this PR, `analysis_setup` referenced a function name the registry didn't recognize, so this can only fix a previously-broken path, not regress a working one. Confirm the worker image still builds within reasonable size/time after adding parselmouth (it bundles a compiled Praat binary) — flag if this meaningfully affects deploy time on the 20-day timeline.
