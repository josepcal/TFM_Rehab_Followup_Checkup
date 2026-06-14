---
name: protect-endpoint-rbac
description: "Trigger: protected endpoint, RBAC, Keycloak JWT, JWKS, role check, RLS context. Use for every secured FastAPI route."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## Plan

Use this workflow skill when creating or reviewing protected endpoints. Pair with `fastapi` for route/schema conventions.

## When this applies

Use for JWT validation, role checks, current principal dependencies, RLS session context and authorization tests.

## Steps

1. Validate bearer JWT against Keycloak JWKS; backend is bearer-only (ADR-0004).
2. Extract `sub` and role claims; allowed roles are `medical`, `patient`, `technician`, `admin` (ADR-0004).
3. Check endpoint role before executing patient-data logic.
4. Set DB session identity/role context required by RLS before querying patient-data tables (ADR-0014).
5. Map the endpoint to an SDD UC/AC and enforce resource ownership/visibility in API code.
6. Test correct role, wrong role, missing token and forbidden resource access.

## Minimal pattern

```python
@router.get("/secure")
def secure_route(principal=Depends(require_role("medical")), db=Depends(get_db)):
    # TODO (verify): exact helper that sets app.identity_id for this DB session.
    return {"sub": principal["sub"]}
```

## Files and paths

- `api/app/auth.py` — Keycloak/JWT role dependencies.
- `api/app/db.py` — DB session and RLS context wiring.
- `api/app/**/**/*router.py` — protected routes.

## Validation checklist

- [ ] JWT is validated via JWKS, not trusted blindly.
- [ ] Role check uses ADR roles.
- [ ] DB session receives RLS identity context.
- [ ] API enforces ownership/visibility before returning data.
- [ ] Tests include correct role, wrong role and cross-resource denial.

## Common mistakes

- Treating frontend protected routes as security.
- Reading patient data before setting RLS context.
- Accepting `doctor_id` or `patient_id` from the body as authority instead of JWT-derived identity.
