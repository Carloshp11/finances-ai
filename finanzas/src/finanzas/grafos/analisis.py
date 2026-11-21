"""S2 subgraph: periodic metrics and summaries (week and month).

Node logic is DUMMY, except for `publicar`, which computes the real output paths. Nothing is
written to disk and nothing is stored in the database yet.
"""

from langgraph.graph import END, START, StateGraph

from finanzas.config import cargar_settings
from finanzas.modelos.dominio import MetricasPeriodo, Resumen
from finanzas.modelos.estados import EstadoAnalisis
from finanzas.trazas import traza

_GRAFO = "analisis"


def determinar_periodos(state: EstadoAnalisis) -> dict:
    traza(_GRAFO, "determinar_periodos")
    # Future: de-duplicate, and when a week crosses two months make sure both months are
    # recalculated.
    entrada = list(state.get("periodos_entrada", []))
    return {"periodos": entrada or ["2026-11"]}


def calcular_metricas(state: EstadoAnalisis) -> dict:
    traza(_GRAFO, "calcular_metricas")
    # Future: deterministic SQL per period and scope (`hogar` plus each user). In `hogar`
    # exclude interna_propia and entre_personas; per user exclude only interna_propia.
    metricas = [
        MetricasPeriodo(
            tipo="semana" if "-W" in periodo else "mes",
            periodo=periodo,
            ambito="hogar",
            ingresos_centimos=200000,
            gastos_centimos=4530,
            neto_centimos=195470,
            por_categoria={"supermercado": 4530},
            n_operaciones=2,
        )
        for periodo in state.get("periodos", [])
    ]
    return {"metricas": metricas}


def redactar_resumenes(state: EstadoAnalisis) -> dict:
    traza(_GRAFO, "redactar_resumenes")
    # Future: LLM (settings.analisis.modelo) that writes FROM THE METRICS, never from raw
    # operations.
    resumenes = [
        Resumen(
            tipo=m.tipo,
            periodo=m.periodo,
            ambito=m.ambito,
            contenido_md=f"# Resumen {m.tipo} {m.periodo} ({m.ambito})\n\n(dummy)",
            metricas=m,
        )
        for m in state.get("metricas", [])
    ]
    return {"resumenes": resumenes}


def publicar(state: EstadoAnalisis) -> dict:
    traza(_GRAFO, "publicar")
    # The paths are REAL but nothing is written yet.
    # Future: UPSERT into `resumenes` with estado='vigente' and write the .md file.
    carpeta = cargar_settings().rutas.ruta_resumenes
    rutas = [
        str(carpeta / r.tipo / f"{r.periodo}_{r.ambito}.md") for r in state.get("resumenes", [])
    ]
    return {"rutas_publicadas": rutas}


def construir_grafo_analisis():
    """Build and compile the analysis subgraph."""
    builder = StateGraph(EstadoAnalisis)
    builder.add_node("determinar_periodos", determinar_periodos)
    builder.add_node("calcular_metricas", calcular_metricas)
    builder.add_node("redactar_resumenes", redactar_resumenes)
    builder.add_node("publicar", publicar)
    builder.add_edge(START, "determinar_periodos")
    builder.add_edge("determinar_periodos", "calcular_metricas")
    builder.add_edge("calcular_metricas", "redactar_resumenes")
    builder.add_edge("redactar_resumenes", "publicar")
    builder.add_edge("publicar", END)
    return builder.compile()
