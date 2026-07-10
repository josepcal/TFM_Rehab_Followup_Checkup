# Segunda auditoría — revisión de la remediación (audit del diff)

## Anclaje

| Campo | Valor |
|---|---|
| **Base (código auditado en la 1ª pasada)** | `85780d7` |
| **HEAD en el momento de esta revisión** | `66b1d30` + working tree |
| **Superficie auditada** | Diff `85780d7 → HEAD` (16 ficheros, 355 inserciones) |
| **Fecha** | 2026-07-09 |
| **Alcance** | Solo el código escrito **para remediar** la 1ª auditoría. No re-audita el resto del repo. |

### Por qué esta auditoría

El código que corrige una vulnerabilidad es código nuevo, y el código nuevo tiene bugs.
Los cambios de remediación tocaron superficie crítica (validación de tokens, middleware de
auditoría, gate de consentimiento, borrado de datos biométricos, grants de BD) que **nadie
había auditado**, porque no existía cuando se hizo la primera pasada.

**Método:** revisión adversarial del diff, buscando activamente qué se rompió al arreglar.
Cada hallazgo se verificó empíricamente contra la BD real antes de afirmarlo; las sospechas
que no se sostuvieron se retiran explícitamente (ver *Sospechas descartadas*).

---

## Hallazgos

| # | Sev | Ubicación | Hallazgo | Verificación |
|---|---|---|---|---|
| R1 | **Crítico** | `api/app/worker.py` (`_has_active_consent`) | **El fix del #4 no cierra el agujero que dice cerrar.** El consentimiento es append-only sin UNIQUE (la migración `0012` lo elimina a propósito). `grant()` **siempre inserta** una fila activa sin revocar las previas; `withdraw()` revoca **solo la más reciente** (`order_by(...).limit(1)`). Dos `grant` (doble click, reintento de red, dos pestañas) → dos filas activas → un `withdraw` deja una viva. `_has_active_consent` pregunta *"¿existe ALGUNA fila con `withdrawn_at IS NULL`?"* → devuelve `True`. **El paciente revocó y el worker procesa su audio biométrico igual.** | ✅ Demostrado contra la BD: tras 2 grants + 1 withdraw quedaron 2 filas activas y `_has_active_consent = True`. **✅ RESUELTO (2026-07-09)** — corregido por dos vías que se refuerzan: (a) `_has_active_consent` y `get_active` miran ahora la fila **más reciente** del trail (ordenan primero, luego comprueban `withdrawn_at`), no *"¿alguna activa?"*; (b) `withdraw()` revoca **todas** las filas activas con un timestamp compartido, no solo la última. Verificado contra la BD (mismo escenario + contraprueba de fila huérfana antigua → `False`) y con test de regresión `test_withdraw_closes_all_duplicate_active_rows`. Suite: 197 unit passed. También afectaba al guard de subidas (`get_active` vía `require_active_consent`), ahora igualmente cerrado. |
| R2 | **Alto (legal)** | `api/app/iam/router.py` (`_purge_patient_recordings`) | **Registro falso de cumplimiento del art. 17.** Si el borrado en el bucket falla (MinIO caído, credencial rota), el `except` lo loguea y **continúa**: pone `media_uri = None` y `media_status = 'purged'`. La BD afirma que el audio se borró, el bucket lo conserva, y al perder `media_uri` **ya no se sabe qué objeto quedó huérfano**. `erase_my_data` devuelve **204 OK**. Ante una inspección, el sistema miente. | ✅ Demostrado con storage mockeado a fallo: `media_uri=None`, `media_status='purged'`, sin excepción. **✅ RESUELTO (2026-07-09)** — **fail-closed:** se quitó el `try/except`; si `storage.delete` falla, la excepción propaga y, como `erase_my_data` corre en una transacción única (`get_db → session.begin()`), **toda la anonimización hace rollback** y el endpoint devuelve 500. Una fila se marca `purged` **solo tras** borrar el objeto de verdad. Verificado: storage caído → excepción propagada, `media_uri` conservado, `media_status='available'` (nada certificado en falso); storage OK → 40 WAV purgados (40→0). Suite: 197 unit passed. Import `logging` huérfano eliminado de paso. |
| R3 | **Alto** | `api/db-migrations/.../0015_worker_consent_read.py` (`downgrade`) | **El rollback de la migración se rompe.** El `downgrade()` restaura el CHECK sin `'skipped'` pero **no limpia las filas que ya tienen ese estado**. Con un solo job `skipped` (los que crea el propio fix del #4), el `ADD CONSTRAINT` falla — y como el `DROP CONSTRAINT` ya se ejecutó, la tabla queda **sin constraint**. Un rollback de emergencia en prod deja la BD peor que antes. | ✅ Reproducido: `ERROR: check constraint "ck_analysis_job_status" ... is violated by some row`. **✅ RESUELTO (2026-07-09)** — el `downgrade()` ahora hace `UPDATE ... SET status='error' WHERE status='skipped'` **entre** el DROP y el ADD del constraint (el `error_detail='CONSENT_WITHDRAWN'` se conserva, así que el motivo no se pierde). Verificado con el **ciclo alembic completo** (`upgrade → downgrade → upgrade`) con un job `skipped` real presente: baja sin error, migra el job a `error`, y vuelve a subir dejando el CHECK con `skipped`. |
| R4 | **Medio** | `api/app/main.py` (`AuditMiddleware.dispatch`) | **Se perdió la detección de intrusión.** El filtro `200 <= status < 300` (introducido para no auditar acciones inexistentes) elimina el rastro de **todo acceso denegado**. La guía de auditoría pide explícitamente en A09 (`AUDIT_FTM.md:101`): *"Alerting en fallos de RLS / **autorización denegada repetida**"*. Un atacante probando 500 `id`s ajenos (BOLA) genera 500 respuestas 403 que ahora **no dejan ningún rastro**. Se cambió un problema (atribución falsificable) por otro (ceguera ante ataques). El modelo `EventLog` no tiene columna para distinguir *acción realizada* de *intento denegado*. | ✅ Confirmado por lectura del código + requisito explícito en la guía. **✅ RESUELTO (2026-07-09)** — migración `0016` añade columna `outcome` (`success`/`denied`, CHECK + índice parcial sobre los `denied`). El middleware ahora audita **2xx como `success` y 401/403 como `denied`**; el resto (400/404/5xx) sigue sin auditarse (no son ni acción ni decisión de autorización). Se reconcilian los dos requisitos: no se atribuye una acción inexistente a un sub falso (un 401 sin sub validado → `actor_id=NULL`), pero el intento denegado **sí queda registrado** para A09. Verificado: POST denegado (403) → fila `denied` con `/patients|create|denied`; caso 2xx sigue como `success` (19 success + 1 denied); migración reversible (downgrade+upgrade limpio); 197 unit passed. |
| R5 | **Bajo** | `api/app/config.py` / `ai/service.py` | **La invariante "endpoint UE" está documentada pero no aplicada.** El fail-closed exige que `llm_api_base` esté configurado, pero **acepta cualquier URL** — incluido `https://api.anthropic.com` (el endpoint global, no-UE) que el hallazgo #1 pretendía evitar. El comentario dice *"MUST be an EU-resident endpoint"*; nada lo verifica. | ✅ Confirmado por lectura: no hay validación del valor. |
| R6 | **Bajo** | `api/app/worker.py:92` | **Código muerto:** `ConsentWithdrawnError` se define y nunca se lanza ni se captura. Introducida durante la remediación del #4 y no usada. | ✅ `rg` confirma una sola aparición (la definición). **✅ RESUELTO (2026-07-09)** — eliminada junto al arreglo de R1. |
| R7 | **Info** | `api/app/auth.py` (modo dev) | En `auth_mode=dev`, `request.state.auth_sub = "dev-user"`, que no existe en `clinical.app_user`. El audit log registra la acción con `actor_id = NULL`. No es un riesgo (dev nunca corre en prod, bloqueado por `get_settings`), pero la atribución en dev es inexistente. | ✅ Confirmado por lectura. |

---

## Sospechas descartadas (verificadas y retiradas)

Se investigaron y **no se sostienen**. Se documentan para dejar constancia de que se miraron:

| Sospecha | Por qué se descarta |
|---|---|
| `_purge_patient_recordings` dejaría recordings huérfanos fuera de la cadena de joins | `clinical.rehab_program.diagnostic_id` es **NOT NULL**, así que todo recording es alcanzable. Verificado contra la BD: 41 recordings con WAV, 41 alcanzables por la query. |
| El pin de dependencias rompió los tests | Falso. Los 3 tests unitarios rotos lo estaban por el gate de consentimiento del #4 (`FakeSession` sin `execute`). Los 28 de integración fallaban porque se ejecutaron sin `AUTH_MODE=dev` (el `api/.env` local fuerza `keycloak`). Con el entorno correcto: **196 + 30 + 1 tests pasan**. |

---

## Veredicto

La remediación **cerró los hallazgos que se propuso cerrar** en A07 (×2), A02, A03 y A09, y
todos fueron verificados en su momento. Pero introdujo **tres defectos de severidad Alta o
superior** (R1, R2, R3) y **degradó una capacidad de seguridad existente** (R4).

El más grave es **R1**: el fix del hallazgo #4 (worker no re-chequea consentimiento) **no
funciona** en presencia de consentimientos duplicados, que son alcanzables desde el endpoint
público del paciente sin ninguna barrera. El agujero RGPD art. 7.3 sigue abierto.

**R2** es el de peor impacto legal: no solo no borra, sino que **certifica falsamente** que
borró, y destruye el puntero necesario para limpiar después.

### Orden de corrección recomendado

1. **R1** — `_has_active_consent` debe mirar el **estado más reciente** del consentimiento, no
   *"¿existe alguna fila activa?"*. Alternativamente (mejor), arreglar la raíz: `grant()` debe
   revocar las filas activas previas antes de insertar, o `withdraw()` revocar **todas**.
2. **R2** — Un fallo de storage debe **abortar** la anonimización (transacción) o, si se opta por
   best-effort, **conservar `media_uri`** y marcar `media_status='purge_failed'` para poder reintentar.
   Nunca escribir `purged` sobre un objeto que sigue vivo.
3. **R3** — El `downgrade()` debe migrar las filas `skipped` a un estado válido (p. ej. `error`)
   **antes** de restaurar el CHECK.
4. **R4** — Auditar también los denegados, distinguiéndolos: añadir columna `outcome`
   (`success` / `denied`) al `EventLog`, o un `action` distinto. Solo entonces filtrar por 2xx
   deja de perder señal.
5. **R5, R6, R7** — Menores; ver tabla.

> **Nota de método.** Estos hallazgos salieron de auditar mi propio trabajo de remediación con
> ojo adversarial. Ninguno era visible desde la primera auditoría porque el código no existía.
> Es la evidencia de por qué un ciclo *auditar → remediar → re-auditar el diff* vale más que
> una auditoría suelta.
