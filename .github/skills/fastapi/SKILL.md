---
name: fastapi
description: "Trigger: FastAPI route, endpoint, router, Pydantic v2 schema, pagination, HTTP errors. Use for every FTM API change."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## Plan

Use this skill to implement FastAPI code consistently. Link to `protect-endpoint-rbac` for authentication, RBAC and RLS details.

## When this applies

Use for routers, dependencies, request/response schemas, pagination, OpenAPI contracts, status codes and API tests.

## Steps

1. Map the endpoint to an SDD use case and acceptance criteria when possible.
2. Put request/response contracts in Pydantic v2 models; keep schemas explicit and typed.
3. Keep routers thin: dependency injection, role guard, body/query parsing, service call and response code.
4. Put orchestration in a service and persistence in an adapter/repository.
5. Use consistent HTTP errors: validation errors from Pydantic, 403 for authorization, 404 for missing resources.
6. Add tests for valid request, invalid request, unauthorized role and forbidden data access.

## Minimal pattern

```python
@router.post("/", response_model=DiagnosticOut, status_code=201)
def create_diagnostic(
    body: DiagnosticIn,
    principal=Depends(require_role("medical")),
    service: DiagnosticService = Depends(get_diagnostic_service),
):
    return service.create_diagnostic(body, principal["sub"])
```

## Files and paths

- `api/app/*/*router.py` — route definitions.
- `api/app/*/schemas.py` — Pydantic contracts.
- `api/app/*/*service.py` — orchestration.
- `.github/skills/protect-endpoint-rbac/SKILL.md` — security flow.

## Validation checklist

- [ ] Endpoint has a Pydantic request/response model where applicable.
- [ ] Endpoint has a role dependency and RLS context path when it touches patient data.
- [ ] Router does not contain persistence-heavy query logic.
- [ ] Tests include correct role and wrong role.
- [ ] OpenAPI-visible schema names are stable.

## Common mistakes

- Encoding business rules only in the route function.
- Trusting `doctor_id` or patient identity from request body instead of JWT-derived principal.
- Treating Pydantic validation status codes as product decisions without documenting them.
