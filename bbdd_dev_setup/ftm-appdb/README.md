# FTM - BD de la app (dev)

Stack local SOLO de la base de datos de la aplicacion (postgres-app) + aplicacion
de las migraciones Alembic. Separado del stack de Keycloak.

## Contenido
- `docker-compose.yaml` - postgres:16 como servicio `postgres-app`, expuesto en 5432.
- `.env.example`        - plantilla de credenciales (copiar a `.env`).
- `up.sh`               - levanta la BD, prepara el venv y ejecuta `alembic upgrade head`.

## Donde colocarlo
Copia estos ficheros en `bbdd_dev_setup/`, es decir, en la carpeta que YA contiene
tu directorio `alembic/` (con su `alembic.ini`, schema y seed). El script espera
encontrar `alembic/` a su lado.

```
bbdd_dev_setup/
├── alembic/              <- tu setup de Alembic (ya existe)
│   ├── alembic.ini
│   └── ...
├── docker-compose.yaml   <- nuevo
├── .env                  <- nuevo (lo creas tu)
└── up.sh                 <- nuevo
```

## Uso
```bash
cp .env.example .env     # rellena POSTGRES_USER / PASSWORD / DB (solo la 1a vez)
chmod +x up.sh           # solo la 1a vez
./up.sh
```

## Antes de la primera ejecucion
El contenedor manual anterior (`postgres-dev`) ocupa el mismo puerto 5432. Eliminalo:
```bash
docker rm -f postgres-dev
```

## Notas
- Este compose usa un volumen NUEVO (`app_pgdata`), distinto del `pgdata` que creaste
  a mano. Arranca vacio, pero `up.sh` ejecuta Alembic y reconstruye schema + seed.
  El volumen antiguo `pgdata` puedes borrarlo cuando quieras: `docker volume rm pgdata`.
- El script exporta `DATABASE_URL` antes de llamar a Alembic. Tu `env.py` da prioridad
  a esa variable sobre la `sqlalchemy.url` de `alembic.ini`, asi que la conexion la
  manda el `.env`. Por eso el `.env` debe cuadrar con la BD que se crea.
- HIGIENE: ahora mismo `alembic.ini` lleva la contrasena en claro (`sqlalchemy.url`).
  Como `env.py` ya soporta `DATABASE_URL`, lo ideal es dejar en `alembic.ini` una URL
  sin secreto (o un placeholder) y mantener la contrasena real solo en `.env`
  (que va en .gitignore). Asi no comiteas el secreto.
- Es SOLO para desarrollo local.

## Comandos utiles
```bash
docker compose ps                                   # estado
docker compose exec postgres-app psql -U <user> -d <db>
docker compose stop                                 # parar (conserva datos)
docker compose down -v                              # eliminar TODO incluido el volumen
```
