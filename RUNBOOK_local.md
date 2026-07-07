# Levantar FTM en local

> 🇬🇧 English: this runbook is Spanish-only for now.

Guía para correr **todo el sistema FTM en tu máquina**: las bases de datos, Keycloak,
MinIO, la API (bff + worker) y el frontend. Pensado para desarrollar y probar el flujo
completo (login → grabar → subir → analizar → métricas) sin tocar Hetzner.

> Para el detalle de solo Keycloak + las dos Postgres, ver
> [`bbdd_dev_setup/README_local_env.md`](bbdd_dev_setup/README_local_env.md).
> Para el despliegue en producción, ver [`terraform/README_ES.md`](terraform/README_ES.md).

## Qué levanta cada pieza

| Componente | Dónde | Puerto | Cómo |
|------------|-------|--------|------|
| Postgres app + Keycloak + Keycloak DB | `bbdd_dev_setup/` | 5432, 8085 | `./up.sh` (también corre las migraciones) |
| MinIO (grabaciones) + init de bucket | `bbdd_dev_setup/ftm-recording-database/` | 9000, 9001 | `./up.sh` |
| API (bff) | `api/` | 8000 | `uvicorn` |
| Worker (análisis de audio) | `api/` | — | `python -m app.worker` |
| Frontend (Vite) | `web/` | 5173 | `npm run dev` |

## Requisitos

- Docker Engine + `docker compose` v2, demonio arrancado.
- **Coloca el repo en el filesystem de Linux** (p. ej. `~/ftm/`), NO en `/mnt/c` (WSL).
- Python 3.12 + `ffmpeg` (el worker decodifica audio `.webm`): `sudo apt install ffmpeg`.
- Node 20+ para el frontend.
- Puertos libres: 5432, 8000, 8085, 9000, 9001, 5173.

## Ruta rápida

Abre **4 terminales**: una para levantar las tres bases (pasos 1-3, quedan en background) y una para cada uno de bff, worker y frontend (primer plano).

```bash
# 1. Bases de datos de la app (+ migraciones alembic)  ── background
cd bbdd_dev_setup
cp .env.example .env        # rellena los valores la primera vez
chmod +x up.sh && ./up.sh

# 2. Keycloak + su Postgres (realm ftm)  ── background
cd keycloak/ftm-keycloak
chmod +x up.sh && ./up.sh
cd ../..                    # vuelve a bbdd_dev_setup

# 3. MinIO + bucket ftm-recordings  ── background
cd ftm-recording-database
cp .env.example .env        # la primera vez
chmod +x up.sh && ./up.sh
```

```bash
# 4. API (bff)  ── terminal propia
cd api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# variables mínimas (ver tabla abajo); o define un api/.env
export DATABASE_URL="postgresql://ftm_app:<FTM_APP_DB_PASSWORD>@localhost:5432/appdb"  # BD: appdb
export STORAGE_BACKEND=s3 S3_ENDPOINT_URL=http://localhost:9000 \
       S3_ACCESS_KEY_ID=ftm-recordings-svc S3_SECRET_ACCESS_KEY=<svc-pw> \
       S3_BUCKET=ftm-recordings S3_FORCE_PATH_STYLE=true
uvicorn app.main:app --reload --port 8000
```

```bash
# 5. Worker  ── otra terminal (mismo venv y mismas vars que el bff)
cd api && source .venv/bin/activate
python -m app.worker
```

```bash
# 6. Frontend  ── otra terminal
cd web
npm install
npm run dev        # http://localhost:5173, proxya /api -> localhost:8000
```

Abre **http://localhost:5173** e inicia sesión con un usuario semilla (`paciente1` / `paciente1`).

## Variables mínimas de la API en local

La API lee su config de variables de entorno (pydantic Settings, ver `api/app/config.py`).
En local puedes dejar `APP_ENV=dev` para saltarte los guardas de producción.

| Variable | Valor local típico | Para qué |
|----------|--------------------|----------|
| `APP_ENV` | `dev` | en `dev` no exige keycloak ni la clave de cifrado |
| `AUTH_MODE` | `dev` o `keycloak` | `dev` = atajo sin login real |
| `DATABASE_URL` | `postgresql://ftm_app:...@localhost:5432/appdb` | **usar `ftm_app`** (no el owner) para que aplique RLS |
| `KEYCLOAK_ISSUER` | `http://localhost:8085/realms/ftm` | solo si `AUTH_MODE=keycloak` |
| `KEYCLOAK_JWKS_URL` | `http://localhost:8085/realms/ftm/protocol/openid-connect/certs` | idem |
| `STORAGE_BACKEND` | `s3` | usar MinIO (o `local` para disco) |
| `S3_ENDPOINT_URL` | `http://localhost:9000` | MinIO local |
| `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | `ftm-recordings-svc` / su pw | usuario acotado al bucket |
| `S3_BUCKET` | `ftm-recordings` | bucket de grabaciones |
| `S3_FORCE_PATH_STYLE` | `true` | MinIO usa path-style |

## Credenciales semilla

| Qué | Valor |
|-----|-------|
| BD app | `appuser` / `<pass>` @ `localhost:5432/appdb` (owner/migrator) |
| Rol runtime API | `ftm_app` / `<FTM_APP_DB_PASSWORD>` (no owner → RLS aplica) |
| Consola Keycloak | `admin` / `admin` en http://localhost:8085/admin |
| Usuarios app | `medico1`, `paciente1`, `paciente2`, `tecnico1`, `admin1` (pass = usuario) |
| Consola MinIO | `minioadmin` / `minioadmin123` en http://localhost:9001 |

## Trampas frecuentes

| Síntoma | Causa | Solución |
|---------|-------|----------|
| `permission denied for table patient` | faltan grants de RLS | `alembic upgrade head` (re-aplica `0004_runtime_grants`) |
| API ve todo, RLS no filtra | te conectas como owner (`appuser`) | usa `ftm_app` en `DATABASE_URL` |
| `analyze` falla, `NoBackendError` | falta `ffmpeg` para `.webm` | `sudo apt install ffmpeg` |
| Subida a MinIO 403 | falta el bucket o el usuario | el `up.sh` de `ftm-recording-database` los crea; vuelve a ejecutarlo |
| Puerto 5432 ocupado | viejo `postgres-dev` corriendo | `docker rm -f postgres-dev` |
| El realm no se re-importa | solo se importa si `ftm` no existe | `docker compose down -v` y `./up.sh` (borra datos) |

## Parar / limpiar

```bash
# parar conservando datos
cd bbdd_dev_setup && docker compose stop
cd ftm-recording-database && docker compose stop

# borrar TODO (incluidos volúmenes/datos)
docker compose down -v      # en cada carpeta
```

## Verificación

- [ ] http://localhost:8085/realms/ftm responde (Keycloak + realm).
- [ ] http://localhost:9001 abre la consola de MinIO; existe el bucket `ftm-recordings`.
- [ ] http://localhost:8000/docs abre la API (FastAPI).
- [ ] http://localhost:5173 carga el frontend.
- [ ] Login `paciente1` → ve solo sus datos → grabar → subir → analizar → métricas.
