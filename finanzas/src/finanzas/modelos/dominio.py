"""Domain models: the data contracts passed between nodes and written to the database."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

FormatoFichero = Literal["csv", "tsv", "desconocido"]
EstadoFichero = Literal["pendiente", "en_proceso", "procesado", "error", "pendiente_confirmacion"]
TipoTransferencia = Literal["ninguna", "interna_propia", "entre_personas"]


class FicheroDetectado(BaseModel):
    usuario: str
    ruta: str  # relative to rutas.inputs, e.g. "carlos/extracto_2026_10.csv"
    sha256: str
    formato: FormatoFichero
    tamano_bytes: int


class FormatoExtracto(BaseModel):
    """Column mapping for one specific bank onto the canonical columns."""

    firma_cabecera: str
    delimitador: str  # "," | ";" | "\t"
    codificacion: str = "utf-8"
    filas_a_saltar: int = 0
    columna_fecha: str
    columna_fecha_valor: str | None = None
    columna_importe: str | None = None  # signed amount in a single column
    columna_cargo: str | None = None  # or debit/credit in separate columns
    columna_abono: str | None = None
    columna_concepto: str
    columna_saldo: str | None = None
    columna_iban_contraparte: str | None = None  # TODO(P2)
    formato_fecha: str = "%d/%m/%Y"
    separador_decimal: str = ","
    separador_miles: str = "."
    confirmado: bool = False


class Operacion(BaseModel):
    usuario: str
    cuenta_iban: str | None = None  # TODO(P2)
    fecha: date
    fecha_valor: date | None = None
    importe_centimos: int  # negative = debit
    saldo_posterior_centimos: int | None = None
    moneda: str = "EUR"
    concepto_original: str
    iban_contraparte: str | None = None  # TODO(P2)
    fichero_sha256: str
    hash_operacion: str


class ResultadoExtraccion(BaseModel):
    fichero_sha256: str
    ruta: str
    estado: Literal["procesado", "error", "pendiente_confirmacion"]
    n_operaciones: int = 0
    errores: list[str] = Field(default_factory=list)
    periodos: list[str] = Field(default_factory=list)  # weeks and months touched


class OperacionAEnriquecer(BaseModel):
    id: int
    fecha: date
    importe_centimos: int
    concepto_original: str


class EnriquecimientoOperacion(BaseModel):
    """Structured output the LLM must return for each operation."""

    id: int
    concepto_limpio: str
    categoria: str  # must exist in the categorias table
    etiqueta_libre: str


class FiltroEnriquecimiento(BaseModel):
    modo: Literal["pendientes", "rango"]
    desde: date | None = None
    hasta: date | None = None
    usuario: str | None = None


class ResumenEnriquecimiento(BaseModel):
    lotes: int = 0
    enriquecidas: int = 0
    fallidas: int = 0
    periodos_afectados: list[str] = Field(default_factory=list)


class MetricasPeriodo(BaseModel):
    tipo: Literal["semana", "mes"]
    periodo: str
    ambito: str  # "hogar" or a user name
    ingresos_centimos: int = 0
    gastos_centimos: int = 0  # positive value
    neto_centimos: int = 0
    por_categoria: dict[str, int] = Field(default_factory=dict)
    n_operaciones: int = 0


class Resumen(BaseModel):
    tipo: Literal["semana", "mes"]
    periodo: str
    ambito: str
    contenido_md: str
    metricas: MetricasPeriodo
