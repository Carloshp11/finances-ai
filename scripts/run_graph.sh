#!/usr/bin/env bash
# Run the two-node hello-world graph once. Extra arguments form the user input.
#   ./scripts/run_graph.sh "Your question"
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

require_command uv "Install uv: https://docs.astral.sh/uv/getting-started/installation/"

cd "$REPO_ROOT"
exec uv run python -m local_ai.main "$@"
