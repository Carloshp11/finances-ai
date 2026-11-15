"""Entry point: configure, trace, run the hello-world graph once, print the answer."""

from __future__ import annotations

import sys
import urllib.error
import urllib.request

from local_ai.config import ConfigError, Settings, load_settings
from local_ai.graphs.hello_world import build_graph
from local_ai.models.factory import create_model
from local_ai.observability.phoenix import setup_observability

DEFAULT_INPUT = "Explain in one sentence what LangGraph is."


def check_ollama(base_url: str, timeout: float = 3.0) -> None:
    """Fail early with a clear message if the local Ollama server is not reachable."""
    url = f"{base_url}/api/version"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            f"Ollama is not reachable at {base_url}. Start the Ollama app and retry. ({exc})"
        ) from exc


def run(settings: Settings, user_input: str) -> str:
    setup_observability(settings)
    check_ollama(settings.ollama_base_url)
    model = create_model(
        settings.ollama_model,
        temperature=settings.ollama_temperature,
        base_url=settings.ollama_base_url,
        num_ctx=settings.ollama_num_ctx,
    )
    graph = build_graph(model)
    result = graph.invoke({"user_input": user_input, "prompt": "", "response": ""})
    return result["response"]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    user_input = " ".join(args).strip() or DEFAULT_INPUT

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    try:
        response = run(settings, user_input)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(response)
    return 0


if __name__ == "__main__":
    sys.exit(main())
