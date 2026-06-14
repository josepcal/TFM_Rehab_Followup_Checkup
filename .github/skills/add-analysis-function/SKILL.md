---
name: add-analysis-function
description: "Trigger: add metric, new audio function, register analysis, librosa/scipy, worker metric extraction. Use whenever adding FTM metrics."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## Plan

Use this workflow skill to add a new analysis function safely. Pair with `audio-dsp-python` for DSP implementation details.

## When this applies

Use when adding a new audio metric, changing metric extraction, registering a function, adding `metric_definition` rows, or changing worker execution.

## Steps

1. Define the metric purpose and map it to `analysis_setup` / `metric_definition` (SDD §7.2).
2. Put function code under `analysis/functions/` if that path exists; otherwise add `> TODO (to confirm with product owner): exact analysis function package path`.
3. Register by stable versioned name such as `voice_stability_v1`.
4. Return a JSON-compatible `dict` of metrics only; no PII, no patient ID, no recording ID, no media URI, no raw audio.
5. Execute through the worker with timeout and error capture (ADR-0007).
6. Persist `raw_json`, flattened `recording_metric` rows and traceability fields: `function_name`, `function_version`, `code_sha`, `status`, `error_detail` (ADR-0009).
7. Add unit tests for the function and worker/persistence tests for success and error.

## Minimal snippet

```python
# TODO (to confirm with product owner): exact registry API is not specified by SDD/ADR.
# Expected shape if the project adopts a decorator:
# @register_analysis("voice_stability_v1")
def voice_stability_v1(audio_path: str) -> dict[str, float | int | str | None]:
    return {"voice_stability.score": 0.0}
```

## Files and paths

- `analysis/functions/` — requested function location; verify path.
- `setup.analysis_setup` and `setup.metric_definition` — configuration source.
- `metrics.metric_result` and `metrics.recording_metric` — persistence target.
- `.github/skills/audio-dsp-python/SKILL.md` — audio processing rules.

## Validation checklist

- [ ] Function name is versioned with `_vN` or equivalent explicit version.
- [ ] Output is metrics-only and contains no PII.
- [ ] Worker timeout/error path stores `status=error`.
- [ ] `code_sha` and function version are persisted.
- [ ] Tests cover valid audio, corrupt audio and expected metric keys.

## Common mistakes

- Adding runtime upload/execution of arbitrary code; ADR-0008 forbids it.
- Changing a metric's meaning without versioning the function/definition.
- Sending metric output directly to LLM without pseudonymized payload filtering.
