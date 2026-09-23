#!/bin/sh
set -eu

MODE="$(printf '%s' "${ADK_SERVER_MODE:-api}" | tr '[:upper:]' '[:lower:]')"
HOST_VALUE="${HOST:-0.0.0.0}"
PORT_VALUE="${PORT:-8000}"
AGENTS_DIR_VALUE="${AGENTS_DIR:-agents}"

if [ "$MODE" = "web" ]; then
  set -- python -m google.adk.cli web \
    --host "$HOST_VALUE" \
    --port "$PORT_VALUE"

  if [ -n "${ALLOW_ORIGINS:-}" ]; then
    set -- "$@" --allow_origins "${ALLOW_ORIGINS}"
  fi

  if [ "${ADK_A2A:-false}" = "true" ]; then
    set -- "$@" --a2a
  fi

  if [ "${TRACE_TO_CLOUD:-false}" = "true" ]; then
    set -- "$@" --trace_to_cloud
  fi

  if [ "${RELOAD_AGENTS:-false}" = "true" ]; then
    set -- "$@" --reload_agents
  fi

  if [ -n "${SESSION_DB_URI:-}" ]; then
    set -- "$@" --session_service_uri "${SESSION_DB_URI}"
  fi

  if [ -n "${ARTIFACT_SERVICE_URI:-}" ]; then
    set -- "$@" --artifact_service_uri "${ARTIFACT_SERVICE_URI}"
  fi

  if [ -n "${MEMORY_SERVICE_URI:-}" ]; then
    set -- "$@" --memory_service_uri "${MEMORY_SERVICE_URI}"
  fi

  if [ -n "${EVAL_STORAGE_URI:-}" ]; then
    set -- "$@" --eval_storage_uri "${EVAL_STORAGE_URI}"
  fi

  set -- "$@" "$AGENTS_DIR_VALUE"
else
  set -- uvicorn app:app \
    --host "$HOST_VALUE" \
    --port "$PORT_VALUE"
fi

exec "$@"
