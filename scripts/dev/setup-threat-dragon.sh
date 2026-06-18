#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE="${THREAT_DRAGON_IMAGE:-owasp/threat-dragon:stable}"
CONTAINER="${THREAT_DRAGON_CONTAINER:-pocketlab-threat-dragon}"
HOST_PORT="${THREAT_DRAGON_PORT:-8082}"
MODEL_DIR="${POCKETLAB_THREAT_MODEL_DIR:-$ROOT/threat-model}"
RUNTIME_DIR="${POCKETLAB_THREAT_DRAGON_DIR:-$ROOT/.pocketlab/threat-dragon}"
ENV_FILE="$RUNTIME_DIR/.env"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

random_hex_16() {
  openssl rand -hex 16
}

ensure_env_kv() {
  local key="$1"
  local value="$2"

  if grep -q "^${key}=" "$ENV_FILE"; then
    return 0
  fi

  echo "Adding missing ${key} to $ENV_FILE"
  printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
}

command -v docker >/dev/null 2>&1 || fail "Docker is not installed or not in PATH."
command -v openssl >/dev/null 2>&1 || fail "openssl is required to generate Threat Dragon local secrets."
docker info >/dev/null 2>&1 || fail "Docker is installed but unavailable. Start Docker and check user permissions."

case "$IMAGE" in
  *:latest)
    fail "Refusing to use ':latest'. Use owasp/threat-dragon:stable or another pinned non-latest tag."
    ;;
esac

mkdir -p "$MODEL_DIR" "$RUNTIME_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "Creating Threat Dragon env file: $ENV_FILE"
  {
    echo "# Local Pocket Lab Threat Dragon runtime settings."
    echo "# Do not commit this file. It contains local runtime secrets."
    echo "# Threat model source-of-truth remains in the repository under threat-model/."
  } > "$ENV_FILE"
  chmod 0600 "$ENV_FILE"
fi

# Threat Dragon expects ENCRYPTION_KEYS as a JSON array string.
# Example from Threat Dragon docs:
# ENCRYPTION_KEYS='[{"isPrimary": true, "id": 0, "value": "..."}]'
if ! grep -q '^ENCRYPTION_KEYS=' "$ENV_FILE"; then
  key_value="$(random_hex_16)"
  ensure_env_kv "ENCRYPTION_KEYS" "'[{\"isPrimary\": true, \"id\": 0, \"value\": \"${key_value}\"}]'"
fi

ensure_env_kv "ENCRYPTION_JWT_SIGNING_KEY" "$(random_hex_16)"
ensure_env_kv "ENCRYPTION_JWT_REFRESH_SIGNING_KEY" "$(random_hex_16)"
ensure_env_kv "NODE_ENV" "development"
ensure_env_kv "SERVER_API_PROTOCOL" "http"
ensure_env_kv "PORT" "3000"
ensure_env_kv "APP_PORT" "8080"

chmod 0600 "$ENV_FILE"

echo "Pulling $IMAGE ..."
docker pull "$IMAGE"

CONTAINER_PORT="${THREAT_DRAGON_CONTAINER_PORT:-}"
if [ -z "$CONTAINER_PORT" ]; then
  exposed_ports="$(docker image inspect "$IMAGE" --format '{{range $p, $_ := .Config.ExposedPorts}}{{println $p}}{{end}}' 2>/dev/null || true)"
  CONTAINER_PORT="$(printf '%s\n' "$exposed_ports" | sed -n 's#/tcp##p' | head -n 1)"
fi

CONTAINER_PORT="${CONTAINER_PORT:-3000}"

if docker ps --format '{{.Names}}' | grep -Fxq "$CONTAINER"; then
  echo "Threat Dragon is already running as container '$CONTAINER'."
  docker port "$CONTAINER" || true
  echo "URL: http://localhost:$HOST_PORT"
  exit 0
fi

if docker ps -a --format '{{.Names}}' | grep -Fxq "$CONTAINER"; then
  echo "Removing existing container '$CONTAINER' for idempotent restart."
  docker rm -f "$CONTAINER" >/dev/null
fi

echo "Starting Threat Dragon on http://localhost:$HOST_PORT ..."
echo "Mapping host port $HOST_PORT to container port $CONTAINER_PORT."

docker run -d \
  --name "$CONTAINER" \
  --env-file "$ENV_FILE" \
  -e "ENV_FILE=$ENV_FILE" \
  -p "127.0.0.1:$HOST_PORT:$CONTAINER_PORT" \
  -v "$MODEL_DIR:/threat-model" \
  -v "$RUNTIME_DIR:/data" \
  "$IMAGE" >/dev/null

sleep 5

if ! docker ps --format '{{.Names}}' | grep -Fxq "$CONTAINER"; then
  echo "ERROR: Threat Dragon container exited during startup." >&2
  echo
  echo "Recent container logs:" >&2
  docker logs --tail=160 "$CONTAINER" >&2 || true
  echo
  echo "Local env file keys currently present:" >&2
  sed -n 's/^\([^=#][^=]*\)=.*/\1=<redacted>/p' "$ENV_FILE" >&2 || true
  exit 1
fi

cat <<MSG
Threat Dragon is running.
URL: http://localhost:$HOST_PORT
Container: $CONTAINER
Image: $IMAGE
Container port: $CONTAINER_PORT
Repository threat-model mount: $MODEL_DIR -> /threat-model
Runtime data mount: $RUNTIME_DIR -> /data

Docker port mapping:
$(docker port "$CONTAINER" || true)

Logs:
  docker logs -f $CONTAINER

Stop:
  docker rm -f $CONTAINER
MSG
