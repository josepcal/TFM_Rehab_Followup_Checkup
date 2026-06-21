# API Specification: Sustained Phonation Analysis Function (`sustained_phonation_v1`, UC-04)

## Purpose

Define the behavior of the `sustained_phonation_v1` analysis function: what it computes from a WAV recording, how it fails on degenerate input, and what it persists once executed by the D8 worker — without redefining any of the registry, queueing, or trigger-authorization behavior already specified in `analysis-registry-worker-uc6`.

## Requirements

### Requirement: Compute phonation duration and pitch stability from a WAV recording

The function MUST compute the total duration of voiced phonation and a pitch-stability score from a single-channel WAV recording, returning both as a flat dict.

#### Scenario: Clear sustained vowel

- GIVEN a WAV recording of a patient sustaining a vowel cleanly for approximately 12 seconds
- WHEN `sustained_phonation_v1` is executed against it
- THEN it returns a dict with `phonation_seconds` approximately matching the voiced duration
- AND `f0_stability` between `0` and `1`.

#### Scenario: Noisy but usable recording

- GIVEN a WAV recording with audible background noise but a clearly voiced phonation segment
- WHEN `sustained_phonation_v1` is executed against it
- THEN it returns a result without raising
- AND `f0_stability` is lower than it would be for an equivalent clean recording.

### Requirement: Reject degenerate input instead of returning misleading zeros

The function MUST raise an error rather than silently return a zero-valued result when no voiced phonation is detected, so that a signal problem is never recorded as a clinical "zero seconds" attempt.

#### Scenario: Silence-only recording

- GIVEN a WAV recording containing no voiced speech (silence or pure noise floor)
- WHEN `sustained_phonation_v1` is executed against it
- THEN it raises `InsufficientSignalError`
- AND no `phonation_seconds`/`f0_stability` values are returned.

#### Scenario: Worker persists the failure as an error state

- GIVEN `sustained_phonation_v1` raises `InsufficientSignalError` for a given job
- WHEN the D8 worker's existing exception-capture path handles it
- THEN `metric_result.status` is set to `error` with an `error_detail` describing insufficient signal
- AND no `raw_json` or `recording_metric` rows are persisted for that execution
- AND the worker continues processing subsequent jobs without crashing.

### Requirement: Output is deterministic for a given input

The function MUST return the same result every time it is run against the same WAV file with the same `params`, so that reanalysis (ADR-0010) overwrites with an equivalent value rather than introducing nondeterministic drift.

#### Scenario: Repeated execution on the same recording

- GIVEN a WAV recording and a fixed `params` dict
- WHEN `sustained_phonation_v1` is executed twice against the same file
- THEN both executions return identical `phonation_seconds` and `f0_stability` values.

### Requirement: Thresholds are configurable via `params`, not hardcoded

The function MUST read its voiced-detection and pitch-range thresholds from the `params` dict (sourced from `analysis_setup.function_params`, per the FTM plan §5.2), falling back to documented defaults when absent.

#### Scenario: Default thresholds used when params is empty

- GIVEN `params = {}`
- WHEN `sustained_phonation_v1` is executed
- THEN it uses `top_db=30` for voiced-segment detection and a `C2`-`C7` pitch range, matching the FTM plan §6.1 reference defaults.

#### Scenario: Explicit `top_db` override

- GIVEN `params = {"top_db": 20}`
- WHEN `sustained_phonation_v1` is executed against a quiet recording
- THEN the tighter threshold is used for voiced-segment detection instead of the default.

### Requirement: Declare returned metrics in `metric_definition`

The system MUST have a `metric_definition` row for each key the function returns, so the metric is labeled and weighted for downstream consumers (UI, reporting), without that declaration being used to validate or reject the function's actual output (ADR-0008 — the system does not interpret metric semantics).

#### Scenario: Both declared metrics are present

- GIVEN the `metric_definition` seed for `sustained_phonation_v1`
- WHEN it is queried
- THEN it contains exactly two rows, `phonation_seconds` and `f0_stability`, each with a `label`, a `unit`, and a `weight`
- AND the weights sum to `1.0`.

#### Scenario: An undeclared key in the function's output is still persisted

- GIVEN a hypothetical future change to `sustained_phonation_v1` that adds a third key to its returned dict without a corresponding `metric_definition` row
- WHEN the worker persists the result
- THEN `metric_result.raw_json` and `recording_metric` still store the undeclared key
- AND no validation error is raised, consistent with ADR-0008's "the system does not interpret metrics" principle.
