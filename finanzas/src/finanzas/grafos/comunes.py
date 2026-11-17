"""Functions shared by the root graph and the query CLI."""

from finanzas.config import cargar_settings
from finanzas.db.conexion import inicializar_bd
from finanzas.modelos.estados import EstadoRaiz
from finanzas.trazas import traza


def nodo_inicializar_bd(state: EstadoRaiz) -> dict:
    traza("raiz", "inicializar_bd")
    inicializar_bd(cargar_settings())  # REAL: creating the schema is cheap and idempotent
    return {}


def comprobar_pendientes() -> str | None:
    """DUMMY. A plain function (not a node), reused by the root node and the query CLI.

    Future logic: count files on disk with no 'procesado' entry, files in error,
    pendiente_confirmacion or en_proceso state, and operations not yet enriched.
    Returns a warning text or None. It NEVER raises and NEVER blocks.
    """
    traza("comun", "comprobar_pendientes")
    return "Aviso (dummy): hay 1 fichero pendiente de procesar y 3 operaciones sin enriquecer."


def nodo_comprobar_pendientes(state: EstadoRaiz) -> dict:
    aviso = comprobar_pendientes()
    return {"avisos": [aviso] if aviso else []}
