"""State TypedDicts for the LangGraph graphs.

Fields annotated with operator.add (or add_messages) are reducers: parallel branches
accumulate into them instead of overwriting each other.
"""

import operator
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from finanzas.modelos.dominio import (
    EnriquecimientoOperacion,
    FicheroDetectado,
    FiltroEnriquecimiento,
    FormatoExtracto,
    MetricasPeriodo,
    Operacion,
    OperacionAEnriquecer,
    ResultadoExtraccion,
    Resumen,
    ResumenEnriquecimiento,
)


class EstadoRaiz(TypedDict, total=False):
    modo: Literal["procesar", "reenriquecer"]
    filtro_reenriquecimiento: FiltroEnriquecimiento | None
    avisos: Annotated[list[str], operator.add]
    periodos_afectados: list[str]
    resumen_ingesta: dict
    resumen_enriquecimiento: ResumenEnriquecimiento | None
    resumenes_generados: list[str]


class EstadoIngesta(TypedDict, total=False):
    ficheros_detectados: list[FicheroDetectado]
    ficheros_pendientes: list[FicheroDetectado]
    resultados: Annotated[list[ResultadoExtraccion], operator.add]  # reducer: fan-out
    n_transferencias_internas: int
    resumen_enriquecimiento: ResumenEnriquecimiento | None
    periodos_afectados: list[str]
    avisos: Annotated[list[str], operator.add]


class EstadoExtraccion(TypedDict, total=False):
    fichero: FicheroDetectado
    filas_crudas: list[dict]
    cabecera: list[str]
    firma_cabecera: str
    formato: FormatoExtracto | None
    formato_ok: bool
    operaciones: list[Operacion]
    errores_validacion: list[str]
    resultado: ResultadoExtraccion


class EstadoEnriquecimiento(TypedDict, total=False):
    filtro: FiltroEnriquecimiento
    cursor_id: int  # last operation id processed
    lote_actual: list[OperacionAEnriquecer]
    salida_lote: list[EnriquecimientoOperacion]
    resumen: ResumenEnriquecimiento


class EstadoAnalisis(TypedDict, total=False):
    periodos_entrada: list[str]  # what arrives from ingestion or re-enrichment
    periodos: list[str]  # weeks and months to recalculate (normalised)
    metricas: list[MetricasPeriodo]
    resumenes: list[Resumen]
    rutas_publicadas: list[str]


class EstadoConsultor(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    aviso_inicial: str | None
