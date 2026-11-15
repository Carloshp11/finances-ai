#!/usr/bin/env bash
# Start Phoenix in this terminal (UI on http://localhost:6006). Ctrl+C stops it.
# The logic lives in the phoenix-start entry point; use `uv run phoenix-start` to run it detached.
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

require_command uv "Install uv: https://docs.astral.sh/uv/getting-started/installation/"

exec uv run phoenix-start --foreground "$@"
