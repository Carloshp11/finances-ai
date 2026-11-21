"""Excel reader: one sheet into a located header plus raw rows with native cell types.

No type inference happens here. Text stays text, numbers stay numbers and dates stay dates:
the normaliser decides what each value means. Both `.xls` and `.xlsx` go through the
calamine engine, always passed explicitly.
"""

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from python_calamine import CalamineError

from finanzas.modelos.dominio import CeldaNativa


class ErrorLecturaExcel(ValueError):
    """The workbook cannot be read: protected, corrupt, no such sheet or no table."""


@dataclass(frozen=True)
class LecturaExcel:
    cabecera: list[str]
    filas_crudas: list[dict[str, CeldaNativa]]
    hoja: str
    avisos: list[str] = field(default_factory=list)


def leer_excel(ruta: Path, hoja: str | int = 0) -> LecturaExcel:
    """Read one sheet with pandas and the calamine engine, without type inference.

    - header=None: the header is located here, by `localizar_cabecera`.
    - dtype=object: pandas must not coerce any column.
    - Empty cells become None; empty rows are dropped.
    - `avisos` reports the ignored sheets and any data to the right of the header.

    Raises ErrorLecturaExcel (a ValueError) with a Spanish message when the workbook is
    protected, corrupt, lacks the requested sheet or has no recognisable header row.
    A missing file raises FileNotFoundError, which is a caller error, not a bad workbook.
    """
    try:
        with pd.ExcelFile(ruta, engine="calamine") as libro:
            hojas = [str(h) for h in libro.sheet_names]
            nombre_hoja = _resolver_hoja(hojas, hoja, ruta)
            df = pd.read_excel(libro, sheet_name=nombre_hoja, header=None, dtype=object)
    except CalamineError as exc:
        protegido = any(p in str(exc).lower() for p in ("password", "encrypt"))
        motivo = (
            "está protegido con contraseña"
            if protegido
            else "está dañado o no es un libro de Excel válido"
        )
        raise ErrorLecturaExcel(f"No se puede leer '{ruta.name}': {motivo}.") from exc

    avisos: list[str] = []
    if len(hojas) > 1:
        otras = ", ".join(f"'{h}'" for h in hojas if h != nombre_hoja)
        avisos.append(
            f"El libro tiene {len(hojas)} hojas; se lee '{nombre_hoja}' y se ignoran: {otras}."
        )

    filas = [[_celda(v) for v in fila] for fila in df.itertuples(index=False, name=None)]
    try:
        cabecera, filas_crudas, filas_con_exceso = _extraer_tabla(filas)
    except ValueError as exc:
        raise ErrorLecturaExcel(f"'{ruta.name}', hoja '{nombre_hoja}': {exc}") from exc
    if filas_con_exceso:
        avisos.append(
            f"{filas_con_exceso} filas tienen datos a la derecha de la cabecera "
            f"({len(cabecera)} columnas); esas celdas se ignoran."
        )
    return LecturaExcel(
        cabecera=cabecera, filas_crudas=filas_crudas, hoja=nombre_hoja, avisos=avisos
    )


def _extraer_tabla(
    filas: list[list[CeldaNativa]],
) -> tuple[list[str], list[dict[str, CeldaNativa]], int]:
    """Header, data rows as dicts and the number of rows with data beyond the header width.

    Raises ValueError (from `localizar_cabecera`) when there is no header row.
    """
    i_cabecera = localizar_cabecera(filas)
    fila_cabecera = filas[i_cabecera]
    while fila_cabecera and _es_vacia(fila_cabecera[-1]):  # the sheet grid is rectangular
        fila_cabecera = fila_cabecera[:-1]
    cabecera = _nombres_cabecera(fila_cabecera)

    filas_crudas: list[dict[str, CeldaNativa]] = []
    filas_con_exceso = 0
    for fila in filas[i_cabecera + 1 :]:
        if all(_es_vacia(v) for v in fila):
            continue
        if any(not _es_vacia(v) for v in fila[len(cabecera) :]):
            filas_con_exceso += 1
        # zip truncates to the header width on purpose; the overflow was counted above
        filas_crudas.append(dict(zip(cabecera, fila, strict=False)))
    return cabecera, filas_crudas, filas_con_exceso


def localizar_cabecera(filas: list[list[CeldaNativa]], minimo_columnas: int = 3) -> int:
    """Index of the first row with at least `minimo_columnas` non-empty text cells.

    Raises ValueError when no such row exists (no recognisable table).
    # TODO(P5): replace this heuristic if the real files need an explicit override.
    """
    for i, fila in enumerate(filas):
        if sum(isinstance(v, str) and bool(v.strip()) for v in fila) >= minimo_columnas:
            return i
    raise ValueError(
        f"No se encontró una fila de cabecera (al menos {minimo_columnas} celdas de texto)."
    )


def _resolver_hoja(hojas: list[str], hoja: str | int, ruta: Path) -> str:
    """Name of the requested sheet, by position or by name."""
    if isinstance(hoja, int):
        if not 0 <= hoja < len(hojas):
            raise ErrorLecturaExcel(
                f"'{ruta.name}' tiene {len(hojas)} hojas; no existe la hoja número {hoja}."
            )
        return hojas[hoja]
    if hoja not in hojas:
        raise ErrorLecturaExcel(f"'{ruta.name}' no tiene ninguna hoja llamada '{hoja}'.")
    return hoja


def _es_vacia(valor: CeldaNativa) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _celda(valor: object) -> CeldaNativa:
    """pandas NaN -> None; numpy scalars -> Python scalars; everything else unchanged."""
    if pd.isna(valor):  # first: NaN != None
        return None
    if isinstance(valor, pd.Timestamp):
        return valor.to_pydatetime()
    if isinstance(valor, np.generic):
        return valor.item()
    return valor  # type: ignore[return-value]


def _nombres_cabecera(fila: list[CeldaNativa]) -> list[str]:
    """Strip text; empty header cells become 'columna_<n>'; duplicates get '_2', '_3'."""
    nombres: list[str] = []
    vistos: set[str] = set()
    for n, valor in enumerate(fila, start=1):
        base = "" if valor is None else str(valor).strip()
        base = base or f"columna_{n}"
        nombre, k = base, 1
        while nombre in vistos:
            k += 1
            nombre = f"{base}_{k}"
        vistos.add(nombre)
        nombres.append(nombre)
    return nombres
