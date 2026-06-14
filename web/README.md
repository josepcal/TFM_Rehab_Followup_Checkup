# FTM Web UI

Frontend SPA for the doctor-facing UC-01 Diagnostic Assessment flow.

## Local development

Run the API on `http://localhost:8000` and then start Vite:

```bash
cd web
npm install
npm run dev
```

Open `http://localhost:5173`.

Vite exposes browser calls under `/api/*` and rewrites them to the local FastAPI routes (`/patients`, `/diagnostics/`, ...).

## Resolved UI integration decisions

| Topic | Decision | Notes |
|---|---|---|
| Patient endpoint | Use existing `GET /patients` | Backend RLS/auth decides visible patients. |
| Diagnostic history | Use `GET /diagnostics/?patient_id=<id>` | The UI also filters defensively by `patient_id` until the backend contract is hardened. |
| Auth mode | `createBrowserAuthClient()` uses dev/mock auth locally | Production Keycloak wiring remains behind `web/src/auth/authClient.ts`. |
| Test runner | Vitest + Testing Library | Matches Vite and covers component/API-client scenarios. |
| Pagination envelope | Normalize both `data` and `items` | Current backend returns `data`; OpenSpec/design tolerated drift. |

## Useful scripts

```bash
npm run lint
npm test
npm run build
```

## Scope

In scope: UC-01 AC-01 and AC-03 for medical users.

Out of scope: UC-02 programs/exercises, recordings, metrics, reports, patient UI, and LLM insight.
