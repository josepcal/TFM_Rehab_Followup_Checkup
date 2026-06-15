# FTM - Keycloak local (dev)

Stack de Keycloak + Postgres dedicada para desarrollo local del proyecto FTM.

## Contenido
- `docker-compose.yaml` - Keycloak 26.6.3 + postgres-keycloak, con import automatico del realm.
- `realm-export.json`   - Realm `ftm`: clients `ftm-web` (publico, PKCE S256) y `ftm-api` (bearer-only), roles `medical/patient/technician/admin` y 4 usuarios semilla.
- `up.sh`               - Levanta el stack y espera a que el realm responda.

## Requisitos
- Docker Engine con el plugin `docker compose` (v2).
- Demonio de Docker arrancado (`sudo systemctl start docker`).
- Colocar la carpeta en el filesystem de Linux (p. ej. `~/ftm/infra/`), NO en `/mnt/c`.

## Arranque
```bash
chmod +x up.sh      # solo la primera vez
./up.sh
```
Cuando termine, abre http://localhost:8080/admin (admin / admin), cambia al realm `ftm`
y entra con cualquier usuario seed (contrasena = nombre de usuario).

## Subjects estables para la app

El `id` de cada usuario seed se fija en el export para que el claim OIDC `sub`
coincida con `clinical.app_user.external_subject` en la BD de desarrollo:

| Usuario | Rol | `sub` esperado |
|---|---|---|
| `medico1` | `medical` | `idp|doctor-default` |
| `paciente1` | `patient` | `idp|patient-default` |
| `tecnico1` | `technician` | `idp|technical-default` |
| `admin1` | `admin` | `idp|admin-default` |

Si Keycloak ya estaba levantado antes de este cambio, la importacion no se
repite automaticamente. Para aplicar estos IDs desde cero:

```bash
docker compose down -v
./up.sh
```

## Notas
- La importacion del realm solo ocurre la PRIMERA vez (si el realm `ftm` aun no existe).
  Para re-importar desde cero: `docker compose down -v` (borra el volumen) y vuelve a `./up.sh`.
- `start-dev` y `sslRequired: none` son SOLO para desarrollo. En produccion: `start` con
  hostname real, TLS terminado en nginx, sin usuarios semilla y secretos fuera del repo.

## Comandos utiles
```bash
docker compose logs -f keycloak     # ver logs
docker compose stop                 # parar (conserva datos)
docker compose down                 # eliminar contenedores (conserva datos)
docker compose down -v              # eliminar TODO incluido el volumen de datos
```
