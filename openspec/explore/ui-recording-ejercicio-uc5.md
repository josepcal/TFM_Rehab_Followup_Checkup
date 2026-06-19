# Explore: UI Recording Ejercicio (UC-05)

## User Need

Patients need a simple way to record an assigned exercise from one of their rehab programs. The v0 flow starts from the rehab program screen, opens “View exercises and record progress”, and records through a modal/dialog.

## Current State

- Patient portal can show rehab programs and assigned exercises.
- Typed frontend API clients exist for diagnostic/program flows.
- A new recording backend contract is being specified for upload URL + metadata registration.

## Constraints

- The patient must explicitly consent before capturing audio/video.
- Raw media must be uploaded only to the authorized upload target.
- UI must not send raw media or identity data to an LLM.
- Browser recording output format is browser-dependent (`audio/webm` is common).

## Options Considered

| Option | Summary | Pros | Cons |
|--------|---------|------|------|
| Inline record controls in program detail | Record directly from existing detail table | Fewer screens | Diverges from v0 and makes detail crowded. |
| Dedicated exercise recording screen | Program detail CTA opens exercise recording view | Matches v0, focused flow | Adds screen state. |
| Native file upload only | Patient selects existing video/audio | Simple implementation | Does not satisfy “record progress” dialog. |

## Decision

Use the dedicated “View exercises and record progress” screen with a modal recording dialog, keeping the existing program detail clean.

## Open Questions

- Whether video should be enabled by default or added after audio-only stabilization.
- Whether the UI should show previous recordings immediately or defer to reporting/history.
