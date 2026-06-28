# ADR — Medical Rehab Follow-up Check-up Tool (FTM)

Registro de decisiones arquitecturales. Estilo Nygard (Estado · Contexto · Decisión · Consecuencias).

- **Fecha de registro:** 2026-06-28
- **Alcance:** MVP (≈20 días, 1 desarrollador). Decisiones reversibles salvo indicación.
- **Fuentes:** Plan de implementación · SDD v1.8 · `ftm_schema.sql` / `models.py`.
- **Estados:** `Aceptada` · `Aceptada (deuda)` (con compromiso conocido) · `Pendiente PO` (requiere visto bueno de product owner/legal).

> Las decisiones marcan el estado **implementado** en la capa de datos + diseño. La capa de
> aplicación (API, worker, frontend, IaC) está especificada pero sin construir.

---

## ADR-0001 — Monolito modular en lugar de microservicios
- **Estado:** Aceptada
- **Contexto:** MVP en 20 días con 1 desarrollador. Los microservicios añaden despliegue, observabilidad, contratos entre servicios y red.
- **Decisión:** Monolito modular cuyos módulos (`iam`, `clinical`, `recording`, `metrics`, `analysis`, `reporting`) son los futuros servicios si el producto crece. Ningún módulo accede a la BD de otro salvo por su servicio. Para casos de uso no triviales, los módulos pueden organizarse con arquitectura hexagonal / ports-and-adapters: router → application service → port/protocol → infrastructure adapter.
- **Consecuencias:** Separación lógica hoy, física mañana sin reescritura. Los casos con reglas de negocio, autorización o persistencia compleja quedan desacoplados de FastAPI y SQLAlchemy mediante puertos/adaptadores. No se exige esta estructura para endpoints triviales. Un worker asíncrono aparte para el procesamiento pesado.

## ADR-0002 — Backend Python 3.12 + FastAPI
- **Estado:** Aceptada
- **Contexto:** El núcleo sensible es el análisis de señal de audio y el LLM, donde Python es nativo (librosa, scipy, NumPy, SDKs de LLM).
- **Decisión:** FastAPI + Pydantic v2 + SQLAlchemy 2.0; migraciones con Alembic.
- **Consecuencias:** APIs tipadas y OpenAPI gratis; mismo lenguaje en API y análisis.

## ADR-0003 — Frontend SPA React + Vite + TypeScript
- **Estado:** Aceptada
- **Contexto:** Se necesita grabación de audio en navegador (`MediaRecorder`) y gráficas de seguimiento; sin app nativa en MVP.
- **Decisión:** React 18 + Vite + TS, TanStack Query, Recharts, `keycloak-js`.
- **Consecuencias:** Web responsive cubre la grabación; app nativa queda fuera del MVP.

## ADR-0004 — Autenticación delegada en Keycloak (OIDC/OAuth2 + PKCE S256)
- **Estado:** Aceptada
- **Contexto:** No queremos gestionar credenciales ni el ciclo de vida de usuarios en la app; datos de salud exigen un IdP robusto.
- **Decisión:** Keycloak como IdP. El SPA es client público con Authorization Code + PKCE (S256). El backend es bearer-only: valida la firma del JWT contra el JWKS y lee rol/`sub` de los claims. Roles: `medical` (gp/especialista), `patient`, `technician`, `admin`.
- **Consecuencias:** Cero contraseñas en la app. `app_user` solo guarda `external_subject`/identidad y rol, no credenciales.

## ADR-0005 — PostgreSQL con separación por esquemas
- **Estado:** Aceptada
- **Contexto:** El requisito de "espacios de datos separados" por rol y la frontera de anonimización.
- **Decisión:** Un PostgreSQL con 6 esquemas: `clinical`, `recording`, `metrics`, `setup`, `audit`, `reference`. La BD de la app es **distinta** de la de Keycloak.
- **Consecuencias:** Aislamiento lógico que materializa los espacios de la spec; base para los grants por esquema y la RLS (ADR-0014).

## ADR-0006 — Grabaciones en object storage privado, no en la BD
- **Estado:** Aceptada
- **Contexto:** El audio (WAV) es voz = dato biométrico de categoría especial; no debe exponerse ni inflar la BD.
- **Decisión:** Bucket privado con signed URLs (S3/GCS gestionado, o MinIO self-host). La BD guarda solo metadatos (`media_uri`, `duration_seconds`, `sample_rate`, `size_bytes`, `sha256`).
- **Consecuencias:** Lifecycle y caducidad de enlaces; borrado lógico del media manteniendo métricas e informes.

## ADR-0007 — Worker asíncrono para extracción y LLM
- **Estado:** Aceptada
- **Contexto:** La extracción de métricas y la llamada al LLM no deben bloquear la API. Son además procesamiento potencialmente pesado (CPU para el análisis de audio, latencia de red para el LLM) que conviene aislar del proceso que sirve el resto de los endpoints (ADR-0001), tanto para no degradar la API bajo carga como para poder escalar el worker de forma independiente.
- **Decisión:** Worker como contenedor aparte; cola ligera (Redis + RQ o tabla de jobs en Postgres con `SKIP LOCKED`). La API solo encola `{recording_id, function_name}` y responde de inmediato; el worker resuelve el job, ejecuta con timeout y captura de errores.
- **Consecuencias:** El insight de IA es opcional y asíncrono; los fallos se registran como estado de error (ver ADR-0009). **No hay reintento automático:** un fallo deja el job en estado de error y el reanálisis es un disparo manual nuevo que sobrescribe el resultado anterior (ADR-0010, ADR-0011) — este worker no implementa una política de retry/backoff.

## ADR-0008 — Extracción de métricas agnóstica
- **Estado:** Aceptada
- **Contexto:** El sistema no debe conocer la semántica de las métricas; el técnico define el análisis.
- **Decisión:** `analysis_setup` referencia una función/endpoint de análisis por nombre (`metric_api_endpoint`); `metric_definition` declara qué métricas devuelve (con composición ponderada). El sistema ejecuta y persiste el JSON íntegro (`metric_result.raw_json`) y las métricas aplanadas (`recording_metric`), sin interpretarlas. Las funciones se despliegan con el código (PR + revisión), no se suben en runtime.
- **Consecuencias:** Añadir un ejercicio = registrar su función + definiciones, sin tocar el núcleo. No hay ejecución de código arbitrario (no hay sandboxing en runtime).

## ADR-0009 — Trazabilidad clínica de la ejecución vía git
- **Estado:** Aceptada
- **Contexto:** Una métrica clínica debe ser reproducible/auditable: ¿qué función y versión la produjo?
- **Decisión:** Sin firma digital por función. La cadena de custodia es git (PR + deploy), materializada en `metric_result`: `function_name`, `function_version` y `code_sha` (commit desplegado), más `status` (`success`/`error`) y `error_detail`. `raw_json` opcional con CHECK (`status=success ⇒ raw_json` presente).
- **Consecuencias:** Auditoría "esta métrica la produjo X@commit Y el día Z" sin infraestructura de firma.

## ADR-0010 — `metric_result` 1:1 con la grabación
- **Estado:** Aceptada (deuda)
- **Contexto:** ¿Una grabación tiene un resultado de análisis o un histórico de reanálisis?
- **Decisión:** `metric_result.recording_id` es UNIQUE (1:1). Un reanálisis **actualiza** el resultado; no se versiona.
- **Consecuencias:** Modelo simple. El disparo de análisis (ADR-0011) no genera histórico. **Deuda:** el histórico de reanálisis exigiría relajar el UNIQUE.

## ADR-0011 — Disparo del análisis por médico o paciente, asíncrono
- **Estado:** Aceptada
- **Contexto:** ¿Quién lanza el análisis de una grabación?
- **Decisión:** Lo lanza quien tenga lectura RLS sobre la grabación —en la práctica médico o paciente— de forma asíncrona (`POST /recordings/{id}/run`). El técnico queda excluido por RLS. La función se toma del `analysis_setup` del ejercicio salvo override.
- **Consecuencias:** Sin auto-trigger al subir; un clic explícito. Reanálisis = sobrescritura (ADR-0010).

## ADR-0012 — Atestación simple, no firma electrónica cualificada
- **Estado:** Pendiente PO
- **Contexto:** El diagnóstico y el informe necesitan "firma". ¿Cualificada (eIDAS)?
- **Decisión (default MVP):** Atestación simple = identidad del médico (`sub` Keycloak + `colegiado_id`) + timestamp (`signed_at`/`attested_at`) + hash inmutable del contenido (`content_hash`), registrada en `audit`/`event_log`. NO es firma cualificada.
- **Consecuencias:** Cubre el MVP. El upgrade a un QTSP (lista de confianza / Cl@ve-Autofirma) queda post-MVP, pendiente de PO/legal.

## ADR-0013 — Frontera de pseudonimización ante el LLM
- **Estado:** Aceptada
- **Contexto:** El plan prometía que el LLM nunca viera identidad ni audio, pero el modelo no lo garantizaba (claves enlazables, puntero al media).
- **Decisión:** (1) `clinical.pseudonym_map` (identidad↔pseudónimo) en la zona identificada, bajo RLS, sin acceso para la IA. (2) `metric_result.pseudonym_id` **sin FK** → borrar el mapa anonimiza las métricas (derecho al olvido). (3) Vista `metrics.v_ai_payload` como única interfaz del rol `ftm_ai` (pseudónimo + valores). (4) Rol `ftm_worker` cruza la frontera (resuelve el pseudónimo y escribe métricas; no llama al LLM). (5) El egress relativiza fechas y solo envía métricas declaradas + el criterio revisado.
- **Consecuencias:** Al LLM solo cruzan métricas acústicas pseudonimizadas. Pseudonimización ≠ anonimización (art. 32 RGPD): sigue requiriendo DPA con el proveedor y procesamiento UE (ADR-0015). `ftm_ai` ve todas las filas pseudónimas vía la vista; el acotado por petición lo hace el código.

## ADR-0014 — Row-Level Security por paciente/rol
- **Estado:** Aceptada (deuda)
- **Contexto:** El grant daba a `ftm_patient` lectura sobre todo `clinical`; hace falta aislamiento por fila.
- **Decisión:** RLS en las tablas con datos de paciente. Contrato de sesión: la app conecta con el login del rol y fija `SET app.identity_id`; nunca como owner (sin `FORCE`, para que owner y funciones SECURITY DEFINER omitan RLS y evitar recursión). Helpers `current_patient_id/_doctor_id/_pseudonym`. Predicados: paciente solo lo suyo (por `patient_id`, por cadena `EXISTS`, o por pseudónimo en métricas); médicos (gp + especialista) a nivel de **clínica**; técnico e IA fuera de los datos clínicos; worker con lectura para resolver el pseudónimo.
- **Consecuencias:** Defensa en profundidad (un bug de la API no filtra filas fuera de rol). **Deuda:** el particionado por médico (cada médico solo sus pacientes) requiere una tabla de relación de cuidado. **Riesgo operativo:** la app NO debe conectar como owner. **Sin verificar:** las políticas necesitan tests de aislamiento contra un PostgreSQL real (hito D18).

## ADR-0015 — Residencia de datos en la UE
- **Estado:** Aceptada
- **Contexto:** Datos de salud + voz biométrica bajo RGPD.
- **Decisión:** Todos los recursos en región UE. **FR-16:** grabaciones en la UE. **FR-17:** procesamiento del LLM en la UE, solo métricas pseudonimizadas, sin entrenamiento con los datos.
- **Consecuencias:** Restringe la elección de proveedor de LLM y de storage; exige DPA.

## ADR-0016 — Alta de pacientes por Administrador (MVP)
- **Estado:** Aceptada (deuda)
- **Contexto:** ¿El paciente se auto-registra o lo da de alta la clínica?
- **Decisión:** En MVP el alta de pacientes la realiza el Admin (UC-11); no hay auto-registro de paciente. Keycloak emite la credencial.
- **Consecuencias:** Evita auto-registro público sobre datos sensibles. **Deuda:** perfiles de gestión más ricos a iterar después.

## ADR-0017 — Migraciones con Alembic en modo SQL-first
- **Estado:** Aceptada
- **Contexto:** `ftm_schema.sql` contiene vista, funciones, roles, grants y RLS que el autogenerate de Alembic no genera.
- **Decisión:** `ftm_schema.sql` es la fuente de verdad inicial. La revisión baseline (`0001`) ejecuta el DDL íntegro (con un snapshot propio bundleado). `env.py` cablea `target_metadata = models.Base.metadata` para el autogenerate de tablas en migraciones futuras; vista/roles/grants/RLS se añaden a mano con `op.execute`. No se mezcla con `create_all()`.
- **Consecuencias:** A partir de la baseline, las migraciones son la fuente de verdad. `models.py` y `ftm_schema.sql` se mantienen en espejo a mano.

## ADR-0018 — Despliegue en contenedores tras nginx, reutilizando la IaC
- **Estado:** Aceptada
- **Contexto:** Existe IaC empezada (nginx + Keycloak + postgres-keycloak); el plazo no admite reinventarla.
- **Decisión:** Se extiende esa IaC con `api`, `worker` y `postgres-app`. nginx es el único punto de entrada (TLS, HSTS/CSP/CORS, enrutado a `/`, `/api`, `/realms`). Misma topología en local (docker-compose) y prod. Realm de Keycloak como `realm-export.json`.
- **Consecuencias:** Despliegue temprano (D5) y "siempre desplegable". Mapeo directo a servicios gestionados (ALB, RDS, S3) si se escala.

## ADR-0019 — Selección de proveedor de LLM y almacenamiento (residencia UE)
- **Estado:** Aceptada (provisional — confirmar DPA, región y cláusula de no-entrenamiento al contratar)
- **Contexto:** ADR-0015 exige residencia UE para las grabaciones y para el procesamiento del LLM, lo que restringe la elección de proveedor. Además, una herramienta de rehabilitación médica probablemente sea un **sistema de IA de alto riesgo** bajo el EU AI Act (plena aplicación para alto riesgo el 2 de agosto de 2026), lo que favorece proveedores con modelo auditable y residencia UE contractual.
- **Decisión (MVP):**
  - **LLM — opción por defecto:** mantener **Claude** (ya referenciado en el modelo/seed) desplegado por una vía con residencia UE — **AWS Bedrock** (región UE, p. ej. Fráncfort) o **Google Vertex AI** con endpoints UE, donde Anthropic no retiene datos para entrenamiento y aplica el DPA del hiperescalar.
  - **LLM — alternativa soberana documentada:** **Mistral** (UE-nativo, datos en centros UE, no-entrenamiento contractual, y opción de auto-hospedar modelos open-weight a futuro). Preferible si la soberanía pesa más que el modelo concreto.
  - **Almacenamiento (WAV + BD):** región UE, preferentemente **España** — AWS `eu-south-2` (Aragón), Azure Spain Central o GCP `europe-southwest1` (Madrid); o **self-host MinIO** sobre infra UE. Proveedores europeos soberanos (OVHcloud, Scaleway, Hetzner, IONOS) como opción sin exposición a la CLOUD Act.
- **Alternativas consideradas:** Azure OpenAI / OpenAI con residencia UE (familia GPT); modelo open-weight **auto-hospedado** end-to-end (máxima soberanía, mayor coste operativo — descartado para el MVP por el plazo de 20 días).
- **Consecuencias:** Sobrecoste de los endpoints regionales (p. ej. +10% en Vertex UE) y dependencia del DPA por proveedor. Mistral reduce la superficie Schrems II / CLOUD Act y encaja mejor con el AI Act, a cambio de cambiar de modelo. Decisión a **confirmar contractualmente** y a revisar conforme evolucionen las ofertas de residencia. Enlaza con ADR-0013 (solo cruzan métricas pseudonimizadas) y ADR-0015 (residencia UE).

## ADR-0020 — Cola de jobs de análisis en Postgres (`SKIP LOCKED`), sin broker externo
- **Estado:** Aceptada
- **Contexto:** ADR-0007 dejó abierta la elección entre Redis+RQ y una tabla Postgres con `SELECT … FOR UPDATE SKIP LOCKED`. Para el MVP (1 desarrollador, 20 días, datos de salud en UE) sumar Redis implica otro servicio, otra imagen en docker-compose, otra dependencia de residencia y otro punto de fallo operativo.
- **Decisión:** Cola implementada como tabla `metrics.analysis_job` con las columnas `id`, `recording_id`, `function_name`, `status` (`pending` / `running` / `done` / `error`), `attempts`, `error_detail`, `locked_at`, `created_at`, `updated_at`. El worker reclama jobs con `SELECT … FOR UPDATE SKIP LOCKED` dentro de una transacción, lo que garantiza que varios workers paralelos nunca procesen el mismo job. La API encola con `INSERT` + `FLUSH`; el worker resuelve y actualiza el estado.
- **Consecuencias:** Cero dependencias adicionales; la BD ya es el sistema de registro (ADR-0005). La durabilidad y el aislamiento los da Postgres de forma nativa. **Limitación asumida:** no hay retry/backoff automático (coherente con ADR-0007); un job en `error` requiere un disparo manual nuevo. La tabla no particiona ni archiva jobs históricos en el MVP — **deuda:** limpiar filas viejas si el volumen crece.

## ADR-0021 — Audit log sin IP ni session_id
- **Estado:** Aceptada
- **Contexto:** UC-15 introduce `audit.event_log` para el registro de mutaciones clínicas. Se evaluó añadir `ip text` y `session_id text` a la tabla.
- **Decisión:** Ninguno de los dos campos se almacena en `audit.event_log`.
  - **IP:** nginx captura la IP en su access log — es su capa de responsabilidad. Duplicarla en la BD clínica no añade valor clínico y viola el principio de minimización de datos (RGPD art. 5.1.c).
  - **Session ID:** el ciclo de vida de sesión pertenece al IdP (Keycloak). El JWT ya lleva `sub` (actor) + `iat`/`exp` (ventana temporal). Rastrear "qué hizo este usuario en esta sesión" se resuelve filtrando `actor_id` + rango de `occurred_at`, sin estado de sesión en la BD clínica.
- **Consecuencias:** La tabla queda con los campos mínimos necesarios para accountability RGPD: `entity_type`, `entity_id`, `action`, `actor_id`, `payload`, `occurred_at`. Para trazabilidad de IP se consultan los logs de nginx; para trazabilidad de sesión se consulta Keycloak. Decisión documentada también en la tabla de decisiones de `openspec/design/audit-log-uc15.md`.

---

## ADR-0022 — `actor_id` en audit log se resuelve desde JWT sin revalidar firma
- **Estado:** Aceptada (deuda)
- **Contexto:** `AuditMiddleware` corre post-response en el frame de `BaseHTTPMiddleware`. El `sub` validado por `current_principal()` no es accesible porque `call_next` ejecuta el handler en `copy_context()` — las mutaciones de ContextVar del handler no propagan al middleware.
- **Decisión:** El middleware decodifica el JWT del header `Authorization` en base64 sin verificar la firma (`_extract_sub`), extrae el `sub` y lo usa para resolver el `actor_id`. Esto es aceptable porque: (1) el token ya fue validado por `current_principal()` antes de que el middleware escriba el log; (2) si el token es inválido el handler ya devolvió 401/403; (3) el middleware solo usa el sub para atribución en el audit log, no para decisiones de autorización.
- **Riesgo residual:** Un token con `sub` forjado que pase la validación JWKS (imposible sin la clave privada de Keycloak) contaminaría el audit log con una identidad falsa. No es un vector de escalada de privilegios.
- **Deuda:** Mover el `sub` validado a `request.state.audit_sub` desde `current_principal()` o desde el propio handler, y eliminar `_extract_sub`. Esto elimina la dependencia del parseo manual del JWT. **Disparador:** cuando se añadan tests de integración E2E o se audite el módulo IAM para producción.

---

## Decisiones abiertas / pendientes
- **ADR-0012** (firma cualificada) y AC-00 (redacción) → pendientes de PO/legal.
- **ADR-0014** (RLS por médico) y **ADR-0010** (histórico de reanálisis) → deudas con disparador conocido.
- Validación end-to-end contra PostgreSQL real (aplicar `alembic upgrade head` + tests de aislamiento RLS) → pendiente; nada se ha ejecutado aún contra una BD.
- **ADR-0019** (selección de proveedor) → elección provisional; confirmar DPA, región y no-entrenamiento al contratar.
