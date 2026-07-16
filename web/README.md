# FTM Web UI — ejecución local

Frontend React/Vite del *Rehab Follow-up Check-up Tool*. Cubre el workspace
clínico (diagnósticos y programas), el portal de paciente (consentimiento RGPD,
grabaciones, métricas) y el panel de administración/auditoría. Puede trabajarse
en dos modos:

| Modo | Uso | Backend esperado |
|---|---|---|
| Dev/mock | Desarrollo rápido de UI | API con `AUTH_MODE=dev` |
| Keycloak / PKCE | Integración real con login | API con `AUTH_MODE=keycloak` |

> `web/src/auth/authClient.ts` selecciona el modo con `VITE_FTM_AUTH_MODE`.
> Por defecto usa mock local (`dev`). Con `VITE_FTM_AUTH_MODE=pkce` inicializa
> `keycloak-js` con Authorization Code + PKCE S256.

## Requisitos

- Node.js y npm.
- API arrancada en `http://localhost:8000`.
- Para PKCE: Keycloak local arrancado en `http://localhost:8085`.

## Modo dev/mock

Este modo no abre login de Keycloak. El frontend usa una sesión simulada y Vite
redirige `/api/*` a FastAPI.

```bash
# Desde la raíz del repo.

# Terminal 1: API en modo dev.
cd api
cp .env.example .env
# Comprueba: AUTH_MODE=dev
uvicorn app.main:app --reload --port 8000

# Terminal 2: frontend.
cd web
npm install
npm run dev
```

Abre:

```text
http://localhost:5173
```

Variables útiles para cambiar la sesión mock:

```bash
VITE_FTM_DEV_ROLE=medical npm run dev
VITE_FTM_DEV_ROLE=patient npm run dev
VITE_FTM_DEV_AUTHENTICATED=false npm run dev
```

Roles admitidos:

```text
medical | patient | technician | admin
```

## Modo Keycloak / PKCE

PKCE se ejecuta en el navegador con el cliente público `ftm-web`. La API solo
recibe `Authorization: Bearer <token>` y valida el JWT contra Keycloak.

### 1) Levantar Keycloak

```bash
# Desde la raíz del repo.
cd bbdd_dev_setup/keycloak/ftm-keycloak
chmod +x up.sh
./up.sh
```

Datos del realm local:

| Elemento | Valor |
|---|---|
| URL | `http://localhost:8085` |
| Realm | `ftm` |
| Cliente SPA | `ftm-web` |
| Redirect URI | `http://localhost:5173/*` |
| PKCE | `S256` |
| Usuarios | `medico1`, `paciente1`, `paciente2`, `tecnico1`, `admin1` |
| Contraseña | Igual que el usuario |

### 2) Arrancar API en modo Keycloak

Arranca la API con `AUTH_MODE=keycloak` apuntando al realm local. La configuración
del backend (`.env`, `DATABASE_URL` contra `appdb`, URLs de Keycloak) está en
[`../api/README.md`](../api/README.md).

### 3) Arrancar frontend

```bash
# Desde la raíz del repo.
cd web
npm install
VITE_FTM_AUTH_MODE=pkce npm run dev
```

Desde la raíz del repo también puedes usar:

```bash
VITE_FTM_AUTH_MODE=pkce npm --prefix web run dev
```

El adaptador usa estos valores por defecto:

| Variable | Valor por defecto |
|---|---|
| `VITE_FTM_AUTH_MODE` | `dev` |
| `VITE_FTM_KEYCLOAK_URL` | `http://localhost:8085` |
| `VITE_FTM_KEYCLOAK_REALM` | `ftm` |
| `VITE_FTM_KEYCLOAK_CLIENT_ID` | `ftm-web` |

Con `VITE_FTM_AUTH_MODE=pkce`, al abrir `http://localhost:5173` el navegador
redirige a Keycloak. Entra con `medico1` / `medico1` para acceder al workspace
médico.

## Proxy de desarrollo

`vite.config.ts` publica `/api/*` en el navegador y lo reescribe hacia FastAPI:

```text
Browser:  http://localhost:5173/api/patients
Proxy:    http://localhost:8000/patients
```

## Scripts

```bash
npm run dev      # Vite dev server
npm run lint     # TypeScript sin emitir
npm test         # Vitest
npm run build    # TypeScript + build Vite
npm run preview  # Preview del build
```

## Alcance actual

Implementado en la UI:

- **Workspace clínico** (`features/diagnostics/`): diagnósticos y programas de rehabilitación.
- **Portal de paciente** (`features/patient/`): consentimiento RGPD, subida de grabaciones,
  análisis de ejercicios y visualización de métricas.
- **Panel de administración** (`features/admin/`): dashboard de eventos de auditoría.

Fuera de alcance en el MVP:

- Alta de pacientes desde la UI (existe el endpoint de API, no la pantalla).
- Insights vía LLM (la integración con IA no está implementada todavía).
