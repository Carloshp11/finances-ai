"""Pure helper functions: no I/O apart from sha256_fichero, which only reads a file."""

import hashlib
import unicodedata
from collections.abc import Iterable
from datetime import date
from pathlib import Path

_TAMANO_BLOQUE = 64 * 1024


def normalizar_iban(iban: str) -> str:
    """Upper case and no spaces."""
    return iban.replace(" ", "").upper()


def normalizar_texto(texto: str) -> str:
    """Lower case, accents removed (NFKD), spaces collapsed, stripped."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    sin_acentos = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return " ".join(sin_acentos.lower().split())


def semana_iso(d: date) -> str:
    """ISO year and two-digit week, e.g. '2026-W46'."""
    anio, semana, _ = d.isocalendar()
    return f"{anio}-W{semana:02d}"


def mes(d: date) -> str:
    """Year and month, e.g. '2026-11'."""
    return f"{d.year:04d}-{d.month:02d}"


def periodos_de_fechas(fechas: Iterable[date]) -> list[str]:
    """Sorted, de-duplicated set of the weeks and months touched by the dates."""
    periodos: set[str] = set()
    for d in fechas:
        periodos.add(semana_iso(d))
        periodos.add(mes(d))
    return sorted(periodos)


def calcular_firma_cabecera(columnas: list[str]) -> str:
    """First 16 hex chars of the sha256 of the normalised column names joined by '|'."""
    texto = "|".join(normalizar_texto(c) for c in columnas)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def calcular_hash_operacion(
    cuenta: str | None,
    fecha: date,
    importe_centimos: int,
    concepto: str,
    ocurrencia: int,
) -> str:
    """sha256 of the operation key, including its occurrence index within the same file.

    `ocurrencia` is the number of times the same (account, date, amount, concept) tuple
    already appeared earlier in the same file (0, 1, 2...). Two identical coffees on the
    same day therefore do not collapse, while the same movement in two overlapping
    statements does.
    """
    clave = (
        f"{cuenta or ''}|{fecha.isoformat()}|{importe_centimos}|"
        f"{normalizar_texto(concepto)}|{ocurrencia}"
    )
    return hashlib.sha256(clave.encode("utf-8")).hexdigest()


def sha256_fichero(ruta: Path) -> str:
    """sha256 of the file contents, read in 64 KB blocks."""
    digest = hashlib.sha256()
    with open(ruta, "rb") as fichero:
        for bloque in iter(lambda: fichero.read(_TAMANO_BLOQUE), b""):
            digest.update(bloque)
    return digest.hexdigest()
