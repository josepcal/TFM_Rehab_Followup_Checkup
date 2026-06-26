# API Specification: Sustained Phonation Analysis Function (`sustained_phonation_v1`, UC-04)

> **Revised:** requirements now reflect the vendored `analyze_sustained_vowel`
> (Praat/parselmouth) output — five metrics instead of two. Registry/worker/trigger
> behavior is unchanged from `analysis-registry-worker-uc6` and not repeated here.
>
> **Re-revised (post task 2.4):** added a minimum-duration scenario — empirical testing
> showed degenerate input doesn't always surface as a Praat error or a NaN value; a
> short-but-technically-voiced recording needed its own explicit rejection rule.

## Purpose

Define the behavior of the `sustained_phonation_v1` analysis function: what it computes from a WAV recording via the vendored `analyze_sustained_vowel`, how it fails on degenerate input, and what it persists once executed by the D8 worker.

## Requirements

### Requirement: Compute acoustic voice-quality metrics from a sustained-vowel recording

The function MUST compute maximum phonation duration and four voice-quality measures (jitter, shimmer, HNR, intensity stability) from a single-channel WAV recording, returning all five as a flat dict.

#### Scenario: Clear sustained vowel

- GIVEN a WAV recording of a patient sustaining a vowel cleanly for approximately 12 seconds
- WHEN `sustained_phonation_v1` is executed against it
- THEN it returns a dict with `phonation_duration_sec`, `jitter_local_pct`, `shimmer_local_pct`, `hnr_db`, and `volume_std_db`
- AND all five values are finite numbers in clinically plausible ranges.

#### Scenario: Noisy but usable recording

- GIVEN a WAV recording with audible background noise but a clearly voiced phonation segment
- WHEN `sustained_phonation_v1` is executed against it
- THEN it returns a result without raising
- AND `jitter_local_pct`/`shimmer_local_pct` are higher and `hnr_db` is lower than for an equivalent clean recording.

### Requirement: Normalize input encoding before analysis

The function MUST attempt to normalize the input WAV to mono 16-bit PCM before analysis, to handle non-standard encodings (32-bit float, odd sample rates) that some recording devices produce despite the `.wav` extension.

#### Scenario: Standard PCM WAV input

- GIVEN a recording already in mono 16-bit PCM format
- WHEN `sustained_phonation_v1` is executed
- THEN normalization is a no-op (cached or pass-through) and analysis proceeds as normal.

#### Scenario: Non-standard WAV input with `ffmpeg` available

- GIVEN a recording with a 32-bit float or otherwise non-standard WAV encoding
- WHEN `sustained_phonation_v1` is executed and `ffmpeg` is available on the worker
- THEN the file is re-encoded to mono 16-bit PCM before analysis
- AND the analysis proceeds without error attributable to encoding.

#### Scenario: `ffmpeg` unavailable

- GIVEN `ffmpeg` is not installed on the worker
- WHEN `sustained_phonation_v1` is executed against a standard WAV recording
- THEN normalization falls back to the original file
- AND analysis still completes for files Praat can already read directly.

### Requirement: Reject degenerate input instead of returning misleading zeros or NaNs

The function MUST raise `InsufficientSignalError` rather than return a result with zero phonation duration or any NaN-valued metric, so that a signal problem is never recorded as a clinical attempt.

#### Scenario: Silence-only recording

- GIVEN a WAV recording containing no voiced speech
- WHEN `sustained_phonation_v1` is executed against it
- THEN it raises `InsufficientSignalError`, whether the underlying cause is a Praat error or a degenerate (zero-duration / NaN) result
- AND no metric values are returned.

#### Scenario: Worker persists the failure as an error state

- GIVEN `sustained_phonation_v1` raises `InsufficientSignalError` for a given job
- WHEN the D8 worker's existing exception-capture path handles it
- THEN `metric_result.status` is set to `error` with an `error_detail` describing insufficient signal
- AND no `raw_json` or `recording_metric` rows are persisted for that execution
- AND the worker continues processing subsequent jobs without crashing.

#### Scenario: Technically voiced but too short to be a valid attempt

- GIVEN a WAV recording with a real, detectable voiced segment shorter than the configured minimum duration (default `1.0` second, via `params.min_duration_sec`)
- WHEN `sustained_phonation_v1` is executed against it
- THEN it raises `InsufficientSignalError`, even though no individual metric value is NaN and no underlying Praat error occurred
- AND the error message distinguishes this from the silence/NaN case, attributing the rejection to insufficient duration.

### Requirement: Output is deterministic for a given input

The function MUST return the same result every time it is run against the same WAV file with the same `params`, so that reanalysis (ADR-0010) overwrites with an equivalent value rather than introducing nondeterministic drift.

#### Scenario: Repeated execution on the same recording

- GIVEN a WAV recording and a fixed `params` dict
- WHEN `sustained_phonation_v1` is executed twice against the same file
- THEN both executions return identical values for all five metrics.

### Requirement: Pitch range is configurable via `params`

The function MUST read `f0min`/`f0max` from the `params` dict (sourced from `analysis_setup.function_params`), falling back to the vendored function's own defaults when absent.

#### Scenario: Default pitch range used when params is empty

- GIVEN `params = {}`
- WHEN `sustained_phonation_v1` is executed
- THEN it uses `f0min=75`, `f0max=400` Hz, matching `analyze_sustained_vowel`'s own defaults.

#### Scenario: Explicit pitch-range override

- GIVEN `params = {"f0min": 100, "f0max": 300}`
- WHEN `sustained_phonation_v1` is executed
- THEN the narrower pitch range is used for pitch-dependent measures instead of the default.

### Requirement: Declare returned metrics in `metric_definition`

The system MUST have a `metric_definition` row for each of the five keys the function returns, so each metric is labeled and weighted for downstream consumers, without that declaration being used to validate or reject the function's actual output (ADR-0008).

#### Scenario: All five declared metrics are present

- GIVEN the `metric_definition` seed for `sustained_phonation_v1`
- WHEN it is queried
- THEN it contains exactly five rows (`phonation_duration_sec`, `jitter_local_pct`, `shimmer_local_pct`, `hnr_db`, `volume_std_db`), each with a `label`, a `unit`, and a `weight`
- AND the weights sum to `1.0`.
