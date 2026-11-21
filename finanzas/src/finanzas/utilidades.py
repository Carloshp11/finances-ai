"""Pure helper functions. The only I/O is reading files: sha256_fichero and the signature check."""

import hashlib
import os
import re
import unicodedata
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from finanzas.modelos.dominio import (
    CeldaNativa,
    FicheroDetectado,
    FormatoExtracto,
    FormatoFichero,
)

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


# --- Format detection -------------------------------------------------------------------

FIRMA_OLE2 = bytes.fromhex("D0CF11E0A1B11AE1")  # .xls (BIFF8 inside an OLE2 container)
FIRMA_ZIP = b"PK\x03\x04"  # .xlsx (zip container)

EXTENSION_FORMATO: dict[str, FormatoFichero] = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".txt": "tsv",
    ".xls": "xls",
    ".xlsx": "xlsx",
}  # TODO(P1): PDF is not supported yet


def detectar_formato_por_contenido(ruta: Path) -> FormatoFichero:
    """Look at the first bytes of the file, not at its extension.

    OLE2 signature -> 'xls'; ZIP signature -> 'xlsx'. Anything else -> 'desconocido' (for
    example HTML or XML saved with an .xls name). Raises OSError if the file cannot be read.
    """
    with open(ruta, "rb") as fichero:
        cabecera = fichero.read(len(FIRMA_OLE2))
    if cabecera.startswith(FIRMA_OLE2):
        return "xls"
    if cabecera.startswith(FIRMA_ZIP):
        return "xlsx"
    return "desconocido"


def formato_de_fichero(ruta: Path) -> tuple[FormatoFichero, str | None]:
    """Return (formato, aviso) for a file: by extension, plus a signature check for Excel.

    The aviso is a Spanish, user-facing message, or None when the file is accepted. Text
    formats (csv, tsv) are decided by extension only.
    """
    candidato = EXTENSION_FORMATO.get(ruta.suffix.lower())
    if candidato is None:
        extension = ruta.suffix or "sin extensión"
        return "desconocido", f"{ruta.name}: formato no admitido ({extension})"
    if candidato in ("xls", "xlsx"):
        try:
            real = detectar_formato_por_contenido(ruta)
        except OSError as exc:  # e.g. the file is locked because Excel has it open
            return (
                "desconocido",
                f"{ruta.name}: no se puede leer el fichero ({exc.strerror or exc})",
            )
        if real != candidato:
            if real == "desconocido":
                detalle = "el contenido no es un libro Excel (¿HTML o XML guardado como Excel?)"
            else:
                detalle = (
                    f"el contenido es de tipo {real} (¿renombrado o protegido con contraseña?)"
                )
            return "desconocido", f"{ruta.name}: la extensión es {ruta.suffix} pero {detalle}"
    return candidato, None


# --- Input folder scan (T1.1) -------------------------------------------------------------

_PREFIJOS_IGNORADOS = (".", "~$")  # dotfiles and Office lock files (~$libro.xlsx)
_NOMBRES_IGNORADOS = frozenset({"thumbs.db", "desktop.ini"})
_SUFIJOS_TEMPORALES = frozenset({".tmp", ".part", ".crdownload"})


def es_nombre_ignorable(nombre: str) -> bool:
    """True for hidden, lock and temporary names that are skipped silently."""
    minusculas = nombre.lower()
    return (
        nombre.startswith(_PREFIJOS_IGNORADOS)
        or minusculas in _NOMBRES_IGNORADOS
        or Path(minusculas).suffix in _SUFIJOS_TEMPORALES
    )


def _ficheros_ordenados(raiz: Path) -> list[Path]:
    """Regular files under raiz, pruning ignorable names, sorted by relative POSIX path.

    os.walk does not descend into symlinked folders; symlinked files are skipped.
    """
    encontrados: list[Path] = []
    for carpeta, subcarpetas, nombres in os.walk(raiz):
        subcarpetas[:] = [d for d in subcarpetas if not es_nombre_ignorable(d)]
        for nombre in nombres:
            ruta = Path(carpeta) / nombre
            if not es_nombre_ignorable(nombre) and not ruta.is_symlink():
                encontrados.append(ruta)
    return sorted(encontrados, key=lambda p: p.relative_to(raiz).as_posix())


def escanear_carpeta(raiz: Path) -> tuple[list[FicheroDetectado], list[str]]:
    """Scan raiz/<usuario>/... and return (accepted files, Spanish avisos).

    Deterministic: sorted by relative POSIX path. Never raises for a missing folder or an
    unreadable file; each problem becomes an aviso and the file is left out. Files with
    identical content keep only the first one (sha256 is the key of `ficheros`).
    """
    if not raiz.is_dir():
        return [], [f"La carpeta de inputs no existe: {raiz}"]
    detectados: list[FicheroDetectado] = []
    avisos: list[str] = []
    por_sha256: dict[str, str] = {}
    for ruta in _ficheros_ordenados(raiz):
        relativa = ruta.relative_to(raiz)
        rel = relativa.as_posix()
        if len(relativa.parts) == 1:
            avisos.append(f"{rel}: está fuera de una carpeta de usuario y se ignora")
            continue
        formato, aviso = formato_de_fichero(ruta)
        if formato == "desconocido":
            avisos.append(aviso or f"{rel}: formato no admitido")
            continue
        try:
            sha256 = sha256_fichero(ruta)
            tamano = ruta.stat().st_size
        except OSError as exc:  # e.g. a file locked by another process
            avisos.append(f"{rel}: no se puede leer el fichero ({exc.strerror or exc})")
            continue
        if sha256 in por_sha256:
            avisos.append(f"{rel}: contenido idéntico a {por_sha256[sha256]}; se ignora")
            continue
        por_sha256[sha256] = rel
        detectados.append(
            FicheroDetectado(
                usuario=relativa.parts[0],
                ruta=rel,
                sha256=sha256,
                formato=formato,
                tamano_bytes=tamano,
            )
        )
    return detectados, avisos


# --- Cell conversion (Excel values, decisions X4 to X6) ---------------------------------

# Serial 61 is 1900-03-01. Earlier serials are affected by Excel's fictitious 1900-02-29.
EPOCA_EXCEL = date(1899, 12, 30)
_SERIE_EXCEL_MINIMA = 61
_CIEN = Decimal(100)
_UN = Decimal(1)


def _decimal_desde_texto(texto: str, formato: FormatoExtracto) -> Decimal:
    """Parse a text amount strictly, with the separators of the mapping.

    Strict on purpose: with Spanish separators, '45.30' would otherwise become 4530 once the
    '.' is dropped as a thousands separator. Thousands groups must have exactly three digits.
    """
    limpio = texto.strip()
    decimal = re.escape(formato.separador_decimal)
    if formato.separador_miles:
        miles = re.escape(formato.separador_miles)
        parte_entera = rf"(?:\d{{1,3}}(?:{miles}\d{{3}})+|\d+)"
    else:
        parte_entera = r"\d+"
    if re.fullmatch(rf"[+-]?{parte_entera}(?:{decimal}\d+)?", limpio, re.ASCII) is None:
        raise ValueError(f"Importe no válido: {texto!r}")
    if formato.separador_miles:
        limpio = limpio.replace(formato.separador_miles, "")
    return Decimal(limpio.replace(formato.separador_decimal, "."))


def importe_a_centimos(valor: CeldaNativa, formato: FormatoExtracto) -> int:
    """Convert an amount cell to integer cents. Money never goes through float arithmetic.

    - int/float (numeric cell): Decimal(str(valor)). str() gives the shortest repr, so 45.3
      is exactly Decimal('45.3') and not 45.2999999999999971578...
    - str (text cell): parsed strictly with the separators of `formato`.
    - bool, None, dates, NaN, infinity or overflow: ValueError.
    Rounding is ROUND_HALF_UP to the cent (ties go away from zero).
    """
    if isinstance(valor, str):
        importe = _decimal_desde_texto(valor, formato)
    elif isinstance(valor, bool) or not isinstance(valor, int | float):
        raise ValueError(f"Importe no válido: {valor!r}")
    else:
        importe = Decimal(str(valor))
    if not importe.is_finite():
        raise ValueError(f"Importe no válido: {valor!r}")
    try:
        return int((importe * _CIEN).quantize(_UN, rounding=ROUND_HALF_UP))
    except InvalidOperation:  # magnitude beyond the precision of the default context
        raise ValueError(f"Importe fuera de rango: {valor!r}") from None


def fecha_a_date(valor: CeldaNativa, formato: FormatoExtracto) -> date:
    """Convert a date cell to date.

    - datetime -> .date() (checked before date, because datetime is a subclass of date)
    - date -> unchanged
    - str -> strptime with formato.formato_fecha
    - int/float -> Excel serial number counted from 1899-12-30; the time fraction is dropped.
      Serials below 61 are rejected (Excel's 1900 leap-year bug makes them ambiguous).
      The 1904 date system is not supported.
    - bool, None or anything else: ValueError.
    """
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        try:
            return datetime.strptime(valor.strip(), formato.formato_fecha).date()
        except ValueError:
            raise ValueError(
                f"Fecha no válida: {valor!r} (formato esperado {formato.formato_fecha})"
            ) from None
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        raise ValueError(f"Fecha no válida: {valor!r}")
    try:
        dias = int(valor)  # ValueError for NaN, OverflowError for infinity
        if dias >= _SERIE_EXCEL_MINIMA:
            return EPOCA_EXCEL + timedelta(days=dias)  # OverflowError beyond year 9999
    except (ValueError, OverflowError):
        pass
    raise ValueError(f"Fecha no válida: número de serie {valor!r}")


def celda_a_texto(valor: CeldaNativa) -> str:
    """Text for logs and for the LLM sample (filas_muestra). Never raises.

    None -> ''; text is stripped; dates in ISO format (a datetime at midnight is shown as a
    date); numbers in plain notation, with no thousands separator and no trailing '.0'.
    """
    if valor is None:
        return ""
    if isinstance(valor, str):
        return valor.strip()
    if isinstance(valor, bool):
        return str(valor)
    if isinstance(valor, datetime):
        if valor.time() == datetime.min.time():
            return valor.date().isoformat()
        return valor.isoformat(sep=" ", timespec="seconds")
    if isinstance(valor, date):
        return valor.isoformat()
    if not isinstance(valor, int | float):
        return str(valor).strip()  # e.g. a time cell: never let a log line raise
    numero = Decimal(str(valor)).normalize()  # also avoids scientific notation
    return "0" if numero == 0 else format(numero, "f")
