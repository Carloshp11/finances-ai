"""Tracing must never block or break a run when Phoenix is unreachable."""

import socket
import time

from finanzas import observabilidad


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_collector_inaccesible_devuelve_false():
    assert (
        observabilidad._collector_accesible(f"http://127.0.0.1:{_puerto_libre()}/v1/traces")
        is False
    )


def test_collector_accesible_devuelve_true():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        puerto = s.getsockname()[1]
        assert observabilidad._collector_accesible(f"http://127.0.0.1:{puerto}/v1/traces") is True


def test_registro_sin_phoenix_continua_sin_trazas(monkeypatch, capsys):
    monkeypatch.setenv("PHOENIX_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv(
        "PHOENIX_COLLECTOR_ENDPOINT", f"http://127.0.0.1:{_puerto_libre()}/v1/traces"
    )
    monkeypatch.setattr(observabilidad, "_intentado", False)
    monkeypatch.setattr(observabilidad, "_provider", None)

    inicio = time.monotonic()
    observabilidad._registrar_phoenix()
    observabilidad.vaciar_trazas()

    assert time.monotonic() - inicio < 5
    assert observabilidad._provider is None
    assert "Phoenix no responde" in capsys.readouterr().err
