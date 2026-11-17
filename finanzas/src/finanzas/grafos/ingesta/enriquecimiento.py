"""S1.2 subgraph: enrichment of operations in batches (a loop with a cursor).

It is used in two places:
- from ingestion, with filtro.modo="pendientes";
- from re-enrichment, with filtro.modo="rango".

The cursor (cursor_id) pages through the rows in both modes, so the same rows are never
selected forever. Node logic is DUMMY: it always runs two batches and then stops.
"""

from datetime import date

from langgraph.graph import END, START, StateGraph

from finanzas.modelos.dominio import (
    EnriquecimientoOperacion,
    OperacionAEnriquecer,
    ResumenEnriquecimiento,
)
from finanzas.modelos.estados import EstadoEnriquecimiento
from finanzas.trazas import traza
from finanzas.utilidades import periodos_de_fechas

_GRAFO = "enriquecimiento"
_LOTES_DUMMY = 2  # the dummy loop runs this many batches, then stops


def seleccionar_lote(state: EstadoEnriquecimiento) -> dict:
    traza(_GRAFO, "seleccionar_lote")
    # Future: SELECT according to `filtro` and the cursor:
    #   WHERE id > cursor_id ORDER BY id LIMIT settings.enriquecimiento.tamano_lote
    # and, for modo="pendientes", enriquecida_en IS NULL and intentos < max_reintentos.
    resumen = state.get("resumen") or ResumenEnriquecimiento()
    cursor = state.get("cursor_id", 0)
    if resumen.lotes < _LOTES_DUMMY:
        lote = [
            OperacionAEnriquecer(
                id=cursor + 1,
                fecha=date(2026, 11, 3),
                importe_centimos=-4530,
                concepto_original="COMPRA TARJ MERCADONA",
            ),
            OperacionAEnriquecer(
                id=cursor + 2,
                fecha=date(2026, 11, 5),
                importe_centimos=200000,
                concepto_original="NOMINA",
            ),
        ]
    else:
        lote = []
    return {"lote_actual": lote}


def enriquecer_lote(state: EstadoEnriquecimiento) -> dict:
    traza(_GRAFO, "enriquecer_lote")
    # Future: serialise the batch to JSONL (id, fecha, importe_eur, concepto), prompt with the
    # active categories and their descriptions, structured output list[EnriquecimientoOperacion].
    # Validate each categoria against the table (fallback "otros"), normalise etiqueta_libre
    # with normalizar_texto, retry up to max_reintentos, then salida_lote=[] on failure.
    salida = [
        EnriquecimientoOperacion(
            id=op.id,
            concepto_limpio="dummy",
            categoria="otros",
            etiqueta_libre="dummy",
        )
        for op in state.get("lote_actual", [])
    ]
    return {"salida_lote": salida}


def persistir_lote(state: EstadoEnriquecimiento) -> dict:
    traza(_GRAFO, "persistir_lote")
    # Future: ONE transaction per batch: UPDATE concepto_limpio, categoria, etiqueta_libre,
    # enriquecida_en=now, enriquecida_con="<modelo>|<version_prompt>". Operations in the batch
    # without output get intentos_enriquecimiento += 1 and count as `fallidas`.
    lote = state.get("lote_actual", [])
    resumen = state.get("resumen") or ResumenEnriquecimiento()
    salida = state.get("salida_lote", [])
    periodos_lote = periodos_de_fechas(op.fecha for op in lote)
    periodos = sorted(set(resumen.periodos_afectados) | set(periodos_lote))
    nuevo_resumen = resumen.model_copy(
        update={
            "lotes": resumen.lotes + 1,
            "enriquecidas": resumen.enriquecidas + len(salida),
            "fallidas": resumen.fallidas + (len(lote) - len(salida)),
            "periodos_afectados": periodos,
        }
    )
    cursor = max((op.id for op in lote), default=state.get("cursor_id", 0))
    return {"cursor_id": cursor, "resumen": nuevo_resumen}


def construir_grafo_enriquecimiento():
    """Build and compile the batch-enrichment subgraph."""
    builder = StateGraph(EstadoEnriquecimiento)
    builder.add_node("seleccionar_lote", seleccionar_lote)
    builder.add_node("enriquecer_lote", enriquecer_lote)
    builder.add_node("persistir_lote", persistir_lote)

    builder.add_edge(START, "seleccionar_lote")
    builder.add_conditional_edges(
        "seleccionar_lote",
        lambda s: "enriquecer_lote" if s.get("lote_actual") else END,
        ["enriquecer_lote", END],
    )
    builder.add_edge("enriquecer_lote", "persistir_lote")
    builder.add_edge("persistir_lote", "seleccionar_lote")
    return builder.compile()
