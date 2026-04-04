#!/bin/sh
set -e

IMAGE="moirai"
PORT=5000
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

docker build -t "$IMAGE" "$SCRIPT_DIR"
docker run --rm -it -p "$PORT:$PORT" "$IMAGE" "$@"
