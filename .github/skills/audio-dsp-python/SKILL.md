---
name: audio-dsp-python
description: "Trigger: audio DSP, WAV, librosa, scipy, soundfile, numpy, metric extraction. Use for every FTM audio metric function."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## Plan

Use this skill for audio metric code. Pair it with `add-analysis-function` when adding a registered analysis function.

## When this applies

Use for loading WAV/audio, computing metrics with Python scientific libraries, performance/memory choices and metric return contracts.

## Steps

1. Confirm the recording source comes from private object storage, not the LLM path.
2. Load only what the function needs; avoid keeping large audio arrays longer than necessary.
3. Return a plain `dict` / JSON-compatible metrics object with no identity, PII, media URI or raw audio.
4. Keep metric names stable and version the function name when behavior changes.
5. Handle corrupt audio and partial data with explicit error paths.
6. Test deterministic fixtures and edge cases such as silence, corrupt file and short duration.

## Minimal pattern

```python
def analyze_voice_sample(audio_path: str) -> dict[str, float | int | str | None]:
    """Return metrics only; never return PII or raw audio."""
    # TODO (verify): exact loader library and project registry API.
    return {"duration_seconds": 0.0}
```

## Files and paths

- `analysis/functions/` — requested location; verify exact repo path before creating.
- `.github/skills/add-analysis-function/SKILL.md` — registration and persistence workflow.

## Validation checklist

- [ ] Output contains metrics only and no PII.
- [ ] Function handles corrupt/empty/short audio.
- [ ] Tests cover expected metric keys and null behavior.
- [ ] Runtime and memory are acceptable for ~60 s audio target.
- [ ] Function code ships by PR and deploy, not runtime upload.

## Common mistakes

- Returning file paths, patient names or recording IDs in metrics.
- Letting DSP exceptions skip `status=error` persistence.
- Making metrics depend on frontend labels instead of stable metric paths.
