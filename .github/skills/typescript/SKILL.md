---
name: typescript
description: "Trigger: TypeScript strict typing, API types, props, narrowing, no-any. Use for every FTM frontend type change."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## Plan

Use this skill to keep frontend types strict and aligned with API contracts. Do not invent schemas that are not in the API or SDD.

## When this applies

Use for TypeScript types, API response models, component props, route params, form values and type guards.

## Steps

1. Prefer generated or shared API contracts when available.
2. Use `unknown` plus narrowing instead of `any` for untrusted data.
3. Keep domain names aligned with API/DB concepts: `Diagnostic`, `RehabProgram`, `ProgramExercise`, `MetricResult`.
4. Separate transport DTOs from view models when formatting dates, labels or chart data.
5. Add exhaustive checks for role/status unions.

## Minimal pattern

```ts
type UserRole = "medical" | "patient" | "technician" | "admin";

function assertNever(value: never): never {
  throw new Error(`Unexpected value: ${value}`);
}
```

## Files and paths

- `web/src/**/*.ts` and `web/src/**/*.tsx` — expected paths; verify current frontend layout.
- `Architecture.md` — domain terminology and guardrails.

## Validation checklist

- [ ] No new `any` was introduced.
- [ ] API data is typed at the boundary.
- [ ] Role/status strings match ADR/SDD terms.
- [ ] DTO-to-view transformations are explicit.
- [ ] Missing source contract is marked TODO.

## Common mistakes

- Duplicating backend schemas manually without tracking drift.
- Treating optional nullable metric values as always numeric.
- Encoding roles not present in ADR-0004.
