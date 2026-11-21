"""Smoke tests for the graphs and the database. They never touch the real data/finanzas.db."""

import sqlite3
from datetime import date

import pytest
from finanzas.config import cargar_settings
from finanzas.db.conexion import inicializar_bd
from finanzas.grafos.consultor.grafo import construir_grafo_consultor
from finanzas.grafos.ingesta.enriquecimiento import construir_grafo_enriquecimiento
from finanzas.grafos.ingesta.extraccion import construir_grafo_extraccion
from finanzas.grafos.ingesta.grafo import construir_grafo_ingesta
from finanzas.grafos.raiz import construir_grafo_raiz
from finanzas.modelos.dominio import FicheroDetectado, FiltroEnriquecimiento, ResumenEnriquecimiento
from finanzas.observabilidad import construir_config
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

TABLAS_ESPERADAS = {
    "ficheros",
    "formatos_extracto",
    "cuentas",
    "categorias",
    "operaciones",
    "resumenes",
}


@pytest.fixture(autouse=True)
def bd_temporal(tmp_path, monkeypatch):
    """Point the database at a temporary file for every test."""
    ruta = tmp_path / "test.db"
    monkeypatch.setenv("FINANZAS_RUTAS__BASE_DATOS", str(ruta))
    # Tests must not send spans to a Phoenix collector.
    monkeypatch.setenv("PHOENIX_TELEMETRY_ENABLED", "false")
    return ruta


def test_inicializar_bd_idempotente(bd_temporal):
    settings = cargar_settings()
    inicializar_bd(settings)
    inicializar_bd(settings)  # second call must not fail

    conn = sqlite3.connect(bd_temporal)
    tablas = {fila[0] for fila in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    n_categorias = conn.execute("SELECT COUNT(*) FROM categorias").fetchone()[0]
    conn.close()

    assert TABLAS_ESPERADAS <= tablas  # sqlite_sequence also exists (AUTOINCREMENT)
    assert n_categorias == 15


def test_extraccion_dummy():
    salida = construir_grafo_extraccion().invoke(
        {
            "fichero": FicheroDetectado(
                usuario="carlos", ruta="carlos/x.csv", sha256="a", formato="csv", tamano_bytes=10
            )
        }
    )
    assert salida["resultado"].estado == "procesado"
    assert salida["resultado"].n_operaciones == 2


def test_enriquecimiento_termina():
    salida = construir_grafo_enriquecimiento().invoke(
        {
            "filtro": FiltroEnriquecimiento(modo="pendientes"),
            "cursor_id": 0,
            "resumen": ResumenEnriquecimiento(),
        },
        construir_config(),
    )
    assert salida["resumen"].lotes == 2


def test_ingesta_fanout():
    salida = construir_grafo_ingesta().invoke({}, construir_config())
    assert len(salida["resultados"]) == 2


def test_raiz_procesar():
    salida = construir_grafo_raiz().invoke({"modo": "procesar"}, construir_config())
    assert salida["resumenes_generados"]


def test_raiz_reenriquecer_no_pasa_por_ingesta(capsys):
    filtro = FiltroEnriquecimiento(modo="rango", desde=date(2026, 10, 1), hasta=date(2026, 11, 15))
    construir_grafo_raiz().invoke(
        {"modo": "reenriquecer", "filtro_reenriquecimiento": filtro}, construir_config()
    )
    salida = capsys.readouterr().out
    assert "ingesta." not in salida
    assert "raiz.marcar_obsoletos" in salida


def test_consultor_memoria():
    grafo = construir_grafo_consultor(InMemorySaver())
    cfg = construir_config(thread_id="memoria")
    grafo.invoke({"messages": [HumanMessage("hola")]}, cfg)
    grafo.invoke({"messages": [HumanMessage("/tool")]}, cfg)
    # hola, respuesta, /tool, llamada a herramienta, resultado, respuesta final
    assert len(grafo.get_state(cfg).values["messages"]) == 6


def test_consultor_tool():
    grafo = construir_grafo_consultor(InMemorySaver())
    cfg = construir_config(thread_id="herramienta")
    grafo.invoke({"messages": [HumanMessage("/tool")]}, cfg)
    mensajes = grafo.get_state(cfg).values["messages"]
    assert any(isinstance(m, ToolMessage) for m in mensajes)
