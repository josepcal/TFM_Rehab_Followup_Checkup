---
name: containers-and-nginx
description: "Trigger: Docker, docker-compose, nginx, /api, /realms, TLS, container deploy. Use for FTM local/prod topology changes."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## Plan

Use this skill for container topology and nginx routing. Do not invent infrastructure providers or secret-store details not present in ADRs.

## When this applies

Use for Dockerfiles, compose files, nginx routing, TLS/CORS/HSTS/CSP, container wiring, local topology and deployment changes.

## Steps

1. Preserve the ADR topology: nginx routes `/`, `/api`, and `/realms` (ADR-0018).
2. Keep `postgres-app` separate from `postgres-keycloak` (ADR-0005).
3. Add `api`, `worker`, `postgres-app` and private object storage integration around the existing Keycloak stack.
4. Keep media storage private and EU-region capable.
5. Do not commit secrets; use the configured secret mechanism.
6. Document any unconfirmed command or provider as TODO.

## Minimal topology

```text
nginx -> /      -> SPA
nginx -> /api   -> FastAPI
nginx -> /realms -> Keycloak
```

## Files and paths

- `infra/` — expected IaC path; verify exact current path.
- `bbdd_dev_setup/` — current local DB/Keycloak setup path.
- `.github/workflows/` — CI workflow path if used.

## Validation checklist

- [ ] nginx routes `/`, `/api`, `/realms` correctly.
- [ ] App and Keycloak databases are separate.
- [ ] Worker can reach app DB and object storage without exposing media publicly.
- [ ] TLS/security headers are preserved at nginx.
- [ ] Missing provider/secret details are TODOs.

## Common mistakes

- Pointing Keycloak and app at the same PostgreSQL database.
- Exposing object storage publicly instead of using signed URLs.
- Baking secrets into compose or workflow files.
