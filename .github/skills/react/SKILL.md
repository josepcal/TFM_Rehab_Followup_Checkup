---
name: react
description: "Trigger: React 18, Vite, component, hook, UI state, page, form. Use whenever FTM frontend code is created or refactored."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## Plan

Use this skill for React UI structure. Link to `frontend-data-auth` for API data, Keycloak and charts.

## When this applies

Use for React components, hooks, pages, forms, loading/error states and UI composition.

## Steps

1. Read `Architecture.md` for the clinical flow and privacy guardrails.
2. Keep components focused: container/page components orchestrate; presentational components render.
3. Model loading, empty and error states explicitly.
4. Do not keep JWTs or secrets in component state beyond what `keycloak-js` manages.
5. Use role-aware UI only as convenience; backend authorization remains mandatory.
6. Keep recording UI mindful of explicit consent before capture (FR-14, FR-16).

## Minimal pattern

```tsx
export function LoadingState({ label }: { label: string }) {
  return <p aria-live="polite">{label}</p>;
}
```

## Files and paths

- `web/` — expected frontend root; verify exact path before editing.
- `.github/skills/frontend-data-auth/SKILL.md` — queries, auth and charts.
- `.github/skills/audio-recording-web/SKILL.md` — browser recording flow.

## Validation checklist

- [ ] Component has typed props.
- [ ] Loading, error and empty states are handled.
- [ ] Role-gated UI does not replace backend checks.
- [ ] Accessibility basics: labels, focus and contrast.
- [ ] No PII or raw audio is sent to an LLM path.

## Common mistakes

- Fetching data imperatively in multiple components instead of using a shared query pattern.
- Assuming hidden UI means secure access.
- Starting recording before consent is explicit.
