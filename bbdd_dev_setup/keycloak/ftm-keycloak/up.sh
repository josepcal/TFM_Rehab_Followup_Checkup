#!/usr/bin/env bash
#
# up.sh - Levanta el stack Keycloak + Postgres (postgres-keycloak)
# Uso:    ./up.sh
#
set -euo pipefail

COMPOSE_FILE="docker-compose.yaml"
KC_URL="http://localhost:8080"
REALM="ftm"

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

# --- Levantar el stack ---
echo "==> Levantando Keycloak + Postgres..."
docker compose -f "$COMPOSE_FILE" up -d

# --- Esperar readiness (realm importado y respondiendo) ---
echo "==> Esperando a que el realm '$REALM' este disponible (puede tardar ~30-60s la 1a vez)..."
WELL_KNOWN="$KC_URL/realms/$REALM/.well-known/openid-configuration"
ATTEMPTS=0
MAX_ATTEMPTS=60
until curl -sf "$WELL_KNOWN" >/dev/null 2>&1; do
  ATTEMPTS=$((ATTEMPTS + 1))
  if [ "$ATTEMPTS" -ge "$MAX_ATTEMPTS" ]; then
    echo ""
    echo "AVISO: Keycloak tarda mas de lo esperado. Revisa los logs con:" >&2
    echo "       docker compose -f $COMPOSE_FILE logs -f keycloak" >&2
    exit 1
  fi
  printf '.'
  sleep 3
done

echo ""
echo "============================================================"
echo " Keycloak LISTO"
echo "------------------------------------------------------------"
echo " Consola admin : $KC_URL/admin   (admin / admin)"
echo " Realm         : $REALM"
echo " Clients       : ftm-web (publico, PKCE S256) | ftm-api (bearer-only)"
echo " Usuarios seed : medico1 | paciente1 | tecnico1 | admin1"
echo "                 (contrasena = nombre de usuario)"
echo "------------------------------------------------------------"
echo " Logs   : docker compose -f $COMPOSE_FILE logs -f keycloak"
echo " Parar  : docker compose -f $COMPOSE_FILE stop"
echo " Borrar : docker compose -f $COMPOSE_FILE down        (conserva datos)"
echo "          docker compose -f $COMPOSE_FILE down -v     (borra datos)"
echo "============================================================"
