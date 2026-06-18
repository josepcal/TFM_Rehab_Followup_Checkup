# FTM - Stack local (dev): Keycloak + Postgres

Entorno de desarrollo local del proyecto FTM con identidad (Keycloak) y las dos
bases de datos separadas que pide el plan: la de la app y la de Keycloak.

## Contenido
- `docker-compose.yaml` - 3 servicios:
    * postgres-app       -> BD de la aplicacion (datos clinicos), expuesta en 5432
    * postgres-keycloak  -> BD de Keycloak (identidad), NO expuesta
    * keycloak 26.6.3    -> con import automatico del realm `ftm`
- `realm-export.json`   - Realm `ftm`: clients `ftm-web` (publico, PKCE S256) y
                          `ftm-api` (bearer-only), roles medical/patient/technician/admin
                          y 5 usuarios semilla.
- `up.sh`               - Levanta el stack y espera a que el realm responda.

## Requisitos
- Docker Engine con el plugin `docker compose` (v2), demonio arrancado.
- Colocar la carpeta en el filesystem de Linux (p. ej. `~/ftm/infra/`), NO en `/mnt/c`.
- El puerto 5432 debe estar libre. Si tienes el viejo contenedor `postgres-dev`
  corriendo, eliminalo antes:  docker rm -f postgres-dev

## Arranque
```bash
chmod +x up.sh      # solo la primera vez
./up.sh
```

## Credenciales (NO mezclar)
- BD postgres-app      : user=ftm  pass=ftmpass  db=ftm   (localhost:5432)
- BD postgres-keycloak : user=keycloak pass=keycloakpass  (uso interno, sin puerto)
- Consola Keycloak     : admin / admin   en http://localhost:8085/admin
- Usuarios app (ftm)   : medico1 | paciente1 | paciente2 | tecnico1 | admin1 (pass = usuario)

Cadena de conexion de la app:
    postgresql://ftm:ftmpass@localhost:5432/ftm

Subjects OIDC (`sub`) esperados para alinear Keycloak con `clinical.app_user.external_subject`:
- medico1   -> `idp|doctor-default`
- paciente1 -> `idp|patient-default`
- paciente2 -> `idp|patient-second`
- tecnico1  -> `idp|technical-default`
- admin1    -> `idp|admin-default`

## Usuarios de BD

- `appuser` es el usuario owner/migrator creado por Docker (`POSTGRES_USER`). Úsalo para Alembic/setup, no para la API.
- La migración `0003_runtime_app_role` crea `ftm_app` con la password definida en `FTM_APP_DB_PASSWORD`.
- La API debe usar `DATABASE_URL=postgresql://ftm_app:<FTM_APP_DB_PASSWORD>@localhost:5432/appdb` para que RLS aplique a un usuario no owner.
- Si aparece `permission denied for table patient`, ejecuta `alembic upgrade head`: la migración `0004_runtime_grants` re-aplica los grants de los roles RLS efectivos.

## Notas
- La importacion del realm solo ocurre la PRIMERA vez (si el realm `ftm` no existe).
  Para re-importar: `docker compose down -v` y vuelve a `./up.sh` (borra TODOS los datos).
- `start-dev` y `sslRequired: none` son SOLO para desarrollo.
- Las dos Postgres usan volumenes distintos (app_pgdata y kc_pgdata): datos aislados.

## Comandos utiles
```bash
docker compose logs -f keycloak     # ver logs de keycloak
docker compose ps                   # estado de los 3 servicios
docker compose stop                 # parar (conserva datos)
docker compose down                 # eliminar contenedores (conserva datos)
docker compose down -v              # eliminar TODO incluidos los volumenes
```
