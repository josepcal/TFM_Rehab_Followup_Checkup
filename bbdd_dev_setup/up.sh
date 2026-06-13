#!/usr/bin/env bash
#
# up.sh - Levanta la BD de la app (postgres-app) y aplica las migraciones Alembic.
#
# Coloca este script (junto con docker-compose.yaml y .env) en bbdd_dev_setup/,
# es decir, en la carpeta que contiene el directorio alembic/.
#
# Uso:
#   cp .env.example .env   # y rellena los valores (solo la 1a vez)
#   ./up.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE_FILE="docker-compose.yaml"
ENV_FILE=".env"
ALEMBIC_DIR="alembic"
VENV_DIR=".venv"

# --- Comprobaciones previas ---
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker no esta en el PATH." >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: el demonio de Docker no responde. Arrancalo con:" >&2
  echo "       sudo systemctl start docker" >&2
  exit 1
fi
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: falta $ENV_FILE. Copia .env.example a .env y rellena los valores:" >&2
  echo "       cp .env.example .env" >&2
  exit 1
fi
if [ ! -d "$ALEMBIC_DIR" ]; then
  echo "ERROR: no encuentro la carpeta '$ALEMBIC_DIR' aqui." >&2
  echo "       Coloca este script en bbdd_dev_setup/ (junto a alembic/)." >&2
  exit 1
fi

# --- Cargar variables de entorno ---
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${POSTGRES_USER:?Falta POSTGRES_USER en .env}"
: "${POSTGRES_PASSWORD:?Falta POSTGRES_PASSWORD en .env}"
: "${POSTGRES_DB:?Falta POSTGRES_DB en .env}"

# URL de conexion, por si tu env.py de Alembic la lee de DATABASE_URL
export DATABASE_URL="postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}"

# --- Levantar la BD ---
echo "==> Levantando postgres-app..."
docker compose -f "$COMPOSE_FILE" up -d

echo "==> Esperando a que Postgres acepte conexiones..."
until docker compose -f "$COMPOSE_FILE" exec -T postgres-app \
      pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; do
  printf '.'
  sleep 2
done
echo " ok"

# --- Entorno virtual + dependencias ---
if [ ! -d "$VENV_DIR" ]; then
  echo "==> Creando entorno virtual ($VENV_DIR)..."
  python3 -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if python -c "import alembic" >/dev/null 2>&1; then
  echo "==> Dependencias de migracion ya presentes."
else
  echo "==> Instalando dependencias de migracion..."
  if [ -f requirements.txt ]; then
    pip install -q -r requirements.txt
  else
    pip install -q alembic sqlalchemy psycopg2-binary
  fi
fi

# --- Migraciones ---
echo "==> Aplicando migraciones Alembic (upgrade head)..."
( cd "$ALEMBIC_DIR" && alembic upgrade head )

echo ""
echo "============================================================"
echo " BD de la app LISTA"
echo "------------------------------------------------------------"
echo " Servicio    : postgres-app   (localhost:5432)"
echo " Base        : $POSTGRES_DB    user=$POSTGRES_USER"
echo " Conexion    : postgresql://$POSTGRES_USER:***@localhost:5432/$POSTGRES_DB"
echo " Migraciones : aplicadas (alembic upgrade head)"
echo "------------------------------------------------------------"
echo " psql   : docker compose -f $COMPOSE_FILE exec postgres-app psql -U $POSTGRES_USER -d $POSTGRES_DB"
echo " Parar  : docker compose -f $COMPOSE_FILE stop"
echo " Borrar : docker compose -f $COMPOSE_FILE down        (conserva datos)"
echo "          docker compose -f $COMPOSE_FILE down -v     (borra datos)"
echo "============================================================"
