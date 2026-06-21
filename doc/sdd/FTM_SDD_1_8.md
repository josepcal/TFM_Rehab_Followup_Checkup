# Medical Rehab Follow-up Check-up Tool (FTM) — Software Design Document

## Meta-Data
- **Version:** 1.8
- **Date:** 2026/06/07
- **Function:** Medical Rehab Follow-up Check-up Tool
- **Actors:** Patient, Doctors (GP, Specialist, Technician)

---

## Changelog (1.7 → 1.8)

Frontera de pseudonimización ante IA, RLS efectiva por rol y residencia de datos en la UE:

- **Pseudonimización ante el LLM (FR-04):** nueva entidad `clinical.pseudonym_map`
  (identidad↔pseudónimo, en la zona identificada, bajo RLS, sin acceso para el rol de IA).
  `metrics.metric_result` añade `PSEUDONYM_ID` **sin FK**, de modo que borrar el mapa
  (derecho al olvido) deja las métricas de facto anónimas. Nueva vista `metrics.v_ai_payload`
  como **única interfaz** del rol `ftm_ai` (pseudónimo + métricas numéricas), que pierde el
  acceso a `recording` y a las tablas base de métricas. Nuevo rol `ftm_worker` que cruza la
  frontera identidad→pseudónimo (resuelve el pseudónimo y escribe métricas; no llama al LLM).
- **Residencia de datos (UE):** nuevos **FR-16** (grabaciones en la UE) y **FR-17**
  (procesamiento del LLM en la UE; solo métricas pseudonimizadas, sin entrenamiento).
- **RLS efectiva (FR-09):** funciones de identidad (`current_patient_id/_doctor_id/_pseudonym`)
  y 39 políticas por tabla (paciente solo lo suyo, médicos a nivel de clínica, técnico/IA fuera
  de los datos clínicos). Reemplaza el ejemplo comentado por una implementación completa.

## Changelog (1.6 → 1.7)

Cierre de huecos de arquitectura (decisiones de diseño) sobre el modelo existente:

- **Trazabilidad clínica de la ejecución** en `Metric Result`: nuevos `FUNCTION_NAME`,
  `FUNCTION_VERSION`, `CODE_SHA` (commit desplegado, cadena de custodia vía git) y
  `STATUS` (`success`/`error`) + `ERROR_DETAIL` para el manejo de errores del worker.
  `RAW_JSON` pasa a ser **opcional** (un resultado en error puede no llevar JSON; un
  *check* obliga a que `STATUS=success ⇒ RAW_JSON` presente).
- **Metadatos de calidad de la grabación** en `Exercise Recording`: `DURATION_SECONDS`,
  `SAMPLE_RATE`, `SIZE_BYTES`, `SHA256` (integridad). El `RECORDED_BY` ya existente actúa
  como autor/subida.
- **Atestación clínica (§6.1)**: `Diagnostic` añade `CONTENT_HASH`; `Exercise Report` añade
  `ATTESTED_AT`, `ATTESTED_BY` y `CONTENT_HASH`. Firma de MVP = identidad + timestamp + hash,
  **no** firma electrónica cualificada (eIDAS) — upgrade a QTSP fuera del MVP.
- **Requisitos no funcionales (§6)** completados (rendimiento, escalabilidad, fiabilidad,
  usabilidad) con SLAs mínimos de piloto.
- **Disparo del análisis (UC-06 / AC-11)**: lo lanzan **médico o paciente** (quien tenga
  lectura RLS sobre la grabación), de forma **asíncrona**; el Technical Specialist queda
  excluido por RLS. `Metric Result` sigue siendo **1:1** con la grabación, por lo que un
  reanálisis **actualiza** el resultado (el histórico de reanálisis exigiría relajar el
  `UNIQUE` y queda como deuda).
- El alta de pacientes por **Administrador** (UC-11) y de médicos (UC-12) ya estaba reflejada.

## Changelog (1.5 → 1.6)

Normas clínicas (valores de referencia) en el modelo:

- Nuevo esquema `reference` con la entidad **Metric Norm**: catálogo de normas por métrica,
  **compartido entre pacientes** e independiente del `analysis_setup`. Se enlaza por
  `METRIC_CODE` (= `path` de la métrica).
- La norma incluye `DIRECTION` (`higher_better`/`lower_better`/`in_range`), un **rango bueno**
  (`GOOD_MIN`/`GOOD_MAX`) y un **rango pobre** (`POOR_MIN`/`POOR_MAX`) —que permiten clasificar en
  **3 niveles** (bueno / intermedio / pobre), no solo dentro/fuera—, fuente y versión, y es
  **estratificable por sexo y edad** (`NULL` = comodín).
- El **Patient** incorpora `SEX` para poder aplicar las normas estratificadas (la edad se deriva
  de `BIRTH_DATE`).

## Changelog (1.4 → 1.5)

Refinamiento del modelo de métricas asociadas al Analysis Setup:

- Las métricas pueden ser **jerárquicas y compuestas**. `Metric Definition` se direcciona por
  `PATH` (ruta en el JSON) y distingue métricas crudas de derivadas (`VALUE_KIND`); admite
  `SECTION`, `NULLABLE` y `TARGET_VALUE`.
- Nueva entidad **Metric Composition**: define las métricas derivadas como combinación
  **ponderada** de otras (materializa la "ponderación de métricas" del objetivo).
- **Doble almacenamiento** del resultado: nueva entidad **Metric Result** con el JSON íntegro
  (`RAW_JSON`, consultable por `jsonb_path`) + fecha y nota; y `Recording Metric` pasa a guardar
  los valores **aplanados** por `METRIC_PATH` (con `IS_NULL`).
- **AI Insight** pasa a colgar del `Metric Result` (no de la grabación).
- `Metric Result` es **1:1 con la grabación** (`RECORDING_ID` único): cada grabación tiene a lo
  sumo un resultado, manteniendo el JSON en el espacio `metrics` (sin tocar el de grabaciones).

## Changelog (1.3 → 1.4)

Esta versión incorpora las decisiones tomadas en el diseño de la base de datos:

- El **Analysis Setup** pasa a asociarse al **Program Exercise** (instancia del
  ejercicio en el programa), no al Rehab Exercise. Afecta a glosario, UC-14, UC-16,
  AC-09 y §7.
- Los espacios de datos de §6.1 se materializan como **esquemas** de base de datos:
  `clinical`, `recording`, `metrics`, `setup` y `audit` (transversal). Se corrige el
  texto "3 espacios" → **4 espacios**.
- Se corrige el modelo de datos (§7): se elimina `REHAB_PROGRAM_ID` de Diagnostic (la
  relación 1→N la mantiene Rehab Program); se corrige la dirección Doctor→Diagnostic;
  se completan los atributos y relaciones marcados como _(pendiente)_.
- Nuevas entidades: **App User** (identidad; credenciales gestionadas por Actor 5),
  **Patient Consent** (FR-14 / EC-7), **Metric Definition** (separa la definición de la
  métrica de su valor) y **Event Log** (FR-15 / UC-15).
- **Exercise Recording** con borrado lógico (UC-13): el media se purga del repositorio
  pero la entidad, sus métricas e insights persisten.
- Se completan los perfiles de sistema (Administrator, Technician) y las máquinas de
  estado (§8).

---

## Glossary

- **Exercise Recording / Recording:** soporte de audio o vídeo para registrar la
  ejecución de un ejercicio de rehabilitación.
- **Recording Analysis / Analysis Setup:** entidad de setup del análisis; definición y
  configuración de las métricas, su API de evaluación, el modelo usado para el AI insight
  y los criterios para evaluar las métricas. Se asocia a un **Program Exercise** (instancia).
- **Program Exercise:** ejecución/instancia de un ejercicio de rehabilitación (Rehab
  Exercise) dentro de un Rehab Program; sobre ella se configura el Recording Analysis y se
  cuelgan las grabaciones.
- **Rehab Exercise:** ejercicio del catálogo reutilizable, definido para procesos de
  recuperación. No contiene el Analysis Setup.
- **Rehab Program:** plan para mejorar el bienestar de un paciente diagnosticado
  de una enfermedad / lesión / trastorno / síndrome / condición / limitación
  funcional / factor de riesgo / deterioro.
- **AI insight:** evaluación del Modelo de IA de la grabación de ejercicio de acuerdo al
  Recording Analysis previamente configurado (metricas y criterio)
- **Recording Metrics** Lista de indicadores definidos en el "Recording Analysis" y 
  extraídos del Exercise Recording mediante el API 
- ** Exercise Report** Resumen de Exercise recordings del mismo tipo, junto a sus metricas 
  y Evaluaciones (si las hay) , durante un periodo de tiempo
- ** Follow-up CheckUp** Agregacion de Exercise reports de un mismo Rehab Program durante un periodo de tiempo

---

## 1. Overview

- **Descripción breve:**
  Sistema de seguimiento de pacientes.

- **Objetivo:**
  Ayudar a monitorizar el grado de avance de un paciente en programas de
  rehabilitación. Para obtener una visión objetiva, el grado de avance se
  describe mediante la ponderación de métricas relacionadas con ejercicios
  pautados en el programa de rehabilitación. Las métricas las pauta un
  especialista técnico a partir de la recogida de datos de grabaciones
  (audio/vídeo) que el propio paciente (o acompañante) realiza.

- **Contexto del negocio:**
  Las mediciones se pueden realizar de manera personal por el fisioterapeuta o
  acompañante del paciente, o bien extraídas de grabaciones con la ayuda de IA
  aumentada.

---

## 2. Stakeholders

- **Product owner:** _(pendiente)_
- **Tech lead:** _(pendiente)_
- **Equipo involucrado:** Todos una única persona, al ser un Trabajo Fin de
  Módulo.

---

## 3. Actors

- **Actor 1:** Paciente, Acompañante(s) y Fisioterapeutas
- **Actor 2:** (Doctor) Médico de cabecera (GP) y Médico Especialista
- **Actor 3:** (Doctor) Especialista Médico Técnico
- **Actor 4:** Sistema guiado por IA (LLM)
- **Actor 5:** Sistema de Autenticación y Autorización
- **Actor 6:** Aplicacion
- **Actor 7:** Administrador del sistema (altas de usuarios y médicos)

---

## 4. Use Cases

### UC-01: Diagnóstico (Diagnostic Assessment)
- **Descripción:** El Médico Especialista realiza un diagnóstico al paciente.
- **Actor principal:** Médico Especialista
- **Precondiciones:** El paciente debe padecer una enfermedad o dolencia conocida.
- **Postcondiciones:** El diagnóstico queda registrado en el sistema a nombre del
  paciente y con "firma" del Médico Especialista.

### UC-02: Setup del programa de rehabilitación y ejercicios
- **Descripción:** El Médico Especialista crea un programa de rehabilitación a
  partir de unos ejercicios base.
- **Actor principal:** Médico Especialista
- **Precondiciones:** El paciente debe tener un diagnóstico.
- **Postcondiciones:** La tabla de ejercicios queda registrada en el sistema a
  nombre del paciente con un "Fisioterapeuta" asignado.

### UC-03: Setup del análisis asistido por IA
- **Descripción:** El Medical Technical Specialist realiza un setup de las
  métricas y mediciones del ejercicio asignado por el Médico Especialista en el
  plan de rehabilitación.
- **Actor principal:** Medical Technical Specialist
- **Precondiciones:** Ejercicio existente en la tabla de ejercicios de
  rehabilitación generada por el Médico Especialista de acuerdo al diagnóstico.
- **Postcondiciones:** Generación del Recording Analysis Setup, que incluye:
  - API para el análisis de la grabación.
  - Métricas retornadas por la API.
  - Prompt para el AI Insight de las métricas (incluye criterio para la
    interpretación de métricas).

### UC-04: Recording Analysis
- **Descripción:** El Medical Technical Specialist realiza una
  programación/asignación del sistema de grabación y extracción de métricas para
  su interpretación.
- **Actor principal:** Medical Technical Specialist
- **Precondiciones:** UC-02 (requerido un ejercicio de acuerdo a un diagnóstico).
  UC-05 (opcional, grabación del ejercicio).
- **Postcondiciones:** Generación del Recording Analysis Setup, que incluye:
  - Métricas retornadas por la API.

### UC-05: Exercise Recording
- **Descripción:** El paciente realiza una grabación del ejercicio (para una
  fecha dada).
- **Actor principal:** Paciente (opcionalmente un fisioterapeuta)
- **Precondiciones:** UC-02 (requerido un ejercicio de acuerdo a un programa de
  rehabilitación).
- **Postcondiciones:** Generación del Recording, que incluye:
  - Soporte para la grabación (audio/vídeo).

### UC-06: Exercise Recording Metric retrieval
- **Descripción:** El paciente/doctor pide una lista de métricas de un recording.
- **Actor principal:** Paciente / Doctor (opcionalmente un fisioterapeuta)
- **Precondiciones:** UC-05 (requerido un recording de un ejercicio de acuerdo a
  un programa de rehabilitación).
- **Postcondiciones:** Se devuelve la lista de Recording Metrics asociadas al recording
  (valores extraídos por la API según el Analysis Setup del Program Exercise).

### UC-07: Generate AI insights
- **Descripción:** La IA lee las métricas y aplica el análisis definido por el
  Medical Technical Specialist.
- **Actor principal:** Paciente (opcionalmente un fisioterapeuta)
- **Precondiciones:** UC-06, UC-04 (requerido un ejercicio de acuerdo a un
  diagnóstico), UC-03 (requerido prompt para interpretar las métricas).
- **Postcondiciones:** Generación de conclusiones con el LLM:
  - Informe generado por IA de la interpretación de las métricas.

### UC-08: Exercise Report
- **Descripción:** Se genera un reporte del/los ejercicio(s) realizado(s).
- **Actor principal:** Paciente (opcionalmente un fisioterapeuta)
- **Precondiciones:** UC-05 (requerido un exercise recording). UC-04 (opcional,
  análisis de las métricas). UC-06 (opcional, AI insight sobre las métricas).
- **Postcondiciones:** Generación del reporte en un registro con id reporte unico.

### UC-09: Follow-up check-up
- **Descripción:** Follow-up check-up del programa de rehabilitación.
- **Actor principal:** Médico de cabecera (GP), Médico Especialista
- **Precondiciones:** UC-08 (requerido un set de reportes de ejercicios), un perido de  tiempo.
- **Postcondiciones:** Follow-up check-up creado y vinculado al Rehab Program.

### UC-11: Alta de usuario 
- **Descripción:** Administrador del sistema da de alta Usuario
- **Actor principal:** Administrador del sistema
- **Precondiciones:** El usuario tiene identificador unico, nombre, apellidos y edad
- **Postcondiciones:** El usuario esta presente en la BBDD como Paciente con identity ID unico

### UC-12: Alta de Medico
- **Descripción:** Administrador del sistema da de alta Medico
- **Actor principal:** Administrador del sistema 
- **Precondiciones:** El usuario tiene identificador de colegiado, nombre y apellidos
- **Postcondiciones:** El usuario esta presente en la BBDD como Medico (tipo GP, Medical Especialist, 
			Medical Technical Spetialist) con identity ID unico y numero de colegiado unico.

### UC-13: Borrado de recording
- **Descripción:** Paciente borra recording
- **Actor principal:** Paciente
- **Precondiciones:** El recording existe esta relacionado  a un PROGRAM_EXERCISE_ID
- **Postcondiciones:** El recording se marca como borrado en la BBDD y es eliminado del repositorio de 
		recordings, los exercise reports relacionados no se borran, solo tienen metricas y interpretaciones

### UC-14: Modificacion de Analysis Setup
- **Descripción:** Doctor cambia las metricas, API, modelo o prompt utilizado en el IA Analysis Setup
- **Actor principal:** Mecial Technical Spetialist 
- **Precondiciones:** El ANALYSIS_SETUP existe y esta relacionado a un PROGRAM_EXERCISE
- **Postcondiciones:** El ANALYSIS_SETUP es actualizado (se incrementa su VERSION)
	
### UC-15: Monitorizacion de Eventos
- **Descripción:** El sistema registra una acción de Creacion/Alta/Modificacion/Eliminación de una Entidad (DIAGNOSIS, ANALYSIS_SETUP
	, EXERCISE RECORDING, FOLLOWUP_CHECKUP
- **Actor principal:** Aplicacion
- **Precondiciones:** La BBDD esta disponible y es operativa
- **Postcondiciones:** Se registra un evento (alta/modificación/borrado) en el log de
  auditoría (EVENT_LOG)
	
### UC-16: Eliminacion de ejercicio del programa
- **Descripción:** Doctor elimina un Program Exercise de un REHAB_PROGRAM
- **Actor principal:** Doctor
- **Precondiciones:** El PROGRAM_EXERCISE existe y no tiene ANALYSIS_SETUP asociado
- **Postcondiciones:** El PROGRAM_EXERCISE se elimina del programa; el Rehab Exercise del
  catálogo se mantiene (es reutilizable)
		
### Flujo principal
1. Medical Specialist realiza Diagnostic Assessment.
2. Medical Specialist & Physiotherapist listan y configuran rehab exercises.
3. Medical Specialist & Medical Technical Specialist realizan Recording Analysis
   Configuration Setup.
4. Medical Technical Specialist genera el Recording Analysis procedure para
   extraer métricas.
5. El paciente graba el ejercicio y solicita el recording analysis setup del
   paso 4.
   - 5.1. (Opcional) El sistema pide a la IA generar Recording Analysis insights.
   - 5.2. El sistema crea el Exercise Report y lo persiste en base de datos.
6. GP & Medical Specialists crean el Follow-up Check-up a partir de los Exercise
   Reports.

### Flujos alternativos

**A1: Manual Follow-up Check-up (sin uso Metricas ni IA)**
1. Medical Specialist realiza Diagnostic Assessment.
2. Medical Specialist & Physiotherapist listan y configuran rehab exercises.
3. El paciente graba el ejercicio.
   - 3.1. El sistema crea el Exercise Report y lo persiste en base de datos.
4. GP & Medical Specialists crean el Follow-up Check-up a partir de los Exercise
   Reports.

**A2: Manual Follow-up Check-up (con uso de Metricas)**
1. Medical Specialist realiza Diagnostic Assessment.
2. Medical Specialist & Physiotherapist listan y configuran rehab exercises.
3. Medical Specialist & Medical Technical Specialist realizan Recording Analysis
   Configuration Setup.
4. Medical Technical Specialist genera el Recording Analysis procedure para
   extraer métricas.
5. El paciente graba el ejercicio y solicita el recording analysis setup del
   paso 4.
   - 5.1. El sistema crea el Exercise Report y lo persiste en base de datos.
6. GP & Medical Specialists crean el Follow-up Check-up a partir de los Exercise
   Reports.

### Relaciones UML
- `<<include>>`: _(pendiente)_
- `<<extend>>`: _(pendiente)_
- Generalización: _(pendiente)_

---

## 5. Functional Requirements (or BRs)

- **FR-00:** Solo los usuarios identificados y autorizados por el sistema de
  autorización (Actor #5) pueden acceder a la aplicación.
- **FR-01:** El paciente puede crear grabaciones de cada ejercicio y adjuntarlas
  al sistema.
- **FR-02:** El Médico Especialista puede crear/listar/asignar programas de
  rehabilitación a los pacientes.
- **FR-03:** El Medical Technical Specialist debe vincular cada ejercicio a un
  Analysis Setup.
- **FR-04:** El paciente puede solicitar a la app las métricas de un recording.
- **FR-05:** El paciente puede solicitar a la app la evaluación por IA de un
  recording.
- **FR-06:** El Doctor (GP, Medical Specialist, Medical Technical Specialist)
  puede solicitar un Exercise Report.
- **FR-07:** El Doctor (GP, Medical Specialist, Medical Technical Specialist)
  puede solicitar un Follow-up Check-up a partir de los Exercise Reports del
  mismo rehab program.
- **FR-08:** El Medical Technical Specialist debe programar las Recording metrics,
  el servicio API y el servicio AI LLM de cada Analysis Setup vinculado a un
  ejercicio individual.
- **FR-09:** El paciente solo puede ver sus diagnósticos, rehab programs y
  follow-up check-ups vinculados.
- **FR-10:** El paciente puede borrar las grabaciones que ha generado.
- **FR-11:** El Doctor (GP, Medical Specialist, Medical Technical Specialist)
  puede crear un Diagnostic.
- **FR-12:** El Doctor (GP, Medical Specialist, Medical Technical Specialist)
  puede crear un Rehab Exercise.
- **FR-13:** El Doctor (GP, Medical Specialist, Medical Technical Specialist)
  puede crear un Rehab Program.
- **FR-14:** El paciente debe dar consentimiento sobre los rehab programs para las
  grabaciones.
- **FR-15:** Todas las acciones sobre las entidades de la base de datos deben ser
  monitorizadas.
- **FR-16:** El repositorio de grabaciones (media/audio) debe **residir en la UE**
  (residencia de datos; la voz es dato biométrico de categoría especial).
- **FR-17:** El procesamiento por el LLM debe realizarse **en la UE**; solo recibe métricas
  **pseudonimizadas** (FR-04) y los datos no deben usarse para entrenamiento.

---

## 6. Non-Functional Requirements

> SLAs mínimos dimensionados para un **piloto de una clínica** (no para escala).

- **Performance:** API p95 < 300 ms en operaciones CRUD; subida de grabación hasta ~10 MB /
  ~60 s de audio; extracción de métricas (worker) < 30 s por grabación; AI insight < 15 s y
  **asíncrono** (no bloquea la UI).

### 6.1 Security

#### Data Security
Existen **4 espacios separados** de datos que, en la implementación, se materializan como
**esquemas** de base de datos (más un esquema transversal de auditoría):

| # | Espacio de datos | Esquema BBDD | Quién puede acceder |
|---|---|---|---|
| 1 | Patient data | `clinical` | Medical Specialist, GP, Patient |
| 2 | Exercise Recording | `recording` | Medical Specialist, GP, Patient |
| 3 | Exercise Recording metrics | `metrics` | Medical Specialist, GP, Patient e IA Model |
| 4 | Recording Analysis Setup | `setup` | Medical Specialist, Medical Technical Specialist e IA |
| — | Auditoría de eventos | `audit` | Aplicación / Administrador |
| — | Normas clínicas (referencia) | `reference` | Lectura: todos los roles · Escritura: Especialista, Técnico |

El control de acceso se concede por esquema (`GRANT` por rol) y se refuerza con Row-Level
Security para que el paciente solo vea sus propios datos (FR-09). El esquema `setup` queda
aislado de la identidad del paciente.

#### Attestation (firma de MVP)
El **Diagnostic** y el **Exercise Report** se atestan con: identidad del médico (referencia al
IdP externo + `COLEGIADO_ID`) + timestamp (`SIGNED_AT` / `ATTESTED_AT`) + **hash inmutable del
contenido** (`CONTENT_HASH`), registrado además en `EVENT_LOG`. **No** es firma electrónica
cualificada (eIDAS); el upgrade a un prestador cualificado (QTSP) queda fuera del MVP.

#### Pseudonimización ante IA (FR-04)
Lo único que cruza al LLM es un payload pseudonimizado `{ pseudónimo, ejercicio, métricas
numéricas, histórico, criterio }`; **nunca** identidad, `RECORDING_ID`, `MEDIA_URI` ni audio.
Se materializa así:
- `clinical.pseudonym_map` (identidad↔pseudónimo) vive en la zona identificada, bajo RLS;
  el rol `ftm_ai` **no** accede.
- `metrics.metric_result.PSEUDONYM_ID` lo denormaliza el worker de extracción; **sin FK**, de
  modo que borrar el mapa (derecho al olvido) deja las métricas de facto anónimas.
- La vista `metrics.v_ai_payload` es la **única** interfaz de lectura del rol `ftm_ai`
  (pseudónimo + valores numéricos); ese rol pierde el acceso a `recording` y a las tablas base
  de métricas.
- El rol `ftm_worker` cruza la frontera (resuelve el pseudónimo y escribe métricas); no llama
  al LLM.
- El egress relativiza fechas y envía solo las métricas declaradas y el criterio revisado
  (nunca texto libre clínico ni `RAW_JSON`).

> Pseudonimización ≠ anonimización (art. 32 RGPD): el dato sigue siendo personal, requiere DPA
> con el proveedor del LLM y procesamiento en la UE (FR-17). Al LLM solo llegan métricas
> acústicas derivadas, no una plantilla biométrica.

#### Row-Level Security (FR-09)
RLS activa en las tablas con datos de paciente (`clinical`, `recording`, `metrics`). Contrato de
sesión: la app conecta con el **login del rol** del usuario y fija `SET app.identity_id`; nunca
como owner. Funciones de identidad (`clinical.current_patient_id/_doctor_id/_pseudonym`,
SECURITY DEFINER) alimentan los predicados.
- **Paciente:** ve **solo lo suyo** (por `patient_id`, o en métricas por su pseudónimo).
- **Médicos (GP + especialista):** acceso a nivel de **clínica** (MVP). El particionado por médico
  (cada médico solo sus pacientes) exigiría una tabla de relación de cuidado → deuda documentada.
- **Técnico e IA:** fuera de los datos clínicos (sin grant y sin policy); la IA solo lee la vista
  pseudonimizada y el worker de extracción tiene lectura para resolver el pseudónimo.

Es **defensa en profundidad**: aunque un bug de la API deje pasar una petición, la BD no devuelve
filas fuera del alcance del rol. Las políticas deben validarse con los tests de aislamiento contra
una instancia real (no son verificables sin ejecutar PostgreSQL).


#### System profiles
Existen los siguientes perfiles de sistema:

1. **Medical:** GP, Doctor expert, Physiotherapist
2. **Patient:** Patient
3. **Administrator:** da de alta usuarios y médicos (UC-11, UC-12) y administra el sistema
4. **Technician:** Medical Technical Specialist; configura el Analysis Setup de los ejercicios

> Son **4 perfiles**, que se corresponden con el rol del usuario en la BBDD
> (`user_role`: medical / patient / administrator / technician).

- **Scalability:** objetivo ~50 usuarios concurrentes; 1 worker; escalado **vertical**. Colas
  distribuidas / microservicios quedan fuera del MVP.
- **Reliability:** uptime objetivo 99 %; backup diario de la base de datos; lifecycle/retención
  en el repositorio de grabaciones; reintento de extracción (2 intentos → `STATUS=error` en el
  Metric Result).
- **Usability:** navegadores evergreen (Chrome/Firefox/Edge/Safari actuales) con foco en la
  grabación en navegador; accesibilidad mínima (labels, foco, contraste); no WCAG completo en MVP.

---

## 7. Data Model

El modelo se organiza en los **esquemas** de §6.1. El detalle completo de columnas, tipos y
restricciones está en el diccionario de datos y en el esquema SQL / SQLAlchemy que acompañan
a este documento. La identidad de los usuarios se delega en el sistema de autenticación
externo (Actor 5): el sistema solo guarda una referencia.

### 7.1 Identidad y clínico (esquema `clinical`)

**App User** _(nueva)_
- Atributos: `IDENTITY_ID`, `ROLE` (medical/patient/administrator/technician),
  `EXTERNAL_SUBJECT` (referencia al IdP externo, Actor 5), `STATUS`
- Relaciones: 1–0..1 con Patient y con Doctor. No almacena credenciales.

**Patient**
- Atributos: `PATIENT_ID`, `IDENTITY_ID`, `NATIONAL_ID`, `Nombre`, `Apellidos`, `BIRTH_DATE`,
  `SEX` (para aplicar normas estratificadas)
- Relaciones: `Patient(IDENTITY_ID) → App User`; `Diagnostic(PATIENT_ID) → Patient`

**Pseudonym Map** _(nueva)_
- Atributos: `PATIENT_ID` (PK → Patient), `PSEUDONYM_ID` (UUID único)
- Relaciones: 1:1 con Patient. Vive en `clinical` (zona identificada), bajo RLS; el rol de IA
  **no** accede. Único vínculo identidad↔pseudónimo (frontera de §6.1). Su borrado anonimiza
  las métricas asociadas.

**Doctor**
- Atributos: `DOCTOR_ID`, `IDENTITY_ID`, `COLEGIADO_ID`, `DOCTOR_TYPE`
  (gp / medical_specialist / medical_technical_specialist / physiotherapist),
  `Nombre`, `Apellidos`
- Relaciones: `Doctor(IDENTITY_ID) → App User`; firma diagnósticos
  (`Diagnostic(DOCTOR_ID) → Doctor`)

**Diagnostic**
- Atributos: `DIAGNOSTIC_ID`, `PATIENT_ID`, `DOCTOR_ID`, `DOLENCIA`, `DESCRIPTION`,
  `HISTORY`, `SYMPTOMS`, `SIGNATURE`, `SIGNED_AT`, `CONTENT_HASH` (hash inmutable del
  contenido firmado; ver Attestation en §6.1)
- Relaciones: `→ Patient(PATIENT_ID)`, `→ Doctor(DOCTOR_ID)` (firmante).
  **Se elimina `REHAB_PROGRAM_ID`**: la relación con el programa la mantiene Rehab Program
  (1 Diagnostic → N Rehab Program).

**Rehab Program**
- Atributos: `REHAB_PROGRAM_ID`, `DIAGNOSTIC_ID`, `PHYSIOTHERAPIST_ID` (opcional),
  `STATUS`, `START_DATE`, `END_DATE`
- Relaciones: `→ Diagnostic(DIAGNOSTIC_ID)`; `→ Doctor` (fisioterapeuta asignado);
  1 → N Program Exercise.

**Rehab Exercise** (catálogo)
- Atributos: `RH_EXERCISE_ID`, `TYPE`, `DESCRIPTION`, `CREATED_BY`
- Relaciones: 1 → N Program Exercise. **Ya no contiene `ANALYSIS_SETUP_ID`**.

**Program Exercise** (instancia)
- Atributos: `PROGRAM_EXERCISE_ID`, `REHAB_PROGRAM_ID`, `RH_EXERCISE_ID`, `FREQUENCY`,
  `STATUS`
- Relaciones: `→ Rehab Program`, `→ Rehab Exercise`; **1 → 0..1 Analysis Setup** (nueva
  ubicación); 1 → N Exercise Recording.

**Patient Consent** _(nueva)_
- Atributos: `CONSENT_ID`, `PATIENT_ID`, `REHAB_PROGRAM_ID`, `GRANTED`, `GRANTED_AT`,
  `WITHDRAWN_AT`
- Relaciones: `→ Patient`, `→ Rehab Program`. Soporta FR-14 y EC-7 (revocación sin borrar
  historial).

**Exercise Report**
- Atributos: `EXERCISE_REPORT_ID`, `REHAB_PROGRAM_ID`, `PROGRAM_EXERCISE_ID` (opcional),
  `PERIOD_START`, `PERIOD_END`, `SUMMARY`, `CREATED_BY`, `ATTESTED_AT`, `ATTESTED_BY`,
  `CONTENT_HASH` (atestación del médico; ver §6.1)
- Relaciones: `→ Rehab Program`; N–N con Exercise Recording (tabla
  `exercise_report_recording`). El vínculo persiste tras el borrado lógico de la grabación
  (UC-13).

**Follow-up Check-up**
- Atributos: `FOLLOWUP_CHECKUP_ID`, `REHAB_PROGRAM_ID`, `PATIENT_ID`, `PERIOD_START`,
  `PERIOD_END`, `SUMMARY`, `CREATED_BY`
- Relaciones: `→ Rehab Program`, `→ Patient`; N–N con Exercise Report (tabla
  `followup_checkup_report`).

### 7.2 Configuración de análisis (esquema `setup`)

**Analysis Setup** (Recording Analysis)
- Atributos: `ANALYSIS_SETUP_ID`, `PROGRAM_EXERCISE_ID` (único), `DESCRIPTION`, `TYPE`,
  `METRIC_API_ENDPOINT`, `AI_MODEL`, `AI_PROMPT`, `CRITERIA`, `VERSION`
- Relaciones: **`→ Program Exercise` (0..1 por instancia)**; 1 → N Metric Definition.
  `VERSION` se incrementa al modificarse (UC-14).

**Metric Definition** _(refinada — direccionada por path)_
- Atributos: `METRIC_DEF_ID`, `ANALYSIS_SETUP_ID`, `PATH` (ruta en el JSON, p. ej.
  `domains.voice_stability`), `LABEL`, `SECTION` (`domains`/`raw`/…), `VALUE_KIND`
  (`raw`/`derived`), `UNIT`, `DATA_TYPE`, `NULLABLE`, `TARGET_VALUE`, `EVALUATION_CRITERIA`,
  `DISPLAY_ORDER`
- Relaciones: `→ Analysis Setup`; 1 → N Recording Metric; N–N consigo misma (composición)
  vía Metric Composition. Único por `(ANALYSIS_SETUP_ID, PATH)`.

**Metric Composition** _(nueva)_
- Atributos: `PARENT_METRIC_DEF_ID`, `CHILD_METRIC_DEF_ID`, `WEIGHT`
- Relaciones: ambos `→ Metric Definition`. Expresa una métrica derivada como
  `valor = Σ WEIGHT_i · valor(hija_i)` (ponderación de métricas).

### 7.3 Grabaciones (esquema `recording`)

**Exercise Recording**
- Atributos: `RECORDING_ID`, `PROGRAM_EXERCISE_ID`, `RECORDED_BY` (autor/subida), `MEDIA_KIND`
  (audio/video), `MEDIA_URI`, `MEDIA_STATUS` (available/purged/corrupt), `RECORDING_DATE`,
  `DURATION_SECONDS`, `SAMPLE_RATE`, `SIZE_BYTES`, `SHA256` (integridad), `IS_DELETED`, `DELETED_AT`
- Relaciones: `→ Program Exercise`; 1 → 0..1 Metric Result.
  **Borrado lógico (UC-13)**: al borrar, el media se purga del repositorio pero la entidad
  y sus resultados (métricas/insights) persisten.

### 7.4 Métricas e insights (esquema `metrics`)

**Doble almacenamiento**: el JSON íntegro del resultado más los valores seguidos aplanados.

**Metric Result** _(nueva)_
- Atributos: `RESULT_ID`, `RECORDING_ID` (único), `PSEUDONYM_ID` (sin FK; pseudónimo del
  paciente — lo único que cruza al LLM vía `v_ai_payload`), `ANALYSIS_SETUP_ID`, `RESULT_DATE`,
  `NOTE`, `RAW_JSON` (documento JSON íntegro de la API; consultable por `jsonb_path`;
  **opcional**: obligatorio solo si `STATUS=success`, garantizado por *check*), `FUNCTION_NAME`,
  `FUNCTION_VERSION`, `CODE_SHA` (commit desplegado — trazabilidad clínica), `STATUS`
  (`success`/`error`), `ERROR_DETAIL`, `EXTRACTED_AT`
- Vista `metrics.v_ai_payload`: interfaz pseudonimizada de la IA (pseudónimo + métricas
  numéricas), sin claves enlazables.
- Relaciones: `→ Exercise Recording` (1:1, una grabación tiene a lo sumo un resultado),
  `→ Analysis Setup`; 1 → N Recording Metric; 1 → 0..1 AI Insight.

**Recording Metric** (valor aplanado)
- Atributos: `RECORDING_METRIC_ID`, `RESULT_ID`, `METRIC_DEF_ID` (opcional),
  `METRIC_PATH` (snapshot), `VALUE_NUM`, `VALUE_TEXT`, `IS_NULL`
- Relaciones: `→ Metric Result`, `→ Metric Definition`. `METRIC_PATH` se guarda como snapshot
  para sobrevivir a cambios del setup (UC-14); `IS_NULL` marca nulos legítimos.

**AI Insight**
- Atributos: `AI_INSIGHT_ID`, `RESULT_ID` (único), `ANALYSIS_SETUP_ID`, `MODEL_USED`,
  `PROMPT_USED`, `INSIGHT_TEXT`, `GENERATED_AT`
- Relaciones: `→ Metric Result` (0..1), `→ Analysis Setup`.

### 7.5 Auditoría (esquema `audit`)

**Event Log** _(nueva)_
- Atributos: `EVENT_ID`, `ENTITY_TYPE`, `ENTITY_ID`, `ACTION` (create/update/delete),
  `ACTOR_ID`, `PAYLOAD`, `OCCURRED_AT`
- Relaciones: `→ App User` (actor); referencia polimórfica a cualquier entidad. Soporta
  FR-15 / UC-15.

### 7.6 Normas clínicas (esquema `reference`)

**Metric Norm** _(nueva)_
- Atributos: `NORM_ID`, `METRIC_CODE` (= `path` de la métrica), `LABEL`, `UNIT`,
  `DIRECTION` (`higher_better`/`lower_better`/`in_range`), `SEX` (NULL = cualquiera),
  `AGE_MIN`, `AGE_MAX` (NULL = sin límite), `GOOD_MIN`, `GOOD_MAX`, `POOR_MIN`, `POOR_MAX`,
  `SOURCE`, `VERSION`
- Relaciones: enlace **lógico** con Metric Definition por `METRIC_CODE` = `path` (sin FK).
  Catálogo **compartido entre pacientes** e independiente del Analysis Setup; estratificable
  por sexo y edad. Único por `(METRIC_CODE, SEX, AGE_MIN, AGE_MAX, VERSION)`.

---

## 8. State Machine

**Entidad "Program Exercise" (instancia del ejercicio del paciente):**

```
Asignado            --(paciente sube grabación)----------> Grabado
Grabado             --(la API ejecuta el análisis)-------> MétricasExtraídas
MétricasExtraídas   --(opcional: IA interpreta)----------> ConInsight
MétricasExtraídas   --(genera informe)-------------------> Reportado
ConInsight          --(genera informe)-------------------> Reportado
```

**Entidad "Patient Follow-up":**

```
Registrado          --(médico crea diagnóstico)---------> Diagnosticado
Diagnosticado       --(programa de ejercicios vinculado)-> ConPrograma
ConPrograma         --(≥1 informe generado)-------------> EnSeguimiento
EnSeguimiento       --(nuevos informes)-----------------> EnSeguimiento
```

---

## 9. Acceptance Criteria

### AC-01: Diagnostic Search (Doctor Search)
```gherkin
Given: A doctor logs in the system app
When:  Doctor searches for Patient
Then:  Doctor finds Patient diagnosis history
Consequence if not met: Doctor cannot create Diagnostic
```

### AC-02: Diagnostic Search (Patient Search)
```gherkin
Given: A Patient logs in the system app
When:  Patient searches for Diagnostic
Then:  Patient finds all his diagnostic history
Consequence if not met: Patient cannot access his Diagnostic history
```

### AC-03: Diagnostic creation
```gherkin
Given: A doctor finds a Patient in the app
When:  Doctor explores the Patient
Then:  Doctor can create a Diagnosis linked to the user
Consequence if not met: Diagnosis is not created
```

### AC-04: Setup del plan de rehabilitación
```gherkin
Given: A doctor has a Diagnostic assigned to a Patient
When:  A doctor creates a rehab plan
Then:  The rehabilitation plan is created, linked to Diagnostic
Consequence if not met: Patient cannot perform Recovery plan
```

### AC-05: Setup de la tabla de ejercicios de rehabilitación
```gherkin
Given: A doctor finds a Rehab program linked to a Diagnostic
When:  A doctor assigns a program exercise
Then:  The program exercise is linked to the rehab program
Consequence if not met: Patient cannot perform Recovery plan
```

### AC-06: Rehab Program Search (Doctor Search)
```gherkin
Given: A doctor logs in the system app
When:  Doctor searches for Rehab program
Then:  Doctor finds all Rehab programs
Consequence if not met: Doctor cannot access rehab programs
```

### AC-07: Rehab Program Search (Patient Search)
```gherkin
Given: A Patient logs in the system app
When:  Patient searches for Rehab program
Then:  Patient finds all his Rehab programs linked to their Diagnostics
Consequence if not met: Patient cannot access his Diagnostic history
```

### AC-08: Rehab Exercise Search (Doctor Search)
```gherkin
Given: A doctor logs in the system app
When:  Doctor searches for Rehab exercise
Then:  Doctor finds all Rehab exercises
Consequence if not met: Doctor cannot find rehab exercises
```

### AC-09: Program Exercise Analysis Setup (Doctor Search)
```gherkin
Given: A doctor logs in the system app
When:  Doctor finds a Program Exercise (assigned exercise inside a rehab program)
Then:  Doctor can set up the Analysis Setup linked to that Program Exercise, including:
       API to process recording, Recording Metrics to retrieve, AI Insight (prompt)
Consequence if not met: Doctor cannot create the Analysis setup; recording Metrics linked
       to the Program Exercise are not set
```

### AC-10: Rehab Exercise Recording (Patient)
```gherkin
Given: A patient logs in the system app
When:  Patient finds a program exercise inside one of his rehab programs
Then:  Patient can record the Exercise; the recording is saved and the Exercise
       Recording entity is registered in the Medical Database
Consequence if not met: Exercise recording is not saved
```

### AC-11: Exercise Recording Metrics Retrieval
```gherkin
Given: A Doctor OR the Patient (anyone with RLS read access to the recording) is logged in
       and finds a program exercise with a recording
When:  The actor triggers recording metric retrieval (analysis run)
Then:  The app ENQUEUES the analysis ASYNCHRONOUSLY; the API/worker extracts metrics and
       saves a Metric Result (with FUNCTION_NAME, FUNCTION_VERSION, CODE_SHA, STATUS) plus
       the flattened Recording Metrics, linked to the recording
Consequence if not met: Exercise recording does not contain recording metrics and
       cannot be processed by AI
```
> El **Medical Technical Specialist queda excluido** por RLS (sin lectura sobre los esquemas
> `recording`/`metrics`). Como `Metric Result` es **1:1** con la grabación, un reanálisis
> **actualiza** el resultado existente (un histórico de reanálisis requeriría relajar el `UNIQUE`).

### AC-12: Exercise AI Insight (Doctor)
```gherkin
Given: A Doctor logs in the system app; an exercise recording is available for the
       Doctor and the recording has metrics
When:  Doctor asks for AI Insight
Then:  App asks the LLM for metric interpretation using the metrics; the
       interpretation is saved in the Exercise recording
Consequence if not met: AI Insight not included in exercise recording
```

### AC-13: Exercise Report
```gherkin
Given: A Doctor logs in the system app, searches for a rehab program, a Program
       exercise in this rehab program has recordings available, and there are
       exercise recordings available
When:  Doctor asks for Exercise Report
Then:  App creates an Exercise report for the list of exercise recordings and
       saves it into the Database
Consequence if not met: Doctor cannot have a summary of exercise recordings and
       needs to check them one by one
```

### AC-14: Follow-up check-up
```gherkin
Given: A Doctor logs in the system app and there are Exercise reports for a given
       Rehab Program
When:  Doctor creates a Follow-up check-up for the Rehab program
Then:  App creates the Follow-up check-up
Consequence if not met: Doctor cannot review the status of the rehab program for a
       patient in a summarized way
```

---

## 10. Integration Needs

- **INT-1:** Aplicación ↔ módulo de login / **obligatoria**
- **INT-2:** Aplicación ↔ Base de Datos de Salud (médicos, usuarios,
  diagnósticos, …) / **obligatoria**
- **INT-3:** Aplicación ↔ Base de Datos de Grabaciones / opcional
- **INT-4:** Aplicación ↔ LLM / opcional

---

## 11. Edge Cases

- **EC-1:** Aplicación no di sponible
- **EC-2:** Base de datos de Salud no disponible
- **EC-3:** Base de datos de Grabaciones no disponible
- **EC-4:** Modelo LLM no disponible
- **EC-5:** grabación corrupta
- **EC-6:** IA no disponible
- **EC-7:** paciente que retira consentimiento
- **EC-8:** ejercicio no realizado
- **EC-9:** datos parciales


---

## 12. Geographical restrictions

Servicio limitado a España. **Residencia de datos en la UE** (FR-16/FR-17): las grabaciones, la
base de datos y el procesamiento del LLM se ubican en región UE.
