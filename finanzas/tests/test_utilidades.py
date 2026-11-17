import hashlib
from datetime import date
from pathlib import Path

from finanzas.utilidades import (
    calcular_firma_cabecera,
    calcular_hash_operacion,
    mes,
    normalizar_iban,
    normalizar_texto,
    periodos_de_fechas,
    semana_iso,
    sha256_fichero,
)


def test_normalizar_iban_quita_espacios_y_pasa_a_mayusculas():
    assert normalizar_iban(" es12 3456 ") == "ES123456"


def test_semana_iso():
    assert semana_iso(date(2026, 11, 17)) == "2026-W47"


def test_mes():
    assert mes(date(2026, 11, 17)) == "2026-11"


def test_normalizar_texto():
    assert normalizar_texto("  Café  MERCADONA ") == "cafe mercadona"


def test_calcular_hash_operacion_ocurrencia_distinta_da_hash_distinto():
    args = (None, date(2026, 11, 3), -450, "COMPRA CAFE", 0)
    otro = (None, date(2026, 11, 3), -450, "COMPRA CAFE", 1)
    assert calcular_hash_operacion(*args) != calcular_hash_operacion(*otro)


def test_calcular_hash_operacion_misma_entrada_mismo_hash():
    args = ("ES00", date(2026, 11, 3), -450, "Compra café", 0)
    assert calcular_hash_operacion(*args) == calcular_hash_operacion(*args)


def test_calcular_firma_cabecera_ignora_mayusculas_y_espacios():
    assert calcular_firma_cabecera(["Fecha", "Importe"]) == calcular_firma_cabecera(
        [" fecha ", "IMPORTE"]
    )


def test_periodos_de_fechas_sin_duplicados_y_ordenado():
    fechas = [date(2026, 11, 17), date(2026, 11, 3), date(2026, 11, 17)]
    assert periodos_de_fechas(fechas) == ["2026-11", "2026-W45", "2026-W47"]


def test_sha256_fichero_coincide_con_hashlib(tmp_path: Path):
    ruta = tmp_path / "x.csv"
    contenido = b"fecha;importe\n" * 10000  # mas de un bloque de 64 KB
    ruta.write_bytes(contenido)
    assert sha256_fichero(ruta) == hashlib.sha256(contenido).hexdigest()
