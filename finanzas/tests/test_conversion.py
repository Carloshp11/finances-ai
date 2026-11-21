import random
from datetime import date, datetime
from decimal import Decimal

import pytest
from finanzas.modelos.dominio import FormatoExtracto
from finanzas.utilidades import EPOCA_EXCEL, celda_a_texto, fecha_a_date, importe_a_centimos

FMT_ES = FormatoExtracto(
    firma_cabecera="x", delimitador=";", columna_fecha="Fecha", columna_concepto="Concepto"
)  # defaults: "," decimal and "." thousands
FMT_EN = FMT_ES.model_copy(
    update={"separador_decimal": ".", "separador_miles": ",", "formato_fecha": "%Y-%m-%d"}
)
FMT_SIN_MILES = FMT_ES.model_copy(update={"separador_miles": ""})
SERIE_3_NOV = (date(2026, 11, 3) - EPOCA_EXCEL).days

IMPORTES_ES = [
    (-45.3, -4530),
    (200000, 20000000),
    (200000.0, 20000000),
    (0, 0),
    (-0.0, 0),
    (1e-05, 0),
    (0.005, 1),
    (-0.005, -1),
    (4.35, 435),  # 4.35 * 100 is 434.99999999999994 in floats
    (0.29, 29),
    (1.15, 115),
    (19.99, 1999),
    (0.1 + 0.2, 30),
    ("-45,30", -4530),
    ("+45,30", 4530),
    ("45,3", 4530),
    ("  45,30  ", 4530),
    ("0", 0),
    ("1.200,00", 120000),
    ("1.200", 120000),
    ("1.234.567,89", 123456789),
    ("0,005", 1),
    ("-0,005", -1),
    ("0,004", 0),
]


@pytest.mark.parametrize(("valor", "esperado"), IMPORTES_ES)
def test_importe_a_centimos_es(valor, esperado):
    resultado = importe_a_centimos(valor, FMT_ES)
    assert resultado == esperado
    assert type(resultado) is int


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("-45.30", -4530), ("1,200.00", 120000), ("1,234,567.89", 123456789), (45.3, 4530)],
)
def test_importe_a_centimos_en(valor, esperado):
    assert importe_a_centimos(valor, FMT_EN) == esperado


def test_importe_a_centimos_sin_separador_de_miles():
    assert importe_a_centimos("1200,50", FMT_SIN_MILES) == 120050


@pytest.mark.parametrize(
    "valor",
    [
        "abc",
        "",
        "   ",
        "45.30",
        "1.20",
        "1.2000",
        "1,2,3",
        "12 €",
        "--5",
        "1e3",
        "٣,٥",
        True,
        False,
        None,
        float("nan"),
        float("inf"),
        1e300,
        date(2026, 11, 3),
        "NaN",
    ],
)
def test_importe_a_centimos_invalido(valor):
    with pytest.raises(ValueError, match="Importe"):
        importe_a_centimos(valor, FMT_ES)


def test_importe_a_centimos_coincide_con_decimal_exacto():
    rng = random.Random(20261103)
    for _ in range(1000):
        d = Decimal(rng.randint(-(10**9), 10**9)).scaleb(-2)  # exact, two decimals
        assert importe_a_centimos(float(d), FMT_ES) == int(d * 100)
        assert importe_a_centimos(str(d).replace(".", ","), FMT_ES) == int(d * 100)


@pytest.mark.parametrize(
    ("valor", "formato", "esperado"),
    [
        (datetime(2026, 11, 3, 10, 15), FMT_ES, date(2026, 11, 3)),
        (date(2026, 11, 3), FMT_ES, date(2026, 11, 3)),
        (SERIE_3_NOV, FMT_ES, date(2026, 11, 3)),
        (float(SERIE_3_NOV) + 0.75, FMT_ES, date(2026, 11, 3)),  # time fraction dropped
        (61, FMT_ES, date(1900, 3, 1)),
        ("03/11/2026", FMT_ES, date(2026, 11, 3)),
        (" 03/11/2026 ", FMT_ES, date(2026, 11, 3)),
        ("2026-11-03", FMT_EN, date(2026, 11, 3)),
    ],
)
def test_fecha_a_date(valor, formato, esperado):
    assert fecha_a_date(valor, formato) == esperado


@pytest.mark.parametrize(
    "valor",
    [
        "31/02/2026",
        "2026-11-03",
        "",
        "  ",
        "abc",
        None,
        True,
        0,
        60,
        -5,
        20261103,
        float("nan"),
        float("inf"),
        1e300,
    ],
)
def test_fecha_a_date_invalida(valor):
    with pytest.raises(ValueError, match="Fecha"):
        fecha_a_date(valor, FMT_ES)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (None, ""),
        ("", ""),
        ("  hola  ", "hola"),
        (date(2026, 11, 3), "2026-11-03"),
        (datetime(2026, 11, 3), "2026-11-03"),
        (datetime(2026, 11, 3, 10, 15), "2026-11-03 10:15:00"),
        (1234.5, "1234.5"),
        (200000.0, "200000"),
        (200000, "200000"),
        (-45.3, "-45.3"),
        (1e-05, "0.00001"),
        (1e16, "10000000000000000"),
        (-0.0, "0"),
        (True, "True"),
    ],
)
def test_celda_a_texto(valor, esperado):
    assert celda_a_texto(valor) == esperado
