#!/usr/bin/env bash
# Shared helpers for the project scripts. Sourced, not executed directly.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Make uv (installed by winget) and Ollama available when they are not on PATH yet.
add_known_tool_dirs() {
  local candidate
  for candidate in \
    "${LOCALAPPDATA:-}/Programs/Ollama" \
    "${LOCALAPPDATA:-}/Microsoft/WinGet/Links" \
    "${HOME}/.local/bin" \
    "${HOME}/.cargo/bin"; do
    if [ -d "$candidate" ]; then
      PATH="$candidate:$PATH"
    fi
  done
  # winget places uv in a versioned package folder; add it if present.
  for candidate in "${LOCALAPPDATA:-}"/Microsoft/WinGet/Packages/astral-sh.uv_*; do
    if [ -d "$candidate" ]; then
      PATH="$candidate:$PATH"
    fi
  done
  export PATH
}

# Read a single KEY=value from a dotenv file without sourcing it.
read_env_value() {
  local key="$1" file="$2" default="$3" value=""
  if [ -f "$file" ]; then
    value="$(grep -E "^${key}=" "$file" | tail -n 1 | cut -d= -f2- | tr -d '\r' || true)"
  fi
  printf '%s' "${value:-$default}"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Error: '$1' is not available in this shell. $2" >&2
    exit 1
  fi
}

add_known_tool_dirs
