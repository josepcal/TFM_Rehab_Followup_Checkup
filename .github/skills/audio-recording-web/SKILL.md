---
name: audio-recording-web
description: "Trigger: MediaRecorder, browser audio, WAV upload, signed URL, recording metadata, consent. Use for FTM web recording work."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## Plan

Use this workflow skill for browser recording and upload. Pair with `react`, `typescript` and `frontend-data-auth` for UI/data conventions.

## When this applies

Use for MediaRecorder, WAV/audio capture, signed upload URLs, recording metadata registration, consent UX and delete/purge flows.

## Steps

1. Require explicit patient consent before recording because voice is biometric special-category data (FR-14, FR-16, SDD §6.1).
2. Capture audio/video in the browser with `MediaRecorder` as specified for the SPA (ADR-0003).
3. Request a signed URL from the API; upload media directly to private object storage (ADR-0006).
4. Register metadata in `recording.exercise_recording`: media kind/status, URI, date, duration, sample rate, size and SHA-256 where available (SDD §7.3).
5. Do not send raw audio to the backend unless the signed upload flow requires it; never send raw audio to the LLM.
6. Implement logical deletion: purge media, keep DB row, metrics and reports (UC-13).

## Minimal flow

```text
consent -> MediaRecorder -> signed URL -> private bucket -> metadata API -> recording row
```

## Files and paths

- `web/` — expected frontend path; verify before editing.
- `api/app/recording/` — expected recording API module; verify current structure.
- `recording.exercise_recording` — metadata table.

## Validation checklist

- [ ] Consent is explicit before capture.
- [ ] Upload uses signed URL and private storage.
- [ ] Metadata is persisted without raw binary in PostgreSQL.
- [ ] Delete purges media but preserves reports/metrics.
- [ ] No LLM path receives audio or media URI.

## Common mistakes

- Uploading media to a public bucket.
- Storing WAV blobs in PostgreSQL.
- Starting recording automatically on page load.
