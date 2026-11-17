"""Root graph: modes `procesar` (ingestion) and `reenriquecer` (re-enrichment by date range).

Both modes always end with the analysis of the affected periods.
"""

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from finanzas.grafos.analisis import construir_grafo_analisis
from finanzas.grafos.comunes import nodo_comprobar_pendientes, nodo_inicializar_bd
from finanzas.grafos.ingesta.enriquecimiento import construir_grafo_enriquecimiento
from finanzas.grafos.ingesta.grafo import construir_grafo_ingesta
from finanzas.modelos.dominio import FiltroEnriquecimiento, ResumenEnriquecimiento
from finanzas.modelos.estados import EstadoRaiz
from finanzas.trazas import traza

_GRAFO = "raiz"

_grafo_ingesta = construir_grafo_ingesta()
_grafo_enriquecimiento = construir_grafo_enriquecimiento()
_grafo_analisis = construir_grafo_analisis()


def nodo_ingesta(state: EstadoRaiz, config: RunnableConfig) -> dict:
    traza(_GRAFO, "ingesta")
    salida = _grafo_ingesta.invoke({}, config)
    resultados = salida.get("resultados", [])
    resumen_ingesta: dict[str, int] = {}
    for r in resultados:
        resumen_ingesta[r.estado] = resumen_ingesta.get(r.estado, 0) + 1
    return {
        "periodos_afectados": salida.get("periodos_afectados", []),
        "resumen_ingesta": resumen_ingesta,
        "resumen_enriquecimiento": salida.get("resumen_enriquecimiento"),
        "avisos": salida.get("avisos", []),
    }


def nodo_reenriquecimiento(state: EstadoRaiz, config: RunnableConfig) -> dict:
    traza(_GRAFO, "reenriquecimiento")
    filtro: FiltroEnriquecimiento = state["filtro_reenriquecimiento"]
    salida = _grafo_enriquecimiento.invoke(
        {"filtro": filtro, "cursor_id": 0, "resumen": ResumenEnriquecimiento()},
        config,
    )
    resumen = salida["resumen"]
    return {
        "resumen_enriquecimiento": resumen,
        "periodos_afectados": resumen.periodos_afectados,
    }


def nodo_marcar_obsoletos(state: EstadoRaiz) -> dict:
    traza(_GRAFO, "marcar_obsoletos")
    # Future: UPDATE resumenes SET estado='obsoleto' WHERE periodo IN (periodos_afectados).
    # It is a safety net: if the later analysis fails, the consultor knows the summaries
    # are no longer aligned with the labels.
    return {}


def nodo_analisis(state: EstadoRaiz, config: RunnableConfig) -> dict:
    traza(_GRAFO, "analisis")
    salida = _grafo_analisis.invoke(
        {"periodos_entrada": state.get("periodos_afectados", [])}, config
    )
    return {"resumenes_generados": salida.get("rutas_publicadas", [])}


def nodo_cerrar(state: EstadoRaiz) -> dict:
    traza(_GRAFO, "cerrar")
    # Dummy: prints a readable final summary.
    print("--- Resumen final ---")
    print(f"Modo: {state.get('modo')}")
    for aviso in state.get("avisos", []):
        print(f"Aviso: {aviso}")
    print(f"Ficheros: {state.get('resumen_ingesta', {})}")
    resumen = state.get("resumen_enriquecimiento")
    if resumen is not None:
        print(f"Operaciones enriquecidas: {resumen.enriquecidas}")
    print(f"Resúmenes generados: {len(state.get('resumenes_generados', []))}")
    return {}


def construir_grafo_raiz():
    """Build and compile the root graph."""
    builder = StateGraph(EstadoRaiz)
    builder.add_node("inicializar_bd", nodo_inicializar_bd)
    builder.add_node("comprobar_pendientes", nodo_comprobar_pendientes)
    builder.add_node("ingesta", nodo_ingesta)
    builder.add_node("reenriquecimiento", nodo_reenriquecimiento)
    builder.add_node("marcar_obsoletos", nodo_marcar_obsoletos)
    builder.add_node("analisis", nodo_analisis)
    builder.add_node("cerrar", nodo_cerrar)

    builder.add_edge(START, "inicializar_bd")
    builder.add_edge("inicializar_bd", "comprobar_pendientes")
    builder.add_conditional_edges(
        "comprobar_pendientes",
        lambda s: "ingesta" if s["modo"] == "procesar" else "reenriquecimiento",
        ["ingesta", "reenriquecimiento"],
    )
    builder.add_edge("ingesta", "analisis")
    builder.add_edge("reenriquecimiento", "marcar_obsoletos")
    builder.add_edge("marcar_obsoletos", "analisis")
    builder.add_edge("analisis", "cerrar")
    builder.add_edge("cerrar", END)
    return builder.compile()
