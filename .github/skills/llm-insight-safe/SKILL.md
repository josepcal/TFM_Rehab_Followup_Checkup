---
name: llm-insight-safe
description: "Trigger: LLM insight, AI payload, pseudonymization, privacy leak, prompt, metrics.v_ai_payload. Use for every FTM LLM call."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## Plan

Use this workflow skill to call the LLM without crossing the anonymization boundary. This is a non-negotiable privacy control.

## When this applies

Use for AI insight generation, prompt construction, LLM provider integration, payload tests, pseudonymized metrics and data egress review.

## Steps

1. Read only from `metrics.v_ai_payload` or equivalent pseudonymized metrics interface (ADR-0013).
2. Build structured input: `{ pseudonym_id, exercise, criteria, current_metrics, history }`.
3. Exclude identity, names, national IDs, `recording_id`, `media_uri`, audio and raw clinical free text.
4. Run insight asynchronously and make the feature optional; core flow must work without AI (ADR-0007, SDD AC-12).
5. Store output in `metrics.ai_insight` linked to `metric_result`, not to identified patient data directly.
6. Confirm EU processing and no-training terms before provider use (ADR-0015, ADR-0019).

## Minimal IO contract

```json
{
  "pseudonym_id": "uuid",
  "exercise": "stable exercise label or code",
  "criteria": "reviewed criteria from analysis setup",
  "current_metrics": {"metric.path": 1.23},
  "history": [{"relative_day": -7, "metrics": {"metric.path": 1.0}}]
}
```

## Files and paths

- `metrics.v_ai_payload` — only AI-readable DB interface.
- `metrics.ai_insight` — persistence target.
- `Architecture.md` — anonymization boundary.

## Validation checklist

- [ ] Payload has no identity, PII, raw clinical text, audio, `recording_id` or `media_uri`.
- [ ] Payload uses pseudonymized metrics only.
- [ ] LLM call is async and optional.
- [ ] Provider region/no-training assumptions are documented.
- [ ] Tests assert forbidden fields are absent.

## Common mistakes

- Joining from `metrics` back to `clinical` to enrich a prompt.
- Sending raw JSON that contains more than declared metrics.
- Treating pseudonymization as anonymization for GDPR purposes.
