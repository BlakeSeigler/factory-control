#!/usr/bin/env bash
# Run simulator, supervisor and dashboard together; Ctrl-C stops all three.
set -euo pipefail
cd "$(dirname "$0")/.."
trap 'kill 0' EXIT INT TERM
uv run fc sim "$@" &
sleep 5  # four OPC UA servers take ~1 s each to initialize
uv run fc supervisor &
uv run fc dashboard &
wait
