#!/usr/bin/env bash
#
# Start the Voice Reader app with Docker.
#
#   ./start.sh            build (if needed) and start in the background
#   ./start.sh --build    force a rebuild of the image, then start
#   ./start.sh --fg       run in the foreground, streaming logs
#   ./start.sh logs       follow the logs of a running container
#   ./start.sh stop       stop and remove the container
#   ./start.sh status     show the container status
#
set -euo pipefail

cd "$(dirname "$0")"

PORT="${VOICE_PORT:-8080}"

# Pick whichever compose flavour is installed.
if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "Error: neither 'docker compose' nor 'docker-compose' is available." >&2
  echo "Install Docker Desktop or the compose plugin, then try again." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Error: the Docker daemon is not running. Start Docker and try again." >&2
  exit 1
fi

case "${1:-up}" in
  up|--fg|--build|-b)
    args=(up)
    [[ "${1:-}" == "--build" || "${1:-}" == "-b" ]] && args+=(--build)
    if [[ "${1:-}" == "--fg" ]]; then
      echo "Starting Voice Reader on http://localhost:${PORT} (Ctrl-C to stop)..."
      exec "${COMPOSE[@]}" "${args[@]}"
    fi
    args+=(-d)
    echo "Starting Voice Reader..."
    "${COMPOSE[@]}" "${args[@]}"
    echo
    echo "Voice Reader is running at http://localhost:${PORT}"
    echo "Logs: ./start.sh logs    Stop: ./start.sh stop"
    ;;
  logs)
    exec "${COMPOSE[@]}" logs -f
    ;;
  stop|down)
    echo "Stopping Voice Reader..."
    "${COMPOSE[@]}" down
    ;;
  restart)
    "${COMPOSE[@]}" down
    exec "$0" --build
    ;;
  status|ps)
    exec "${COMPOSE[@]}" ps
    ;;
  -h|--help|help)
    sed -n '3,10p' "$0" | sed 's/^# \{0,1\}//'
    ;;
  *)
    echo "Unknown command: $1" >&2
    echo "Try: ./start.sh --help" >&2
    exit 1
    ;;
esac
