#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
docker build -t ptb "$SCRIPT_DIR"
