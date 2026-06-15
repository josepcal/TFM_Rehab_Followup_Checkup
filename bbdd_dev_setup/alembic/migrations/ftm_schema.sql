-- =============================================================================
-- Medical Rehab Follow-up Check-up Tool (FTM) — Modelo de datos
-- DDL PostgreSQL · derivado del SDD v1.7 (2026/06/07)
--
-- Decisiones de diseño aplicadas:
--   * Analysis Setup cuelga de Program Exercise (no de Rehab Exercise).
--   * Datos separados en 5 esquemas alineados con la matriz de seguridad 6.1:
--       clinical  -> espacio "Patient data"
--       recording -> espacio "Exercise Recording"
--       metrics   -> espacio "Exercise Recording metrics"
--       setup     -> espacio "Recording Analysis Setup"
--       audit     -> monitorización de eventos (FR-15 / UC-15)
--   * Exercise Recording con borrado lógico: el media se purga del repositorio
--     pero las métricas e insights persisten y siguen ligados a los reportes.
--   * Autenticación delegada en un IdP externo (Actor 5); app_user solo guarda
--     identidad y rol, no credenciales.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()

CREATE SCHEMA IF NOT EXISTS clinical;
CREATE SCHEMA IF NOT EXISTS setup;
CREATE SCHEMA IF NOT EXISTS recording;
CREATE SCHEMA IF NOT EXISTS metrics;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS reference;

-- =============================================================================
-- TIPOS ENUMERADOS
-- =============================================================================

CREATE TYPE clinical.user_role AS ENUM
    ('medical', 'patient', 'admin', 'technician');

CREATE TYPE clinical.doctor_type AS ENUM
    ('gp', 'medical_specialist', 'medical_technical_specialist', 'physiotherapist');

CREATE TYPE clinical.program_status AS ENUM
    ('active', 'completed', 'cancelled');

CREATE TYPE recording.media_kind AS ENUM ('audio', 'video');

CREATE TYPE recording.media_status AS ENUM ('available', 'purged', 'corrupt');

CREATE TYPE setup.metric_value_kind AS ENUM ('raw', 'derived');

CREATE TYPE audit.action AS ENUM ('create', 'update', 'delete');

CREATE TYPE clinical.sex AS ENUM ('male', 'female', 'other', 'unspecified');

CREATE TYPE reference.norm_direction AS ENUM ('higher_better', 'lower_better', 'in_range');

CREATE TYPE metrics.result_status AS ENUM ('success', 'error');

-- =============================================================================
-- ESQUEMA: clinical  (espacio "Patient data")
-- =============================================================================

-- Identidad única del sistema. La autenticación real la provee el IdP externo
-- (Actor 5); aquí solo se guarda la referencia al sujeto externo y el perfil.
CREATE TABLE clinical.app_user (
    identity_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    role             clinical.user_role NOT NULL,
    external_subject text UNIQUE,                       -- sub/claim del IdP
    status           text NOT NULL DEFAULT 'active',
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE clinical.patient (
    patient_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_id uuid NOT NULL UNIQUE REFERENCES clinical.app_user(identity_id),
    national_id text NOT NULL UNIQUE,
    first_name  text NOT NULL,
    last_name   text NOT NULL,
    birth_date  date,
    sex         clinical.sex,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Mapa paciente <-> pseudónimo (frontera de pseudonimización ante la IA).
-- Único punto donde existe el vínculo identidad<->pseudónimo; el rol ftm_ai NO accede.
-- Borrar esta fila (derecho al olvido) deja las métricas del pseudónimo de facto anónimas.
CREATE TABLE clinical.pseudonym_map (
    patient_id   uuid PRIMARY KEY REFERENCES clinical.patient(patient_id),
    pseudonym_id uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE clinical.doctor (
    doctor_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_id  uuid NOT NULL UNIQUE REFERENCES clinical.app_user(identity_id),
    colegiado_id text NOT NULL UNIQUE,
    doctor_type  clinical.doctor_type NOT NULL,
    first_name   text NOT NULL,
    last_name    text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE clinical.diagnostic (
    diagnostic_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id    uuid NOT NULL REFERENCES clinical.patient(patient_id),
    doctor_id     uuid NOT NULL REFERENCES clinical.doctor(doctor_id),  -- firmante
    dolencia      text NOT NULL,
    description   text,
    history       text,
    symptoms      text,
    signature     text NOT NULL,
    signed_at     timestamptz NOT NULL DEFAULT now(),
    content_hash  text,                                  -- hash inmutable del contenido firmado
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

-- Un diagnóstico puede originar uno o varios programas a lo largo del tiempo.
CREATE TABLE clinical.rehab_program (
    rehab_program_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    diagnostic_id     uuid NOT NULL REFERENCES clinical.diagnostic(diagnostic_id),
    physiotherapist_id uuid REFERENCES clinical.doctor(doctor_id),       -- asignado (UC-02)
    name              text,
    status            clinical.program_status NOT NULL DEFAULT 'active',
    start_date        date,
    end_date          date,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);

-- Catálogo reutilizable de ejercicios (plantilla). El análisis NO cuelga de aquí.
CREATE TABLE clinical.rehab_exercise (
    rh_exercise_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    type           text NOT NULL,
    description    text,
    created_by     uuid REFERENCES clinical.doctor(doctor_id),
    created_at     timestamptz NOT NULL DEFAULT now()
);

-- Instancia de un ejercicio del catálogo dentro de un programa concreto.
CREATE TABLE clinical.program_exercise (
    program_exercise_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rehab_program_id    uuid NOT NULL REFERENCES clinical.rehab_program(rehab_program_id),
    rh_exercise_id      uuid NOT NULL REFERENCES clinical.rehab_exercise(rh_exercise_id),
    frequency           text,
    status              text NOT NULL DEFAULT 'active',
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- Consentimiento por programa (FR-14); revocable sin borrar historial (EC-7).
CREATE TABLE clinical.patient_consent (
    consent_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id       uuid NOT NULL REFERENCES clinical.patient(patient_id),
    rehab_program_id uuid NOT NULL REFERENCES clinical.rehab_program(rehab_program_id),
    granted          boolean NOT NULL DEFAULT true,
    granted_at       timestamptz NOT NULL DEFAULT now(),
    withdrawn_at     timestamptz,
    UNIQUE (patient_id, rehab_program_id)
);

-- Resumen de grabaciones del mismo tipo en un periodo (UC-08).
CREATE TABLE clinical.exercise_report (
    exercise_report_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rehab_program_id    uuid NOT NULL REFERENCES clinical.rehab_program(rehab_program_id),
    program_exercise_id uuid REFERENCES clinical.program_exercise(program_exercise_id),
    period_start        date NOT NULL,
    period_end          date NOT NULL,
    summary             text,
    created_by          uuid REFERENCES clinical.doctor(doctor_id),
    attested_at         timestamptz,
    attested_by         uuid REFERENCES clinical.doctor(doctor_id),
    content_hash        text,                              -- hash inmutable del informe atestado
    created_at          timestamptz NOT NULL DEFAULT now(),
    CHECK (period_end >= period_start)
);

-- Agregación de reportes de un mismo programa en un periodo (UC-09).
CREATE TABLE clinical.followup_checkup (
    followup_checkup_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rehab_program_id    uuid NOT NULL REFERENCES clinical.rehab_program(rehab_program_id),
    patient_id          uuid NOT NULL REFERENCES clinical.patient(patient_id),
    period_start        date NOT NULL,
    period_end          date NOT NULL,
    summary             text,
    created_by          uuid REFERENCES clinical.doctor(doctor_id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    CHECK (period_end >= period_start)
);

-- N:N reporte <-> reporte (agregación del follow-up).
CREATE TABLE clinical.followup_checkup_report (
    followup_checkup_id uuid NOT NULL REFERENCES clinical.followup_checkup(followup_checkup_id) ON DELETE CASCADE,
    exercise_report_id  uuid NOT NULL REFERENCES clinical.exercise_report(exercise_report_id),
    PRIMARY KEY (followup_checkup_id, exercise_report_id)
);

-- =============================================================================
-- ESQUEMA: recording  (espacio "Exercise Recording")
-- =============================================================================

CREATE TABLE recording.exercise_recording (
    recording_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    program_exercise_id uuid NOT NULL REFERENCES clinical.program_exercise(program_exercise_id),
    recorded_by         uuid REFERENCES clinical.app_user(identity_id),  -- paciente/acompañante/fisio
    media_kind          recording.media_kind NOT NULL,
    media_uri           text,                                            -- puntero al repositorio (INT-3)
    media_status        recording.media_status NOT NULL DEFAULT 'available',
    recording_date      date NOT NULL,
    duration_seconds    double precision,
    sample_rate         integer,
    size_bytes          bigint,
    sha256              text,                                            -- integridad del fichero
    is_deleted          boolean NOT NULL DEFAULT false,                  -- borrado lógico (UC-13)
    deleted_at          timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- =============================================================================
-- ESQUEMA: setup  (espacio "Recording Analysis Setup")
-- =============================================================================

-- 0..1 por Program Exercise: el FK en el lado dependiente con UNIQUE.
CREATE TABLE setup.analysis_setup (
    analysis_setup_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    program_exercise_id uuid NOT NULL UNIQUE
                        REFERENCES clinical.program_exercise(program_exercise_id),
    description         text,
    type                text,
    metric_api_endpoint text,
    ai_model            text,
    ai_prompt           text,
    criteria            text,
    version             integer NOT NULL DEFAULT 1,   -- se incrementa al modificar (UC-14)
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- Definicion de cada metrica seguida, direccionada por su ruta (path) en el JSON.
CREATE TABLE setup.metric_definition (
    metric_def_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_setup_id   uuid NOT NULL
                        REFERENCES setup.analysis_setup(analysis_setup_id) ON DELETE CASCADE,
    path                text NOT NULL,                  -- p.ej. 'domains.voice_stability'
    label               text,
    section             text,                           -- 'domains' | 'raw' | ...
    value_kind          setup.metric_value_kind NOT NULL DEFAULT 'raw',
    unit                text,
    data_type           text,
    nullable            boolean NOT NULL DEFAULT false,  -- la metrica puede venir nula
    target_value        double precision,                -- objetivo/umbral para el seguimiento
    evaluation_criteria text,
    display_order       integer,
    UNIQUE (analysis_setup_id, path)
);

-- Metricas compuestas: una metrica derivada es combinacion ponderada de otras.
-- Materializa la "ponderacion de metricas" del objetivo del sistema.
CREATE TABLE setup.metric_composition (
    parent_metric_def_id uuid NOT NULL
                         REFERENCES setup.metric_definition(metric_def_id) ON DELETE CASCADE,
    child_metric_def_id  uuid NOT NULL
                         REFERENCES setup.metric_definition(metric_def_id),
    weight               double precision NOT NULL,
    PRIMARY KEY (parent_metric_def_id, child_metric_def_id),
    CHECK (parent_metric_def_id <> child_metric_def_id)
);

-- =============================================================================
-- ESQUEMA: metrics  (espacio "Exercise Recording metrics")
-- Doble almacenamiento: documento JSON integro (metric_result.raw_json,
-- consultable por jsonb_path/GIN) + valores aplanados de las metricas seguidas
-- (recording_metric) para graficar y evaluar sin recorrer el JSON.
-- =============================================================================

-- Una fila por ejecucion del analisis sobre una grabacion: JSON completo de la
-- API (claves dinamicas como per_place incluidas) + fecha y nota del resultado.
CREATE TABLE metrics.metric_result (
    result_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    recording_id      uuid NOT NULL UNIQUE REFERENCES recording.exercise_recording(recording_id),
    pseudonym_id      uuid NOT NULL,                       -- sin FK: borrar el mapa -> métricas anónimas
    analysis_setup_id uuid REFERENCES setup.analysis_setup(analysis_setup_id),
    result_date       date,
    note              text,
    raw_json          jsonb,                              -- opcional: en error puede no haber JSON
    function_name     text,                               -- función ejecutada (snapshot)
    function_version  text,                               -- versión semántica (p. ej. '1.0')
    code_sha          text,                               -- commit desplegado (cadena de custodia)
    status            metrics.result_status NOT NULL DEFAULT 'success',
    error_detail      text,
    extracted_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (status <> 'success' OR raw_json IS NOT NULL)
);

-- Valores aplanados de las metricas declaradas en el setup, por path.
-- metric_path es snapshot (sobrevive a cambios del setup); is_null marca nulos.
CREATE TABLE metrics.recording_metric (
    recording_metric_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    result_id           uuid NOT NULL REFERENCES metrics.metric_result(result_id) ON DELETE CASCADE,
    metric_def_id       uuid REFERENCES setup.metric_definition(metric_def_id),
    metric_path         text NOT NULL,
    value_num           double precision,
    value_text          text,
    is_null             boolean NOT NULL DEFAULT false
);

-- Interpretacion por IA de un resultado: 0..1 por metric_result (UNIQUE).
CREATE TABLE metrics.ai_insight (
    ai_insight_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    result_id         uuid NOT NULL UNIQUE REFERENCES metrics.metric_result(result_id) ON DELETE CASCADE,
    analysis_setup_id uuid REFERENCES setup.analysis_setup(analysis_setup_id),
    model_used        text,
    prompt_used       text,
    insight_text      text NOT NULL,
    generated_at      timestamptz NOT NULL DEFAULT now()
);

-- Vista pseudonimizada: ÚNICA interfaz de lectura del rol de IA. Proyecta solo el
-- pseudónimo y los valores numéricos (sin recording_id, media_uri ni identidad).
CREATE VIEW metrics.v_ai_payload AS
SELECT mr.pseudonym_id,
       mr.function_name AS exercise,
       mr.result_date,
       rm.metric_path,
       rm.value_num
FROM   metrics.recording_metric rm
JOIN   metrics.metric_result   mr ON mr.result_id = rm.result_id
WHERE  mr.status = 'success' AND rm.is_null = false;

-- =============================================================================
-- UNIÓN CRUZADA clinical <-> recording (se crea tras existir ambas tablas)
-- =============================================================================

-- N:N reporte <-> grabación. El vínculo persiste aunque la grabación se marque
-- como borrada (is_deleted = true), garantizando UC-13.
CREATE TABLE clinical.exercise_report_recording (
    exercise_report_id uuid NOT NULL REFERENCES clinical.exercise_report(exercise_report_id) ON DELETE CASCADE,
    recording_id       uuid NOT NULL REFERENCES recording.exercise_recording(recording_id),
    PRIMARY KEY (exercise_report_id, recording_id)
);

-- =============================================================================
-- ESQUEMA: audit  (monitorización de eventos · FR-15 / UC-15)
-- =============================================================================

-- Tabla polimórfica: registra alta/modificación/borrado de cualquier entidad.
CREATE TABLE audit.event_log (
    event_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type text NOT NULL,           -- p.ej. 'clinical.diagnostic'
    entity_id   uuid NOT NULL,
    action      audit.action NOT NULL,
    actor_id    uuid REFERENCES clinical.app_user(identity_id),
    payload     jsonb,                   -- diff / estado de la entidad
    occurred_at timestamptz NOT NULL DEFAULT now()
);

-- =============================================================================
-- ESQUEMA: reference  (normas clínicas compartidas, datos no sensibles)
-- =============================================================================

-- Catálogo de normas por métrica, compartido entre pacientes e independiente del
-- analysis_setup. Se enlaza por metric_code (= path de la métrica). Estratificable
-- por sexo y rango de edad; NULL = aplica a cualquiera (comodín).
CREATE TABLE reference.metric_norm (
    norm_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_code    text NOT NULL,                 -- coincide con metric_definition.path
    label          text,
    unit           text,
    direction      reference.norm_direction NOT NULL, -- higher_better / lower_better / in_range
    sex            clinical.sex,                  -- NULL = cualquier sexo
    age_min        integer,                       -- NULL = sin límite inferior
    age_max        integer,                       -- NULL = sin límite superior
    good_min       double precision,              -- rango BUENO (límite inferior)
    good_max       double precision,              -- rango BUENO (límite superior)
    poor_min       double precision,              -- rango POBRE (límite inferior)
    poor_max       double precision,              -- rango POBRE (límite superior)
    source         text,                          -- referencia clínica de la norma
    version        integer NOT NULL DEFAULT 1,
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (metric_code, sex, age_min, age_max, version),
    CHECK (age_min IS NULL OR age_max IS NULL OR age_min <= age_max)
);


CREATE INDEX idx_diagnostic_patient       ON clinical.diagnostic(patient_id);
CREATE INDEX idx_diagnostic_doctor        ON clinical.diagnostic(doctor_id);
CREATE INDEX idx_program_diagnostic       ON clinical.rehab_program(diagnostic_id);
CREATE INDEX idx_progex_program           ON clinical.program_exercise(rehab_program_id);
CREATE INDEX idx_progex_exercise          ON clinical.program_exercise(rh_exercise_id);
CREATE INDEX idx_consent_program          ON clinical.patient_consent(rehab_program_id);
CREATE INDEX idx_report_program           ON clinical.exercise_report(rehab_program_id);
CREATE INDEX idx_checkup_program          ON clinical.followup_checkup(rehab_program_id);
CREATE INDEX idx_checkup_patient          ON clinical.followup_checkup(patient_id);

CREATE INDEX idx_recording_progex         ON recording.exercise_recording(program_exercise_id);
CREATE INDEX idx_recording_active         ON recording.exercise_recording(program_exercise_id) WHERE is_deleted = false;

CREATE INDEX idx_metricdef_setup          ON setup.metric_definition(analysis_setup_id);
CREATE INDEX idx_metric_result_json       ON metrics.metric_result USING gin (raw_json);
CREATE INDEX idx_metric_result_pseudonym  ON metrics.metric_result(pseudonym_id);
CREATE INDEX idx_recmetric_result         ON metrics.recording_metric(result_id);
CREATE INDEX idx_recmetric_def            ON metrics.recording_metric(metric_def_id);

CREATE INDEX idx_event_entity             ON audit.event_log(entity_type, entity_id);
CREATE INDEX idx_event_actor              ON audit.event_log(actor_id);
CREATE INDEX idx_metric_norm_code         ON reference.metric_norm(metric_code);

-- =============================================================================
-- COMENTARIOS (diccionario de datos resumido)
-- =============================================================================

COMMENT ON SCHEMA clinical  IS 'Espacio Patient data: identidad, diagnósticos, programas, reportes y follow-ups.';
COMMENT ON SCHEMA recording IS 'Espacio Exercise Recording: metadatos de grabaciones (media en repositorio externo).';
COMMENT ON SCHEMA metrics   IS 'Espacio Exercise Recording metrics: valores extraídos e insights de IA.';
COMMENT ON SCHEMA setup     IS 'Espacio Recording Analysis Setup: configuración de análisis (restringido, sin datos de paciente).';
COMMENT ON SCHEMA audit     IS 'Monitorización de eventos sobre las entidades de la BBDD.';
COMMENT ON SCHEMA reference IS 'Normas clínicas compartidas (no sensibles): valores de referencia por métrica, estratificados por sexo/edad.';

COMMENT ON COLUMN recording.exercise_recording.is_deleted IS 'Borrado lógico (UC-13): el media se purga pero métricas e insights persisten.';
COMMENT ON COLUMN setup.analysis_setup.program_exercise_id IS 'Análisis configurado por instancia de ejercicio del programa (0..1).';
COMMENT ON COLUMN metrics.metric_result.raw_json IS 'Documento JSON integro devuelto por la API (fidelidad total; consultable por jsonb_path). Opcional: obligatorio solo si status = success (CHECK).';
COMMENT ON COLUMN metrics.metric_result.code_sha IS 'Commit desplegado que ejecuto la funcion: trazabilidad clinica (cadena de custodia via git).';
COMMENT ON COLUMN metrics.metric_result.status IS 'success/error del worker; en error puede no haber raw_json y error_detail describe el fallo.';
COMMENT ON COLUMN recording.exercise_recording.sha256 IS 'Hash de integridad del fichero subido.';
COMMENT ON TABLE  clinical.pseudonym_map IS 'Mapa identidad<->pseudonimo (frontera de pseudonimizacion ante IA); ftm_ai no accede. Borrarlo anonimiza las metricas asociadas.';
COMMENT ON COLUMN metrics.metric_result.pseudonym_id IS 'Pseudonimo del paciente (sin FK): lo unico que cruza al LLM, via la vista v_ai_payload.';
COMMENT ON VIEW   metrics.v_ai_payload IS 'Interfaz pseudonimizada para el rol de IA: pseudonimo + metricas numericas, sin claves enlazables.';
COMMENT ON COLUMN metrics.recording_metric.metric_path IS 'Ruta de la metrica en el JSON; snapshot para sobrevivir a cambios del setup (UC-14).';

-- =============================================================================
-- ROLES Y PRIVILEGIOS (matriz de seguridad 6.1)
-- Punto de partida; el aislamiento fino "paciente ve solo lo suyo" (FR-09)
-- se completa con Row-Level Security (ejemplo al final).
-- =============================================================================

CREATE ROLE ftm_gp;                  -- Médico de cabecera
CREATE ROLE ftm_medical_specialist;  -- Médico especialista
CREATE ROLE ftm_technician;          -- Medical Technical Specialist
CREATE ROLE ftm_patient;             -- Paciente
CREATE ROLE ftm_ai;                  -- Modelo de IA

-- GP: datos clínicos, grabaciones y lectura de métricas. NO accede a setup.
GRANT USAGE ON SCHEMA clinical, recording, metrics TO ftm_gp;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA clinical, recording TO ftm_gp;
GRANT SELECT ON ALL TABLES IN SCHEMA metrics TO ftm_gp;

-- Medical Specialist: todo lo del GP + configuración de análisis (setup).
GRANT USAGE ON SCHEMA clinical, recording, metrics, setup TO ftm_medical_specialist;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA clinical, recording, setup TO ftm_medical_specialist;
GRANT SELECT ON ALL TABLES IN SCHEMA metrics TO ftm_medical_specialist;

-- Technician: SOLO setup (+ lectura mínima del ejercicio para enlazarlo).
GRANT USAGE ON SCHEMA setup, clinical TO ftm_technician;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA setup TO ftm_technician;
GRANT SELECT (program_exercise_id, rehab_program_id, rh_exercise_id)
    ON clinical.program_exercise TO ftm_technician;

-- Patient: sus datos clínicos, sus grabaciones (crea/borra), lectura de métricas.
GRANT USAGE ON SCHEMA clinical, recording, metrics TO ftm_patient;
GRANT SELECT ON ALL TABLES IN SCHEMA clinical TO ftm_patient;
GRANT SELECT, INSERT, UPDATE, DELETE ON recording.exercise_recording TO ftm_patient;
GRANT SELECT ON ALL TABLES IN SCHEMA metrics TO ftm_patient;

-- IA (servicio que llama al LLM externo): SOLO la vista pseudonimizada + escritura de insight.
-- No ve recording_id, media_uri ni identidad — esta es la frontera de pseudonimización (FR-04).
GRANT USAGE ON SCHEMA setup, metrics TO ftm_ai;
GRANT SELECT ON ALL TABLES IN SCHEMA setup TO ftm_ai;            -- prompt/criteria/defs (config, sin PII)
GRANT SELECT ON metrics.v_ai_payload TO ftm_ai;                  -- única lectura de métricas
GRANT SELECT, INSERT, UPDATE ON metrics.ai_insight TO ftm_ai;

-- Worker de extracción: cruza la frontera identidad -> pseudónimo. Resuelve el pseudónimo,
-- lee el media y escribe las métricas. NO llama al LLM externo.
CREATE ROLE ftm_worker;
GRANT USAGE ON SCHEMA clinical, recording, setup, metrics TO ftm_worker;
GRANT SELECT ON recording.exercise_recording TO ftm_worker;
GRANT SELECT ON clinical.pseudonym_map, clinical.program_exercise,
                clinical.rehab_program, clinical.diagnostic TO ftm_worker;  -- resolver paciente -> pseudónimo
GRANT SELECT ON ALL TABLES IN SCHEMA setup TO ftm_worker;
GRANT SELECT, INSERT, UPDATE ON metrics.metric_result, metrics.recording_metric TO ftm_worker;

-- Reference (normas): lectura para todos los roles; escritura para especialista y técnico.
GRANT USAGE ON SCHEMA reference TO ftm_gp, ftm_medical_specialist, ftm_technician, ftm_patient, ftm_ai;
GRANT SELECT ON ALL TABLES IN SCHEMA reference TO ftm_gp, ftm_medical_specialist, ftm_technician, ftm_patient, ftm_ai;
GRANT INSERT, UPDATE ON ALL TABLES IN SCHEMA reference TO ftm_medical_specialist, ftm_technician;

-- ===========================================================================
-- ROW-LEVEL SECURITY (FR-09)
-- Contrato de sesión: la app conecta con el LOGIN del rol del usuario
--   (ftm_patient / ftm_gp / ftm_medical_specialist / ...) y ejecuta, por sesión:
--       SET app.identity_id = '<app_user.identity_id>';
--   NUNCA conecta como owner. No se usa FORCE: el owner y las funciones SECURITY
--   DEFINER omiten RLS (evita recursión al resolver identidad).
-- Alcance MVP: el paciente ve SOLO lo suyo; los médicos (gp + especialista) ven a
--   nivel de clínica; técnico e IA quedan fuera de los datos clínicos. El particionado
--   por médico (cada médico solo sus pacientes) exigiría una tabla de relación de
--   cuidado y queda como deuda documentada.
-- ===========================================================================

-- Helpers de identidad (SECURITY DEFINER => omiten RLS al leer patient/doctor/map).
CREATE FUNCTION clinical.current_patient_id() RETURNS uuid
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = clinical AS $$
  SELECT patient_id FROM clinical.patient
  WHERE identity_id = current_setting('app.identity_id', true)::uuid $$;

CREATE FUNCTION clinical.current_doctor_id() RETURNS uuid
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = clinical AS $$
  SELECT doctor_id FROM clinical.doctor
  WHERE identity_id = current_setting('app.identity_id', true)::uuid $$;

CREATE FUNCTION clinical.current_pseudonym() RETURNS uuid
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = clinical AS $$
  SELECT pseudonym_id FROM clinical.pseudonym_map
  WHERE patient_id = clinical.current_patient_id() $$;

-- clinical.app_user --------------------------------------------------------
ALTER TABLE clinical.app_user ENABLE ROW LEVEL SECURITY;
CREATE POLICY app_user_staff ON clinical.app_user FOR ALL
  TO ftm_gp, ftm_medical_specialist USING (true) WITH CHECK (true);
CREATE POLICY app_user_self ON clinical.app_user FOR SELECT
  TO ftm_patient USING (identity_id = current_setting('app.identity_id', true)::uuid);

-- clinical.patient ---------------------------------------------------------
ALTER TABLE clinical.patient ENABLE ROW LEVEL SECURITY;
CREATE POLICY patient_staff ON clinical.patient FOR ALL
  TO ftm_gp, ftm_medical_specialist USING (true) WITH CHECK (true);
CREATE POLICY patient_self ON clinical.patient FOR SELECT
  TO ftm_patient USING (patient_id = clinical.current_patient_id());

-- clinical.pseudonym_map (ftm_ai SIN grant: nunca lo ve) -------------------
ALTER TABLE clinical.pseudonym_map ENABLE ROW LEVEL SECURITY;
CREATE POLICY pseudo_staff ON clinical.pseudonym_map FOR ALL
  TO ftm_gp, ftm_medical_specialist USING (true) WITH CHECK (true);
CREATE POLICY pseudo_self ON clinical.pseudonym_map FOR SELECT
  TO ftm_patient USING (patient_id = clinical.current_patient_id());
CREATE POLICY pseudo_worker ON clinical.pseudonym_map FOR SELECT
  TO ftm_worker USING (true);

-- clinical.diagnostic ------------------------------------------------------
ALTER TABLE clinical.diagnostic ENABLE ROW LEVEL SECURITY;
CREATE POLICY diag_staff ON clinical.diagnostic FOR ALL
  TO ftm_gp, ftm_medical_specialist USING (true) WITH CHECK (true);
CREATE POLICY diag_self ON clinical.diagnostic FOR SELECT
  TO ftm_patient USING (patient_id = clinical.current_patient_id());
CREATE POLICY diag_worker ON clinical.diagnostic FOR SELECT
  TO ftm_worker USING (true);

-- clinical.rehab_program ---------------------------------------------------
ALTER TABLE clinical.rehab_program ENABLE ROW LEVEL SECURITY;
CREATE POLICY prog_staff ON clinical.rehab_program FOR ALL
  TO ftm_gp, ftm_medical_specialist USING (true) WITH CHECK (true);
CREATE POLICY prog_self ON clinical.rehab_program FOR SELECT
  TO ftm_patient USING (EXISTS (SELECT 1 FROM clinical.diagnostic d
    WHERE d.diagnostic_id = rehab_program.diagnostic_id
      AND d.patient_id = clinical.current_patient_id()));
CREATE POLICY prog_worker ON clinical.rehab_program FOR SELECT
  TO ftm_worker USING (true);

-- clinical.program_exercise ------------------------------------------------
ALTER TABLE clinical.program_exercise ENABLE ROW LEVEL SECURITY;
CREATE POLICY pex_staff ON clinical.program_exercise FOR ALL
  TO ftm_gp, ftm_medical_specialist USING (true) WITH CHECK (true);
CREATE POLICY pex_self ON clinical.program_exercise FOR SELECT
  TO ftm_patient USING (EXISTS (SELECT 1 FROM clinical.rehab_program rp
    JOIN clinical.diagnostic d ON d.diagnostic_id = rp.diagnostic_id
    WHERE rp.rehab_program_id = program_exercise.rehab_program_id
      AND d.patient_id = clinical.current_patient_id()));
CREATE POLICY pex_tech ON clinical.program_exercise FOR SELECT
  TO ftm_technician USING (true);
CREATE POLICY pex_worker ON clinical.program_exercise FOR SELECT
  TO ftm_worker USING (true);

-- clinical.patient_consent -------------------------------------------------
ALTER TABLE clinical.patient_consent ENABLE ROW LEVEL SECURITY;
CREATE POLICY consent_staff ON clinical.patient_consent FOR ALL
  TO ftm_gp, ftm_medical_specialist USING (true) WITH CHECK (true);
CREATE POLICY consent_self ON clinical.patient_consent FOR SELECT
  TO ftm_patient USING (patient_id = clinical.current_patient_id());

-- clinical.exercise_report -------------------------------------------------
ALTER TABLE clinical.exercise_report ENABLE ROW LEVEL SECURITY;
CREATE POLICY report_staff ON clinical.exercise_report FOR ALL
  TO ftm_gp, ftm_medical_specialist USING (true) WITH CHECK (true);
CREATE POLICY report_self ON clinical.exercise_report FOR SELECT
  TO ftm_patient USING (EXISTS (SELECT 1 FROM clinical.rehab_program rp
    JOIN clinical.diagnostic d ON d.diagnostic_id = rp.diagnostic_id
    WHERE rp.rehab_program_id = exercise_report.rehab_program_id
      AND d.patient_id = clinical.current_patient_id()));

-- clinical.exercise_report_recording (link) --------------------------------
ALTER TABLE clinical.exercise_report_recording ENABLE ROW LEVEL SECURITY;
CREATE POLICY errec_staff ON clinical.exercise_report_recording FOR ALL
  TO ftm_gp, ftm_medical_specialist USING (true) WITH CHECK (true);
CREATE POLICY errec_self ON clinical.exercise_report_recording FOR SELECT
  TO ftm_patient USING (EXISTS (SELECT 1 FROM clinical.exercise_report er
    JOIN clinical.rehab_program rp ON rp.rehab_program_id = er.rehab_program_id
    JOIN clinical.diagnostic d ON d.diagnostic_id = rp.diagnostic_id
    WHERE er.exercise_report_id = exercise_report_recording.exercise_report_id
      AND d.patient_id = clinical.current_patient_id()));

-- clinical.followup_checkup ------------------------------------------------
ALTER TABLE clinical.followup_checkup ENABLE ROW LEVEL SECURITY;
CREATE POLICY fchk_staff ON clinical.followup_checkup FOR ALL
  TO ftm_gp, ftm_medical_specialist USING (true) WITH CHECK (true);
CREATE POLICY fchk_self ON clinical.followup_checkup FOR SELECT
  TO ftm_patient USING (patient_id = clinical.current_patient_id());

-- clinical.followup_checkup_report (link) ----------------------------------
ALTER TABLE clinical.followup_checkup_report ENABLE ROW LEVEL SECURITY;
CREATE POLICY fcr_staff ON clinical.followup_checkup_report FOR ALL
  TO ftm_gp, ftm_medical_specialist USING (true) WITH CHECK (true);
CREATE POLICY fcr_self ON clinical.followup_checkup_report FOR SELECT
  TO ftm_patient USING (EXISTS (SELECT 1 FROM clinical.followup_checkup fc
    WHERE fc.followup_checkup_id = followup_checkup_report.followup_checkup_id
      AND fc.patient_id = clinical.current_patient_id()));

-- recording.exercise_recording ---------------------------------------------
ALTER TABLE recording.exercise_recording ENABLE ROW LEVEL SECURITY;
CREATE POLICY rec_staff ON recording.exercise_recording FOR ALL
  TO ftm_gp, ftm_medical_specialist USING (true) WITH CHECK (true);
CREATE POLICY rec_self ON recording.exercise_recording FOR ALL
  TO ftm_patient
  USING (EXISTS (SELECT 1 FROM clinical.program_exercise pe
    JOIN clinical.rehab_program rp ON rp.rehab_program_id = pe.rehab_program_id
    JOIN clinical.diagnostic d ON d.diagnostic_id = rp.diagnostic_id
    WHERE pe.program_exercise_id = exercise_recording.program_exercise_id
      AND d.patient_id = clinical.current_patient_id()))
  WITH CHECK (EXISTS (SELECT 1 FROM clinical.program_exercise pe
    JOIN clinical.rehab_program rp ON rp.rehab_program_id = pe.rehab_program_id
    JOIN clinical.diagnostic d ON d.diagnostic_id = rp.diagnostic_id
    WHERE pe.program_exercise_id = exercise_recording.program_exercise_id
      AND d.patient_id = clinical.current_patient_id()));
CREATE POLICY rec_worker ON recording.exercise_recording FOR SELECT
  TO ftm_worker USING (true);

-- metrics.metric_result (paciente por pseudónimo; worker escribe) -----------
ALTER TABLE metrics.metric_result ENABLE ROW LEVEL SECURITY;
CREATE POLICY mr_staff ON metrics.metric_result FOR SELECT
  TO ftm_gp, ftm_medical_specialist USING (true);
CREATE POLICY mr_self ON metrics.metric_result FOR SELECT
  TO ftm_patient USING (pseudonym_id = clinical.current_pseudonym());
CREATE POLICY mr_worker ON metrics.metric_result FOR ALL
  TO ftm_worker USING (true) WITH CHECK (true);

-- metrics.recording_metric -------------------------------------------------
ALTER TABLE metrics.recording_metric ENABLE ROW LEVEL SECURITY;
CREATE POLICY rm_staff ON metrics.recording_metric FOR SELECT
  TO ftm_gp, ftm_medical_specialist USING (true);
CREATE POLICY rm_self ON metrics.recording_metric FOR SELECT
  TO ftm_patient USING (EXISTS (SELECT 1 FROM metrics.metric_result mr
    WHERE mr.result_id = recording_metric.result_id
      AND mr.pseudonym_id = clinical.current_pseudonym()));
CREATE POLICY rm_worker ON metrics.recording_metric FOR ALL
  TO ftm_worker USING (true) WITH CHECK (true);

-- metrics.ai_insight (la IA escribe; lee vía v_ai_payload, no esta tabla) --
ALTER TABLE metrics.ai_insight ENABLE ROW LEVEL SECURITY;
CREATE POLICY ai_staff ON metrics.ai_insight FOR SELECT
  TO ftm_gp, ftm_medical_specialist USING (true);
CREATE POLICY ai_self ON metrics.ai_insight FOR SELECT
  TO ftm_patient USING (EXISTS (SELECT 1 FROM metrics.metric_result mr
    WHERE mr.result_id = ai_insight.result_id
      AND mr.pseudonym_id = clinical.current_pseudonym()));
CREATE POLICY ai_write ON metrics.ai_insight FOR ALL
  TO ftm_ai USING (true) WITH CHECK (true);

-- Nota: la vista metrics.v_ai_payload se ejecuta como su owner (omite RLS), por lo que
-- ftm_ai sigue leyendo métricas pseudonimizadas. El acotado por petición (un solo
-- pseudónimo/resultado) lo aplica el código de egress.
