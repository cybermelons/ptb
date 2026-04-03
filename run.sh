#!/bin/bash
export MSYS_NO_PATHCONV=1
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

ENTRYPOINT=()

if [[ "$1" == "-b" || "$1" == "--bash" ]]; then
  ENTRYPOINT=(--entrypoint bash)
  shift
fi

WINPTY=()
if command -v winpty &>/dev/null; then
  WINPTY=(winpty)
fi

"${WINPTY[@]}" docker run -it --rm \
  --cap-add=NET_ADMIN \
  --device=/dev/net/tun \
  -e TERM=xterm-256color \
  --env-file "$SCRIPT_DIR/.env" \
  -v "$SCRIPT_DIR":/htb \
  -v ptb-home:/home/hacker \
  "${ENTRYPOINT[@]}" \
  ptb "$@"
