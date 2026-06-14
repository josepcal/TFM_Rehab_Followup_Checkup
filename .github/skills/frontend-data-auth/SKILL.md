---
name: frontend-data-auth
description: "Trigger: TanStack Query, keycloak-js, protected routes, token refresh, Recharts. Use for FTM frontend data/auth/chart work."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## Plan

Use this skill for frontend API access, authentication and follow-up charts. Keep security authority in the backend and RLS.

## When this applies

Use for TanStack Query queries/mutations, cache keys, invalidation, Keycloak login/refresh, role-protected routes and Recharts visualizations.

## Steps

1. Use `keycloak-js` with Authorization Code + PKCE S256 as specified (ADR-0003, ADR-0004).
2. Attach bearer tokens to API calls; do not persist secrets in the repo or browser app code.
3. Use stable query keys based on resource and parameters.
4. Invalidate affected queries after mutations.
5. For charts, transform typed API data into minimal chart view models.
6. Show loading/error states and handle token refresh failures by routing to login.

## Minimal pattern

```ts
const diagnosticKey = ["diagnostics", { patientId, limit, offset }] as const;
```

## Files and paths

- `web/` — expected frontend root; verify exact current path.
- `.github/skills/react/SKILL.md` — component conventions.
- `.github/skills/typescript/SKILL.md` — strict typing.

## Validation checklist

- [ ] Query keys include all filters that affect data.
- [ ] Mutations invalidate or update relevant caches.
- [ ] Protected routes check role for UX only; backend still enforces auth.
- [ ] Charts do not reveal another patient's data.
- [ ] Token handling follows Keycloak flow and avoids committed secrets.

## Common mistakes

- Using local role checks as the only access control.
- Building chart datasets from untyped API responses.
- Forgetting empty states for no metrics or no recordings.
