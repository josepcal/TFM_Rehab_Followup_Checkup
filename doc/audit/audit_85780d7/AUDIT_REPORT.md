# Auditoría de seguridad y arquitectura — FTM

## Anclaje de la auditoría

| Campo | Valor |
|---|---|
| **Commit auditado (short)** | `85780d7` |
| **Commit auditado (full)** | `85780d75cba29616ef20e246076e6f1cd3c95f2e` |
| **Branch** | `feature/auditoria` |
| **Fecha del commit** | 2026-07-08 22:53:11 +0200 |
| **Asunto del commit** | memoria de proyecto (presentacion) |
| **Fecha de la auditoría** | 2026-07-09 |
| **Guía seguida** | `doc/audit/AUDIT_FTM.md` |

> Todos los hallazgos de este informe corresponden al estado del código en el commit
> `85780d7`. Cualquier cambio posterior invalida las referencias `fichero:línea`.
>
> **Nota de lectura:** el informe documenta dos momentos. La columna *Hallazgo* describe el
> estado **auditado** (commit `85780d7`); las anotaciones **✅ RESUELTO / 🟡 PARCIAL / ❌ Pendiente**
> reflejan el estado tras la **remediación del 2026-07-09**. Las referencias `fichero:línea` de la
> columna *Ubicación* apuntan al código original, no al remediado.

### Nota de método

- **Método:** código real trazado con `rg` + lectura directa de migraciones Alembic y
  políticas RLS. No se asumió que la memoria describa lo implementado.
- **Branch:** la guía pedía `master`; la auditoría se ejecutó sobre `feature/auditoria`
  (checkout local activo). Se señala por transparencia.
- **SCA (durante la auditoría inicial):** `pip-audit`, `bandit` y `semgrep` no estaban
  instalados; el eje A03 se auditó por lectura manual de pins. Solo se confirmó `ruff` limpio.
- **SCA (durante la remediación, 2026-07-09):** se instaló y ejecutó `pip-audit`, que
  **encontró 4 CVEs reales** en las dependencias (`starlette`, `pydantic-settings`, `msgpack`,
  `ecdsa`). Tres se cerraron; `ecdsa` (transitiva de `python-jose`) no tiene fix disponible.
  `npm audit` sobre el frontend: **0 vulnerabilidades**. Ambos quedaron automatizados en CI.
  `bandit`/`semgrep` siguen sin ejecutarse (SAST no cubierto).

---

## Verificación de los 4 invariantes críticos

| # | Invariante | Veredicto | Evidencia |
|---|---|---|---|
| 1 | Rol `ai` no alcanza `clinical`/`pseudonym_map` | ⚠️ **Correcto a nivel BD, pero vacuo** | RLS niega `ftm_ai` sobre `pseudonym_map` (`api/db-migrations/migrations/ftm_schema.sql:527`) y no hay grant. PERO el rol `ftm_ai` **nunca se asume en runtime**: no está en `DB_ROLE_BY_APP_ROLE` (`api/app/db.py:23-28`) y `generate_insight` no tiene ningún caller. La frontera existe en SQL pero el código que debía respetarla no está conectado. |
| 2 | LLM no sale de la UE | ❌ **Violado** (al auditar) → 🟡 **mitigado técnicamente** | `api/app/ai/service.py:35` llamaba a `https://api.anthropic.com` (endpoint global, fuera de UE), sin config de región. **Remediado (2026-07-09):** URL externalizada a `llm_api_base` con default vacío y **fail-closed** (sin endpoint → cero peticiones salientes). **La base legal (art. 28 + SCC) sigue pendiente**, con endpoint UE o sin él. |
| 3 | Doble capa (RLS + RBAC) en cada endpoint sensible | ❌ **Violado** (el veredicto original era erróneo) → ✅ **Remediado (2026-07-13)** | **El veredicto inicial fue un falso positivo.** `require_role` + RLS **no** son dos capas para el rol médico: todas las policies `*_staff` son `TO ftm_gp, ftm_medical_specialist USING (true) WITH CHECK (true)` — verificado en el Postgres vivo con `pg_policies`. **La RLS no filtra NADA para un médico**; solo filtra para `ftm_patient` (policies `*_self`, todas `FOR SELECT`). Lo que daba la segunda capa en `recording` no era la RLS sino `ProgramExerciseAccessService` (Python), y `reporting`/`followup` **nunca lo llamaban** → BOLA explotable (hallazgo #11). **Remediado:** `ProgramAccessService` cableado en los 8 endpoints de `reporting`/`followup`. |
| 4 | `function_name` por whitelist, sin `eval`/`getattr` dinámico | ✅ **Cumple** | `api/app/analysis/registry.py:34-40`: lookup en dict `REGISTRY[name]`. Cero `eval`/`import` dinámico sobre input. |

---

## Pasada 1 — Arquitectura limpia / hexagonal

| Sev | Categoría | Ubicación | Hallazgo | Remediación |
|---|---|---|---|---|
| Medio | Capas inconsistentes | `api/app/*/` | Solo `clinical` tiene `domain/ports/adapters`. `recording`, `metrics`, `analysis`, `reporting`, `followup`, `iam` son paquetes planos (`models.py` + `router.py`) donde el router habla SQLAlchemy directo. No es hexagonal, es MVC plano con un módulo ejemplar. | Aceptar como "modular monolith pragmático" y ajustar la memoria, O extraer puertos en los módulos de dominio real. No inventar hexagonal donde no está. |
| Medio | Pureza de dominio | `api/app/worker.py:26-28` | El worker importa `metrics.models` y `recording.models` directamente y ejecuta SQL crudo cruzando 5 tablas de `clinical` (`api/app/worker.py:44-56`). Viola "ningún módulo llama a la BD de otro directamente, solo a su servicio". | Encapsular la resolución pseudónimo tras un servicio/puerto. |
| Bajo | Smell REGISTRY global | `api/app/analysis/registry.py:9` | `dict` global mutable de módulo. Aceptable para el MVP, pero es estado compartido. | Documentado como deuda; el acceso ya pasa por `registry.run()`, no se importa el dict crudo desde el worker (bien). |
| Bajo | `iam` bien adelgazado | `api/app/iam/` | ✅ No reimplementa identidad; es validación de token + audit + export/erasure. Conforme a la memoria. | — |

---

## Pasada 2 — OWASP Top 10:2025

| Sev | Cat | Ubicación | Hallazgo | Por qué importa aquí | Remediación |
|---|---|---|---|---|---|
| **Crítico** | A07 | `api/app/auth.py:48` | `verify_aud: False` — **no se valida el `aud`**. Cualquier token válido del realm (emitido para OTRO client) es aceptado. | Un token de `ftm-web` para otro fin, o de cualquier client del realm, entra a la API clínica. | **Remediación en 2 mitades obligatorias** (verificado empíricamente el 2026-07-09 con un token real de `paciente1`): el token emitido por `ftm-web` **no tiene claim `aud` en absoluto** (`aud=None`, `azp=ftm-web`), porque no hay audience mapper en el realm. Por tanto: **(1) Keycloak** — añadir un *Audience mapper* en `ftm-web` (o en un client scope) que inyecte `ftm-api` en `aud`; **(2) código** — recién entonces activar `verify_aud: True` + `audience="ftm-api"`. Activar solo (2) rompe el 100% de los logins. **✅ RESUELTO (2026-07-09)** — ambas mitades aplicadas: mapper `ftm-api-audience` en los dos `realm-export.json` + `auth.py:52-53` valida `aud`. Re-verificado con token real: `aud` pasó de `None` a `ftm-api`; `_decode` acepta el legítimo y rechaza `aud` incorrecto (`JWTClaimsError`). |
| **Crítico** | A07 | `api/app/auth.py:46` | Algoritmo tomado del **propio token**: `algorithms=[key.get("alg", "RS256")]`. Es la JWK, no el header, pero no se **fuerza** RS256 de forma fija. | Confusion de algoritmo / dependes de que la JWK nunca traiga algo débil. | Fijar `algorithms=["RS256"]` constante, nunca derivado. **✅ RESUELTO (2026-07-09)** — `auth.py:50` usa `algorithms=["RS256"]` fijo. |
| **Alto** | A02 | `api/app/main.py:29` | `/docs`, `/openapi.json`, `/redoc` **siempre activos** (el middleware los excluye del audit → confirmación de que están servidos). Sin flag para apagarlos en prod. | Superficie de descubrimiento de toda la API clínica en prod. | `docs_url=None, redoc_url=None, openapi_url=None` cuando `app_env=="prod"`. **✅ RESUELTO (2026-07-09)** — aplicado en `main.py`. Nota: nginx enruta `location /api/` completo a la app (`deploy/nginx/ftm.conf:41`) sin excluir `/api/docs`, así que estar "detrás de nginx" NO protegía. Verificado con TestClient: dev → 200, prod → 404. |
| **Alto** | A03 | `deploy/docker-compose.stack.yaml:20,79` | `postgres:16` y `python:3.12-slim` **sin digest**; `API_IMAGE` default `:latest`. | Build no reproducible; imagen puede cambiar bajo tus pies en un sistema con datos de salud. | Pin por `@sha256:`. MinIO ya está pinneado por RELEASE (bien). **🟡 PARCIAL (2026-07-09)** — bases pineadas por `tag@sha256:` (postgres, keycloak, minio, python). `API_IMAGE` sigue con default `:latest` (el fail-fast se revirtió a pedido del usuario). |
| **Alto** | A03 | entorno | **SCA no ejecutable**: `pip-audit`/`bandit`/`npm audit` no instalados. Deps con `>=` sin límite superior (`api/requirements.txt`). | Sin CVE scan no sabés si `librosa/scipy/jose` arrastran vulnerabilidades. `python-jose` tiene CVEs históricos (algorithm confusion). | Añadir `pip-audit` + `npm audit` en CI; pinnear deps. Evaluar migrar de `python-jose` a `PyJWT`/`authlib`. **✅ RESUELTO (2026-07-09)** — job `sca` en `ci.yml` + `requirements.txt` pineado. Al ejecutarlo aparecieron **4 CVEs reales**: 2 se cerraron al pinnear, `pydantic-settings`→2.14.2, y `ecdsa` (vía `python-jose`, sin fix) queda ignorada y documentada. |
| Medio | A09 | `api/app/main.py:65-86` | El audit **re-parsea el JWT sin validar firma** (`_extract_sub` decodifica base64 el payload). | Un `sub` falsificado puede contaminar la atribución del audit log — el propio registro de trazabilidad es manipulable. | Reusar el `sub` ya validado por `current_principal` (pasarlo por `request.state`), no re-decodificar. **✅ Remediado y verificado (2026-07-09):** `_extract_sub` (base64 sin verificar firma) **eliminado**; `current_principal` publica el `sub` en `request.state.auth_sub` **solo tras validación completa** (firma/iss/aud), y el middleware lo lee de ahí. Además el middleware ahora **solo audita respuestas 2xx** (antes registraba también las rechazadas con 401/403, atribuidas a un sub sin verificar). Verificado: 403 → no auditado, 201 → auditado con `actor_id` resuelto del sub validado. |
| Bajo | A05 | `api/app/db.py:71` | `SET LOCAL ROLE {db_role}` con f-string. | Parece inyección, **pero `db_role` sale de un dict cerrado** (`DB_ROLE_BY_APP_ROLE`), no de input. Mitigado por diseño. | Dejar comentario explicando la invariante para que nadie lo "arregle" mal en el futuro. **❌ Pendiente** — el comentario no se añadió. Sin riesgo activo (el valor no viene de input), pero la invariante sigue sin documentar en el código. |
| Info | A01 | `api/app/recording/router.py` | BOLA cubierto: `_require_authorized_recording` + RLS `rec_self` por `patient_id`. Doble capa real. | — | — |

---

## Pasada 3 — RGPD

| Sev | Categoría | Ubicación | Hallazgo | Remediación |
|---|---|---|---|---|
| **Crítico (legal)** | Residencia UE (art. 44+) | `api/app/ai/service.py:35` | Métricas pseudonimizadas (= dato personal) se envían a `api.anthropic.com` **fuera de la UE**, sin SCC ni región EU. | Usar endpoint/región UE del proveedor o LLM en UE. **Impacto legal directo.** **🟡 PARCIAL (2026-07-09)** — URL externalizada a `settings.llm_api_base` (default **vacío**) con **fail-closed**: sin endpoint configurado no se hace ninguna petición saliente (verificado con mock). Guard de prod: la app no arranca con `LLM_API_KEY` sin `LLM_API_BASE`. **La capa legal sigue abierta:** enviar métricas pseudonimizadas a un tercero exige contrato de encargo (art. 28) + SCC, con endpoint UE o sin él. |
| **Alto** | Revocación efectiva del consentimiento | `api/app/clinical/consent_service.py:108` + `api/app/worker.py:320` | La revocación pone `withdrawn_at`, y el guard bloquea **nuevas subidas** (`api/app/recording/router.py:340`). PERO el **worker NO re-verifica consentimiento** antes de procesar audio ya en cola. Revoco → el análisis en cola corre igual. | Chequear consentimiento activo en `process_one()` antes de ejecutar. **✅ RESUELTO (2026-07-09)** — migración `0015` (grant + policy `consent_worker` + estado `skipped`); `process_one()` re-chequea consentimiento **antes de descargar el WAV**, y si fue revocado **purga el audio** y marca el job `skipped/CONSENT_WITHDRAWN`. La purga queda en `audit.event_log` (art. 5.2). Verificado con el rol `ftm_worker` real. |
| **Alto** | Borrado / art. 17 | `api/app/iam/router.py:122-124` | Erasure es un **stub**: NO borra los WAV del bucket (dato biométrico, art. 9) — deferido explícitamente. El audio identificable por `program_exercise_id` sobrevive al "olvido". | Cascada real al bucket, aunque sea un job supervisado. Documentar retención mientras tanto. **✅ RESUELTO (2026-07-09)** — `_purge_patient_recordings` borra cada WAV del bucket (best-effort con log) y marca `media_status='purged'`. Las métricas se conservan (art. 17.3.c) pero quedan **irreversiblemente anónimas** al borrarse el `pseudonym_map` en la misma transacción. Probado bajo rol `ftm_patient`: 39 WAV → 0. **Deuda:** sin test unitario de erasure. |
| Medio | Cifrado en reposo | — | `national_id` cifrado con Fernet, clave en SOPS (`deploy/secrets.sops.yaml:25`) — **bien**. No se verificó cifrado del volumen Postgres ni del bucket. | Confirmar encryption-at-rest de disco/bucket. |
| Info | Pseudonimización | `api/db-migrations/migrations/ftm_schema.sql:85` | `pseudonym_id` con `gen_random_uuid()` (CSPRNG). No reversible por fuerza bruta. **Correcto.** | — |
| Info | DPIA | — | No hay artefacto DPIA en el repo (tratamiento biométrico art. 35 lo exige). | Documentar DPIA fuera del código. |

---

## TOP 10 priorizado — acción inmediata

| # | Hallazgo | Sev | Impacto legal (RGPD) | Acción | Estado |
|---|---|---|---|---|---|
| 1 | **LLM fuera de UE** (`api/app/ai/service.py:35`) | Crítico | Sí | Endpoint/región UE antes de cualquier tráfico real | 🟡 **Remediado a nivel técnico** — URL externalizada a `llm_api_base` (default vacío), fail-closed si no hay endpoint, guard de prod. **Pendiente legal:** contrato de encargo de tratamiento (art. 28) + SCC antes de enviar datos a cualquier proveedor. |
| 2 | **JWT sin `aud`** (`api/app/auth.py:48`) | Crítico | | `verify_aud: True` + audience fija | ✅ **Remediado y verificado (2026-07-09)** — audience mapper `ftm-api-audience` añadido a `ftm-web` en ambos `realm-export.json`; `auth.py` valida `aud` contra `settings.keycloak_audience`. Probado con token real: `aud=ftm-api` aceptado, `aud` incorrecto rechazado con `JWTClaimsError`. |
| 3 | **Algoritmo JWT no forzado** (`api/app/auth.py:46`) | Crítico | | `algorithms=["RS256"]` constante | ✅ **Remediado (2026-07-09)** — `algorithms=["RS256"]` fijo, ya no derivado del header/JWK. Cierra el vector de algorithm confusion. |
| 4 | **Worker no re-chequea consentimiento** (`api/app/worker.py:320`) | Alto | Sí | Guard de consentimiento en `process_one()` | ✅ **Remediado y verificado (2026-07-09)** — migración `0015` da `SELECT` sobre `patient_consent` a `ftm_worker` + policy `consent_worker` + estado `skipped`. `process_one()` re-chequea consentimiento antes de descargar el WAV; si fue revocado, **purga el audio del bucket** (`storage.delete` + `media_status='purged'`) y marca el job `skipped/CONSENT_WITHDRAWN`. Probado con el rol `ftm_worker` real: consent activo → procesa, revocado → salta. La purga se registra en `audit.event_log` (`_audit_consent_purge`, vía `AuditSessionLocal` con el usuario de login — sin grants nuevos al worker) para trazabilidad art. 5.2; verificado que escribe la fila. |
| 5 | **Erasure no borra WAV** (`api/app/iam/router.py:122`) | Alto | Sí | Cascada al bucket | ✅ **Remediado y verificado (2026-07-09)** — `erase_my_data` ahora invoca `_purge_patient_recordings`, que recorre los recordings del paciente y borra cada WAV del bucket (best-effort con log; un fallo de storage no aborta la anonimización) + marca `media_status='purged'`. Las métricas pseudonimizadas se conservan (art. 17.3.c) pero quedan **irreversiblemente anónimas** al borrarse el `pseudonym_map` en la misma transacción. Probado bajo el rol `ftm_patient`: 39 WAV → 0 con media_uri, 39 marcados purged. **Deuda:** sin test unitario de erasure. |
| 6 | **`/docs` expuesto en prod** (`api/app/main.py:29`) | Alto | | Apagar docs si `app_env=prod` | ✅ **Remediado y verificado (2026-07-09)** — `docs_url`/`redoc_url`/`openapi_url=None` en prod. Defensa en profundidad: nginx enruta `location /api/` completo a la app (`deploy/nginx/ftm.conf:41`) sin excluir `/api/docs`, así que en prod esas rutas SÍ llegaban a FastAPI. Verificado con TestClient: dev → 200, prod → 404 (las tres); `/health` intacto. |
| 7 | **Imágenes sin digest / `:latest`** (`deploy/docker-compose.stack.yaml:166`) | Alto | | Pin `@sha256`, quitar `:latest` | 🟡 **Parcialmente remediado (2026-07-09)** — imágenes base `postgres:16`, `keycloak:26.6.3`, `minio:RELEASE...` y `python:3.12-slim` (Dockerfile) pineadas por `tag@sha256:` (digests reales validados hoy). **`API_IMAGE` sigue con default `:latest`** — el fail-fast `${API_IMAGE:?...}` se revirtió a pedido del usuario para no romper el flujo de deploy actual (el workflow `deploy.yml` publica `:${{github.sha}}` + `:latest`). **Pendiente:** que el deploy consuma el tag `:<sha>` inmutable en vez de `:latest`, alineando `deploy.yml:4` y el RUNBOOK. |
| 8 | **Sin SCA en CI** (deps `>=`) | Alto | | `pip-audit`+`npm audit`; evaluar dejar `python-jose` | ✅ **Remediado y verificado (2026-07-09)** — job `sca` en `ci.yml` (`pip-audit` + `npm audit`, no bloqueante al inicio como `alembic check`); `api/requirements.txt` pineado a versiones exactas (antes `>=`). Descubrió 4 CVEs vivos: 2 se resolvieron al pinnear (FastAPI arrastra starlette parcheado), `pydantic-settings` subida a 2.14.2, y `ecdsa` (transitiva de `python-jose`, **sin fix**) ignorada explícitamente. Verificado: `pip-audit` → "No known vulnerabilities found, 1 ignored". **Deuda:** migrar de `python-jose` a `PyJWT`/`authlib` para eliminar `ecdsa`; quitar `continue-on-error` cuando el backlog esté al día. |
| 9 | **Audit re-parsea JWT sin validar** (`api/app/main.py:83`) | Medio | Sí | Usar `sub` ya validado | ✅ **Remediado y verificado (2026-07-09)** — `_extract_sub` eliminado; el `sub` viaja por `request.state.auth_sub`, escrito solo tras validación completa. **Se descubrió un segundo agujero mayor:** el middleware auditaba también los requests **rechazados** (401/403), así que un no-autenticado podía inyectar filas de audit atribuidas a un médico. Ahora solo se auditan respuestas 2xx. Verificado: 403 → no auditado, 201 → auditado con actor correcto. |
| 10 | **Frontera `ai` es teórica** (`api/app/db.py:23`) | Medio | Sí | Ver nota abajo | ❌ **Pendiente** — requiere cablear `SET LOCAL ROLE ftm_ai` antes de leer `v_ai_payload`. Ver la observación de fondo al final del informe. |

### Observación de fondo — la frontera de anonimización está escrita pero desarmada

La memoria describe una **frontera de anonimización con un rol `ftm_ai` que físicamente no
alcanza `clinical`**. La RLS está impecablemente escrita para eso. **Pero el código runtime
nunca usa ese rol.** `generate_insight` no tiene callers, y `DB_ROLE_BY_APP_ROLE` no mapea
`ai`. Esto es un **GAP de implementación vs. memoria** puro: la defensa más elegante del
sistema está diseñada en SQL y desconectada en Python.

Consecuencia doble:

- **Lo bueno:** hoy no hay egress real al LLM en producción viva, así que el hallazgo #1
  (fuga fuera de UE) es un riesgo *latente*, no *activo* — todavía.
- **Lo malo:** el día que se conecte `generate_insight`, si se hace con la conexión
  `ftm_app` genérica en vez de forzar `SET LOCAL ROLE ftm_ai`, la frontera **no protege**,
  porque `ftm_app` hereda todos los roles (`api/db-migrations/migrations/versions/0004_runtime_grants.py:18`).
  La RLS de `ftm_ai` solo aplica si se asume ese rol, y hoy nadie lo asume.

El `SET LOCAL ROLE ftm_ai` **antes** de leer `v_ai_payload` es lo que convierte el diseño
en control real. Sin eso, es documentación.
