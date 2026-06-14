# Proposal: Doctor Diagnostic UI (UC-01)

**Change Name**: `ui-medico-diagnostico-uc1`  
**Date**: 2026-06-14  
**Status**: Proposed for Specification  
**Selected Approach**: Option A — Minimal UC-01 SPA slice first

---

## Intent

Build the doctor-facing frontend for **UC-01 Diagnostic Assessment**. A medical user must be able to find/select a patient, see diagnostic history, create a diagnostic linked to that patient, view diagnostic detail, and update diagnostic fields.

This complements the existing `api-medico-diagnostico-programa` backend work and focuses only on the UI needed for SDD **AC-01** and **AC-03**.

---

## Scope

### In Scope

- React 18 + Vite + TypeScript frontend scaffold if no `web/` app exists (ADR-0003).
- Keycloak-aware app shell for medical users, with local/dev auth strategy documented (ADR-0004).
- Doctor diagnostic UI routes:
  - patient search/select entry point
  - diagnostic history list
  - create diagnostic form
  - diagnostic detail view
  - update diagnostic form
- Typed API client for UC-01 endpoints:
  - patient lookup/list endpoint used by the UI
  - `GET /diagnostics`
  - `POST /diagnostics/`
  - `GET /diagnostics/{diagnostic_id}`
  - `PATCH /diagnostics/{diagnostic_id}`
- TanStack Query loading, empty, error and mutation states (ADR-0003).
- Display of MVP attestation metadata when returned: `signature`, `signed_at`, `content_hash` (ADR-0012).
- Component/API-client tests linked to AC-01 and AC-03.

### Out of Scope

- UC-02 rehab program UI.
- Program creation, exercise assignment, catalog browsing.
- Recording UI, metrics, reports, follow-up check-ups.
- Patient-facing diagnostic UI.
- LLM insight UI.
- Qualified eIDAS signature workflow; MVP attestation display only.

---

## Capabilities

### New Capabilities

- `doctor-diagnostic-ui`: Medical user can navigate UC-01 diagnostic screens.
- `doctor-patient-diagnostic-history-ui`: Medical user can select/search a patient and view diagnostic history for AC-01.
- `doctor-diagnostic-create-ui`: Medical user can create a diagnostic for AC-03.
- `doctor-diagnostic-detail-edit-ui`: Medical user can inspect and update diagnostic detail.
- `frontend-auth-shell`: SPA shell handles medical-role access and auth state.

### Modified Capabilities

- None. This is a new frontend capability layer over the existing diagnostic API.

---

## Approach

Use **Option A** from exploration: deliver a minimal, reviewable UC-01 SPA slice.

Suggested PR split:

| PR | Goal | Notes |
|---|---|---|
| PR #1 | Frontend foundation | Scaffold React/Vite/TS app, app shell, auth adapter, API client, test setup. |
| PR #2 | Diagnostic history/search UI | Patient selector/search, diagnostic history list, loading/empty/error states. Covers AC-01. |
| PR #3 | Diagnostic create/detail/update UI | Create form, detail page, patch form, attestation metadata display. Covers AC-03. |

Preferred frontend root is `web/`, matching ADR-0003 language and common SPA convention.

> TODO (to confirm with product owner / tech lead): exact patient search endpoint and local auth testing mode.

---

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `web/` | New | React 18 + Vite + TypeScript SPA if no frontend exists. |
| `web/src/auth/` | New | Keycloak/dev auth adapter and medical-role guard. |
| `web/src/api/` | New | Typed API client for patients and diagnostics. |
| `web/src/features/diagnostics/` | New | UC-01 pages, components, forms and query hooks. |
| `web/src/routes/` | New | Diagnostic route definitions and protected route wiring. |
| `web/src/**/*.test.*` | New | Component/API-client tests for AC-01 and AC-03. |
| `.github/workflows/ci.yml` | Modified | Add frontend lint/test/build jobs when scaffold exists. |

---

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| No frontend currently exists | High | Keep PR #1 as minimal scaffold and avoid broader clinical UI. |
| Patient search API contract unclear | Medium | Start from available patient list endpoint or document backend gap before implementation. |
| API response drift | Medium | Generate/centralize typed API DTOs and add contract tests/mocks. |
| Auth complexity with Keycloak PKCE | Medium | Use adapter boundary so tests can mock auth while production uses `keycloak-js`. |
| Scope creep into UC-02 | Medium | Keep programs/exercises explicitly out of this change. |

---

## Rollback Plan

- Revert the `web/` folder and any CI frontend jobs added for this change.
- Backend API remains unchanged.
- If deployed, remove/disable the SPA route from nginx without affecting `/api` or `/realms`.

---

## Dependencies

- Existing diagnostic API from `api-medico-diagnostico-programa`.
- Patient search/list endpoint sufficient for AC-01.
- Keycloak configuration for SPA public client with Authorization Code + PKCE S256 (ADR-0004).
- Frontend package choices from ADR-0003: React 18, Vite, TypeScript, TanStack Query, Recharts, `keycloak-js`.

---

## Success Criteria

- [ ] Medical user can access UC-01 diagnostic UI after auth.
- [ ] AC-01: Doctor can find/select a patient and see diagnostic history.
- [ ] AC-03: Doctor can create a diagnostic linked to that patient.
- [ ] Doctor can view and update diagnostic detail.
- [ ] UI shows loading, empty, validation, 403 and 404 states.
- [ ] UI never asks user to input `doctor_id`; backend identity is authoritative.
- [ ] Attestation metadata is displayed when returned by API.
- [ ] Tests cover AC-01 and AC-03 with Given/When/Then naming or docstrings.
