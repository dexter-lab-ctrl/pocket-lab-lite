#!/usr/bin/env bash
# Bounded HTTP defaults shared by baseline and future gates.

long_gate_http_timeout_seconds() {
  printf '%s\n' "${POCKETLAB_LONG_GATE_HTTP_TIMEOUT:-3}"
}

long_gate_base_url() {
  printf '%s\n' "${POCKETLAB_LONG_GATE_BASE_URL:-http://127.0.0.1:8443}"
}

long_gate_curl_json() {
  local method="$1" url="$2" output="$3" body="${4:-}"
  local args=(
    -fsS
    --connect-timeout "${POCKETLAB_LONG_GATE_CONNECT_TIMEOUT:-2}"
    --max-time "$(long_gate_http_timeout_seconds)"
    -X "$method"
    -H 'Accept: application/json'
  )
  if [[ -n "${POCKETLAB_API_TOKEN:-}" ]]; then
    args+=(-H "Authorization: Bearer ${POCKETLAB_API_TOKEN}")
  fi
  if [[ -n "$body" ]]; then
    args+=(-H 'Content-Type: application/json' --data "$body")
  fi
  curl "${args[@]}" -o "$output" "$url"
}
