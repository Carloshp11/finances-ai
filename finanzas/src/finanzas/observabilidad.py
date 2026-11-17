"""Run configuration and optional Langfuse tracing.

Traces are sent ONLY when both LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set in the
environment. Without them nothing leaves the machine. Credentials are never read from
settings.yaml. Langfuse must also be pointed at a local or self-hosted instance through
LANGFUSE_HOST or LANGFUSE_BASE_URL, in line with the project rule that data stays local.
"""

import os
import sys
from typing import Any

_HANDLER_ACTIVO = False


def _langfuse_configurado() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


def construir_config(thread_id: str | None = None, recursion_limit: int = 1000) -> dict[str, Any]:
    """Return the RunnableConfig to pass to invoke().

    - callbacks: [Langfuse handler] when Langfuse is configured; [] otherwise.
    - recursion_limit: high, because the enrichment loop takes many turns.
    - configurable.thread_id when given (the consultor needs it).
    """
    global _HANDLER_ACTIVO
    callbacks: list[Any] = []
    if _langfuse_configurado():
        try:
            from langfuse.langchain import CallbackHandler

            callbacks.append(CallbackHandler())
            _HANDLER_ACTIVO = True
        except Exception as error:  # noqa: BLE001 - tracing must never break a run
            print(f"Aviso: no se pudo activar Langfuse ({error}); se continúa sin trazas.",
                  file=sys.stderr)

    config: dict[str, Any] = {"callbacks": callbacks, "recursion_limit": recursion_limit}
    if thread_id is not None:
        config["configurable"] = {"thread_id": thread_id}
    return config


def vaciar_trazas() -> None:
    """Send pending Langfuse traces before the process exits. No-op without a handler."""
    global _HANDLER_ACTIVO
    if not _HANDLER_ACTIVO:
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception as error:  # noqa: BLE001
        print(f"Aviso: no se pudieron enviar las trazas de Langfuse ({error}).", file=sys.stderr)
