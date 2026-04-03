#!/bin/bash
docker build -t ptb .
docker run -it --rm \
  --cap-add=NET_ADMIN \
  --device=/dev/net/tun \
  -v "$(pwd)":/htb \
  ptb "$@"
