#!/bin/bash
export MSYS_NO_PATHCONV=1
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [[ "$1" == "-d" || "$1" == "--down" ]]; then
  docker compose down
  exit
fi

docker compose up -d --build

echo "Waiting for VPN to connect..."
for i in $(seq 1 10); do
  state=$(docker compose ps vpn --format "{{.State}}" 2>/dev/null)
  [[ "$state" == "running" ]] && break
  sleep 2
done

docker compose logs --tail 5 vpn

WINPTY=()
if command -v winpty &>/dev/null; then
  WINPTY=(winpty)
fi

if [[ "$1" == "-b" || "$1" == "--bash" ]]; then
  shift
  "${WINPTY[@]}" docker compose exec kali bash "$@"
else
  "${WINPTY[@]}" docker compose exec kali claude --dangerously-skip-permissions "$@"
fi
