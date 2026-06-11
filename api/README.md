# FTM API (backend)

Monolito modular (FastAPI) para el Medical Rehab Follow-up Tool. Una sola imagen
sirve para **api** (uvicorn) y **worker** (`python -m app.worker`).

## Estructura
```
api/
├── Dockerfile  requirements.txt  alembic.ini
├── docker-compose.dev.yml  dev/init.sql        # postgres local para dev
├── migrations/                                  # Alembic (0001 = schemas + RLS + seed)
└── app/
    ├── config.py        # settings; blinda AUTH_MODE=dev en prod
    ├── context.py       # contextvars con sub/rol del token
    ├── auth.py          # Keycloak JWKS  +  atajo AUTH_MODE=dev (cabecera X-Dev-Role)
    ├── db.py            # engine, Base, get_db (inyecta RLS por transaccion)
    ├── storage.py       # LocalStorage (dev) / GcsStorage (prod, signed URLs)
    ├── jobs.py          # cola en Postgres (SKIP LOCKED)
    ├── worker.py        # ejecuta funcion registrada -> metricas (pseudonimo) -> IA
    ├── analysis/
    │   ├── registry.py            # registro AGNOSTICO de funciones
    │   └── functions/voice.py     # sustained_phonation_v1 / breathing_cadence_v1 / ddk_rate_v1
    ├── ai/service.py    # frontera de anonimizacion + llamada LLM (solo metricas)
    ├── clinical/  catalog/  recording/  metrics/  reporting/  iam/   # models + routers
    └── main.py          # FastAPI(root_path="/api")
```

## Desarrollo local (sin Keycloak)
```bash
docker compose -f docker-compose.dev.yml up -d        # postgres local
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# Migraciones: se ejecutan como DUENO (postgres), no como ftm_app
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ftm alembic upgrade head

# App (runtime como ftm_app; AUTH_MODE=dev evita levantar Keycloak)
cp .env.example .env       # AUTH_MODE=dev, DATABASE_URL con ftm_app
uvicorn app.main:app --reload --port 8000
python -m app.worker       # en otra terminal

# Probar (el atajo de dev elige rol con la cabecera X-Dev-Role):
curl -H "X-Dev-Role: medical" -X POST localhost:8000/patients \
     -H "content-type: application/json" -d '{"nombre":"Ana","apellidos":"Lopez"}'
```

## Construir y subir la imagen (prod)
```bash
gcloud auth configure-docker europe-west1-docker.pkg.dev
docker build -t europe-west1-docker.pkg.dev/TU_PROJECT/ftm/ftm-api:latest .
docker push  europe-west1-docker.pkg.dev/TU_PROJECT/ftm/ftm-api:latest
```

## Notas de diseño
- **RLS por claims**: `get_db` fija `app.user`/`app.role` (LOCAL a la transaccion) antes de
  cualquier query. Las politicas viven en la migracion 0001. Las migraciones corren como
  dueño; la app como `ftm_app` (no dueño) => la RLS le aplica.
- **Registro agnostico**: el tecnico añade funciones con `@register_analysis("nombre")` en
  `app/analysis/functions/`. El worker resuelve por nombre y persiste el dict que devuelvan.
- **Anonimizacion**: al LLM solo le llega `{pseudonimo, ejercicio, metricas, historico}`.
  Nunca audio ni identidad (FR-04).
- **AUTH_MODE=dev**: salta JWKS y usa `X-Dev-Role`. `get_settings()` aborta el arranque si se
  detecta en prod.

## Pendiente (MVP)
- Cifrado a nivel de columna de `national_id`.
- Extender RLS al resto de tablas clinicas (patron de `patient`).
- Endpoint que dispara el insight IA y compone el informe (UC-06/07).
- Tests de aislamiento por rol.
