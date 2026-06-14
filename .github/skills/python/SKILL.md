---
name: python
description: "Trigger: Python 3.12, package code, services, worker logic, pytest, domain exceptions. Use for FTM Python conventions even when not asked."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## Plan

Use this skill for Python implementation style in FTM. Keep architectural rules in `Architecture.md`; this file only defines coding conventions.

## When this applies

Use for backend modules, workers, domain services, test helpers, package layout, typing, exceptions and Python refactors.

## Steps

1. Read `Architecture.md` and identify the bounded context: `iam`, `clinical`, `recording`, `metrics`, `analysis`, or `reporting` (ADR-0001).
2. Keep domain code independent from web framework details when practical; routers call services, services call adapters/repositories.
3. Use Python 3.12 typing. Prefer explicit return types, dataclasses or Pydantic models for boundary objects.
4. Use async only where the framework or IO path requires it; do not fake async around synchronous SQLAlchemy sessions.
5. Raise domain-specific errors or FastAPI `HTTPException` only at API/validation boundaries.
6. Test with `pytest`; use fake repositories for fast service tests and PostgreSQL integration tests for RLS/schema behavior.

## Minimal patterns

```python
from dataclasses import dataclass
from uuid import UUID

@dataclass(frozen=True)
class MetricValue:
    metric_path: str
    value_num: float | None
    is_null: bool
```

## Files and paths

- `api/app/<context>/` — backend bounded-context package.
- `api/tests/` — fast unit/service tests.
- `api/tests/integration/` — DB-backed tests.
- `Architecture.md` — source for architecture constraints.

## Validation checklist

- [ ] Code belongs to one bounded context or crosses contexts through a service boundary.
- [ ] Types are explicit; avoid untyped dicts outside boundary payloads.
- [ ] Tests cover success and failure paths.
- [ ] No credentials, PII-to-LLM payloads, or raw audio leaks were introduced.
- [ ] Any missing command/tooling detail is marked TODO, not invented.

## Common mistakes

- Putting SQLAlchemy query logic directly in routers.
- Sharing database models across modules as a shortcut.
- Adding runtime code loading for analysis functions; functions must ship by PR + deploy (ADR-0008).
