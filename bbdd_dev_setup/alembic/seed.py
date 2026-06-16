"""Seed de datos FTM a partir de patient_sessions.json (disartria flácida).

Crea, sobre el modelo de models.py:
  1. Un doctor por defecto.
  2. Un paciente por defecto con datos clínicos completos.
  2b. Diez pacientes demo adicionales para poblar el listado.
  3. Un diagnóstico de disartria flácida.
  4. Un programa de rehabilitación logopédico.
  5. Tres ejercicios del programa (uno por grabación: fonación, DDK pa-ta-ka, lectura).
  6. Las definiciones de métricas de cada ejercicio (con composición ponderada de las derivadas).
Y carga el array de sesiones del JSON como, por sesión y ejercicio:
  - una grabación (exercise_recording),
  - un resultado (metric_result) con el JSON troceado por ejercicio en raw_json,
  - las métricas seguidas aplanadas (recording_metric).

Nota de modelado: la API emite UN JSON combinado por sesión (cubre los 3 ejercicios). Como
metric_result es 1:1 con la grabación, el seed reparte cada sesión entre las 3 grabaciones
troceando el JSON por dominio clínico; el detalle fino de per_place se conserva íntegro en
raw_json y solo se aplanan las métricas declaradas.

Uso:
    pip install "sqlalchemy>=2.0" "psycopg[binary]"
    python seed.py --json patient_sessions.json \
        --db "postgresql+psycopg://user:pass@localhost/ftm"
    # validación sin BD:
    python seed.py --json patient_sessions.json --dry-run
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import uuid

import models as m

# ---------------------------------------------------------------------------
# Catálogo de los 3 ejercicios: troceado del JSON, definiciones y composición.
# def = (path, label, section, value_kind, unit, data_type, nullable, target, order)
# ---------------------------------------------------------------------------
RAW, DER = "raw", "derived"

EXERCISES = [
    dict(
        key="sustained_phonation", ex_type="phonation",
        ex_desc="Fonación sostenida de la vocal /a/ (calidad de voz).",
        setup_desc="Análisis de fonación sostenida: calidad de voz (HNR, jitter, shimmer, MPT).",
        slice_domains=["voice_stability", "respiratory_support"],
        slice_raw=["phonation_duration_sec", "jitter_local_pct", "shimmer_local_pct",
                   "hnr_db", "volume_std_db"],
        defs=[
            ("domains.voice_stability", "Estabilidad de voz", "domains", DER, "score", "float", False, 80.0, 1),
            ("domains.respiratory_support", "Soporte respiratorio", "domains", DER, "score", "float", False, 80.0, 2),
            ("raw.phonation_duration_sec", "Tiempo máximo de fonación", "raw", RAW, "s", "float", False, 15.0, 3),
            ("raw.jitter_local_pct", "Jitter local", "raw", RAW, "%", "float", False, 1.04, 4),
            ("raw.shimmer_local_pct", "Shimmer local", "raw", RAW, "%", "float", False, 3.8, 5),
            ("raw.hnr_db", "HNR", "raw", RAW, "dB", "float", False, 20.0, 6),
            ("raw.volume_std_db", "Variabilidad de volumen", "raw", RAW, "dB", "float", False, None, 7),
        ],
        comps=[
            ("domains.voice_stability", [("raw.jitter_local_pct", -0.3), ("raw.shimmer_local_pct", -0.3), ("raw.hnr_db", 0.4)]),
            ("domains.respiratory_support", [("raw.phonation_duration_sec", 0.7), ("raw.volume_std_db", -0.3)]),
        ],
    ),
    dict(
        key="ddk_pataka", ex_type="ddk",
        ex_desc="Diadococinesia pa-ta-ka (ritmo y cierre articulatorio).",
        setup_desc="Análisis de diadococinesia (DDK) pa-ta-ka: tasa, regularidad y cierre por punto.",
        slice_domains=["ddk_regular", "labial_closure", "lingual_closure"],
        slice_raw=["smr_n_syllables", "smr_rate_syll_sec", "smr_cv_interval", "per_place",
                   "labial_mod_depth", "lingual_mod_depth"],
        defs=[
            ("domains.ddk_regular", "Regularidad DDK", "domains", DER, "score", "float", False, 80.0, 1),
            ("domains.labial_closure", "Cierre labial", "domains", DER, "score", "float", False, 80.0, 2),
            ("domains.lingual_closure", "Cierre lingual", "domains", DER, "score", "float", False, 80.0, 3),
            ("raw.smr_n_syllables", "Nº de sílabas (SMR)", "raw", RAW, "count", "int", False, None, 4),
            ("raw.smr_rate_syll_sec", "Tasa silábica", "raw", RAW, "syll/s", "float", False, 6.0, 5),
            ("raw.smr_cv_interval", "CV del intervalo", "raw", RAW, "ratio", "float", False, 0.1, 6),
            ("raw.labial_mod_depth", "Prof. modulación labial", "raw", RAW, "ratio", "float", False, None, 7),
            ("raw.lingual_mod_depth", "Prof. modulación lingual", "raw", RAW, "ratio", "float", False, None, 8),
            ("raw.per_place.pa.mod_depth", "mod_depth /pa/", "raw", RAW, "ratio", "float", True, None, 9),
            ("raw.per_place.ka.mod_depth", "mod_depth /ka/", "raw", RAW, "ratio", "float", True, None, 10),
            ("raw.per_place.ta.mod_depth", "mod_depth /ta/", "raw", RAW, "ratio", "float", True, None, 11),
        ],
        comps=[
            ("domains.ddk_regular", [("raw.smr_rate_syll_sec", 0.6), ("raw.smr_cv_interval", -0.4)]),
            ("domains.labial_closure", [("raw.labial_mod_depth", 1.0)]),
            ("domains.lingual_closure", [("raw.lingual_mod_depth", 1.0)]),
        ],
    ),
    dict(
        key="reading_passage", ex_type="reading",
        ex_desc="Lectura de un texto pautado (inteligibilidad y fraseo).",
        setup_desc="Análisis de lectura: inteligibilidad, fraseo y grupos respiratorios.",
        slice_domains=["intelligibility"],
        slice_raw=["mean_phrase_sec", "max_phrase_sec", "n_breath_groups"],
        defs=[
            ("domains.intelligibility", "Inteligibilidad", "domains", DER, "score", "float", True, 80.0, 1),
            ("raw.mean_phrase_sec", "Duración media de frase", "raw", RAW, "s", "float", False, None, 2),
            ("raw.max_phrase_sec", "Duración máxima de frase", "raw", RAW, "s", "float", False, None, 3),
            ("raw.n_breath_groups", "Nº de grupos respiratorios", "raw", RAW, "count", "int", False, None, 4),
        ],
        comps=[],
    ),
]


# Normas clínicas compartidas (ilustrativas), con rango bueno y rango pobre.
# (metric_code, direction, sex, age_min, age_max, good_min, good_max, poor_min, poor_max, unit, source)
NORMS = [
    ("raw.jitter_local_pct", "lower_better", None, None, None, None, 1.04, 2.0, None, "%", "Referencia acústica (ilustrativa)"),
    ("raw.shimmer_local_pct", "lower_better", None, None, None, None, 3.8, 8.0, None, "%", "Referencia acústica (ilustrativa)"),
    ("raw.hnr_db", "higher_better", None, None, None, 20.0, None, None, 10.0, "dB", "Referencia acústica (ilustrativa)"),
    ("raw.phonation_duration_sec", "higher_better", "male", None, None, 20.0, None, None, 8.0, "s", "MPT adulto, varón (ilustrativa)"),
    ("raw.phonation_duration_sec", "higher_better", "female", None, None, 15.0, None, None, 6.0, "s", "MPT adulto, mujer (ilustrativa)"),
    ("raw.smr_rate_syll_sec", "higher_better", None, None, None, 6.0, None, None, 3.0, "syll/s", "Tasa DDK adulto (ilustrativa)"),
    ("raw.smr_cv_interval", "lower_better", None, None, None, None, 0.1, 0.3, None, "ratio", "Regularidad DDK (ilustrativa)"),
]


DEMO_PATIENTS = [
    ("00000001R", "María", "López Martín", datetime.date(1962, 2, 18), m.Sex.female),
    ("00000002W", "Antonio", "Sánchez Ruiz", datetime.date(1954, 9, 7), m.Sex.male),
    ("00000003A", "Carmen", "Navarro Gil", datetime.date(1971, 6, 23), m.Sex.female),
    ("00000004G", "Rafael", "Torres Vega", datetime.date(1949, 11, 3), m.Sex.male),
    ("00000005M", "Lucía", "Moreno Soler", datetime.date(1980, 1, 29), m.Sex.female),
    ("00000006Y", "Javier", "Iglesias León", datetime.date(1968, 12, 14), m.Sex.male),
    ("00000007F", "Elena", "Castillo Pardo", datetime.date(1959, 5, 9), m.Sex.female),
    ("00000008P", "Miguel", "Romero Vidal", datetime.date(1976, 8, 31), m.Sex.male),
    ("00000009D", "Isabel", "Herrera Campos", datetime.date(1947, 4, 20), m.Sex.female),
    ("00000010X", "Pablo", "Molina Serrano", datetime.date(1985, 10, 12), m.Sex.male),
]


def get_by_path(session: dict, path: str):
    cur = session
    for part in path.split("."):
        cur = cur.get(part) if isinstance(cur, dict) else None
        if cur is None:
            return None
    return cur


def build_slice(session: dict, dom_keys, raw_keys) -> dict:
    return {
        "date": session.get("date"),
        "domains": {k: session.get("domains", {}).get(k) for k in dom_keys},
        "raw": {k: session.get("raw", {}).get(k) for k in raw_keys},
        "note": session.get("note", ""),
    }


def build_all(sessions: list[dict]):
    """Construye todo el grafo de objetos ORM (sin BD). Devuelve (objetos, stats)."""
    objs, stats = [], {"recordings": 0, "metrics": 0, "nulls": 0, "norms": 0}

    # --- 1-2. Identidades, doctor y paciente -------------------------------
    doc_user = m.AppUser(role=m.UserRole.medical, external_subject="idp|doctor-default")
    doctor = m.Doctor(user=doc_user, colegiado_id="COL-0001",
                      doctor_type=m.DoctorType.medical_specialist,
                      first_name="Ana", last_name="García")
    pat_user = m.AppUser(role=m.UserRole.patient, external_subject="idp|patient-default")
    patient = m.Patient(user=pat_user, national_id="00000000T",
                        first_name="José", last_name="Demo",
                        birth_date=datetime.date(1958, 4, 12), sex=m.Sex.male)
    tech_user = m.AppUser(role=m.UserRole.technician, external_subject="idp|technical-default")
    admin_user = m.AppUser(role=m.UserRole.admin, external_subject="idp|admin-default")
    
    # Crear PseudonymMap para el paciente (requerido para MetricResult.pseudonym_id)
    # Generar explícitamente el pseudonym_id porque usa server_default en la BD
    pseudonym = m.PseudonymMap(patient=patient, pseudonym_id=uuid.uuid4())

    objs += [doc_user, doctor, pat_user, patient, tech_user, admin_user, pseudonym]

    for index, (national_id, first_name, last_name, birth_date, sex) in enumerate(DEMO_PATIENTS, start=1):
        demo_user = m.AppUser(role=m.UserRole.patient, external_subject=f"idp|patient-demo-{index:02d}")
        demo_patient = m.Patient(
            user=demo_user,
            national_id=national_id,
            first_name=first_name,
            last_name=last_name,
            birth_date=birth_date,
            sex=sex,
        )
        demo_pseudonym = m.PseudonymMap(patient=demo_patient, pseudonym_id=uuid.uuid4())
        objs += [demo_user, demo_patient, demo_pseudonym]

    # --- 3. Diagnóstico de disartria flácida -------------------------------
    diagnostic = m.Diagnostic(
        patient=patient, doctor=doctor,
        dolencia="Disartria flácida",
        description="Disartria flácida secundaria a lesión de motoneurona inferior.",
        symptoms="Voz débil y soplada, hipernasalidad, fatiga fonatoria, imprecisión articulatoria.",
        signature="Dra. Ana García (COL-0001)",
        content_hash=hashlib.sha256(
            "Disartria flácida|lesión motoneurona inferior".encode()).hexdigest(),
    )
    # --- 4. Programa de rehabilitación logopédico --------------------------
    program = m.RehabProgram(
        diagnostic=diagnostic, physiotherapist=doctor,
        name="Programa logopédico — disartria flácida",
        status=m.ProgramStatus.active, start_date=datetime.date(2026, 5, 30),
    )
    consent = m.PatientConsent(patient=patient, rehab_program=program, granted=True)
    objs += [diagnostic, program, consent]

    # --- 5-6. Ejercicios, setups, definiciones y composición ---------------
    path_map = {}     # key_ejercicio -> {path: MetricDefinition}
    setup_of = {}     # key_ejercicio -> (AnalysisSetup, spec)
    for spec in EXERCISES:
        rex = m.RehabExercise(type=spec["ex_type"], description=spec["ex_desc"])
        pex = m.ProgramExercise(rehab_program=program, rehab_exercise=rex, status="active")
        setup = m.AnalysisSetup(
            program_exercise=pex, description=spec["setup_desc"], type=spec["ex_type"],
            metric_api_endpoint="dysarthria_analysis_v1", ai_model="claude-opus-4-8",
            ai_prompt="Evalúa el progreso de las métricas frente a sus objetivos y resume en lenguaje clínico.",
            criteria="Comparar dominios y métricas crudas contra target_value.", version=1,
        )
        objs += [rex, pex, setup]
        path_map[spec["key"]] = {}
        setup_of[spec["key"]] = (setup, spec)
        for (path, label, section, vkind, unit, dtype, nullable, target, order) in spec["defs"]:
            md = m.MetricDefinition(
                analysis_setup=setup, path=path, label=label, section=section,
                value_kind=m.MetricValueKind(vkind), unit=unit, data_type=dtype,
                nullable=nullable, target_value=target, display_order=order,
            )
            path_map[spec["key"]][path] = md
            objs.append(md)
        for parent_path, children in spec["comps"]:
            parent = path_map[spec["key"]][parent_path]
            for child_path, weight in children:
                objs.append(m.MetricComposition(
                    parent=parent, child=path_map[spec["key"]][child_path], weight=weight))

    # --- Normas clínicas compartidas (catálogo reference) ------------------
    for (code, direction, sex, amin, amax, gmin, gmax, pmin, pmax, unit, source) in NORMS:
        objs.append(m.MetricNorm(
            metric_code=code, direction=m.NormDirection(direction),
            sex=(m.Sex(sex) if sex else None), age_min=amin, age_max=amax,
            good_min=gmin, good_max=gmax, poor_min=pmin, poor_max=pmax,
            unit=unit, source=source))
        stats["norms"] += 1

    # --- Carga de sesiones: grabación + resultado + métricas aplanadas -----
    for idx, session in enumerate(sessions, start=1):
        rec_date = datetime.date.fromisoformat(session["date"])
        for spec in EXERCISES:
            setup, _ = setup_of[spec["key"]]
            pex = setup.program_exercise
            uri = f"s3://ftm-recordings/{spec['key']}/sess{idx:02d}.wav"
            dur = get_by_path(session, "raw.phonation_duration_sec") or 30.0
            rec = m.ExerciseRecording(
                program_exercise=pex, recorded_by_user=pat_user,
                media_kind=m.MediaKind.audio, media_uri=uri,
                media_status=m.MediaStatus.available, recording_date=rec_date,
                duration_seconds=float(dur), sample_rate=16000,
                size_bytes=int(16000 * 2 * float(dur)),          # 16-bit mono PCM
                sha256=hashlib.sha256(uri.encode()).hexdigest(),  # ilustrativo
            )
            result = m.MetricResult(
                recording=rec, analysis_setup=setup, result_date=rec_date,
                pseudonym_id=pseudonym.pseudonym_id,  # Usar el pseudonym_id del paciente
                note=(session.get("note") or None),
                raw_json=build_slice(session, spec["slice_domains"], spec["slice_raw"]),
                function_name=setup.metric_api_endpoint, function_version="1.0",
                code_sha="0000000000000000000000000000000000000000",  # seed: commit ficticio
                status=m.ResultStatus.success,
            )
            objs += [rec, result]
            stats["recordings"] += 1
            for path, md in path_map[spec["key"]].items():
                v = get_by_path(session, path)
                is_null = v is None
                objs.append(m.RecordingMetric(
                    result=result, definition=md, metric_path=path,
                    value_num=(None if is_null else float(v)), is_null=is_null))
                stats["metrics"] += 1
                stats["nulls"] += int(is_null)

    return objs, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="patient_sessions.json")
    ap.add_argument("--db", default=None, help="URL SQLAlchemy; si se omite, modo --dry-run")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(args.json, encoding="utf-8") as fh:
        sessions = json.load(fh)

    objs, stats = build_all(sessions)
    print(f"Objetos construidos: {len(objs)} | sesiones: {len(sessions)} | "
          f"grabaciones: {stats['recordings']} | métricas: {stats['metrics']} "
          f"(nulas: {stats['nulls']}) | normas: {stats['norms']}")

    if args.dry_run or not args.db:
        print("Modo dry-run: no se escribe en la base de datos.")
        return

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    engine = create_engine(args.db)
    m.Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add_all(objs)
        s.commit()
    print("Seed insertado correctamente.")


if __name__ == "__main__":
    main()
