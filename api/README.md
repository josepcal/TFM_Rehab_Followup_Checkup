# FTM API — ejecución local

Backend FastAPI del Medical Rehab Follow-up Tool. Se puede arrancar en dos
modos de autenticación:

| Modo | Uso | Autenticación |
|---|---|---|
| `dev` | Desarrollo rápido sin Keycloak | Cabecera `X-Dev-Role` |
| `keycloak` / PKCE | Desarrollo integrado con el frontend y Keycloak | Bearer JWT emitido por Keycloak |

> Guardarraíl: `AUTH_MODE=dev` está bloqueado si `APP_ENV=prod`.

## Requisitos

- Python 3.12.
- Docker con `docker compose`.
- PostgreSQL de aplicación migrado con Alembic.

> Importante: el repo contiene dos formas locales de levantar la BD de la app.
> No mezcles credenciales entre ellas:
>
> | Stack | Servicio/puerto | Credenciales |
> |---|---|---|
> | `api/docker-compose.dev.yml` | `postgres-app` en `localhost:5432` | DB `ftm`, usuario `ftm_app`, password `ftm` |
> | `bbdd_dev_setup/up.sh` | `postgres-app` en `localhost:5432` | Owner/migraciones: `appuser`; runtime API: `ftm_app` / `FTM_APP_DB_PASSWORD`; DB `appdb` |
>
> Si ves `password authentication failed for user "ftm_app"`, comprueba que
> has ejecutado las migraciones de `bbdd_dev_setup` hasta `head` con
> `FTM_APP_DB_PASSWORD` definido: ahí se crea el login runtime `ftm_app`.

## Modo dev, sin Keycloak

Usa este modo para trabajar solo con la API o para pruebas rápidas.

```bash
cd api

# 1) Levantar PostgreSQL de la app.
docker compose -f docker-compose.dev.yml up -d

# 2) Crear entorno Python e instalar dependencias.
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

# 3) Aplicar migraciones como dueño de la BD.
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ftm \
  alembic upgrade head

# 4) Configurar runtime de la app.
cp .env.example .env
# Comprueba que .env mantiene:
# APP_ENV=dev
# AUTH_MODE=dev
# DATABASE_URL=postgresql://ftm_app:thisIsMyFTMAppDBPassword123@localhost:5432/appdb

# 5) Arrancar API.
uvicorn app.main:app --reload --port 8000
```

Comprobación:

```bash
curl http://localhost:8000/health

curl -H "X-Dev-Role: medical" \
  -H "content-type: application/json" \
  -X POST http://localhost:8000/patients \
  -d '{"nombre":"Ana","apellidos":"Lopez"}'
```

## Modo Keycloak / PKCE

Usa este modo cuando el frontend obtenga tokens con Authorization Code + PKCE
S256 desde el cliente público `ftm-web`. La API no ejecuta PKCE: solo valida el
Bearer JWT contra el JWKS de Keycloak.

```bash
# 1) Levantar Keycloak local en otra terminal, desde la raíz del repo.
cd bbdd_dev_setup/keycloak/ftm-keycloak
chmod +x up.sh
./up.sh
```

El stack local expone Keycloak en `http://localhost:8085` y crea:

| Elemento | Valor |
|---|---|
| Realm | `ftm` |
| Cliente SPA | `ftm-web`, público, PKCE S256 |
| Cliente API | `ftm-api`, bearer-only |
| Usuarios seed | `medico1`, `paciente1`, `paciente2`, `tecnico1`, `admin1` |
| Contraseña seed | Igual que el usuario |

Arranca la API validando tokens de ese realm:

```bash
# 2) Volver a la raíz del repo y entrar en api.
cd api
. .venv/bin/activate

cat > .env <<'EOF'
APP_ENV=dev
AUTH_MODE=keycloak
DATABASE_URL=postgresql://ftm_app:thisIsMyFTMAppDBPassword123@localhost:5432/appdb
KEYCLOAK_ISSUER=http://localhost:8085/realms/ftm
KEYCLOAK_JWKS_URL=http://localhost:8085/realms/ftm/protocol/openid-connect/certs
WAV_BUCKET=
WAV_LOCAL_DIR=/tmp/ftm-recordings
LLM_API_KEY=
LLM_MODEL=claude-3-5-sonnet-latest
EOF

uvicorn app.main:app --reload --port 8000
```

Comprobación básica:

```bash
curl http://localhost:8000/health
# Esperado: {"status":"ok","env":"dev","auth":"keycloak"}
```

Para llamar endpoints protegidos en este modo necesitas un token válido de
Keycloak:

```bash
TOKEN="<access_token_emitido_por_keycloak>"

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/patients
```

## Worker local

El worker usa la misma configuración `.env` que la API.

```bash
cd api
. .venv/bin/activate
python -m app.worker
```

## Almacenamiento de grabaciones

Por defecto, desarrollo usa `STORAGE_BACKEND=local` y guarda los ficheros bajo
`WAV_LOCAL_DIR`. Para usar el MinIO privado incluido en el repositorio:

```bash
cd bbdd_dev_setup/ftm-recording-database
./up.sh
```

Configura la API sin incluir estas credenciales en git:

```env
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=<MINIO_ROOT_PASSWORD>
S3_BUCKET=ftm-recordings
S3_REGION=eu-local-1
S3_FORCE_PATH_STYLE=true
```

La API genera URLs PUT firmadas de 15 minutos. El bucket permanece privado y
PostgreSQL almacena únicamente la clave y los metadatos del medio.

## Tests

```bash
cd api
. .venv/bin/activate
python -m pytest tests -q
```

Los tests de integración con PostgreSQL requieren una BD migrada:

```bash
RUN_INTEGRATION=1 \
DATABASE_URL="postgresql://<user>:<password>@localhost:5432/<db>" \
python -m pytest tests/integration -q
```

## Notas de seguridad

- No uses `AUTH_MODE=dev` en producción.
- No conectes la app como dueño de la base de datos.
- Las migraciones corren como dueño; el runtime debe usar el rol de aplicación.
- Nunca envíes identidad, PII ni audio bruto al LLM.

## Cifrado de columnas sensibles (national_id)

`national_id` se almacena cifrado con Fernet (cifrado simétrico a nivel de aplicación).
La clave nunca toca Postgres — la BD almacena bytes opacos.

### Generar la clave

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Dónde colocarla

En `api/.env`:

```env
NATIONAL_ID_ENCRYPTION_KEY=<clave generada>
```

> La misma clave debe estar en `bbdd_dev_setup/.env`. Si difieren, la API no podrá
> descifrar los datos insertados por el seed.

En producción (`APP_ENV=prod`) la variable es **obligatoria** — el arranque falla
si no está definida. Para producción real, reemplazá `get_fernet()` en
`app/crypto.py` con una llamada a tu KMS (AWS KMS, Vault, etc.).
