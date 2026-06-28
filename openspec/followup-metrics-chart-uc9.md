# Proposal: Follow-up Metrics Evolution Chart (UC-09 extension)

## Intent

El Follow-up Check-up (UC-09) muestra reportes de ejercicios pero no da visibilidad de la evolución temporal de las métricas. Los médicos necesitan ver si el paciente mejora, empeora o se estanca a lo largo del período. Este cambio añade un modal de gráficas de evolución de métricas accesible desde cada check-up, tomando como referencia visual el componente `FollowupMetricsModal` del prototipo v0.

## Scope

### In Scope
- Botón "Metrics" en cada card de check-up dentro de `FollowupCheckupPanel`
- Modal `FollowupMetricsModal` que, dado un check-up, recopila los `recording_id` de todos sus reports vinculados, obtiene las métricas de cada uno y las muestra en gráficas de línea temporales
- Una gráfica general con todas las métricas numéricas disponibles a lo largo del tiempo
- Instalación de `recharts` como dependencia de `web/`
- Adaptación del componente v0 al sistema de CSS plain del proyecto (sin shadcn/tailwind)

### Out of Scope
- Persistencia de los datos del gráfico (siempre se calculan on-demand)
- Filtrado por tipo de métrica (v1: todas las métricas numéricas disponibles)
- Exportación de gráficas a PDF/imagen
- Gráficas por ejercicio individual (v1: vista agregada)

## Approach

1. Instalar `recharts` en `web/package.json`
2. Nuevo componente `FollowupMetricsModal.tsx` — modal nativo (no shadcn Dialog), usando `recharts` `LineChart`
3. Para obtener los recordings de un check-up: el detalle del check-up (`GET /followup-checkups/{id}`) ya devuelve los `exercise_report_id` vinculados; el detalle de cada report devuelve los `recording_id`; para cada recording se llama `GET /recordings/{id}/metrics`
4. Montar el botón "Metrics" en `FollowupCheckupPanel` y renderizar el modal condicionalmente

## Data flow

```
FollowupCheckupPanel
  → [Metrics button click]
  → FollowupMetricsModal(checkupId)
      → GET /followup-checkups/{checkupId}           (ya en hooks: useCheckupDetail)
      → para cada exercise_report_id:
          GET /reports/{reportId}                    (ya en hooks: useReportDetail)
            → extrae recording_ids del report
      → para cada recording_id:
          GET /recordings/{recordingId}/metrics      (ya en api: getRecordingMetrics)
      → renderiza LineChart con { date: recording_date, ...metrics }
```

## Affected Areas

| Área | Impacto | Descripción |
|------|---------|-------------|
| `web/package.json` | Modificado | Añadir `recharts` + `@types/recharts` |
| `web/src/features/diagnostics/components/FollowupMetricsModal.tsx` | Nuevo | Modal con gráfica de evolución |
| `web/src/features/diagnostics/components/FollowupCheckupPanel.tsx` | Modificado | Añadir botón Metrics + renderizar modal |
| `web/src/features/diagnostics/hooks.ts` | Modificado | Añadir `useCheckupMetrics(checkupId)` — fetch encadenado recordings→metrics |

## Risks

| Riesgo | Mitigación |
|--------|-----------|
| Recordings sin métricas extraídas → gráfica vacía | Mostrar estado vacío con mensaje "No metrics available yet" |
| Múltiples fetch encadenados (N reports × M recordings) → latencia visible | Spinner mientras carga; paralelizar con `Promise.all` |
| `recharts` añade ~200KB al bundle | Lazy import del modal con `React.lazy` / dynamic import |
| Nombres de métricas son paths arbitrarios (ej. `domains.voice_stability`) | Mostrar el path como label; no normalizar en v1 |

## Success Criteria

- [ ] Botón "Metrics" visible en cada check-up card dentro de `FollowupCheckupPanel`
- [ ] Modal abre y muestra una `LineChart` con el eje X = fecha de grabación, eje Y = valor de métrica
- [ ] Si no hay métricas disponibles, muestra estado vacío legible
- [ ] Modal cierra con botón o click fuera
- [ ] `recharts` instalado y build pasa sin errores de tipo
