# Tasks: Doctor Diagnostic UI (UC-01)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~900-1,200 (scaffold + auth/API + UI + tests + CI) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR #1 Foundation → PR #2 AC-01 history → PR #3 AC-03 create/detail/edit |
| Delivery strategy | auto-chain |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Scaffold `web/` frontend foundation | PR #1 | Base: feature/tracker branch; includes auth/API/test setup. |
| 2 | Deliver AC-01 patient selection + history | PR #2 | Base: PR #1 branch; component tests included. |
| 3 | Deliver AC-03 create/detail/edit | PR #3 | Base: PR #2 branch; mutation tests included. |
| 4 | Add CI/deploy wiring polish | PR #3 or PR #4 | Split if needed. |

## Phase 1: Frontend Foundation

- [x] 1.1 Create `web/package.json`, `web/vite.config.ts`, `web/tsconfig.json` for React 18 + Vite + TS.
- [x] 1.2 Create `web/src/main.tsx` and `web/src/App.tsx` with a minimal UC-01 shell.
- [x] 1.3 Create `web/src/auth/authClient.ts` with Keycloak boundary and test/dev mock.
- [x] 1.4 Create `web/src/api/http.ts` with bearer token and typed errors.
- [x] 1.5 Add lint/test/build scripts.

## Phase 2: Typed API Contracts

- [ ] 2.1 Create `web/src/api/diagnostics.ts` with DTOs and list/detail/create/patch calls.
- [ ] 2.2 Create `web/src/api/patients.ts` with `PatientOut` and lookup/list call.
- [ ] 2.3 Normalize `items`/`data` paginated responses.
- [ ] 2.4 Test DTO normalization and typed errors.

## Phase 3: AC-01 Patient Selection and History

- [ ] 3.1 Create `DiagnosticWorkspace.tsx` as UC-01 container.
- [ ] 3.2 Create patient selector/search states.
- [ ] 3.3 Create history list refresh on patient change.
- [ ] 3.4 On 403, clear stale records and show auth error.
- [ ] 3.5 Add G/W/T component tests for `UC-01 AC-01`.

## Phase 4: AC-03 Create, Detail, and Edit

- [ ] 4.1 Create diagnostic form; never render/send `doctor_id`.
- [ ] 4.2 Wire `POST /diagnostics/` and refresh/show detail.
- [ ] 4.3 Create detail card using `GET /diagnostics/{diagnostic_id}`.
- [ ] 4.4 Create edit form using `PATCH /diagnostics/{diagnostic_id}`.
- [ ] 4.5 Display returned attestation fields.
- [ ] 4.6 Add G/W/T tests for `UC-01 AC-03`: create, validation, 404, detail, edit, 403.

## Phase 5: Integration and CI

- [ ] 5.1 Add query hooks in `web/src/features/diagnostics/hooks.ts` with invalidation.
- [ ] 5.2 Update `.github/workflows/ci.yml` for conditional `web/` lint/test/build.
- [ ] 5.3 Run frontend build/tests and existing API tests.
- [ ] 5.4 Resolve TODOs: patient endpoint, auth mode, test runner, `items` vs `data`.
