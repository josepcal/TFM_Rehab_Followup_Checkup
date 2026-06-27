# Spec: Follow-up Metrics Charts with Norm Bands (UC-09 extension)

---

## API Spec — `api-metric-norms`

### Endpoints

#### `GET /api/norms`
- **Roles**: all authenticated (`medical`, `patient`, `technician`, `admin`)
- **Response 200**:
```json
[
  {
    "norm_id": "uuid",
    "metric_code": "jitter_local_pct",
    "label": "Jitter (local)",
    "unit": "%",
    "direction": "lower_better",
    "sex": null,
    "age_min": null,
    "age_max": null,
    "good_min": null,
    "good_max": 1.04,
    "poor_min": 3.0,
    "poor_max": null,
    "source": "dysarthria_analysis_v1",
    "version": 1
  }
]
```

#### `GET /api/norms/{metric_code}`
- **Roles**: all authenticated
- **Path param**: `metric_code` (text, e.g. `jitter_local_pct`)
- **Response 200**: single `MetricNorm` object (same shape as above)
- **Response 404**: `{ "detail": "norm not found for metric_code '{metric_code}'" }`

### Norm field semantics by `direction`

| `direction` | `good_min` | `good_max` | `poor_min` | `poor_max` |
|-------------|-----------|-----------|-----------|-----------|
| `higher_better` | threshold value (e.g. 15.0) | `null` | `null` | threshold value (e.g. 6.0) |
| `lower_better` | `null` | threshold value (e.g. 1.04) | threshold value (e.g. 3.0) | `null` |
| `in_range` | range lower bound | range upper bound | range lower bound | range upper bound |

### Seed data (migration `0011_seed_metric_norms.py`)

11 norms from `dysarthria_analysis.py` `NORMS` dict:

| metric_code | direction | good threshold | poor threshold |
|-------------|-----------|---------------|---------------|
| `phonation_duration_sec` | `higher_better` | 15.0 | 6.0 |
| `jitter_local_pct` | `lower_better` | 1.04 | 3.0 |
| `shimmer_local_pct` | `lower_better` | 3.81 | 10.0 |
| `hnr_db` | `higher_better` | 20.0 | 7.0 |
| `volume_std_db_sustain` | `lower_better` | 1.5 | 6.0 |
| `ddk_rate_syll_sec` | `higher_better` | 6.0 | 3.0 |
| `ddk_cv_interval` | `lower_better` | 0.10 | 0.35 |
| `labial_mod_depth` | `higher_better` | 0.85 | 0.35 |
| `lingual_mod_depth` | `higher_better` | 0.85 | 0.35 |
| `smr_rate_syll_sec` | `higher_better` | 5.0 | 2.5 |
| `intelligibility_pct` | `higher_better` | 95.0 | 50.0 |

Grants required: `GRANT SELECT ON reference.metric_norm TO ftm_gp, ftm_medical_specialist, ftm_patient, ftm_technician, ftm_ai;`

### Gherkin

```gherkin
Scenario: List all norms
  Given an authenticated doctor
  When GET /api/norms
  Then 200 with list of 11 MetricNorm objects

Scenario: Get norm by metric_code
  Given an authenticated doctor
  When GET /api/norms/jitter_local_pct
  Then 200 with MetricNorm where direction=lower_better, good_max=1.04, poor_min=3.0

Scenario: Get norm for unknown metric_code
  Given an authenticated doctor
  When GET /api/norms/nonexistent_metric
  Then 404 with detail message
```

---

## UI Spec — `ui-followup-metrics-norms`

### FollowupMetricsModal — refactored

Replace the single `LineChart` with **small multiples**: one chart per metric key, stacked vertically.

#### Layout

```
┌─────────────────────────────────────────────────────────┐
│  Metrics Evolution                              [×]      │
│─────────────────────────────────────────────────────────│
│  jitter_local_pct  ↓ lower better                       │
│  ┌───────────────────────────────────────────────────┐  │
│  │  [poor band: red/orange]                          │  │
│  │  ──────────────── poor threshold                  │  │
│  │                                                   │  │
│  │  ──────────────── good threshold                  │  │
│  │  [good band: green]                               │  │
│  │  • ──── • ──── •  (line with data points)         │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  hnr_db  ↑ higher better                               │
│  ┌───────────────────────────────────────────────────┐  │
│  │  [good band: green above good threshold]          │  │
│  │  • ──── • ──── •  (line)                          │  │
│  │  [intermediate zone: no band]                     │  │
│  │  [poor band: red below poor threshold]            │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

#### Per-metric chart spec

Component: `MetricChart({ metricKey, data, norm })`
- `ResponsiveContainer` width="100%" height=220
- `LineChart` with `margin={{ top: 8, right: 16, left: 0, bottom: 8 }}`
- `CartesianGrid strokeDasharray="3 3"`
- `XAxis dataKey="date"` — tick font size 11
- `YAxis` — auto domain from data + 10% padding; tick font size 11
- `Tooltip`
- **ReferenceArea for good zone** (when norm present):
  - `higher_better`: `y1={norm.good_min} y2={Infinity}` → clamp `y2` to `yDomainMax`; `fill="#dcfce7" fillOpacity={0.5}` (green-100)
  - `lower_better`: `y1={-Infinity} y2={norm.good_max}` → clamp `y1` to `yDomainMin`; same green fill
  - `in_range`: `y1={norm.good_min} y2={norm.good_max}`; green fill
- **ReferenceArea for poor zone** (when norm present):
  - `higher_better`: `y1={-Infinity} y2={norm.poor_max}` → clamp `y1` to `yDomainMin`; `fill="#fee2e2" fillOpacity={0.5}` (red-100)
  - `lower_better`: `y1={norm.poor_min} y2={Infinity}` → clamp `y2` to `yDomainMax`; same red fill
  - `in_range`: outside `[poor_min, poor_max]` → two `ReferenceArea` (below poor_min and above poor_max); red fill
- **ReferenceLine** (optional label) at good threshold with label "good" and poor threshold with label "poor" — `strokeDasharray="4 2"`, green/red stroke
- `Line` `dataKey={metricKey}` `stroke="#8b5cf6"` `strokeWidth={2}` `dot={{ r: 4 }}`

#### Direction indicator
Above each chart, small text:
- `higher_better` → `↑ higher is better`
- `lower_better` → `↓ lower is better`
- `in_range` → `↔ target range`
- no norm → nothing

#### Y-axis domain clamping
```
yDomainMin = min(minDataValue, norm.poor_min ?? norm.good_min ?? minDataValue) * 0.9
yDomainMax = max(maxDataValue, norm.poor_max ?? norm.good_max ?? maxDataValue) * 1.1
```
Always ensure good and poor thresholds are visible in the chart, even if data points don't reach them.

#### Empty / loading states
- Preserved from current implementation
- If a metric has data but no norm → chart renders without ReferenceAreas (graceful degradation)

### Gherkin

```gherkin
Scenario: Small multiples — one chart per metric
  Given a check-up with recordings that have metrics [jitter_local_pct, hnr_db]
  When the FollowupMetricsModal opens and data loads
  Then two separate charts are rendered, one per metric key
  And each chart has its own Y axis and title

Scenario: Good zone band visible
  Given metric jitter_local_pct (lower_better, good_max=1.04)
  And the norm is loaded
  When the chart renders
  Then a green ReferenceArea covers y ∈ (-∞, 1.04]
  And a red ReferenceArea covers y ∈ [3.0, ∞)

Scenario: Higher-better norm bands
  Given metric hnr_db (higher_better, good_min=20.0, poor_max=7.0)
  When the chart renders
  Then a green ReferenceArea covers y ∈ [20.0, yDomainMax]
  And a red ReferenceArea covers y ∈ [yDomainMin, 7.0]

Scenario: Metric without norm degrades gracefully
  Given a metric key with no entry in reference.metric_norm
  When the chart renders
  Then the line is shown without any ReferenceArea
  And no error is thrown

Scenario: Direction indicator shown
  Given metric jitter_local_pct (lower_better)
  When the chart renders
  Then the text "↓ lower is better" appears above the chart
```
