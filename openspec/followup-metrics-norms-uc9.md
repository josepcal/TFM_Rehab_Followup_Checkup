# Proposal: Follow-up Metrics Charts with Norm Bands (UC-09 extension)

## Intent

El modal de métricas actual (`FollowupMetricsModal`) muestra todas las métricas en una única gráfica agregada. Esto dificulta la lectura clínica: escalas distintas se mezclan y no hay referencia visual de qué es "bueno" o "malo". Este cambio reemplaza la gráfica única por **una gráfica por métrica**, cada una con bandas de color que marcan la zona buena (verde) y la zona pobre (rojo/naranja) derivadas de `reference.metric_norm`.

## Scope

### In Scope
- Nuevo endpoint `GET /api/norms` → lista de normas de `reference.metric_norm` (lectura pública para todos los roles)
- Nuevo endpoint `GET /api/norms/{metric_code}` → norma específica por código de métrica
- Seed de datos: migración `0011_seed_metric_norms.py` que inserta las 11 normas de `NORMS` del `dysarthria_analysis.py`
- `FollowupMetricsModal` refactorizado: una sub-gráfica por métrica (`ComposedChart` o `LineChart`) con `ReferenceArea` para la zona buena y `ReferenceArea` para la zona pobre
- Indicador de dirección (`↑ higher better` / `↓ lower better` / `↔ in range`) en el título de cada sub-gráfica
- Hook `useMetricNorms(metricCodes: string[])` para obtener normas del backend

### Out of Scope
- CRUD de normas desde la UI (solo lectura)
- Estratificación por sexo/edad (las 11 normas actuales no tienen estrato — `sex=NULL`, `age_min=NULL`, `age_max=NULL`)
- Gráfica agregada multi-métrica (reemplazada por small multiples)

## Approach

**Backend first**: endpoint de normas → seed migration → frontend hook → refactor modal.

### Norm bands logic por `direction`
| Direction | Zona buena (`ReferenceArea` verde) | Zona pobre (`ReferenceArea` roja) |
|-----------|-------------------------------------|-----------------------------------|
| `higher_better` | `[good_min, ∞)` — valor ≥ good | `(-∞, poor_max]` — valor ≤ poor |
| `lower_better` | `(-∞, good_max]` — valor ≤ good | `[poor_min, ∞)` — valor ≥ poor |
| `in_range` | `[good_min, good_max]` | fuera de `[poor_min, poor_max]` |

Para `higher_better`: `good_min = NORMS[key]["good"]`, `poor_max = NORMS[key]["poor"]`.
Para `lower_better`: `good_max = NORMS[key]["good"]`, `poor_min = NORMS[key]["poor"]`.

### Small multiples layout
Gráficas apiladas verticalmente, una por `metricKey`. Cada una:
- `ResponsiveContainer` width=100%, height=220
- Eje X compartido (fecha de grabación)
- Eje Y autoescalado, con las `ReferenceArea` de norma
- `Line` con puntos y tooltip
- Título con nombre de métrica + indicador de dirección

## Affected Areas

| Área | Impacto | Descripción |
|------|---------|-------------|
| `bbdd_dev_setup/alembic/migrations/versions/0011_seed_metric_norms.py` | Nuevo | Seed de 11 normas desde `NORMS` dict |
| `api/app/norms/` | Nuevo módulo | `models.py`, `schemas.py`, `router.py` |
| `api/app/main.py` | Modificado | Registrar norms router |
| `web/src/api/norms.ts` | Nuevo | Tipo `MetricNorm` + factory `createNormsApi` |
| `web/src/features/diagnostics/api.ts` | Modificado | Intersectar `NormsApi` en `DiagnosticFeatureApi` |
| `web/src/features/diagnostics/hooks.ts` | Modificado | Añadir `useMetricNorms(metricCodes)` |
| `web/src/features/diagnostics/components/FollowupMetricsModal.tsx` | Modificado | Small multiples + `ReferenceArea` por norma |

## Risks

| Riesgo | Mitigación |
|--------|-----------|
| `reference.metric_norm` no tiene datos seeded → gráficas sin bandas | Seed migration antes del frontend; UI degrada sin error (bandas opcionales) |
| `reference` schema puede no tener grants para el rol `medical` | Verificar grants en migration; añadir `GRANT SELECT ON reference.metric_norm TO ftm_gp, ftm_medical_specialist, ftm_patient` |
| Muchas métricas → modal muy largo | `max-height: 80vh` + scroll ya presente en `.modal-content` |
| `recharts` `ReferenceArea` con `y1=Infinity` puede romper el render | Clampear al dominio del eje Y calculado desde los datos |

## Success Criteria

- [ ] `GET /api/norms` devuelve lista de normas; `GET /api/norms/{metric_code}` devuelve la norma de esa métrica
- [ ] Modal muestra una gráfica por métrica (small multiples)
- [ ] Cada gráfica muestra banda verde (zona buena) y banda roja (zona pobre) cuando existe norma para esa métrica
- [ ] Métricas sin norma muestran solo la línea de evolución (sin bandas)
- [ ] Indicador de dirección visible en el título de cada sub-gráfica
- [ ] `tsc --noEmit` y `vitest run` pasan sin errores
