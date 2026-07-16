# FTM API — guía del backend

Backend FastAPI del *Rehab Follow-up Check-up Tool*. Este documento cubre lo
**específico del backend**: modos de autenticación, cifrado de campos sensibles,
uso de tokens y tests.

> Para levantar el entorno local completo (PostgreSQL, Keycloak, MinIO y
> migraciones) usa la fuente de verdad: [`../RUNBOOK_local.md`](../RUNBOOK_local.md).
> La base de datos de la aplicación se aprovisiona desde
> [`../bbdd_dev_setup/`](../bbdd_dev_setup/) — DB `appdb`, owner `appuser` para
> migraciones, y el rol de runtime `ftm_app`. **No uses otra base ni otro rol**:
> la API debe conectar como `ftm_app` para que se aplique la RLS.

## Modos de autenticación

La API arranca en dos modos, controlados por `AUTH_MODE`:

| Modo | Uso | Autenticación |
|---|---|---|
| `dev` | Desarrollo rápido sin Keycloak | Cabecera `X-Dev-Role` |
| `keycloak` | Integrado con el frontend (PKCE S256) | Bearer JWT emitido por Keycloak |

> Guardarraíl: `AUTH_MODE=dev` está **bloqueado si `APP_ENV=prod`**. La API no
> arranca en producción con atajos de autenticación.

En modo `keycloak`, la API **no ejecuta PKCE**: el flujo Authorization Code + PKCE
S256 ocurre en el navegador con el cliente público `ftm-web`. La API solo recibe
`Authorization: Bearer <token>` y valida el JWT contra el JWKS de Keycloak.

## Configuración (`api/.env`)

Copia la plantilla y ajusta el modo:

```bash
cd api
cp .env.example .env
```

Variables relevantes del backend (la conexión y las URLs de Keycloak deben
coincidir con lo que levanta `bbdd_dev_setup/`):

| Variable | Valor local | Notas |
|---|---|---|
| `APP_ENV` | `dev` | En `prod` se activan los guardarraíles. |
| `AUTH_MODE` | `dev` o `keycloak` | Ver tabla de arriba. |
| `DATABASE_URL` | `postgresql://ftm_app:$FTM_APP_DB_PASSWORD@localhost:5432/appdb` | Rol de runtime `ftm_app`, **no** el owner: así aplica la RLS. |
| `KEYCLOAK_ISSUER` | `http://localhost:8085/realms/ftm` | Solo en modo `keycloak`. |
| `KEYCLOAK_JWKS_URL` | `http://localhost:8085/realms/ftm/protocol/openid-connect/certs` | Solo en modo `keycloak`. |
| `NATIONAL_ID_ENCRYPTION_KEY` | *(clave Fernet)* | Ver sección de cifrado. Obligatoria en `prod`. |

> La contraseña de `ftm_app` es `FTM_APP_DB_PASSWORD`, definida en el `.env` de
> `bbdd_dev_setup/`. No la copies en claro: referénciala desde el entorno. Si ves
> `password authentication failed for user "ftm_app"`, es que las migraciones de
> `bbdd_dev_setup` no llegaron a `head` con esa variable definida (ahí se crea el
> rol de runtime).

Arranca la API:

```bash
cd api
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Probar la API

### Modo dev (sin Keycloak)

El rol se pasa por cabecera:

```bash
curl http://localhost:8000/health

curl -H "X-Dev-Role: medical" \
  -H "content-type: application/json" \
  -X POST http://localhost:8000/patients \
  -d '{"nombre":"Ana","apellidos":"Lopez"}'
```

### Modo Keycloak (con token)

Los endpoints protegidos requieren un JWT válido del realm `ftm`:

```bash
curl http://localhost:8000/health
# Esperado: {"status":"ok","env":"dev","auth":"keycloak"}

TOKEN="<access_token_emitido_por_keycloak>"
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/patients
```

Cómo levantar Keycloak y qué usuarios seed existen: ver
[`../RUNBOOK_local.md`](../RUNBOOK_local.md).

## Worker de análisis

El worker usa el **mismo `.env`** que la API:

```bash
cd api
. .venv/bin/activate
python -m app.worker
```

## Almacenamiento de grabaciones

Por defecto, desarrollo usa `STORAGE_BACKEND=local` y guarda los ficheros bajo
`WAV_LOCAL_DIR`. Para usar el MinIO privado del repo, levántalo desde
`bbdd_dev_setup/ftm-recording-database/` (ver `RUNBOOK_local.md`) y configura:

```env
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY_ID=<MINIO_APP_USER>
S3_SECRET_ACCESS_KEY=<MINIO_APP_PASSWORD>
S3_BUCKET=ftm-recordings
S3_FORCE_PATH_STYLE=true
```

La API genera URLs PUT firmadas de 15 minutos. El bucket permanece privado y
PostgreSQL almacena únicamente la clave y los metadatos del medio.

## Cifrado de columnas sensibles (`national_id`)

`national_id` se almacena cifrado con **Fernet** (cifrado simétrico a nivel de
aplicación). La clave nunca toca Postgres — la BD almacena bytes opacos.

Generar la clave:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Colocarla en `api/.env`:

```env
NATIONAL_ID_ENCRYPTION_KEY=<clave generada>
```

> La **misma** clave debe estar en `bbdd_dev_setup/.env`. Si difieren, la API no
> podrá descifrar los datos insertados por el seed.

En producción (`APP_ENV=prod`) la variable es **obligatoria**: el arranque falla si
no está definida. Para producción real, sustituye `get_fernet()` en
`app/crypto.py` por una llamada a un KMS (AWS KMS, Vault, etc.).

## Tests

```bash
cd api
. .venv/bin/activate
python -m pytest tests -q
```

Los tests de integración con PostgreSQL requieren una BD migrada y se activan con
`RUN_INTEGRATION=1`:

```bash
RUN_INTEGRATION=1 \
DATABASE_URL="postgresql://<user>:<password>@localhost:5432/appdb" \
python -m pytest tests/integration -q
```

## Notas de seguridad

- No uses `AUTH_MODE=dev` en producción (el guardarraíl lo impide).
- No conectes la app como owner de la base de datos: el runtime usa `ftm_app`.
- Las migraciones corren como owner; el runtime, como rol de aplicación.
- Nunca envíes identidad, PII ni audio bruto al LLM.
