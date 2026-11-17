"""Consultor tools. All are STUBS: each prints a trace and returns a fixed text.

The docstrings are complete because the LLM will read them in the future.
"""

from typing import Literal

from langchain_core.tools import tool

from finanzas.trazas import traza

_GRAFO = "consultor"


@tool
def leer_resumen(tipo: Literal["semana", "mes"], periodo: str, ambito: str = "hogar") -> str:
    """Return the markdown summary for one period. periodo: '2026-W46' or '2026-11'.
    ambito: 'hogar' or a user's name. Says whether the summary is outdated."""
    traza(_GRAFO, "leer_resumen")
    return f"(dummy) Resumen {tipo} {periodo} {ambito}"


@tool
def metricas(desde: str, hasta: str, ambito: str = "hogar", categoria: str | None = None) -> str:
    """Totals of income, expenses and net between two dates (YYYY-MM-DD), optionally by category."""
    traza(_GRAFO, "metricas")
    return f"(dummy) Métricas de {desde} a {hasta} ({ambito})"


@tool
def buscar_operaciones(
    desde: str,
    hasta: str,
    texto: str | None = None,
    categoria: str | None = None,
    usuario: str | None = None,
    limite: int = 50,
) -> str:
    """List operations that match the filters. For detailed questions."""
    traza(_GRAFO, "buscar_operaciones")
    return "(dummy) Operaciones encontradas: 0"


@tool
def listar_categorias() -> str:
    """Closed list of categories and their descriptions."""
    traza(_GRAFO, "listar_categorias")
    return "(dummy) Categorías: otros"


@tool
def consulta_sql_lectura(sql: str) -> str:
    """Run a READ-ONLY SQL query against the database. SELECT only."""
    traza(_GRAFO, "consulta_sql_lectura")
    # Future: reject anything not starting with SELECT; open the database read-only
    # (sqlite3.connect('file:...?mode=ro', uri=True)); limit the rows returned.
    return "(dummy) Consulta no ejecutada"


HERRAMIENTAS = [leer_resumen, metricas, buscar_operaciones, listar_categorias, consulta_sql_lectura]
