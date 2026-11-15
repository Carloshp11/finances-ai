"""OpenTelemetry/OpenInference setup that sends LangChain traces to local Phoenix.

Traces go only to the collector endpoint configured in .env (by default
http://localhost:6006). No remote collector is configured.
"""

from __future__ import annotations

import threading

from local_ai.config import Settings

_lock = threading.Lock()
_initialized = False


def setup_observability(settings: Settings) -> None:
    """Register the tracer provider and instrument LangChain. Idempotent."""
    global _initialized
    with _lock:
        if _initialized:
            return

        from openinference.instrumentation.langchain import LangChainInstrumentor
        from phoenix.otel import register

        tracer_provider = register(
            endpoint=settings.phoenix_collector_endpoint,
            project_name=settings.phoenix_project_name,
            verbose=False,
        )
        LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
        _initialized = True
