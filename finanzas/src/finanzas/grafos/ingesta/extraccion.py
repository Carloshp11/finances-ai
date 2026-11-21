"""S1.1 subgraph: extraction of one bank statement file (one run per file).

Most node logic is DUMMY: it prints a trace and returns fixed example values
with the correct state shape. See the plan for the future logic of each node.
"""

from datetime import date

from langgraph.graph import END, START, StateGraph

from finanzas.modelos.dominio import (
    FormatoExtracto,
    Operacion,
    ResultadoExtraccion,
)
from finanzas.modelos.estados import EstadoExtraccion
from finanzas.trazas import traza
from finanzas.utilidades import (
    calcular_firma_cabecera,
    calcular_hash_operacion,
    periodos_de_fechas,
)

_GRAFO = "extraccion"


def marcar_en_proceso(state: EstadoExtraccion) -> dict:
    traza(_GRAFO, "marcar_en_proceso")
    # Future: UPSERT into `ficheros` with estado='en_proceso'.
    return {}


def leer_fichero(state: EstadoExtraccion) -> dict:
    traza(_GRAFO, "leer_fichero")
    # TODO(P1): the origin of the statements is not confirmed (CSV/XLSX export or an
    # aggregator). Future: detect delimiter and encoding and read with pandas.
    return {
        "cabecera": ["Fecha", "Concepto", "Importe", "Saldo"],
        "filas_crudas": [
            {
                "Fecha": "03/11/2026",
                "Concepto": "COMPRA TARJ MERCADONA",
                "Importe": "-45,30",
                "Saldo": "1.200,00",
            },
            {
                "Fecha": "05/11/2026",
                "Concepto": "NOMINA",
                "Importe": "2.000,00",
                "Saldo": "3.200,00",
            },
        ],
    }


def resolver_formato(state: EstadoExtraccion) -> dict:
    traza(_GRAFO, "resolver_formato")
    # The signature is REAL (cheap). The LLM mapping is DUMMY.
    # Future: look the signature up in `formatos_extracto`; if it is unknown, the LLM proposes
    # a mapping from settings.formato.filas_muestra rows and it is stored with
    # confirmado = not settings.formato.requiere_confirmacion.
    # TODO(P4): confirmation of new formats by hand.
    firma = calcular_firma_cabecera(state["cabecera"])
    formato = FormatoExtracto(
        firma_cabecera=firma,
        delimitador=";",
        columna_fecha="Fecha",
        columna_importe="Importe",
        columna_concepto="Concepto",
        columna_saldo="Saldo",
        confirmado=True,
    )
    return {
        "firma_cabecera": firma,
        "formato": formato,
        "formato_ok": formato.confirmado,
    }


def normalizar(state: EstadoExtraccion) -> dict:
    traza(_GRAFO, "normalizar")
    # Future: parse dates, decimals and signs according to `formato`.
    # TODO(P2): resolve cuenta_iban.
    fichero = state["fichero"]
    datos = [
        (date(2026, 11, 3), -4530, "COMPRA TARJ MERCADONA"),
        (date(2026, 11, 5), 200000, "NOMINA"),
    ]
    operaciones = [
        Operacion(
            usuario=fichero.usuario,
            cuenta_iban=None,  # TODO(P2)
            fecha=fecha,
            importe_centimos=importe,
            concepto_original=concepto,
            fichero_sha256=fichero.sha256,
            hash_operacion=calcular_hash_operacion(None, fecha, importe, concepto, 0),
        )
        for fecha, importe, concepto in datos
    ]
    return {"operaciones": operaciones}


def validar(state: EstadoExtraccion) -> dict:
    traza(_GRAFO, "validar")
    # Future: schema, reasonable dates, balance check (previous balance + amount = balance)
    # when a balance column exists.
    return {"errores_validacion": []}


def persistir(state: EstadoExtraccion) -> dict:
    traza(_GRAFO, "persistir")
    # Future: ONE transaction: INSERT OR IGNORE of operaciones (by hash_operacion)
    # plus ficheros.estado='procesado'.
    operaciones = state["operaciones"]
    resultado = ResultadoExtraccion(
        fichero_sha256=state["fichero"].sha256,
        ruta=state["fichero"].ruta,
        estado="procesado",
        n_operaciones=len(operaciones),
        periodos=periodos_de_fechas(op.fecha for op in operaciones),
    )
    return {"resultado": resultado}


def marcar_error(state: EstadoExtraccion) -> dict:
    traza(_GRAFO, "marcar_error")
    # Future: ficheros.estado='error' and ficheros.error=...
    resultado = ResultadoExtraccion(
        fichero_sha256=state["fichero"].sha256,
        ruta=state["fichero"].ruta,
        estado="error",
        errores=state.get("errores_validacion", []),
    )
    return {"resultado": resultado}


def marcar_pendiente_confirmacion(state: EstadoExtraccion) -> dict:
    traza(_GRAFO, "marcar_pendiente_confirmacion")
    firma = state.get("firma_cabecera", "")
    resultado = ResultadoExtraccion(
        fichero_sha256=state["fichero"].sha256,
        ruta=state["fichero"].ruta,
        estado="pendiente_confirmacion",
        errores=[f"Formato nuevo pendiente de confirmar: {firma}"],
    )
    return {"resultado": resultado}


def construir_grafo_extraccion():
    """Build and compile the per-file extraction subgraph."""
    builder = StateGraph(EstadoExtraccion)
    builder.add_node("marcar_en_proceso", marcar_en_proceso)
    builder.add_node("leer_fichero", leer_fichero)
    builder.add_node("resolver_formato", resolver_formato)
    builder.add_node("normalizar", normalizar)
    builder.add_node("validar", validar)
    builder.add_node("persistir", persistir)
    builder.add_node("marcar_error", marcar_error)
    builder.add_node("marcar_pendiente_confirmacion", marcar_pendiente_confirmacion)

    builder.add_edge(START, "marcar_en_proceso")
    builder.add_edge("marcar_en_proceso", "leer_fichero")
    builder.add_edge("leer_fichero", "resolver_formato")
    builder.add_conditional_edges(
        "resolver_formato",
        lambda s: "normalizar" if s.get("formato_ok") else "marcar_pendiente_confirmacion",
        ["normalizar", "marcar_pendiente_confirmacion"],
    )
    builder.add_edge("normalizar", "validar")
    builder.add_conditional_edges(
        "validar",
        lambda s: "persistir" if not s.get("errores_validacion") else "marcar_error",
        ["persistir", "marcar_error"],
    )
    builder.add_edge("persistir", END)
    builder.add_edge("marcar_error", END)
    builder.add_edge("marcar_pendiente_confirmacion", END)
    return builder.compile()
