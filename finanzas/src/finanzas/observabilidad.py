"""Run configuration and tracing to a local Arize Phoenix collector.

Traces go only to the collector set in PHOENIX_COLLECTOR_ENDPOINT (default
http://localhost:6006/v1/traces). Phoenix runs on this machine, in line with the project rule
that data never leaves it. If Phoenix is not running or tracing is disabled, the run continues
without traces and only a warning is printed.

Environment variables (same names as the local_ai project, so one .env can serve both):
    PHOENIX_COLLECTOR_ENDPOINT   default http://localhost:6006/v1/traces
    PHOENIX_PROJECT_NAME         default "finanzas"
    PHOENIX_TELEMETRY_ENABLED    default "true"; "false" disables tracing
"""

import os
import socket
import sys
import threading
from typing import Any
from urllib.parse import urlparse

DEFAULT_ENDPOINT = "http://localhost:6006/v1/traces"
PROBE_TIMEOUT_S = 1.0
FLUSH_TIMEOUT_MS = 3000

_lock = threading.Lock()
_provider: Any | None = None  # tracer provider, once registered
_intentado = False


def _telemetria_activa() -> bool:
    valor = os.getenv("PHOENIX_TELEMETRY_ENABLED", "true").strip().lower()
    return valor in {"true", "1", "yes", "on"}


def _collector_accesible(endpoint: str) -> bool:
    """Return True if a TCP connection to the collector succeeds within a short timeout."""
    partes = urlparse(endpoint)
    host = partes.hostname or "localhost"
    puerto = partes.port or (443 if partes.scheme == "https" else 80)
    try:
        with socket.create_connection((host, puerto), timeout=PROBE_TIMEOUT_S):
            return True
    except OSError:
        return False


def _registrar_phoenix() -> None:
    """Register the tracer provider and instrument LangChain. Runs once; never raises."""
    global _provider, _intentado
    with _lock:
        if _intentado:
            return
        _intentado = True
        if not _telemetria_activa():
            return
        endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", DEFAULT_ENDPOINT)
        if not _collector_accesible(endpoint):
            print(
                f"Aviso: Phoenix no responde en {endpoint}; se continúa sin trazas.",
                file=sys.stderr,
            )
            return
        try:
            from openinference.instrumentation.langchain import LangChainInstrumentor
            from phoenix.otel import register

            _provider = register(
                endpoint=endpoint,
                project_name=os.getenv("PHOENIX_PROJECT_NAME", "finanzas"),
                verbose=False,
            )
            LangChainInstrumentor().instrument(tracer_provider=_provider)
        except Exception as error:  # noqa: BLE001 - tracing must never break a run
            _provider = None
            print(
                f"Aviso: no se pudo activar Phoenix ({error}); se continúa sin trazas.",
                file=sys.stderr,
            )


def construir_config(thread_id: str | None = None, recursion_limit: int = 1000) -> dict[str, Any]:
    """Return the RunnableConfig to pass to invoke().

    - recursion_limit: high, because the enrichment loop takes many turns.
    - configurable.thread_id when given (the consultant needs it).
    Tracing is attached globally through OpenInference, so no callback is needed here.
    """
    _registrar_phoenix()
    config: dict[str, Any] = {"recursion_limit": recursion_limit}
    if thread_id is not None:
        config["configurable"] = {"thread_id": thread_id}
    return config


def vaciar_trazas() -> None:
    """Flush pending spans before the process exits. No-op when Phoenix is not active."""
    if _provider is None:
        return
    try:
        _provider.force_flush(timeout_millis=FLUSH_TIMEOUT_MS)
    except Exception as error:  # noqa: BLE001
        print(f"Aviso: no se pudieron enviar las trazas a Phoenix ({error}).", file=sys.stderr)
