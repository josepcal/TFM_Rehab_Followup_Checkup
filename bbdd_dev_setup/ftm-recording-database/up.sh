#!/usr/bin/env bash
#
# up.sh - Levanta MinIO local para las grabaciones WAV de FTM.
# Uso:    ./up.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"
ENV_EXAMPLE=".env.example"

# --- Comprobaciones previas ---
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker no esta instalado o no esta en el PATH." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: el demonio de Docker no responde. Arrancalo con:" >&2
  echo "       sudo systemctl start docker" >&2
  exit 1
fi

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "ERROR: no encuentro $COMPOSE_FILE. Ejecuta el script desde su carpeta." >&2
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  if [ -f "$ENV_EXAMPLE" ]; then
    echo "==> No existe $ENV_FILE; copiando valores locales desde $ENV_EXAMPLE..."
    cp "$ENV_EXAMPLE" "$ENV_FILE"
  else
    echo "ERROR: falta $ENV_FILE y no existe $ENV_EXAMPLE." >&2
    exit 1
  fi
fi

# --- Cargar variables de entorno ---
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${MINIO_ROOT_USER:?Falta MINIO_ROOT_USER en .env}"
: "${MINIO_ROOT_PASSWORD:?Falta MINIO_ROOT_PASSWORD en .env}"
: "${MINIO_REGION_NAME:?Falta MINIO_REGION_NAME en .env}"
: "${MINIO_BUCKET:?Falta MINIO_BUCKET en .env}"
: "${MINIO_API_PORT:?Falta MINIO_API_PORT en .env}"
: "${MINIO_CONSOLE_PORT:?Falta MINIO_CONSOLE_PORT en .env}"

# --- Levantar MinIO ---
echo "==> Levantando MinIO local..."
docker compose -f "$COMPOSE_FILE" up -d minio

# --- Esperar readiness ---
echo "==> Esperando a que MinIO acepte conexiones..."
ATTEMPTS=0
MAX_ATTEMPTS=60
until docker compose -f "$COMPOSE_FILE" exec -T minio mc ready local >/dev/null 2>&1; do
  ATTEMPTS=$((ATTEMPTS + 1))
  if [ "$ATTEMPTS" -ge "$MAX_ATTEMPTS" ]; then
    echo ""
    echo "ERROR: MinIO tarda mas de lo esperado. Revisa logs con:" >&2
    echo "       docker compose -f $COMPOSE_FILE logs -f minio" >&2
    exit 1
  fi
  printf '.'
  sleep 2
done

echo " ok"

# --- Crear/verificar bucket privado ---
echo "==> Creando/verificando bucket privado '$MINIO_BUCKET'..."
docker compose -f "$COMPOSE_FILE" run --rm minio-init >/dev/null

echo ""
echo "============================================================"
echo " MinIO Recording Storage LISTO"
echo "------------------------------------------------------------"
echo " S3 API        : http://localhost:$MINIO_API_PORT"
echo " Consola       : http://localhost:$MINIO_CONSOLE_PORT"
echo " Usuario       : $MINIO_ROOT_USER"
echo " Password      : ***"
echo " Bucket        : $MINIO_BUCKET (privado)"
echo " Region        : $MINIO_REGION_NAME"
echo "------------------------------------------------------------"
echo " Variables API :"
echo "   STORAGE_BACKEND=s3"
echo "   S3_ENDPOINT_URL=http://localhost:$MINIO_API_PORT"
echo "   S3_ACCESS_KEY_ID=$MINIO_ROOT_USER"
echo "   S3_SECRET_ACCESS_KEY=<MINIO_ROOT_PASSWORD>"
echo "   S3_BUCKET=$MINIO_BUCKET"
echo "   S3_REGION=$MINIO_REGION_NAME"
echo "   S3_FORCE_PATH_STYLE=true"
echo "------------------------------------------------------------"
echo " Logs   : docker compose -f $COMPOSE_FILE logs -f minio"
echo " Parar  : docker compose -f $COMPOSE_FILE stop"
echo " Borrar : docker compose -f $COMPOSE_FILE down        (conserva datos)"
echo "          docker compose -f $COMPOSE_FILE down -v     (borra datos)"
echo "============================================================"
