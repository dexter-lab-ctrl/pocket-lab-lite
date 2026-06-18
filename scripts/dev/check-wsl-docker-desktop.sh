#!/usr/bin/env bash
set -Eeuo pipefail

ok(){ printf '[OK] %s\n  %s\n' "$1" "$2"; }
fail(){ printf '[FAIL] %s\n  %s\n' "$1" "$2" >&2; exit 1; }
warn(){ printf '[WARN] %s\n  %s\n' "$1" "$2"; }

REPORT_PATH="${POCKETLAB_WSL_DOCKER_REPORT_PATH:-.pocketlab-dev/reports/wsl-docker-desktop.json}"
COMPOSE_FILE="${POCKETLAB_DOCKER_COMPOSE_FILE:-docker-compose.dev.yml}"
NATS_SERVICE="${POCKETLAB_NATS_COMPOSE_SERVICE:-nats}"
NATS_CONTAINER="${POCKETLAB_NATS_CONTAINER_NAME:-pocketlab-dev-nats}"
NATS_HEALTH_URL="${POCKETLAB_NATS_HEALTH_URL:-http://127.0.0.1:8222/healthz}"
CLEANUP="${POCKETLAB_DOCKER_CHECK_CLEANUP:-0}"
CLEANUP_STATUS="not_requested"

mkdir -p "$(dirname "$REPORT_PATH")"

printf '\nPocket Lab Docker Desktop + WSL2 integration check\n'
printf '=================================================\n'

if [[ "$(uname -s)" != "Linux" ]]; then
  fail "Linux environment" "This check must run inside Ubuntu/WSL Linux."
fi

if grep -qi microsoft /proc/version 2>/dev/null; then
  ok "WSL kernel" "Microsoft WSL kernel detected"
else
  warn "WSL kernel" "Microsoft WSL marker not detected; continuing because Docker may still work on Linux."
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  fail "Docker Compose file" "$COMPOSE_FILE not found. Run from Pocket Lab repo root."
fi
ok "Docker Compose file" "$COMPOSE_FILE"

if ! command -v docker >/dev/null 2>&1; then
  fail "Docker CLI" "docker command not found inside Ubuntu."
fi
ok "Docker CLI" "$(docker --version)"

if ! docker version >/tmp/pocketlab-docker-version.txt 2>&1; then
  fail "Docker engine" "Docker CLI cannot reach Docker Desktop Linux engine. Enable Docker Desktop WSL integration for this Ubuntu distro."
fi
ok "Docker engine" "$(docker version --format '{{.Server.Version}}' 2>/dev/null || tail -n 1 /tmp/pocketlab-docker-version.txt)"

if ! docker compose version >/tmp/pocketlab-docker-compose-version.txt 2>&1; then
  fail "Docker Compose" "docker compose plugin unavailable inside Ubuntu."
fi
ok "Docker Compose" "$(docker compose version)"

if docker info 2>/dev/null | grep -qi "Docker Desktop"; then
  ok "Docker Desktop integration" "Docker engine reports Docker Desktop context"
else
  warn "Docker Desktop integration" "Docker engine reachable, but Docker Desktop marker was not found in docker info."
fi

if docker run --rm hello-world >/tmp/pocketlab-hello-world.txt 2>&1; then
  ok "hello-world container" "Docker can run Linux containers from Ubuntu"
else
  fail "hello-world container" "$(tail -n 3 /tmp/pocketlab-hello-world.txt | tr '\n' ' ')"
fi

docker compose -f "$COMPOSE_FILE" up -d "$NATS_SERVICE" >/tmp/pocketlab-compose-nats-up.txt 2>&1 \
  || fail "NATS compose service" "$(tail -n 5 /tmp/pocketlab-compose-nats-up.txt | tr '\n' ' ')"
ok "NATS compose service" "$NATS_SERVICE started"

if docker ps --format '{{.Names}}' | grep -qx "$NATS_CONTAINER"; then
  ok "NATS container" "$NATS_CONTAINER running"
else
  fail "NATS container" "$NATS_CONTAINER not found in docker ps"
fi

if command -v curl >/dev/null 2>&1; then
  if curl -fsS "$NATS_HEALTH_URL" >/tmp/pocketlab-nats-health.txt 2>&1; then
    ok "NATS monitor health" "$NATS_HEALTH_URL"
  else
    fail "NATS monitor health" "$(cat /tmp/pocketlab-nats-health.txt | tr '\n' ' ')"
  fi
else
  fail "curl" "curl not found; cannot validate NATS monitor health"
fi

if [[ "$CLEANUP" == "1" || "$CLEANUP" == "true" || "$CLEANUP" == "TRUE" ]]; then
  docker compose -f "$COMPOSE_FILE" stop "$NATS_SERVICE" >/tmp/pocketlab-compose-nats-stop.txt 2>&1 \
    || fail "NATS cleanup" "$(tail -n 5 /tmp/pocketlab-compose-nats-stop.txt | tr '\n' ' ')"
  CLEANUP_STATUS="stopped"
  ok "NATS cleanup" "$NATS_SERVICE stopped after validation"
fi

cat > "$REPORT_PATH" <<JSON
{
  "schema": "pocketlab.wslDockerDesktop/v1",
  "generated_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "status": "OK",
  "compose_file": "$COMPOSE_FILE",
  "nats_service": "$NATS_SERVICE",
  "nats_container": "$NATS_CONTAINER",
  "nats_health_url": "$NATS_HEALTH_URL",
  "cleanup_requested": "$CLEANUP",
  "cleanup_status": "$CLEANUP_STATUS"
}
JSON

ok "Docker Desktop WSL report" "$REPORT_PATH"
printf 'Docker Desktop + WSL2 integration check passed.\n'
