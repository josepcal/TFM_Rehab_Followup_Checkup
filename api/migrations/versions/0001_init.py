"""init: schemas, tablas, RLS, seed

Revision ID: 0001
Revises:
"""
import os

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

APP_ROLE = os.environ.get("APP_DB_USER", "ftm_app")
SCHEMAS = ["iam", "clinical", "catalog", "analysis", "recording", "metrics", "reporting"]

E1 = "11111111-1111-1111-1111-111111111111"
E2 = "22222222-2222-2222-2222-222222222222"
E3 = "33333333-3333-3333-3333-333333333333"


def upgrade():
    # --- schemas ---
    for s in SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {s}")

    # --- tablas ---
    op.execute("""
    CREATE TABLE iam.user_ref (
        id uuid PRIMARY KEY, keycloak_id text UNIQUE NOT NULL, perfil text NOT NULL);
    CREATE TABLE iam.consent (
        id uuid PRIMARY KEY, patient_id uuid NOT NULL, tipo text NOT NULL,
        granted_at timestamp DEFAULT now(), revoked_at timestamp);
    CREATE TABLE iam.audit_log (
        id uuid PRIMARY KEY, actor_id text, accion text, recurso text,
        ts timestamp DEFAULT now(), ip text);

    CREATE TABLE catalog.rehab_exercise (
        id uuid PRIMARY KEY, nombre text NOT NULL, descripcion text, tipo text);

    CREATE TABLE clinical.patient (
        id uuid PRIMARY KEY, keycloak_id text, national_id text,
        nombre text, apellidos text, created_at timestamp DEFAULT now());
    CREATE TABLE clinical.doctor (
        id uuid PRIMARY KEY, keycloak_id text NOT NULL, colegiado_id text,
        nombre text, apellidos text);
    CREATE TABLE clinical.care_assignment (
        id uuid PRIMARY KEY, doctor_keycloak_id text NOT NULL,
        patient_id uuid NOT NULL REFERENCES clinical.patient(id),
        created_at timestamp DEFAULT now());
    CREATE TABLE clinical.diagnostic (
        id uuid PRIMARY KEY,
        patient_id uuid NOT NULL REFERENCES clinical.patient(id),
        doctor_id uuid NOT NULL REFERENCES clinical.doctor(id),
        dolencia text, descripcion text, history text, symptoms text, signature text, signed_at timestamp,
        created_at timestamp DEFAULT now());
    CREATE TABLE clinical.rehab_program (
        id uuid PRIMARY KEY,
        diagnostic_id uuid NOT NULL REFERENCES clinical.diagnostic(id),
        estado text DEFAULT 'activo', created_at timestamp DEFAULT now());
    CREATE TABLE clinical.program_exercise (
        id uuid PRIMARY KEY,
        program_id uuid NOT NULL REFERENCES clinical.rehab_program(id),
        exercise_id uuid NOT NULL, pauta text, estado text DEFAULT 'asignado');
    CREATE TABLE clinical.pseudonym_map (
        patient_id uuid PRIMARY KEY REFERENCES clinical.patient(id),
        pseudonym_id uuid NOT NULL);

    CREATE TABLE analysis.analysis_setup (
        id uuid PRIMARY KEY, exercise_id uuid NOT NULL,
        metric_api_endpoint text NOT NULL, function_params jsonb DEFAULT '{}',
        llm_io_contract jsonb DEFAULT '{}', prompt text);
    CREATE TABLE analysis.ai_insight (
        id uuid PRIMARY KEY, recording_metrics_id uuid NOT NULL,
        output jsonb, model text, generated_at timestamp DEFAULT now());

    CREATE TABLE recording.exercise_recording (
        id uuid PRIMARY KEY, program_exercise_id uuid NOT NULL,
        storage_uri text NOT NULL, content_type text DEFAULT 'audio/wav',
        estado text DEFAULT 'grabado', fecha timestamp DEFAULT now());

    CREATE TABLE metrics.recording_metrics (
        id uuid PRIMARY KEY, recording_id uuid NOT NULL, pseudonym_id uuid NOT NULL,
        function_name text NOT NULL, metrics jsonb NOT NULL,
        extracted_at timestamp DEFAULT now());
    CREATE TABLE metrics.analysis_job (
        id uuid PRIMARY KEY, recording_id uuid NOT NULL, function_name text NOT NULL,
        status text DEFAULT 'pending', error text,
        created_at timestamp DEFAULT now(), updated_at timestamp DEFAULT now());

    CREATE TABLE reporting.exercise_report (
        id uuid PRIMARY KEY, recording_id uuid NOT NULL, metrics_id uuid,
        insight_id uuid, resumen text, created_at timestamp DEFAULT now());
    CREATE TABLE reporting.followup_checkup (
        id uuid PRIMARY KEY, patient_id uuid NOT NULL, doctor_id uuid NOT NULL,
        periodo text, report_ids uuid[], notas text, created_at timestamp DEFAULT now());
    """)

    # --- RLS en las tablas criticas (patient y metrics). Alimentada por claims. ---
    op.execute("""
    ALTER TABLE clinical.patient ENABLE ROW LEVEL SECURITY;
    ALTER TABLE clinical.patient FORCE ROW LEVEL SECURITY;

    CREATE POLICY patient_select ON clinical.patient FOR SELECT USING (
        current_setting('app.role', true) = 'system'
        OR keycloak_id = current_setting('app.user', true)
        OR EXISTS (
            SELECT 1 FROM clinical.care_assignment a
            WHERE a.patient_id = patient.id
              AND a.doctor_keycloak_id = current_setting('app.user', true)
              AND current_setting('app.role', true) = 'medical')
    );
    CREATE POLICY patient_insert ON clinical.patient FOR INSERT WITH CHECK (
        current_setting('app.role', true) IN ('medical','admin','system'));
    CREATE POLICY patient_update ON clinical.patient FOR UPDATE USING (
        current_setting('app.role', true) IN ('medical','admin','system'));

    ALTER TABLE metrics.recording_metrics ENABLE ROW LEVEL SECURITY;
    ALTER TABLE metrics.recording_metrics FORCE ROW LEVEL SECURITY;
    CREATE POLICY metrics_read ON metrics.recording_metrics FOR SELECT USING (
        current_setting('app.role', true) IN ('system','medical','patient'));
    CREATE POLICY metrics_write ON metrics.recording_metrics FOR INSERT WITH CHECK (
        current_setting('app.role', true) IN ('system','medical'));
    """)

    # --- Reclamar paciente por DNI exacto (puerta estrecha, audita aparte) ---
    op.execute("""
    CREATE OR REPLACE FUNCTION clinical.claim_patient(p_national_id text)
    RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = clinical AS $$
    DECLARE v_id uuid;
    BEGIN
        SELECT id INTO v_id FROM clinical.patient WHERE national_id = p_national_id;
        IF v_id IS NULL THEN RAISE EXCEPTION 'paciente no encontrado'; END IF;
        INSERT INTO clinical.care_assignment(id, doctor_keycloak_id, patient_id, created_at)
            VALUES (gen_random_uuid(), current_setting('app.user', true), v_id, now());
        RETURN v_id;
    END; $$;
    """)

    # --- Permisos al rol de la app (RLS sigue filtrando; no es dueno de las tablas) ---
    schema_list = ", ".join(SCHEMAS)
    op.execute(f"GRANT USAGE ON SCHEMA {schema_list} TO {APP_ROLE};")
    for s in SCHEMAS:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {s} TO {APP_ROLE};")
    op.execute(f"GRANT EXECUTE ON FUNCTION clinical.claim_patient(text) TO {APP_ROLE};")

    # --- Seed: 3 ejercicios + su analysis_setup (metric_api_endpoint registrado) ---
    op.execute(f"""
    INSERT INTO catalog.rehab_exercise (id, nombre, descripcion, tipo) VALUES
      ('{E1}', 'Fonacion sostenida', 'Rehab de voz', 'voz'),
      ('{E2}', 'Respiracion pautada', 'Rehab respiratoria', 'respiratoria'),
      ('{E3}', 'Diadococinesia pa-ta-ka', 'Rehab del habla', 'habla');

    INSERT INTO analysis.analysis_setup (id, exercise_id, metric_api_endpoint, prompt) VALUES
      (gen_random_uuid(), '{E1}', 'sustained_phonation_v1', 'Evaluar progreso de fonacion'),
      (gen_random_uuid(), '{E2}', 'breathing_cadence_v1',  'Evaluar cadencia respiratoria'),
      (gen_random_uuid(), '{E3}', 'ddk_rate_v1',           'Evaluar tasa diadococinetica');
    """)


def downgrade():
    for s in reversed(SCHEMAS):
        op.execute(f"DROP SCHEMA IF EXISTS {s} CASCADE")
