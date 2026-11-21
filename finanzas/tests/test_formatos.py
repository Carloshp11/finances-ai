import subprocess
import sys
from typing import get_args

import pytest
from finanzas.modelos.dominio import FicheroDetectado, FormatoFichero
from finanzas.utilidades import (
    EXTENSION_FORMATO,
    FIRMA_OLE2,
    FIRMA_ZIP,
    detectar_formato_por_contenido,
    formato_de_fichero,
)

OLE2 = FIRMA_OLE2 + b"\x00" * 504
ZIP = FIRMA_ZIP + b"\x00" * 26
HTML = b"<html><body><table>"


@pytest.mark.parametrize(
    ("contenido", "esperado"),
    [
        (OLE2, "xls"),
        (ZIP, "xlsx"),
        (HTML, "desconocido"),
        (b"", "desconocido"),
        (FIRMA_OLE2[:4], "desconocido"),  # truncated signature
        (b"fecha;importe\n", "desconocido"),
    ],
)
def test_detectar_formato_por_contenido(tmp_path, contenido, esperado):
    ruta = tmp_path / "x.bin"
    ruta.write_bytes(contenido)
    assert detectar_formato_por_contenido(ruta) == esperado


@pytest.mark.parametrize(
    ("nombre", "contenido", "formato", "hay_aviso"),
    [
        ("a.csv", b"fecha;importe\n", "csv", False),
        ("a.tsv", b"fecha\timporte\n", "tsv", False),
        ("a.txt", b"fecha\timporte\n", "tsv", False),
        ("EXTRACTO.XLS", OLE2, "xls", False),  # upper-case extension
        ("a.xlsx", ZIP, "xlsx", False),
        ("A.XLSX", ZIP, "xlsx", False),
        ("a.xls", HTML, "desconocido", True),  # P6: disguised HTML
        ("a.xlsx", HTML, "desconocido", True),
        ("a.xls", ZIP, "desconocido", True),  # xlsx renamed to .xls
        ("a.xlsx", OLE2, "desconocido", True),  # OLE2 is also used by protected workbooks
        ("a.pdf", b"%PDF-1.7", "desconocido", True),
        ("sin_extension", b"", "desconocido", True),
    ],
)
def test_formato_de_fichero(tmp_path, nombre, contenido, formato, hay_aviso):
    ruta = tmp_path / nombre
    ruta.write_bytes(contenido)
    resultado, aviso = formato_de_fichero(ruta)
    assert resultado == formato
    assert (aviso is not None) == hay_aviso
    if aviso:
        assert nombre in aviso


def test_formato_de_fichero_excel_inexistente_avisa_sin_lanzar(tmp_path):
    formato, aviso = formato_de_fichero(tmp_path / "no_existe.xls")
    assert formato == "desconocido"
    assert "no_existe.xls" in aviso


def test_formato_de_fichero_texto_no_lee_el_fichero(tmp_path):
    assert formato_de_fichero(tmp_path / "no_existe.csv") == ("csv", None)


def test_extension_formato_usa_solo_formatos_validos():
    assert set(EXTENSION_FORMATO.values()) <= set(get_args(FormatoFichero))


@pytest.mark.parametrize("formato", ["xls", "xlsx"])
def test_fichero_detectado_acepta_formatos_excel(formato):
    fichero = FicheroDetectado(usuario="u", ruta="u/a", sha256="x", formato=formato, tamano_bytes=1)
    assert fichero.formato == formato


def test_utilidades_se_importa_sin_langgraph():
    codigo = "import sys, finanzas.utilidades; assert 'langgraph' not in sys.modules"
    subprocess.run([sys.executable, "-c", codigo], check=True)
