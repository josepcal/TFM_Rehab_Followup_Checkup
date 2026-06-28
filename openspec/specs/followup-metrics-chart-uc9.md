# Spec: Follow-up Metrics Evolution Chart (UC-09 extension)

## UI Spec — `ui-followup-metrics-chart`

### Overview

Extensión de `FollowupCheckupPanel` que añade visualización de la evolución temporal de métricas de recordings, accesible mediante un botón "Metrics" en cada check-up card.

---

### Components

#### Button in FollowupCheckupPanel

- Cada check-up card muestra un botón "Metrics" junto a los botones "Edit" y "Delete"
- Click abre `FollowupMetricsModal` pasando el `followup_checkup_id`
- Botón deshabilitado si el check-up no tiene reports vinculados (`report_count === 0`)

#### FollowupMetricsModal

Modal nativo (no shadcn). Props: `{ checkupId: string; onClose: () => void }`

**States:**
- `loading` — spinner mientras se obtienen datos
- `empty` — mensaje "No metrics available yet for this check-up" si ningún recording tiene métricas
- `ready` — muestra el `LineChart`

**Data fetching (on mount):**
1. Fetch check-up detail → `GET /api/followup-checkups/{checkupId}` → lista de `exercise_report_id`
2. Para cada `exercise_report_id` → `GET /api/reports/{reportId}` → lista de `recording_id`
3. Para cada `recording_id` → `GET /api/recordings/{recordingId}/metrics` → `MetricsOut`
4. Construir series: cada punto es `{ date: recording_date, [metricKey]: value, ... }` ordenado por fecha

**Chart:**
- Librería: `recharts` `LineChart` con `ResponsiveContainer`
- Eje X: fecha de grabación (`recording_date`), formateada como `YYYY-MM-DD`
- Eje Y: valor numérico de la métrica (escala automática)
- Una `Line` por cada clave de métrica presente en los datos (color distinto por línea)
- `Tooltip` con fecha y valores
- `Legend` con los nombres de métricas
- Dimensiones: ancho 100%, alto 320px

**Empty metric handling:**
- Recordings sin métricas (`metrics === null`) se omiten de la serie
- Si ningún recording tiene métricas → estado `empty`

**Close behavior:**
- Botón "×" en la cabecera del modal cierra el modal
- Click en el overlay (backdrop) cierra el modal

---

### Gherkin Scenarios

```gherkin
Scenario: Open metrics modal from check-up card
  Given a FollowupCheckupPanel with at least one check-up that has linked reports
  When the doctor clicks the "Metrics" button on a check-up card
  Then the FollowupMetricsModal opens
  And a loading spinner is shown while data is fetched

Scenario: Display metrics chart when recordings have metrics
  Given a check-up with 2 linked reports, each with 2 recordings that have metrics
  When the modal finishes loading
  Then a LineChart is rendered with the X axis showing recording dates
  And each metric key is shown as a separate Line with a legend entry

Scenario: Empty state when no recordings have metrics
  Given a check-up with linked reports whose recordings have no extracted metrics
  When the modal finishes loading
  Then the chart is NOT rendered
  And the message "No metrics available yet for this check-up" is displayed

Scenario: Close modal with button
  Given the metrics modal is open
  When the doctor clicks the "×" button
  Then the modal closes

Scenario: Close modal with backdrop click
  Given the metrics modal is open
  When the doctor clicks outside the modal content area
  Then the modal closes

Scenario: Metrics button disabled for empty check-up
  Given a check-up card with report_count === 0
  Then the "Metrics" button is present but disabled
```

---

### CSS constraints

- **No Tailwind, no shadcn.** Usar clases del sistema plain CSS del proyecto.
- Modal overlay: `className="modal-overlay"` (verificar en `styles.css`; si no existe, añadir)
- Modal container: `className="modal-content"` o `className="detail-card modal-card"`
- Botón "Metrics": `className="ghost-button v0-program-action"`
- Spinner: elemento `<div className="loading-spinner">` o similar existente en styles.css

---

### Dependency

- `recharts` añadido a `web/package.json` dependencies
- Import del modal con `React.lazy` para no inflar el bundle principal
