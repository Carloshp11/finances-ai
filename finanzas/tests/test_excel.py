from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from finanzas.lectura import excel as modulo_excel
from finanzas.lectura.excel import (
    ErrorLecturaExcel,
    _celda,
    _extraer_tabla,
    _nombres_cabecera,
    leer_excel,
    localizar_cabecera,
)
from python_calamine import CalamineError

FIXTURES = Path(__file__).parent / "fixtures"
SINTETICO = FIXTURES / "extracto_sintetico.xls"


def test_leer_hoja_y_cabecera():
    lectura = leer_excel(SINTETICO)
    assert lectura.hoja == "Movimientos"
    assert lectura.cabecera == ["Fecha", "Concepto", "Importe", "Saldo"]


def test_tipos_nativos_se_conservan():
    filas = leer_excel(SINTETICO).filas_crudas
    assert isinstance(filas[0]["Fecha"], datetime | date)
    assert isinstance(filas[0]["Importe"], float)
    assert filas[1]["Fecha"] == "05/11/2026"
    assert filas[1]["Importe"] == "2.000,00"
    assert isinstance(filas[2]["Importe"], int | float) and filas[2]["Importe"] < 0
    for fila in filas:
        for valor in fila.values():
            assert not isinstance(valor, np.generic)


def test_filas_vacias_se_descartan_y_el_pie_se_conserva():
    filas = leer_excel(SINTETICO).filas_crudas
    assert len(filas) == 4
    assert filas[3] == {"Fecha": "Saldo final", "Concepto": None, "Importe": None, "Saldo": 4174.56}


def test_aviso_de_hojas_adicionales():
    avisos = leer_excel(SINTETICO).avisos
    assert any("Hoja2" in aviso for aviso in avisos)


def test_hoja_por_nombre_y_hoja_inexistente():
    assert leer_excel(SINTETICO, hoja="Movimientos").hoja == "Movimientos"
    with pytest.raises(ErrorLecturaExcel, match="Nope"):
        leer_excel(SINTETICO, hoja="Nope")
    with pytest.raises(ErrorLecturaExcel, match="hoja número 5"):
        leer_excel(SINTETICO, hoja=5)


def test_hoja_sin_tabla_da_error():
    with pytest.raises(ErrorLecturaExcel, match="cabecera"):
        leer_excel(SINTETICO, hoja="Hoja2")


@pytest.mark.parametrize(
    "ruta",
    [FIXTURES / "extracto_html_disfrazado.xls", FIXTURES / "extracto_sintetico.csv"],
)
def test_fichero_que_no_es_excel_da_error_claro(ruta):
    with pytest.raises(ErrorLecturaExcel, match="no es un libro de Excel válido"):
        leer_excel(ruta)


def test_fichero_truncado_o_vacio_da_error(tmp_path):
    vacio = tmp_path / "vacio.xls"
    vacio.write_bytes(b"")
    truncado = tmp_path / "truncado.xls"
    truncado.write_bytes(SINTETICO.read_bytes()[:600])
    for ruta in (vacio, truncado):
        with pytest.raises(ErrorLecturaExcel):
            leer_excel(ruta)


def test_fichero_inexistente_no_se_enmascara(tmp_path):
    with pytest.raises(FileNotFoundError):
        leer_excel(tmp_path / "no_existe.xls")


def test_error_de_contrasena_tiene_mensaje_propio(tmp_path, monkeypatch):
    def falla(*_args, **_kwargs):
        raise CalamineError("Workbook is password protected")

    monkeypatch.setattr(modulo_excel.pd, "ExcelFile", falla)
    with pytest.raises(ErrorLecturaExcel, match="contraseña"):
        leer_excel(tmp_path / "protegido.xls")


def test_localizar_cabecera():
    filas = [
        ["Título", None, None],
        [None, None, None],
        ["a", "b", "c", 1],
        ["x", 1, 2, 3],
    ]
    assert localizar_cabecera(filas) == 2
    assert localizar_cabecera([["a", "b", " ", "c", "d"]]) == 0


@pytest.mark.parametrize("filas", [[[1, 2, 3], [None, 4.5, None]], []])
def test_localizar_cabecera_sin_texto_lanza_value_error(filas):
    with pytest.raises(ValueError):
        localizar_cabecera(filas)


def test_nombres_cabecera_vacios_y_duplicados():
    nombres = _nombres_cabecera([" Fecha ", None, "Importe", "Importe", "Importe", ""])
    assert nombres == ["Fecha", "columna_2", "Importe", "Importe_2", "Importe_3", "columna_6"]


def test_extraer_tabla_recorta_cabecera_y_avisa_de_exceso():
    filas = [
        ["Título", None, None, None, None],
        ["a", "b", "c", None, None],
        [1, 2, 3, None, None],
        [4, 5, 6, None, "sobra"],
        [None, None, None, None, None],
    ]
    cabecera, filas_crudas, con_exceso = _extraer_tabla(filas)
    assert cabecera == ["a", "b", "c"]
    assert filas_crudas == [{"a": 1, "b": 2, "c": 3}, {"a": 4, "b": 5, "c": 6}]
    assert con_exceso == 1


def test_celda_convierte_nan_y_numpy():
    assert _celda(float("nan")) is None
    assert _celda(pd.NaT) is None
    assert _celda(None) is None
    assert type(_celda(np.float64(1.5))) is float
    assert type(_celda(np.int64(3))) is int
    assert _celda("texto") == "texto"
    assert type(_celda(pd.Timestamp("2026-11-03"))) is datetime
