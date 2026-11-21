"""The git-ignored local overlay: what it may change and how it is merged."""

from pathlib import Path

import pytest
import yaml
from finanzas.config import RUTA_SETTINGS, cargar_settings

_IBAN_LOCAL = "ES9999999999999999999999"  # synthetic


def _base(tmp_path: Path) -> Path:
    """A copy of the real settings.yaml, so each test controls its own files."""
    destino = tmp_path / "settings.yaml"
    destino.write_text(RUTA_SETTINGS.read_text(encoding="utf-8"), encoding="utf-8")
    return destino


def _local(ruta: Path, contenido: dict) -> Path:
    ruta.write_text(yaml.safe_dump(contenido), encoding="utf-8")
    return ruta


def test_el_overlay_reemplaza_las_listas_sin_concatenar(tmp_path):
    base = _base(tmp_path)
    local = _local(
        tmp_path / "settings.local.yaml",
        {"cuentas": [{"iban": _IBAN_LOCAL, "usuario": "carlos"}]},
    )
    settings = cargar_settings(base, ruta_local=local)
    assert [c.iban for c in settings.cuentas] == [_IBAN_LOCAL]


def test_sin_fichero_local_no_cambia_nada(tmp_path):
    base = _base(tmp_path)
    sin_overlay = cargar_settings(base)
    con_ruta_inexistente = cargar_settings(base, ruta_local=tmp_path / "no_existe.yaml")
    assert con_ruta_inexistente.cuentas == sin_overlay.cuentas


def test_con_ruta_explicita_se_ignora_el_local_vecino(tmp_path):
    base = _base(tmp_path)
    _local(
        tmp_path / "settings.local.yaml",
        {"cuentas": [{"iban": _IBAN_LOCAL, "usuario": "carlos"}]},
    )
    settings = cargar_settings(base)
    assert _IBAN_LOCAL not in [c.iban for c in settings.cuentas]


def test_clave_no_permitida_falla_sin_mostrar_valores(tmp_path):
    base = _base(tmp_path)
    local = _local(tmp_path / "settings.local.yaml", {"rutas": {"inputs": "valor-privado"}})
    with pytest.raises(ValueError) as error:
        cargar_settings(base, ruta_local=local)
    assert "rutas" in str(error.value)
    assert "valor-privado" not in str(error.value)


def test_las_variables_de_entorno_siguen_ganando(tmp_path, monkeypatch):
    base = _base(tmp_path)
    local = _local(tmp_path / "settings.local.yaml", {"cuentas": []})
    monkeypatch.setenv("FINANZAS_ANALISIS__MODELO", "modelo-de-prueba")
    settings = cargar_settings(base, ruta_local=local)
    assert settings.analisis.modelo == "modelo-de-prueba"
    assert settings.cuentas == []
