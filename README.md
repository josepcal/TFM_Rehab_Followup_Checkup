# FTM Rehab Follow-up Check-up Tool

**FTM** es una plataforma web para el seguimiento de programas de rehabilitación médica. Permite pasar de una valoración diagnóstica a un programa de ejercicios, registrar grabaciones de seguimiento, extraer métricas de forma asíncrona y consultar informes clínicos, manteniendo separación de roles, trazabilidad y controles de privacidad sobre datos sanitarios.

> Este README resume el proyecto y enlaza la documentación completa. Para ejecutar todo el entorno local paso a paso, usa [`RUNBOOK_local.md`](RUNBOOK_local.md).

## Índice

1. [Descripción general del proyecto](#descripción-general-del-proyecto)
2. [Stack tecnológico utilizado](#stack-tecnológico-utilizado)
3. [Instalación y ejecución](#instalación-y-ejecución)
4. [Despliegue en cloud](#despliegue-en-cloud)
5. [Estructura del proyecto](#estructura-del-proyecto)
6. [Funcionalidades principales](#funcionalidades-principales)
7. [Usuarios y contraseñas de prueba](#usuarios-y-contraseñas-de-prueba)
8. [Documentación adicional](#documentación-adicional)
9. [URL de la aplicación](#url-de-la-aplicacion)
10. [Vídeo exposición y demo de aplicación](#video-exposicion-y-demo-de-aplicacion)

## Descripción general del proyecto

FTM (*Follow-up Check-up Tool*) es una herramienta de configuracion, registro y seguimiento de programas de rehabilitacion, y cubre el siguiente flujo clínico:

1. Un profesional sanitario consulta pacientes.
2. Crea diagnóstico del paciente y, a partir de él, un programa de rehabilitación asociado.
3. El programa se compone de ejercicios y configuraciones de análisis ya preconfigurados en la aplicacion.
4. El paciente acepta el consentimiento requerido y sube grabaciones de ejercicios.
5. Un worker procesa las grabaciones, extrae métricas y recomendaciones, y persiste el resultado a peticion del paciente.
6. Los profesionales consultan las grabaciones, sus métricas y recomendaciones, y elaboran informes y controles de seguimiento.
7. La interacción con IA está contemplada en el diseño para generar insights pseudonimizados, pero no está implementada todavía en la versión actual.
8. El sistema registra eventos relevantes para auditoría.

El proyecto trata datos sanitarios y grabaciones de voz, por lo que incorpora guardarraíles de seguridad y privacidad:

- Autenticación delegada en Keycloak mediante OIDC/OAuth2 y PKCE.
- Separación de roles: paciente, médico, técnico y administrador.
- PostgreSQL con esquemas funcionales y Row-Level Security (RLS).
- Diseño de pseudonimización antes de cualquier interacción futura con IA.
- Almacenamiento privado de grabaciones fuera de la base de datos.
- Auditoría de operaciones mutantes y decisiones clínicas trazables.

## Stack tecnológico utilizado

| Capa | Tecnología | Uso en el proyecto |
|---|---|---|
| Frontend | React 18, TypeScript, Vite | SPA para portal clínico, portal paciente y panel de administración. |
| Estado/datos frontend | TanStack Query | Fetching, caché y sincronización con la API. |
| Gráficas | Recharts | Visualización de métricas y resultados. |
| Autenticación frontend | `keycloak-js` | Login PKCE contra Keycloak en modo integrado. |
| Backend | Python 3.12, FastAPI | API BFF y endpoints clínicos. |
| Validación/configuración | Pydantic v2, `pydantic-settings` | Schemas de entrada/salida y variables de entorno. |
| ORM y migraciones | SQLAlchemy 2.0, Alembic | Modelo de datos, migraciones SQL-first y acceso a PostgreSQL. |
| Base de datos | PostgreSQL | Datos clínicos, identidad de aplicación, métricas, jobs y auditoría. |
| Seguridad | Keycloak, JWT, RLS, Fernet | Autenticación, autorización, aislamiento por fila y cifrado de campos sensibles. |
| Almacenamiento | MinIO local / S3-GCS compatible | Grabaciones de ejercicios en object storage privado. |
| Procesamiento asíncrono | Worker Python + cola en PostgreSQL | Extracción de métricas de audio y persistencia de resultados. |
| Audio/DSP | `librosa`, `soundfile`, `scipy`, `praat-parselmouth`, `ffmpeg` | Decodificación y análisis de grabaciones de voz. |
| Infraestructura | Docker Compose, nginx, Terraform | Entorno local y despliegue documentado. |
| Testing | Pytest, Vitest, Testing Library | Tests backend, frontend e integración. |

## Instalación y ejecución

La guía operativa detallada está en [`RUNBOOK_local.md`](RUNBOOK_local.md). Esta sección recoge la ruta rápida y los puntos de verificación.

### Requisitos

- Linux o WSL usando el filesystem de Linux, no `/mnt/c`.
- Docker Engine y `docker compose` v2.
- Python 3.12.
- Node.js 20+ y npm.
- `ffmpeg` instalado para procesar grabaciones `.webm`.
- Puertos libres: `5432`, `8000`, `8085`, `9000`, `9001`, `5173`.

### Ruta rápida local

Abre terminales separadas para infraestructura, API, worker y frontend.

```bash
# 1. Base de datos de aplicación + migraciones
cd bbdd_dev_setup
cp .env.example .env
chmod +x up.sh && ./up.sh

# 2. Keycloak + base de datos de Keycloak
cd keycloak/ftm-keycloak
chmod +x up.sh && ./up.sh
cd ../..

# 3. MinIO + bucket de grabaciones
cd ftm-recording-database
cp .env.example .env
chmod +x up.sh && ./up.sh
```

```bash
# 4. API FastAPI
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

```bash
# 5. Worker de análisis
cd api
source .venv/bin/activate
python -m app.worker
```

```bash
# 6. Frontend Vite
cd web
npm install
VITE_FTM_AUTH_MODE=pkce npm run dev
```

Después abre:

- Frontend: <http://localhost:5173>
- API Swagger/OpenAPI en desarrollo: <http://localhost:8000/docs>
- Keycloak: <http://localhost:8085>
- Consola MinIO: <http://localhost:9001>

### Variables locales importantes

La API lee configuración desde `api/.env`. En local, los valores habituales son:

| Variable | Valor típico | Descripción |
|---|---|---|
| `APP_ENV` | `dev` | Perfil de desarrollo. |
| `AUTH_MODE` | `keycloak` o `dev` | `keycloak` usa JWT real; `dev` permite atajos locales. |
| `DATABASE_URL` | `postgresql://ftm_app:<password>@localhost:5432/appdb` | Conexión runtime de la API. Debe usar `ftm_app`, no el owner, para respetar RLS. |
| `KEYCLOAK_ISSUER` | `http://localhost:8085/realms/ftm` | Emisor OIDC local. |
| `KEYCLOAK_JWKS_URL` | `http://localhost:8085/realms/ftm/protocol/openid-connect/certs` | Claves públicas para validar JWT. |
| `STORAGE_BACKEND` | `s3` | Usa MinIO local como backend compatible S3. |
| `S3_ENDPOINT_URL` | `http://localhost:9000` | Endpoint de MinIO. |
| `S3_BUCKET` | `ftm-recordings` | Bucket privado de grabaciones. |
| `S3_FORCE_PATH_STYLE` | `true` | Necesario para MinIO local. |

Consulta [`RUNBOOK_local.md`](RUNBOOK_local.md) para la tabla completa de variables, credenciales locales, problemas frecuentes y limpieza del entorno.

### Comandos de verificación

```bash
# Backend
cd api
source .venv/bin/activate
python -m pytest tests -q

# Frontend
cd web
npm run lint
npm test
npm run build
```

También puedes comprobar manualmente:

- `http://localhost:8085/realms/ftm` responde.
- `http://localhost:9001` muestra MinIO y existe el bucket `ftm-recordings`.
- `http://localhost:8000/health` devuelve `status: ok`.
- `http://localhost:5173` carga la aplicación.
- Login con `paciente1` permite ver su portal y probar el flujo de grabación/análisis.

## Despliegue en cloud

Además del entorno local, el despliegue final del proyecto se ha realizado en **Hetzner Cloud**. La topología está pensada para ejecutar la aplicación en contenedores detrás de nginx, manteniendo separados los servicios de aplicación, identidad, base de datos y almacenamiento de grabaciones.

Componentes principales del despliegue cloud:

| Componente | Papel en producción |
|---|---|
| Hetzner Cloud | Infraestructura final usada para alojar el sistema. |
| nginx | Reverse proxy de entrada y enrutado hacia frontend/API. |
| Contenedores de aplicación | Ejecución de frontend, API FastAPI y worker. |
| PostgreSQL app | Persistencia de datos clínicos, métricas, auditoría y jobs. |
| PostgreSQL Keycloak | Base de datos separada para identidad. |
| Keycloak | Proveedor OIDC/OAuth2 para login y emisión de JWT. |
| Object storage compatible S3/MinIO | Almacenamiento privado de grabaciones, separado de PostgreSQL. |
| Terraform / scripts de despliegue | Automatización y documentación de infraestructura. |

Referencias de despliegue:

- [`terraform/README_ES.md`](terraform/README_ES.md): guía de infraestructura en español.
- [`deploy/RUNBOOK.md`](deploy/RUNBOOK.md): runbook de despliegue.
- [`doc/memoria_proyecto/Memoria_Proyecto.md`](doc/memoria_proyecto/Memoria_Proyecto.md): explicación narrativa del despliegue y restricciones GDPR.

> Nota: las credenciales, dominios y secretos de producción no deben documentarse en el repositorio. El README solo describe la arquitectura y remite a los runbooks.

## Estructura del proyecto

```text
.
├── api/                         # Backend FastAPI, worker, módulos clínicos y tests Python.
│   ├── app/
│   │   ├── ai/                  # Diseño/servicios preparados para insights IA pseudonimizados.
│   │   ├── analysis/            # Registro y funciones de análisis de audio.
│   │   ├── catalog/             # Catálogos clínicos.
│   │   ├── clinical/            # Diagnósticos, programas, consentimientos y reglas clínicas.
│   │   ├── followup/            # Check-ups de seguimiento.
│   │   ├── iam/                 # Identidad de aplicación y auditoría.
│   │   ├── metrics/             # Resultados y métricas de grabaciones.
│   │   ├── norms/               # Normas y valores de referencia.
│   │   ├── recording/           # Registro, subida, análisis y borrado de grabaciones.
│   │   ├── reporting/           # Informes de ejercicio.
│   │   └── worker.py            # Worker asíncrono de análisis.
│   └── tests/                   # Tests unitarios e integración backend.
├── web/                         # Frontend React/Vite/TypeScript.
│   └── src/
│       ├── api/                 # Clientes HTTP tipados.
│       ├── auth/                # Cliente de autenticación dev/Keycloak.
│       └── features/            # Pantallas de diagnóstico, paciente y administración.
├── bbdd_dev_setup/              # Entorno local de PostgreSQL, Keycloak, MinIO y Alembic.
│   ├── alembic/                 # Migraciones SQL-first y seed.
│   ├── ftm-appdb/               # Base de datos de aplicación.
│   ├── ftm-recording-database/  # MinIO y bucket de grabaciones.
│   └── keycloak/                # Realm local y usuarios semilla.
├── deploy/                      # Runbook y artefactos de despliegue.
├── terraform/                   # Infraestructura como código.
├── doc/                         # Documentación funcional, arquitectura, auditoría, ER y memoria.
├── openspec/                    # Artefactos de especificación/cambios.
├── Architecture.md              # Resumen arquitectónico principal.
├── RUNBOOK_local.md             # Guía completa para levantar el entorno local.
└── README.md                    # Este documento.
```

## Funcionalidades principales

| Área | Funcionalidades |
|---|---|
| Autenticación y roles | Login Keycloak/PKCE, modo dev local, sesiones por rol y acceso diferenciado para paciente, médico, técnico y administrador. |
| Gestión clínica | Alta/consulta de pacientes, diagnósticos, programas de rehabilitación, ejercicios asociados y configuración de análisis. |
| Portal de paciente | Consulta de información propia, consentimiento, subida de grabaciones, visualización de métricas y borrado lógico de grabaciones. |
| Análisis de grabaciones | Subida a object storage privado, job asíncrono, worker de audio, extracción de métricas y persistencia de estado `pending/running/done/error`. |
| Métricas e informes | Recuperación de resultados, recomendaciones persistidas, informes de ejercicios y check-ups de seguimiento. |
| IA segura | Diseño preparado para enviar únicamente métricas pseudonimizadas al proveedor LLM; la integración IA todavía no está implementada. Nunca debe enviarse identidad, PII ni audio bruto. |
| Auditoría | Registro de operaciones mutantes exitosas o denegadas para apoyar trazabilidad y monitorización. |
| Seguridad de datos | RLS por rol/paciente, cifrado de `national_id`, separación entre base de datos de aplicación y base de datos de Keycloak. |
| Documentación técnica | SDD, ADR, auditoría, modelo ER, memoria del proyecto, runbooks locales y despliegue. |

## Usuarios y contraseñas de prueba

El entorno local de Keycloak crea usuarios semilla para probar el login. La contraseña coincide con el nombre de usuario.

| Usuario | Contraseña | Rol esperado | Uso principal |
|---|---|---|---|
| `medico1` | `medico1` | `medical` | Workspace clínico: diagnósticos y programas. |
| `paciente1` | `paciente1` | `patient` | Portal paciente y flujo de grabaciones. |
| `paciente2` | `paciente2` | `patient` | Segundo paciente para validar aislamiento/RLS. |
| `tecnico1` | `tecnico1` | `technician` | Validación de acceso por rol técnico. |
| `admin1` | `admin1` | `admin` | Panel de administración/auditoría. |

Credenciales locales adicionales:

| Servicio | URL | Credenciales |
|---|---|---|
| Consola Keycloak | <http://localhost:8085/admin> | `admin` / `admin` |
| Consola MinIO | <http://localhost:9001> | `minioadmin` / `minioadmin123` |
| Base de datos app, owner/migración | `localhost:5432/appdb` | `appuser` / valor de `.env` |
| Base de datos app, runtime API | `localhost:5432/appdb` | `ftm_app` / `FTM_APP_DB_PASSWORD` |

> No uses estas credenciales fuera del entorno local de desarrollo.

## Documentación adicional

| Documento | Contenido |
|---|---|
| [`RUNBOOK_local.md`](RUNBOOK_local.md) | Ejecución local completa, variables, credenciales, verificación y troubleshooting. |
| [`Architecture.md`](Architecture.md) | Resumen de arquitectura, decisiones principales, componentes, RLS, seguridad y despliegue. |
| [`doc/sdd/FTM_SDD_1_9.md`](doc/sdd/FTM_SDD_1_9.md) | Especificación funcional y no funcional del sistema. |
| [`doc/architecture/ADR_from_SDD_1_9.md`](doc/architecture/ADR_from_SDD_1_9.md) | ADRs derivados del SDD: monolito modular, Keycloak, PostgreSQL, object storage, worker, RLS, etc. |
| [`doc/audit/AUDIT_FTM.md`](doc/audit/AUDIT_FTM.md) | Guía de auditoría de código, OWASP, RGPD y formato de hallazgos. |
| [`doc/bbdd/ftm_erd.md`](doc/bbdd/ftm_erd.md) | Modelo entidad-relación en Mermaid. |
| [`doc/bbdd/ftm_schema.sql`](doc/bbdd/ftm_schema.sql) | Esquema SQL de referencia. |
| [`doc/memoria_proyecto/Memoria_Proyecto.md`](doc/memoria_proyecto/Memoria_Proyecto.md) | Memoria narrativa del proyecto: problema, solución, arquitectura, GDPR, despliegue y mejoras. |
| [`api/README.md`](api/README.md) | Guía específica del backend, modos de autenticación, worker, storage y tests. |
| [`web/README.md`](web/README.md) | Guía específica del frontend, modos dev/PKCE y scripts npm. |
| [`bbdd_dev_setup/README_local_env.md`](bbdd_dev_setup/README_local_env.md) | Detalle del entorno local de base de datos y Keycloak. |
| [`deploy/RUNBOOK.md`](deploy/RUNBOOK.md) | Runbook del despliegue cloud. |
| [`terraform/README_ES.md`](terraform/README_ES.md) | Guía de infraestructura/despliegue en español. |

## Notas de seguridad para desarrollo

- No commits de secretos ni `.env` reales.
- No ejecutar la API con usuario propietario de la base de datos en runtime.
- No desactivar RLS para pruebas funcionales de datos de paciente.
- La integración con IA aún no está implementada; cuando se implemente, no enviar identidad, PII ni audio bruto a servicios LLM.
- Tratar las grabaciones de voz como dato biométrico/sanitario sensible.


## URL de la aplicacion

https://ftm-followup-checkup.duckdns.org/

Usuarios de prueba definidos en el `realm-export.json` de Keycloak y desplegados en prod:

| Usuario | Contraseña | Rol |
|---|---|---|
| `medico1` | `medico1` | `medical` |
| `paciente1` | `paciente1` | `patient` |
| `paciente2` | `paciente2` | `patient` |
| `tecnico1` | `tecnico1` | `technician` |
| `admin1` | `admin1` | `admin` |

## Video exposicion y demo de aplicacion

https://drive.google.com/file/d/1omFGS3u0IoVJcFhNXrV2xgIlVyqXvO6T/view?usp=drive_link
