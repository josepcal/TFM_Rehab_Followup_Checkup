# Design: UI Setup Programa de Rehabilitación (UC-02)

## Technical Approach

Extend the current diagnostics feature with a UC-02 rehab program sub-flow and a top-level Rehab programs navigation entry. The UI supports both paths: patient registry → patient diagnostic record → diagnostic detail → rehab program setup, and top-level navigation → doctor-wide rehab program search. API access stays in `web/src/api`, server state stays in TanStack Query hooks, and presentational UI stays in focused components.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|---|---|---|---|
| Placement | Extend `features/diagnostics` with dual entry points | Separate duplicate feature | UC-02 depends on selected diagnostic context, but AC-06 also benefits from top-level doctor-wide access. |
| API clients | Add `programs.ts` and `catalog.ts` | Put calls in workspace | Keeps DTOs/errors reusable and testable. |
| State | Add hooks in diagnostics `hooks.ts` | Local fetch in components | Matches UC-01 TanStack Query pattern. |
| UI composition | Focused program components | Put all markup in workspace | Keeps `DiagnosticWorkspace` from becoming unreadable. |
| Physiotherapist | Keep optional/manual omitted from UI initially | Build user picker | No doctor directory API exists; SDD says optional. |

## Data Flow

```text
Top-level navigation
  -> user clicks Rehab programs
  -> ProgramList loads doctor-wide GET /programs/?limit=&offset=
  -> user opens ProgramDetail

Diagnostic detail
  -> user clicks Setup rehab program
  -> ProgramForm submits ProgramIn { diagnostic_id, name?, dates?, estado? }
  -> useCreateProgram invalidates programs by diagnostic/patient
  -> ProgramList/ProgramDetail shows created program

Program detail
  -> useProgramExercises(program_id)
  -> useExerciseCatalog()
  -> AssignExerciseForm submits ProgramExerciseIn
  -> mutation invalidates program exercise list
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `web/src/api/programs.ts` | Create | Program DTOs, normalize page, list/detail/create/list exercises/assign calls. |
| `web/src/api/catalog.ts` | Create | `RehabExerciseOut` and `listExercises`. |
| `web/src/features/diagnostics/api.ts` | Modify | Extend `DiagnosticFeatureApi` with programs/catalog APIs. |
| `web/src/features/diagnostics/hooks.ts` | Modify | Add `usePrograms`, `useCreateProgram`, `useProgramExercises`, `useAssignExercise`, `useExerciseCatalog`. |
| `web/src/App.tsx` | Modify | Add top-level navigation entry for Rehab programs. |
| `web/src/features/diagnostics/DiagnosticWorkspace.tsx` | Modify | Add screen state for program create/detail, top-level program entry and actions from diagnostic detail. |
| `web/src/features/diagnostics/components/RehabProgramPanel.tsx` | Create | Program list/detail shell for selected diagnostic. |
| `web/src/features/diagnostics/components/RehabProgramForm.tsx` | Create | Program metadata form. |
| `web/src/features/diagnostics/components/AssignExerciseForm.tsx` | Create | Catalog exercise selector and pauta field. |
| `web/src/features/diagnostics/DiagnosticWorkspace.test.tsx` | Modify | UC-02 AC-04/AC-05/AC-06 tests. |
| `web/src/styles.css` | Modify | Program cards, form layout, exercise table styles. |

## Interfaces / Contracts

```ts
type ProgramIn = {
  diagnostic_id: string;
  estado?: string | null;
  name?: string | null;
  start_date?: string | null;
  end_date?: string | null;
};

type ProgramOut = ProgramIn & {
  id: string;
  diagnostic_id: string;
  created_at?: string | null;
  physiotherapist_id?: string | null;
};

type ProgramExerciseOut = {
  id: string;
  program_id: string;
  exercise_id: string;
  pauta?: string | null;
  estado?: string | null;
  created_at?: string | null;
};

type RehabExerciseOut = {
  id: string;
  nombre: string;
  tipo?: string | null;
};
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|--------------|----------|
| API client | Program query construction and page normalization | Vitest unit tests. |
| Component | AC-04 create program from diagnostic detail | Testing Library with fake API. |
| Component | AC-05 assign exercise and refresh exercise list | Testing Library with fake API. |
| Component | AC-06 list/open owned programs and empty/error states | Testing Library with fake API. |

## Migration / Rollout

No migration required. This is additive UI over existing API endpoints. Rollback by removing new API clients, hooks, components and workspace wiring.

## Open Questions

None. Decision recorded: UC-02 should remain accessible inside the patient/diagnostic workflow and also have a top-level Rehab programs navigation entry.
