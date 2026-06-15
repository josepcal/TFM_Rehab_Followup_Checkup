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
> | `bbdd_dev_setup/up.sh` | `postgres-app` en `localhost:5432` | Las de `bbdd_dev_setup/.env`, por defecto DB `appdb`, usuario `appuser`, password `thisIsMyAppDBPassword123` |
>
> Si ves `password authentication failed for user "ftm_app"`, probablemente
> tienes levantado el stack de `bbdd_dev_setup` pero tu `api/.env` apunta a
> `ftm_app:ftm@localhost:5432/ftm`.

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
# DATABASE_URL=postgresql://ftm_app:ftm@localhost:5432/ftm

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
| Usuarios seed | `medico1`, `paciente1`, `tecnico1`, `admin1` |
| Contraseña seed | Igual que el usuario |

Arranca la API validando tokens de ese realm:

```bash
# 2) Volver a la raíz del repo y entrar en api.
cd api
. .venv/bin/activate

cat > .env <<'EOF'
APP_ENV=dev
AUTH_MODE=keycloak
DATABASE_URL=postgresql://ftm_app:ftm@localhost:5432/ftm
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
