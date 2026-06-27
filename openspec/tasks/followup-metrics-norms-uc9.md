# Tasks: Follow-up Metrics Charts with Norm Bands (UC-09 extension)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 250–320 |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Delivery strategy | single-pr |

---

## PR1 — Backend: Norms endpoint + seed

### Phase 1: Seed migration

- [x] **1.1** Create `bbdd_dev_setup/alembic/migrations/versions/0011_seed_metric_norms.py`.
  - `down_revision = "0010_followup_checkup"`
  - `upgrade()` inserts 11 rows into `reference.metric_norm` using `ON CONFLICT DO NOTHING` (idempotent):

  | metric_code | direction | good threshold field | good value | poor threshold field | poor value | label |
  |---|---|---|---|---|---|---|
  | `phonation_duration_sec` | `higher_better` | `good_min` | 15.0 | `poor_max` | 6.0 | `Phonation Duration` |
  | `jitter_local_pct` | `lower_better` | `good_max` | 1.04 | `poor_min` | 3.0 | `Jitter (local)` |
  | `shimmer_local_pct` | `lower_better` | `good_max` | 3.81 | `poor_min` | 10.0 | `Shimmer (local)` |
  | `hnr_db` | `higher_better` | `good_min` | 20.0 | `poor_max` | 7.0 | `HNR` |
  | `volume_std_db_sustain` | `lower_better` | `good_max` | 1.5 | `poor_min` | 6.0 | `Volume Stability` |
  | `ddk_rate_syll_sec` | `higher_better` | `good_min` | 6.0 | `poor_max` | 3.0 | `DDK Rate` |
  | `ddk_cv_interval` | `lower_better` | `good_max` | 0.10 | `poor_min` | 0.35 | `DDK Regularity` |
  | `labial_mod_depth` | `higher_better` | `good_min` | 0.85 | `poor_max` | 0.35 | `Labial Closure` |
  | `lingual_mod_depth` | `higher_better` | `good_min` | 0.85 | `poor_max` | 0.35 | `Lingual Closure` |
  | `smr_rate_syll_sec` | `higher_better` | `good_min` | 5.0 | `poor_max` | 2.5 | `SMR Rate` |
  | `intelligibility_pct` | `higher_better` | `good_min` | 95.0 | `poor_max` | 50.0 | `Intelligibility` |

  - For `higher_better`: set `good_min=value`, `good_max=NULL`, `poor_min=NULL`, `poor_max=value`
  - For `lower_better`: set `good_min=NULL`, `good_max=value`, `poor_min=value`, `poor_max=NULL`
  - All rows: `sex=NULL`, `age_min=NULL`, `age_max=NULL`, `unit` per metric (sec, %, dB, syll/s, none), `source='dysarthria_analysis_v1'`, `version=1`
  - Also add: `GRANT SELECT ON reference.metric_norm TO ftm_gp, ftm_medical_specialist, ftm_patient, ftm_technician, ftm_ai;`
  - `downgrade()`: `DELETE FROM reference.metric_norm WHERE source = 'dysarthria_analysis_v1';`
  - Style: `op.execute("""...""")` raw SQL, same as `0010_followup_checkup.py`
  - **Files**: `bbdd_dev_setup/alembic/migrations/versions/0011_seed_metric_norms.py`
  - **Acceptance**: `alembic upgrade head` inserts 11 rows; re-running is a no-op; `downgrade -1` removes them.

---

### Phase 2: API module

- [x] **2.1** Create `api/app/norms/__init__.py` (empty).
  - **Files**: `api/app/norms/__init__.py`

- [x] **2.2** Create `api/app/norms/models.py` with `MetricNorm` ORM class.
  - `__tablename__ = "metric_norm"`, `__table_args__ = {"schema": "reference"}`
  - Columns: `norm_id` (UUID PK), `metric_code` (Text), `label` (Text nullable), `unit` (Text nullable), `direction` (Text — store enum as text, no SQLAlchemy Enum type), `sex` (Text nullable), `age_min` (Integer nullable), `age_max` (Integer nullable), `good_min` (Float nullable), `good_max` (Float nullable), `poor_min` (Float nullable), `poor_max` (Float nullable), `source` (Text nullable), `version` (Integer), `created_at` (DateTime timezone=True)
  - **Files**: `api/app/norms/models.py`
  - **Depends on**: 2.1
  - **Acceptance**: `from app.norms.models import MetricNorm` resolves; `MetricNorm.__table_args__["schema"] == "reference"`.

- [x] **2.3** Create `api/app/norms/schemas.py` with `MetricNormOut(BaseModel)`.
  - Fields matching all ORM columns (all nullable fields optional); `ConfigDict(from_attributes=True)`
  - **Files**: `api/app/norms/schemas.py`
  - **Depends on**: 2.1

- [x] **2.4** Create `api/app/norms/router.py` with two endpoints.
  - `router = APIRouter(tags=["norms"])`
  - `GET /norms` → `require_role("medical","patient","technician","admin")` → `db.scalars(select(MetricNorm)).all()` → `list[MetricNormOut]`
  - `GET /norms/{metric_code}` → same auth → `db.scalar(select(MetricNorm).where(MetricNorm.metric_code == metric_code))` → `MetricNormOut` or 404
  - **Files**: `api/app/norms/router.py`
  - **Depends on**: 2.2, 2.3
  - **Acceptance**: both endpoints return correct data; 404 for unknown metric_code.

- [x] **2.5** Register norms router in `api/app/main.py`.
  - `from app.norms.router import router as norms_router`
  - `app.include_router(norms_router, prefix="/api")`
  - **Files**: `api/app/main.py`
  - **Depends on**: 2.4

- [x] **2.6** Write tests in `api/tests/test_norms.py`.
  - Test: `GET /api/norms` returns list (may be empty in test DB — assert 200 + list type)
  - Test: `GET /api/norms/{metric_code}` with seeded norm returns 200 + correct direction
  - Test: `GET /api/norms/nonexistent` returns 404
  - Test: unauthenticated request returns 401/403
  - **Files**: `api/tests/test_norms.py`
  - **Depends on**: 2.4, 2.5
  - **Acceptance**: all tests pass with `pytest`; no regressions.

---

## PR2 — Frontend: small multiples + norm bands

### Phase 3: API client

- [x] **3.1** Create `web/src/api/norms.ts`.
  - Type `MetricNorm`: all fields from spec (nullable floats as `number | null`)
  - Type `NormsApi`: `{ listNorms(): Promise<MetricNorm[]>; getNorm(metricCode: string): Promise<MetricNorm> }`
  - Factory `createNormsApi(http: HttpClient): NormsApi`
    - `listNorms()` → `http.request<MetricNorm[]>("/norms")`
    - `getNorm(metricCode)` → `http.request<MetricNorm>(\`/norms/${metricCode}\`)`
  - **Files**: `web/src/api/norms.ts`
  - **Acceptance**: `tsc --noEmit` passes.

- [x] **3.2** Intersect `NormsApi` into `DiagnosticFeatureApi` and wire factory.
  - `web/src/features/diagnostics/api.ts`: add `NormsApi` to intersection type; add `normsApi` to `createDiagnosticFeatureApi`
  - `web/src/App.tsx`: pass `createNormsApi(http)` to the factory (same pattern as other APIs)
  - `web/src/App.test.tsx`: add `listNorms: async () => []` and `getNorm: async () => { throw new Error("not implemented"); }` to mock
  - **Files**: `web/src/features/diagnostics/api.ts`, `web/src/App.tsx`, `web/src/App.test.tsx`
  - **Depends on**: 3.1
  - **Acceptance**: `tsc --noEmit` passes; existing tests still pass.

---

### Phase 4: Hook

- [x] **4.1** Add `useMetricNorms(metricCodes: string[])` to `web/src/features/diagnostics/hooks.ts`.
  - Query key: `["metric-norms", ...metricCodes.sort()]`
  - Disabled when `metricCodes.length === 0`
  - Fetches `api.listNorms()` and filters to `metricCodes` — one API call, not N
  - Returns `Map<string, MetricNorm>` (metric_code → norm)
  - **Files**: `web/src/features/diagnostics/hooks.ts`
  - **Depends on**: 3.2
  - **Acceptance**: returns empty Map when disabled; returns populated Map when metricCodes provided.

---

### Phase 5: Refactor FollowupMetricsModal

- [x] **5.1** Refactor `web/src/features/diagnostics/components/FollowupMetricsModal.tsx`.

  Replace the single `LineChart` with small multiples. For each `metricKey` in `metricKeys`:

  **Sub-component `MetricChart({ metricKey, data, norm })`**:
  - Compute `yDomainMin` and `yDomainMax`
  - `ReferenceArea` for **good zone** (fill `"#dcfce7"` opacity 0.5)
  - `ReferenceArea` for **poor zone** (fill `"#fee2e2"` opacity 0.5)
  - `Line dataKey={metricKey}` stroke `"#8b5cf6"` strokeWidth 2 dot r=4
  - Direction label above chart

  - **Files**: `web/src/features/diagnostics/components/FollowupMetricsModal.tsx`
  - **Depends on**: 4.1
  - **Acceptance**: renders N charts for N metrics; each chart shows `ReferenceArea` when norm exists; no `ReferenceArea` when norm absent.

---

### Phase 6: Tests

- [x] **6.1** Update `FollowupMetricsModal.test.tsx`.
  - Mock `useCheckupMetrics` and `useMetricNorms`
  - Add test: "renders one chart section per metric key" — assert N headings for N metrics
  - Add test: "renders without error when norms map is empty" (graceful degradation)
  - Keep existing tests: loading, empty, onClose
  - **Files**: `web/src/features/diagnostics/components/FollowupMetricsModal.test.tsx`
  - **Depends on**: 5.1
  - **Acceptance**: all tests pass with `vitest run`.
