#!/usr/bin/env bash
# Start a local Arize Phoenix server (UI on http://localhost:6006).
# Phoenix is run with uvx, not as a project dependency.
# Data is stored outside the repository, and Phoenix's own telemetry is disabled.
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

require_command uvx "Install uv (provides uvx): https://docs.astral.sh/uv/getting-started/installation/"

DATA_DIR="${PHOENIX_DATA_DIR:-$HOME/.local/share/finances-ai/phoenix}"
mkdir -p "$DATA_DIR"

export PHOENIX_WORKING_DIR="$DATA_DIR"
export PHOENIX_HOST="127.0.0.1"
export PHOENIX_PORT="${PHOENIX_PORT:-6006}"
export PHOENIX_TELEMETRY_ENABLED="false"

echo "Phoenix UI: http://localhost:${PHOENIX_PORT}  (data: $DATA_DIR)"
exec uvx arize-phoenix serve
