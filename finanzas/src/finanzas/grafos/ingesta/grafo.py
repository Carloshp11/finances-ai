"""S1 subgraph: ingestion, with a parallel fan-out of one extraction per file.

Node logic is DUMMY except for the structure: the fan-out with Send, the subgraph calls
and the consolidation of results. See the plan for the future logic.
"""

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from finanzas.config import cargar_settings
from finanzas.grafos.ingesta.enriquecimiento import construir_grafo_enriquecimiento
from finanzas.grafos.ingesta.extraccion import construir_grafo_extraccion
from finanzas.modelos.dominio import (
    FicheroDetectado,
    FiltroEnriquecimiento,
    ResumenEnriquecimiento,
)
from finanzas.modelos.estados import EstadoIngesta
from finanzas.trazas import traza
from finanzas.utilidades import escanear_carpeta

_GRAFO = "ingesta"

_grafo_extraccion = construir_grafo_extraccion()
_grafo_enriquecimiento = construir_grafo_enriquecimiento()


def recuperar_en_proceso(state: EstadoIngesta) -> dict:
    traza(_GRAFO, "recuperar_en_proceso")
    # Future: UPDATE ficheros SET estado='pendiente' WHERE estado='en_proceso', with a warning
    # for each file resumed.
    return {"avisos": []}


def escanear_inputs(state: EstadoIngesta) -> dict:
    traza(_GRAFO, "escanear_inputs")
    # Each subfolder of rutas.inputs is a user. TODO(P1): PDF is not supported yet.
    detectados, avisos = escanear_carpeta(cargar_settings().rutas.inputs)
    return {"ficheros_detectados": detectados, "avisos": avisos}


def filtrar_pendientes(state: EstadoIngesta) -> dict:
    traza(_GRAFO, "filtrar_pendientes")
    # Future: drop files whose sha256 is already 'procesado' or 'pendiente_confirmacion' in the DB.
    return {"ficheros_pendientes": list(state.get("ficheros_detectados", []))}


def repartir_ficheros(state: EstadoIngesta):
    """Conditional edge: one Send per pending file, or straight to consolidar."""
    pendientes = state.get("ficheros_pendientes", [])
    if not pendientes:
        return "consolidar"
    return [Send("procesar_fichero", {"fichero": f}) for f in pendientes]


def procesar_fichero(payload: dict, config: RunnableConfig) -> dict:
    """Receives the payload of the Send (NOT the whole EstadoIngesta)."""
    fichero: FicheroDetectado = payload["fichero"]
    traza(_GRAFO, "procesar_fichero", fichero.ruta)
    salida = _grafo_extraccion.invoke({"fichero": fichero}, config)
    return {"resultados": [salida["resultado"]]}  # the operator.add reducer accumulates


def consolidar(state: EstadoIngesta) -> dict:
    traza(_GRAFO, "consolidar")
    # Future: classify tipo_transferencia of the new operations. If iban_contraparte is in
    # `cuentas`: same user -> interna_propia, other user -> entre_personas. Fallback without a
    # counterparty IBAN: match opposite amounts within ventana_dias_emparejamiento days
    # between configured accounts. TODO(P2).
    resultados = state.get("resultados", [])
    periodos = sorted({p for r in resultados for p in r.periodos})
    avisos = [
        f"{r.ruta}: {r.estado} {' '.join(r.errores)}".rstrip()
        for r in resultados
        if r.estado in ("error", "pendiente_confirmacion")
    ]
    return {
        "n_transferencias_internas": 0,  # dummy
        "periodos_afectados": periodos,
        "avisos": avisos,
    }


def enriquecer(state: EstadoIngesta, config: RunnableConfig) -> dict:
    traza(_GRAFO, "enriquecer")
    salida = _grafo_enriquecimiento.invoke(
        {
            "filtro": FiltroEnriquecimiento(modo="pendientes"),
            "cursor_id": 0,
            "resumen": ResumenEnriquecimiento(),
        },
        config,
    )
    resumen = salida["resumen"]
    periodos = sorted(set(state.get("periodos_afectados", [])) | set(resumen.periodos_afectados))
    return {"resumen_enriquecimiento": resumen, "periodos_afectados": periodos}


def construir_grafo_ingesta():
    """Build and compile the ingestion subgraph."""
    builder = StateGraph(EstadoIngesta)
    builder.add_node("recuperar_en_proceso", recuperar_en_proceso)
    builder.add_node("escanear_inputs", escanear_inputs)
    builder.add_node("filtrar_pendientes", filtrar_pendientes)
    builder.add_node("procesar_fichero", procesar_fichero)
    builder.add_node("consolidar", consolidar)
    builder.add_node("enriquecer", enriquecer)

    builder.add_edge(START, "recuperar_en_proceso")
    builder.add_edge("recuperar_en_proceso", "escanear_inputs")
    builder.add_edge("escanear_inputs", "filtrar_pendientes")
    builder.add_conditional_edges(
        "filtrar_pendientes", repartir_ficheros, ["procesar_fichero", "consolidar"]
    )
    builder.add_edge("procesar_fichero", "consolidar")  # consolidar waits for ALL branches
    builder.add_edge("consolidar", "enriquecer")
    builder.add_edge("enriquecer", END)
    return builder.compile()
