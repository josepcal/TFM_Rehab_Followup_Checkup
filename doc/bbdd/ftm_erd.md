# Modelo entidad-relación — FTM

Modelo de datos del *Medical Rehab Follow-up Check-up Tool* (FTM), derivado del SDD v1.8.
Vista de conjunto; la autoridad sobre tipos y restricciones es `ftm_schema.sql` y el detalle por
columna está en el diccionario de datos.

```mermaid
erDiagram
  APP_USER ||--o| PATIENT : es
  PATIENT ||--|| PSEUDONYM_MAP : pseudonimiza
  APP_USER ||--o| DOCTOR : es
  APP_USER ||--o{ EVENT_LOG : ejecuta
  PATIENT ||--o{ DIAGNOSTIC : tiene
  DOCTOR ||--o{ DIAGNOSTIC : firma
  DIAGNOSTIC ||--o{ REHAB_PROGRAM : origina
  DOCTOR ||--o{ REHAB_PROGRAM : supervisa
  PATIENT ||--o{ PATIENT_CONSENT : otorga
  REHAB_PROGRAM ||--o{ PATIENT_CONSENT : requiere
  REHAB_PROGRAM ||--o{ PROGRAM_EXERCISE : contiene
  REHAB_EXERCISE ||--o{ PROGRAM_EXERCISE : instancia
  PROGRAM_EXERCISE ||--o| ANALYSIS_SETUP : configura
  ANALYSIS_SETUP ||--o{ METRIC_DEFINITION : define
  METRIC_DEFINITION ||--o{ METRIC_COMPOSITION : "compone(padre)"
  METRIC_DEFINITION ||--o{ METRIC_COMPOSITION : "parte_de(hijo)"
  PROGRAM_EXERCISE ||--o{ EXERCISE_RECORDING : graba
  EXERCISE_RECORDING ||--o| METRIC_RESULT : produce
  EXERCISE_RECORDING ||--o{ ANALYSIS_JOB : queues
  ANALYSIS_SETUP ||--o{ METRIC_RESULT : aplica
  METRIC_RESULT ||--o{ RECORDING_METRIC : aplana
  METRIC_DEFINITION ||--o{ RECORDING_METRIC : tipa
  METRIC_RESULT ||--o| AI_INSIGHT : interpreta
  REHAB_PROGRAM ||--o{ EXERCISE_REPORT : resume
  EXERCISE_REPORT ||--o{ EXERCISE_REPORT_RECORDING : incluye
  EXERCISE_RECORDING ||--o{ EXERCISE_REPORT_RECORDING : aparece
  REHAB_PROGRAM ||--o{ FOLLOWUP_CHECKUP : controla
  PATIENT ||--o{ FOLLOWUP_CHECKUP : sobre
  FOLLOWUP_CHECKUP ||--o{ FOLLOWUP_CHECKUP_REPORT : agrega
  EXERCISE_REPORT ||--o{ FOLLOWUP_CHECKUP_REPORT : forma

  APP_USER {
    uuid identity_id PK
    string role
    string external_subject
    string status
    timestamp created_at
  }
  PATIENT {
    uuid patient_id PK
    uuid identity_id FK
    string national_id
    string first_name
    string last_name
    date birth_date
    string sex
  }
  PSEUDONYM_MAP {
    uuid patient_id PK
    uuid pseudonym_id
    timestamp created_at
  }
  DOCTOR {
    uuid doctor_id PK
    uuid identity_id FK
    string colegiado_id
    string doctor_type
    string first_name
    string last_name
  }
  DIAGNOSTIC {
    uuid diagnostic_id PK
    uuid patient_id FK
    uuid doctor_id FK
    string dolencia
    text description
    text history
    text symptoms
    string signature
    timestamp signed_at
    string content_hash
  }
  REHAB_PROGRAM {
    uuid rehab_program_id PK
    uuid diagnostic_id FK
    uuid physiotherapist_id FK
    string name
    string status
    date start_date
    date end_date
  }
  PATIENT_CONSENT {
    uuid consent_id PK
    uuid patient_id FK
    uuid rehab_program_id FK
    bool granted
    timestamp granted_at
    timestamp withdrawn_at
  }
  REHAB_EXERCISE {
    uuid rh_exercise_id PK
    string type
    text description
    uuid created_by FK
  }
  PROGRAM_EXERCISE {
    uuid program_exercise_id PK
    uuid rehab_program_id FK
    uuid rh_exercise_id FK
    string frequency
    string status
  }
  ANALYSIS_SETUP {
    uuid analysis_setup_id PK
    uuid program_exercise_id FK
    string description
    string type
    string metric_api_endpoint
    string ai_model
    text ai_prompt
    text criteria
    int version
  }
  METRIC_DEFINITION {
    uuid metric_def_id PK
    uuid analysis_setup_id FK
    string path
    string label
    string section
    string value_kind
    string unit
    string data_type
    bool nullable
    float target_value
    text evaluation_criteria
    int display_order
  }
  METRIC_COMPOSITION {
    uuid parent_metric_def_id FK
    uuid child_metric_def_id FK
    float weight
  }
  EXERCISE_RECORDING {
    uuid recording_id PK
    uuid program_exercise_id FK
    uuid recorded_by FK
    string media_kind
    string media_uri
    string media_status
    date recording_date
    float duration_seconds
    int sample_rate
    bigint size_bytes
    string sha256
    bool is_deleted
    timestamp deleted_at
  }
  METRIC_RESULT {
    uuid result_id PK
    uuid recording_id FK
    uuid pseudonym_id
    uuid analysis_setup_id FK
    date result_date
    text note
    jsonb raw_json
    string function_name
    string function_version
    string code_sha
    string status
    text error_detail
    timestamp extracted_at
  }
  RECORDING_METRIC {
    uuid recording_metric_id PK
    uuid result_id FK
    uuid metric_def_id FK
    string metric_path
    float value_num
    string value_text
    bool is_null
  }
  AI_INSIGHT {
    uuid ai_insight_id PK
    uuid result_id FK
    uuid analysis_setup_id FK
    string model_used
    text prompt_used
    text insight_text
    timestamp generated_at
  }
  EXERCISE_REPORT {
    uuid exercise_report_id PK
    uuid rehab_program_id FK
    uuid program_exercise_id FK
    date period_start
    date period_end
    text summary
    uuid created_by FK
    timestamp attested_at
    uuid attested_by FK
    string content_hash
  }
  EXERCISE_REPORT_RECORDING {
    uuid exercise_report_id FK
    uuid recording_id FK
  }
  FOLLOWUP_CHECKUP {
    uuid followup_checkup_id PK
    uuid rehab_program_id FK
    uuid patient_id FK
    date period_start
    date period_end
    text summary
  }
  FOLLOWUP_CHECKUP_REPORT {
    uuid followup_checkup_id FK
    uuid exercise_report_id FK
  }
  ANALYSIS_JOB {
    uuid id PK
    uuid recording_id FK
    string function_name
    string status
    int attempts
    text error_detail
    timestamp created_at
    timestamp locked_at
    timestamp updated_at
  }
  EVENT_LOG {
    uuid event_id PK
    string entity_type
    uuid entity_id
    string action
    uuid actor_id FK
    jsonb payload
    timestamp occurred_at
  }
  METRIC_NORM {
    uuid norm_id PK
    string metric_code
    string direction
    string sex
    int age_min
    int age_max
    float good_min
    float good_max
    float poor_min
    float poor_max
    string source
    int version
  }
```

> `METRIC_NORM` es un catálogo compartido (esquema `reference`): se enlaza con
> `METRIC_DEFINITION` por `metric_code` = `path` (enlace lógico por código, sin FK), por lo que
> aparece como entidad independiente.
>
> `PSEUDONYM_MAP` (esquema `clinical`) es el único vínculo identidad↔pseudónimo; el rol de IA no
> accede. `METRIC_RESULT.pseudonym_id` no tiene FK al mapa: borrarlo anonimiza las métricas. La
> IA lee solo la vista `metrics.v_ai_payload` (pseudónimo + valores).
