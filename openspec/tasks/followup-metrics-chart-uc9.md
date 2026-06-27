# Tasks: Follow-up Metrics Evolution Chart (UC-09 extension)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 150–200 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Delivery strategy | single-pr |

---

## Tasks

### Phase 1: Dependency

- [x] **1.1** Install `recharts` in `web/`.
  - Run `npm install recharts` from `web/` directory.
  - Verify `recharts` appears in `web/package.json` `dependencies`.
  - **Files**: `web/package.json`, `web/package-lock.json`
  - **Depends on**: nothing.
  - **Acceptance**: `import { LineChart } from "recharts"` resolves without TS error; `tsc --noEmit` passes.

---

### Phase 2: Hook

- [x] **2.1** Add `useCheckupMetrics(checkupId: string | null)` to `web/src/features/diagnostics/hooks.ts`.
  - When `checkupId` is null, hook is disabled (query enabled: false).
  - Fetch chain:
    1. `api.getCheckupDetail(checkupId)` → `exercise_report_id[]`
    2. `Promise.all(reportIds.map(id => api.getReportDetail(id)))` → `recording_id[]` per report (flatten)
    3. `Promise.all(recordingIds.map(id => api.getRecordingMetrics(id)))` → `MetricsOut[]`
  - Transform into chart series: `Array<{ date: string } & Record<string, number>>` — one entry per recording that has `metrics !== null`, sorted by `recording_date` ascending. Each metric key from `MetricsOut.metrics` becomes a field.
  - Return `{ data: ChartPoint[]; metricKeys: string[]; isLoading: boolean; isError: boolean }`.
  - Query key: `["checkup-metrics", checkupId]`.
  - **Files**: `web/src/features/diagnostics/hooks.ts`
  - **Depends on**: nothing (uses existing `api` methods).
  - **Acceptance**: hook returns `data: []` and `metricKeys: []` when all recordings have `metrics: null`; returns correct series when metrics are present.

---

### Phase 3: Modal component

- [x] **3.1** Create `web/src/features/diagnostics/components/FollowupMetricsModal.tsx`.
  - Props: `{ checkupId: string; onClose: () => void }`.
  - Uses `useCheckupMetrics(checkupId)`.
  - **Loading state**: render `<div className="loading-spinner" />` (or equivalent class from `styles.css`) while `isLoading`.
  - **Empty state**: `<p>No metrics available yet for this check-up.</p>` when `data.length === 0` and `!isLoading`.
  - **Chart state**: `recharts` `LineChart` inside `ResponsiveContainer` (width="100%", height=320).
    - `XAxis dataKey="date"`
    - `YAxis` (auto scale)
    - `CartesianGrid strokeDasharray="3 3"`
    - `Tooltip`
    - `Legend`
    - One `<Line>` per key in `metricKeys` — assign distinct colors cycling through a small palette (e.g. `["#8b5cf6","#06b6d4","#f59e0b","#10b981","#ef4444"]`)
  - **Modal shell** (plain CSS — no shadcn Dialog):
    - Outer `<div className="modal-overlay" onClick={onClose}>` (full-screen backdrop)
    - Inner `<div className="modal-content detail-card" onClick={e => e.stopPropagation()}>` (stops backdrop click)
    - Header with title "Metrics Evolution" and `<button className="ghost-button" onClick={onClose}>×</button>`
  - **Files**: `web/src/features/diagnostics/components/FollowupMetricsModal.tsx`
  - **Depends on**: 1.1, 2.1.
  - **Acceptance**: modal renders chart when data present; renders empty message when no data; closes on × click and backdrop click.

- [x] **3.2** Add modal CSS to `web/src/styles.css` if `.modal-overlay` and `.modal-content` classes don't already exist.
  - `.modal-overlay`: `position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 50`
  - `.modal-content`: `background: white; border-radius: 8px; padding: 1.5rem; max-width: 720px; width: 90%; max-height: 80vh; overflow-y: auto`
  - **Files**: `web/src/styles.css`
  - **Depends on**: nothing.
  - **Acceptance**: modal displays centered with backdrop; scrollable if content exceeds 80vh.

---

### Phase 4: Wire into FollowupCheckupPanel

- [x] **4.1** Add Metrics button and modal to `FollowupCheckupPanel.tsx`.
  - Add state: `const [metricsCheckupId, setMetricsCheckupId] = useState<string | null>(null)`.
  - In each check-up card header (alongside Edit/Delete buttons), add:
    ```tsx
    <button
      className="ghost-button v0-program-action"
      disabled={checkup.report_count === 0}
      onClick={() => setMetricsCheckupId(checkup.followup_checkup_id)}
    >
      Metrics
    </button>
    ```
  - At the bottom of the component render (outside the map), add:
    ```tsx
    {metricsCheckupId && (
      <FollowupMetricsModal
        checkupId={metricsCheckupId}
        onClose={() => setMetricsCheckupId(null)}
      />
    )}
    ```
  - Import `FollowupMetricsModal` from `./FollowupMetricsModal`.
  - **Files**: `web/src/features/diagnostics/components/FollowupCheckupPanel.tsx`
  - **Depends on**: 3.1, 3.2.
  - **Acceptance**: button renders in each card; disabled when `report_count === 0`; click opens modal; modal closes via onClose.

---

### Phase 5: Tests

- [x] **5.1** Add tests to `FollowupCheckupPanel.test.tsx` for the Metrics button.
  - Test: "Metrics button renders for each check-up card"
  - Test: "Metrics button is disabled when report_count is 0"
  - Test: "Clicking Metrics button opens FollowupMetricsModal" (mock modal, verify it renders)
  - **Files**: `web/src/features/diagnostics/components/FollowupCheckupPanel.test.tsx`
  - **Depends on**: 4.1.
  - **Acceptance**: all tests pass with `vitest run`.

- [x] **5.2** Create `FollowupMetricsModal.test.tsx`.
  - Mock `useCheckupMetrics` hook.
  - Test: "renders loading state when isLoading=true"
  - Test: "renders empty state when data=[]"
  - Test: "renders chart container when data has entries"
  - Test: "calls onClose when × button is clicked"
  - Test: "calls onClose when overlay is clicked"
  - **Files**: `web/src/features/diagnostics/components/FollowupMetricsModal.test.tsx`
  - **Depends on**: 3.1.
  - **Acceptance**: all tests pass with `vitest run`.
