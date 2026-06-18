# Exploration: UI Setup Programa de Rehabilitación (UC-02)

**Change**: `ui-setup-programa-rehabilitacion-uc2`  
**Scope**: Frontend/UI for UC-02 rehab program setup and exercise table  
**Status**: Exploration complete

## Current State

The current React/Vite app implements the doctor UC-01 diagnostic workspace:

- `web/src/features/diagnostics/DiagnosticWorkspace.tsx` owns patient selection and screen state.
- `PatientDiagnosticRecord.tsx` shows selected patient and diagnostic history.
- `DiagnosticDetailCard.tsx` and `DiagnosticForm.tsx` handle diagnostic detail/create/edit.
- `web/src/api/diagnostics.ts` and `patients.ts` provide typed API clients.
- `web/src/features/diagnostics/hooks.ts` uses TanStack Query for patients and diagnostics.
- Styling is centralized in `web/src/styles.css`, already v0-inspired.

Backend endpoints now available for UC-02:

- `POST /programs/` creates rehab program linked to `diagnostic_id`, optional `name`, `start_date`, `end_date`, `physiotherapist_id`.
- `GET /programs/?diagnostic_id=&patient_id=&limit=&offset=` lists programs visible to doctor.
- `GET /programs/{program_id}` loads detail.
- `GET /programs/{program_id}/exercises` lists assigned exercises.
- `POST /programs/{program_id}/exercises` assigns a catalog exercise.
- `GET /exercises` lists rehab exercise catalog.

## Affected Areas

- `web/src/api/programs.ts` — new typed program API client.
- `web/src/api/catalog.ts` — new typed exercise catalog client.
- `web/src/features/diagnostics/api.ts` — extend feature API type with programs/catalog.
- `web/src/features/diagnostics/hooks.ts` — add program and exercise query/mutation hooks.
- `web/src/App.tsx` — add a top-level navigation entry for rehab programs while keeping diagnostic workflow access.
- `web/src/features/diagnostics/DiagnosticWorkspace.tsx` — add UC-02 screens/actions from diagnostic detail and support top-level program entry state.
- `web/src/features/diagnostics/components/*` — add program list/detail/create and exercise assignment components.
- `web/src/features/diagnostics/DiagnosticWorkspace.test.tsx` — AC-04/AC-05/AC-06 coverage.
- `web/src/styles.css` — v0-style cards/forms/tables for rehab plans.

## Approaches

1. **Extend current diagnostic workspace** — add UC-02 screens after selecting/opening a diagnostic.
   - Pros: Keeps clinical flow patient → diagnostic → rehab plan; reuses current state and styling.
   - Cons: `DiagnosticWorkspace` grows and may need later split.
   - Effort: Medium.

2. **Create separate rehab program workspace route** — independent top-level program UI.
   - Pros: Clean separation for AC-06 program search.
   - Cons: Requires navigation/routing not currently present; duplicates patient/diagnostic context.
   - Effort: Medium/High.

3. **Static/mock UI first** — design screens without API integration.
   - Pros: Fast visual feedback.
   - Cons: Does not satisfy UC-02 API-backed ACs.
   - Effort: Low.

## Recommendation

Use **Approach 1 with dual entry points**. Extend the existing diagnostic workspace with a “Setup rehab program” path from diagnostic detail, and also expose a top-level Rehab programs navigation entry for doctor-wide AC-06 search. Both entries reuse the same program components, clients and hooks. Keep patient-facing AC-07 and recording/metrics out of scope.

## Risks

- `DiagnosticWorkspace` can become too large; mitigate by moving UC-02 rendering into focused components.
- Catalog endpoint returns minimal exercise fields (`id`, `nombre`, `tipo`); UI should not assume richer metadata.
- AC-06 doctor-wide program search needs a top-level entry as well as selected diagnostic context; reuse components to avoid duplicate program UIs.

## Ready for Proposal

Yes. Scope is clear: UI for AC-04, AC-05 and AC-06 only, using the newly applied UC-02 program API.
