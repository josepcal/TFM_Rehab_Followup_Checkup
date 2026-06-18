# Proposal: UI Setup Programa de Rehabilitación (UC-02)

**Change Name**: `ui-setup-programa-rehabilitacion-uc2`  
**Status**: Proposed

## Intent

Add the doctor-facing UI for UC-02 so a medical user can create a rehab program from an existing diagnostic, assign catalog exercises to the program, and search/view rehab programs they own.

## Scope

### In Scope

- Typed frontend API client for `/programs` and `/exercises`.
- TanStack Query hooks for program list/detail/create and program exercise list/assignment.
- UI action from diagnostic detail to setup a rehab program.
- Top-level Rehab programs navigation entry for doctor-wide program search.
- Rehab program create form with optional metadata: name, dates, status.
- Rehab program list/detail UI for the selected diagnostic/patient.
- Exercise assignment UI using catalog exercises and `pauta`.
- Tests for AC-04, AC-05 and AC-06.

### Out of Scope

- Patient-facing AC-07.
- UC-03 analysis setup.
- Recording, metrics, reports, follow-up check-ups.
- Catalog exercise creation/editing.
- Physiotherapist user picker unless the API/user directory exists.

## Capabilities

### New Capabilities

- `doctor-rehab-program-ui`: Medical user can create and inspect rehab programs for UC-02.
- `doctor-program-exercise-ui`: Medical user can assign catalog exercises to a rehab program.
- `doctor-program-search-ui`: Medical user can search/list owned rehab programs.

### Modified Capabilities

- `doctor-diagnostic-ui`: Diagnostic detail gains a transition into rehab program setup.

## Approach

Use Approach #1 with dual entry points: keep rehab setup inside the patient/diagnostic workflow, and add a top-level Rehab programs navigation entry for AC-06 doctor-wide search. Both paths reuse the same typed API clients, hooks and focused program components.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `web/src/api/programs.ts` | New | Program DTOs and API calls. |
| `web/src/api/catalog.ts` | New | Exercise catalog DTOs and API call. |
| `web/src/features/diagnostics/api.ts` | Modified | Extend feature API type. |
| `web/src/features/diagnostics/hooks.ts` | Modified | Program/catalog hooks and mutation invalidation. |
| `web/src/App.tsx` | Modified | Top-level navigation entry for diagnostic workspace vs rehab programs. |
| `web/src/features/diagnostics/DiagnosticWorkspace.tsx` | Modified | UC-02 screen state/actions and top-level program entry mode. |
| `web/src/features/diagnostics/components/` | New/Modified | Program create/list/detail/exercise assignment UI. |
| `web/src/styles.css` | Modified | Rehab program UI styling. |
| `web/src/features/diagnostics/DiagnosticWorkspace.test.tsx` | Modified | AC-04/AC-05/AC-06 tests. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Workspace complexity grows | Medium | Add focused child components and keep orchestration thin. |
| Catalog data is minimal | Medium | Render only `nombre`/`tipo`, keep future fields optional. |
| Program search scope ambiguity | Medium | Support selected patient/diagnostic filters and typed unfiltered search. |

## Rollback Plan

Remove new program/catalog API clients, hooks, components, workspace wiring and tests. UC-01 diagnostic UI remains unchanged.

## Dependencies

- Applied API change `api-setup-programa-rehabilitacion`.
- Existing UC-01 diagnostic UI and auth shell.
- `GET /exercises` catalog endpoint.

## Success Criteria

- [ ] AC-04: doctor can create a rehab program linked to a diagnostic.
- [ ] AC-05: doctor can assign an exercise to a rehab program.
- [ ] AC-06: doctor can find/view owned rehab programs from top-level navigation and diagnostic context.
- [ ] UI handles loading, empty, validation, 403 and 404 states.
- [ ] Tests cover program creation, exercise assignment and program search.
