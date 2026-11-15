#!/usr/bin/env bash
# Prepare the project: Python environment, dependencies and the Ollama model.
# Safe to run more than once.
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

cd "$REPO_ROOT"

require_command uv "Install uv: https://docs.astral.sh/uv/getting-started/installation/"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Review it before running the graph."
fi

echo "==> Syncing Python environment (uv sync)"
uv sync

OLLAMA_MODEL_NAME="$(read_env_value OLLAMA_MODEL .env qwen3:14b)"
OLLAMA_URL="$(read_env_value OLLAMA_BASE_URL .env http://localhost:11434)"

if command -v ollama >/dev/null 2>&1; then
  if curl -fsS -m 5 "$OLLAMA_URL/api/version" >/dev/null 2>&1; then
    if ollama list | awk 'NR>1 {print $1}' | grep -qx "$OLLAMA_MODEL_NAME"; then
      echo "==> Ollama model '$OLLAMA_MODEL_NAME' already present"
    else
      echo "==> Pulling Ollama model '$OLLAMA_MODEL_NAME'"
      ollama pull "$OLLAMA_MODEL_NAME"
    fi
  else
    echo "Warning: Ollama does not respond at $OLLAMA_URL. Start the Ollama app, then rerun setup." >&2
  fi
else
  echo "Warning: 'ollama' not found in PATH. Install Ollama for Windows, then rerun setup." >&2
fi

echo "==> Setup finished"
