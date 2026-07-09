# Auditoría de código — FTM (Medical Rehab Follow-up Tool)

> Checklist y guion de auditoría para pasar con Claude Code sobre un checkout local de `master`.
> Cubre tres ejes: **(1) arquitectura limpia/hexagonal · (2) OWASP Top 10:2025 · (3) RGPD**.
> Contexto crítico del sistema: monolito modular FastAPI + worker · auth Keycloak (OIDC/PKCE) ·
> Postgres con RLS · **frontera de anonimización ante el LLM** · **voz = dato biométrico (RGPD art. 9)**.

---

## Cómo lanzarla con Claude Code

Trabaja sobre un clon local, no sobre MCP de GitHub. Sugerencia de pasadas (una por eje, para que los hallazgos no se mezclen):

**Prompt inicial (pásalo tal cual):**

> Audita este repositorio en tres pasadas separadas siguiendo `AUDIT_FTM.md`. En cada pasada:
> localiza el código real (no asumas que la memoria describe lo implementado), traza los caminos
> completos entre ficheros, y para cada hallazgo devuelve: **[severidad] · categoría · fichero:línea ·
> qué está mal · por qué importa en este dominio (salud/biométrico) · remediación concreta**.
> Severidades: Crítico / Alto / Medio / Bajo / Informativo. No inventes rutas; si algo no existe en
> el código, márcalo como *gap de implementación vs. memoria*.

Pasada 1 → sección **A. Arquitectura**. Pasada 2 → sección **B. OWASP 2025**. Pasada 3 → sección **C. RGPD**.

Herramientas que debe usar en cada pasada: `grep`/`rg` para imports cruzados, lectura del árbol de
`/api` y de las migraciones Alembic, `pip-audit`/`npm audit` (SCA), y `ruff`/`bandit`/`semgrep` si están.

---

## A. Arquitectura limpia / hexagonal

El objetivo declarado es hexagonal (puertos y adaptadores) sobre un monolito modular. Verificar **conformidad**, no presencia.

- [ ] **Pureza del dominio.** Los modelos y la lógica de dominio de cada módulo (`iam`, `clinical`, `recording`, `metrics`, `analysis`, `reporting`) **no importan** FastAPI, SQLAlchemy, `python-jose`, Pydantic-web ni SDKs externos. Grep de `import fastapi` / `import sqlalchemy` / `from anthropic` dentro de capas de dominio → debería dar cero.
- [ ] **Puertos definidos en el dominio.** Persistencia, storage (bucket), LLM y registro de funciones están detrás de **interfaces/Protocols** definidos en el dominio; las implementaciones concretas (repos SQLAlchemy, cliente S3, SDK del LLM) son **adaptadores** en infraestructura.
- [ ] **Dirección de dependencias.** Todas apuntan **hacia dentro** (infra → aplicación → dominio). Ningún módulo de dominio conoce a Keycloak, a Anthropic ni a Postgres por nombre.
- [ ] **Fronteras entre módulos.** Se cumple el principio de la memoria: *ningún módulo llama a la BD de otro directamente, solo a su servicio*. Grep de imports cruzados de modelos/repos entre paquetes de módulos → deberían ser cero; solo se cruzan interfaces de servicio o DTOs.
- [ ] **El `REGISTRY` global de `analysis/registry.py`.** El `dict` global de funciones es un *smell* para hexagonal (estado de módulo, acoplamiento). Verificar que se accede tras un puerto (`AnalysisRunner`) y no importándolo directo desde el worker.
- [ ] **Separación por capas dentro del módulo.** Cada bounded context tiene `domain / application / infrastructure` (o equivalente) y no un único paquete plano con todo mezclado.
- [ ] **`iam` adelgazado.** Confirmar que `iam` no reimplementa identidad (eso es Keycloak) y queda como validación de token, contexto RLS, consentimiento y audit.
- [ ] **Métricas de calidad.** Complejidad ciclomática, funciones largas, duplicación, acoplamiento aferente/eferente por módulo. Marcar hotspots.
- [ ] **Tests como contrato.** ¿Los puertos tienen tests con dobles/fakes? ¿El dominio se testea sin BD ni red?

---

## B. OWASP Top 10:2025

Mapeado a la superficie de ataque real de FTM. **A01, A02, A04, A06 y A10 son los de mayor riesgo aquí.**

### A01 — Broken Access Control *(riesgo #1, incluye ahora BOLA/BFLA y SSRF)*
- [ ] **Doble capa real.** RLS **y** dependencia RBAC de FastAPI están ambas puestas en cada endpoint sensible, no una sola. (§6 y §10 de la memoria dependen de esto; es el riesgo "crítico".)
- [ ] **BOLA (object-level).** ¿Puede un paciente leer la grabación/informe de otro cambiando el `id` en la URL? Probar cada `GET /recordings/{id}`, `/reports`, `/followups/{patientId}`.
- [ ] **BFLA (function-level).** ¿Un rol `patient` puede llamar endpoints de `medical`/`technician`? Verificar el claim de rol en cada ruta.
- [ ] **Invariante de anonimización como control de acceso.** El módulo `ai` **no puede** joinear ni leer del schema `clinical` (ni de `pseudonym_map`). Comprobar a nivel de conexión/rol de BD, no solo por convención de código.
- [ ] **Signed URLs.** Alcance mínimo, caducidad corta, no reutilizables, verificación de propiedad antes de emitir.
- [ ] **SSRF (ahora en A01).** La llamada al LLM y la subida por signed URL: ¿algún parámetro controlable por usuario alcanza una petición saliente? URL del bucket/LLM no derivada de input del cliente.

### A02 — Security Misconfiguration *(subió a #2)*
- [ ] **Cabeceras nginx.** HSTS, CSP, CORS restrictivo (no `*`), X-Content-Type-Options. Confirmar que están y son estrictas.
- [ ] **Sin endpoints de debug** ni OpenAPI/`/docs` expuesto en prod; `DEBUG=false`.
- [ ] **Errores no verbosos.** Ningún stack trace ni mensaje que filtre PII/estructura interna al cliente.
- [ ] **Bucket WAV privado** (uniform access, sin lectura pública) y config de Keycloak endurecida (sin usuarios/clients de ejemplo).
- [ ] **Sin credenciales por defecto** en compose/IaC.

### A03 — Software Supply Chain Failures *(NUEVA)*
- [ ] **Dependencias fijadas** con lockfile (`requirements.txt`/`poetry.lock`, `package-lock.json`). SCA en CI (`pip-audit`, `npm audit`, o similar).
- [ ] **Imágenes base Docker** pinneadas por digest, no `:latest`.
- [ ] **Integridad de `realm-export.json`** y de las migraciones como artefactos versionados.
- [ ] **Procedencia** de `librosa/scipy/soundfile` y del SDK del LLM revisada; sin dependencias no usadas.

### A04 — Cryptographic Failures
- [ ] **TLS** terminado en nginx con config moderna (sin TLS<1.2, cifrados fuertes).
- [ ] **Cifrado en reposo** de `postgres-app` y del bucket WAV.
- [ ] **Cifrado de columna `national_id`** con gestión de claves real (¿dónde vive la clave? no en el repo, no junto al dato).
- [ ] **Generación del pseudónimo.** El UUID por paciente debe ser **criptográficamente aleatorio** (`uuid4`/CSPRNG), nunca secuencial ni derivado de PII (si no, la pseudonimización es reversible por fuerza bruta).
- [ ] **Secretos** (client secret `ftm-api`, API key LLM, credenciales Postgres) fuera del repo y del código.

### A05 — Injection
- [ ] **SQLAlchemy parametrizado** en todo; sin f-strings en queries.
- [ ] **RLS session var.** El `sub`/rol del token se fija en la sesión de BD (`SET`/`set_config`) de forma **parametrizada** — es un punto clásico de inyección en RLS. Verificar que no se concatena el claim en un `SET` por string.
- [ ] **Resolución de `function_name`.** Debe ser un **lookup en whitelist** contra el registry; **nunca** `eval`, `getattr` dinámico ni `import` por nombre de input del usuario.

### A06 — Insecure Design
- [ ] **Frontera de anonimización por diseño.** Enforced a nivel de schema/rol de BD (el rol del `ai` físicamente no alcanza `clinical`), no solo por disciplina de código.
- [ ] **Consentimiento como puerta de diseño.** No se puede grabar/procesar sin consentimiento previo válido; la revocación bloquea el procesamiento efectivamente.
- [ ] **Rate limiting / anti-abuso** en subida de audio e insight LLM.

### A07 — Authentication Failures
- [ ] **Validación JWT completa.** Firma vía JWKS **+ `iss` + `aud` + `exp`**. Rechazar `alg=none` y confusion de algoritmo; forzar el algoritmo esperado (RS256), no confiar en el header del token.
- [ ] **PKCE S256 realmente exigido** por Keycloak (`pkce.code.challenge.method=S256`), client público sin secret.
- [ ] **Almacenamiento de tokens en el SPA** (evitar `localStorage` para tokens de larga vida; revisar manejo de refresh).

### A08 — Software or Data Integrity Failures
- [ ] **Funciones del técnico** solo por PR + review + deploy; **sin carga en runtime** (confirmar que no existe ruta de subida de código).
- [ ] **Integridad CI/CD.** Migraciones Alembic aplicadas de forma controlada; artefactos firmados/verificados.
- [ ] **Validación de salida del LLM** contra el contrato JSON antes de persistir (no confiar ciegamente en el modelo).

### A09 — Security Logging and Alerting Failures
- [ ] **`audit_log` cubre** accesos a datos clínicos y biométricos, y cruces de la frontera de anonimización.
- [ ] **El log NO contiene PII** ni audio ni pseudónimo reidentificable. (El propio audit no debe convertirse en fuga.)
- [ ] **Alerting** en fallos de RLS / autorización denegada repetida.

### A10 — Mishandling of Exceptional Conditions *(NUEVA)*
- [ ] **Timeout + captura de excepciones** en la ejecución de la función del técnico (§10, riesgo Alto). Estado de error persistido en la grabación.
- [ ] **Worker resiliente.** Jobs fallidos no dejan estado inconsistente; reintentos idempotentes.
- [ ] **Fallo del LLM** (timeout, error, JSON inválido) degrada al flujo sin IA, no rompe el informe.
- [ ] **Fail-closed.** Ante error en autorización/RLS, se deniega por defecto; nunca fail-open.
- [ ] **Mensajes de error** sin stack trace ni PII hacia el cliente.

---

## C. RGPD *(ya avanzado en la memoria — auditar conformidad código ↔ memoria)*

- [ ] **Base legal + consentimiento reforzado (art. 9).** La voz es categoría especial. Consentimiento **explícito y previo** a grabar, registrado en `consent`, **revocable**, y la revocación **bloquea el procesamiento** de verdad (no solo marca una fila).
- [ ] **Residencia UE end-to-end.** Todos los recursos en UE, **incluida la región de procesamiento del LLM**. Este es el punto que más se escapa: verificar que la llamada al proveedor del LLM no sale de la UE.
- [ ] **Minimización.** Al LLM solo cruzan métricas pseudonimizadas; el audit de A01/A06 ya lo cubre a nivel técnico.
- [ ] **Pseudonimización ≠ anonimización.** Como el `pseudonym_map` permite reidentificar, las métricas siguen siendo dato personal bajo RGPD. Confirmar que el map está aislado en `clinical` bajo RLS y que nadie más lo alcanza.
- [ ] **Derechos ARCO/portabilidad y borrado.** Los stubs de export/erasure **cascadean** a WAV en bucket + `recording_metrics` + `ai_insight` + informes, no solo a la tabla de paciente. Derecho al olvido con datos pseudonimizados: ¿se borra o se rompe el map?
- [ ] **Retención / lifecycle.** Política de caducidad en el bucket WAV y retención definida para métricas/informes.
- [ ] **DPIA.** Tratamiento de biométrico a escala exige evaluación de impacto documentada — verificar que existe como artefacto (aunque sea fuera del código).
- [ ] **Accountability.** `audit_log` respalda la trazabilidad, pero sin filtrar PII (ya en A09).
- [ ] **Cifrado de datos especiales** (`national_id` y, si aplica, metadatos sensibles) — cubierto en A04, confirmar coherencia.

---

## Formato de salida sugerido para los hallazgos

| Severidad | Eje | Categoría | Ubicación | Hallazgo | Remediación |
|---|---|---|---|---|---|
| Crítico | OWASP | A01 | `api/recording/routes.py:88` | `GET /recordings/{id}` sin check de propiedad | Añadir verificación de `patient_id == token.sub` + test de aislamiento |

> Priorizar Críticos/Altos de A01, A04, A06, A10 y de RGPD (consentimiento/residencia), que son los que en este dominio (salud + voz) tienen impacto legal y clínico, no solo técnico.
