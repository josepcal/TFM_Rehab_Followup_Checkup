# Tasks: UI Setup Programa de Rehabilitación (UC-02)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 650-950 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR #1 API/hooks → PR #2 dual-entry program screens → PR #3 exercise assignment/style polish |
| Delivery strategy | ask-on-risk |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Typed API clients and hooks | PR 1 | No visible UI; tests included. |
| 2 | Program create/search/detail UI with dual entry points | PR 2 | AC-04/AC-06 screens plus top-level navigation. |
| 3 | Exercise assignment UI and polish | PR 3 | AC-05, styles, final tests. |

## Phase 1: API Contracts and Hooks

- [x] 1.1 Create `web/src/api/programs.ts` with `ProgramIn`, `ProgramOut`, `ProgramExerciseIn`, `ProgramExerciseOut`, list/detail/create/list-exercises/assign calls.
- [x] 1.2 Create `web/src/api/catalog.ts` with `RehabExerciseOut` and `listExercises()`.
- [x] 1.3 Extend `web/src/features/diagnostics/api.ts` with program and catalog API types.
- [x] 1.4 Add program/catalog TanStack Query hooks in `web/src/features/diagnostics/hooks.ts` with invalidation.
- [x] 1.5 Add API-client tests for query parameters and paginated normalization.

## Phase 2: Program Creation and Search UI

- [ ] 2.1 Add UC-02 screen state/actions in `DiagnosticWorkspace.tsx` from diagnostic detail and top-level program entry mode.
- [ ] 2.2 Create `RehabProgramForm.tsx` for name/status/start/end fields and submit errors.
- [ ] 2.3 Create `RehabProgramPanel.tsx` to list/open programs for selected diagnostic and doctor-wide top-level search.
- [ ] 2.4 Wire `POST /programs/` from selected diagnostic and refresh program list.
- [ ] 2.5 Update `web/src/App.tsx` with a top-level Rehab programs navigation entry.
- [ ] 2.6 Add AC-04 and AC-06 component tests for diagnostic-context and top-level entry flows.

## Phase 3: Exercise Assignment UI

- [ ] 3.1 Create `AssignExerciseForm.tsx` with catalog selector and `pauta` input.
- [ ] 3.2 Show assigned exercise table from `GET /programs/{id}/exercises`.
- [ ] 3.3 Wire `POST /programs/{id}/exercises` and refresh exercise table.
- [ ] 3.4 Add empty, loading, 403 and 404 states for program/exercise flows.
- [ ] 3.5 Add AC-05 component tests.

## Phase 4: Styling and Verification

- [ ] 4.1 Add v0-consistent rehab program cards/forms/tables in `web/src/styles.css`.
- [ ] 4.2 Run `npm --prefix web test -- --run`.
- [ ] 4.3 Run `npm --prefix web run lint`.
- [ ] 4.4 Run `npm --prefix web run build` and clean generated artifacts if needed.
- [ ] 4.5 Run `api/.venv/bin/python -m pytest api/tests -q` as regression safety.
