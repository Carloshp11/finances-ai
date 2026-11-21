"""Tests of the input folder scan (T1.1), with synthetic files only."""

import hashlib
import shutil
from pathlib import Path

from finanzas.grafos.ingesta.grafo import construir_grafo_ingesta, escanear_inputs
from finanzas.observabilidad import construir_config
from finanzas.utilidades import escanear_carpeta

FIXTURES = Path(__file__).parent / "fixtures"


def _escribir(ruta: Path, contenido: bytes) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(contenido)


def test_camino_feliz(tmp_path):
    xls = (FIXTURES / "extracto_sintetico.xls").read_bytes()
    _escribir(tmp_path / "carlos" / "b.csv", b"b\n")
    _escribir(tmp_path / "carlos" / "a.xls", xls)
    _escribir(tmp_path / "conjunta" / "c.csv", b"c\n")

    detectados, avisos = escanear_carpeta(tmp_path)

    assert avisos == []
    assert [f.ruta for f in detectados] == ["carlos/a.xls", "carlos/b.csv", "conjunta/c.csv"]
    assert [f.usuario for f in detectados] == ["carlos", "carlos", "conjunta"]
    assert [f.formato for f in detectados] == ["xls", "csv", "csv"]
    assert detectados[0].tamano_bytes == len(xls)
    assert detectados[0].sha256 == hashlib.sha256(xls).hexdigest()


def test_orden_determinista(tmp_path):
    uno, dos = tmp_path / "uno", tmp_path / "dos"
    for raiz, orden in ((uno, "abc"), (dos, "cba")):
        for letra in orden:
            _escribir(raiz / "carlos" / f"{letra}.csv", letra.encode())
    assert [f.ruta for f in escanear_carpeta(uno)[0]] == [f.ruta for f in escanear_carpeta(dos)[0]]


def test_nombres_ignorados_en_silencio(tmp_path):
    for ruta in (
        "carlos/~$libro.xlsx",
        "carlos/.DS_Store",
        "carlos/.oculta/x.csv",
        "carlos/Thumbs.db",
        "carlos/x.csv.part",
    ):
        _escribir(tmp_path / ruta, b"x")
    assert escanear_carpeta(tmp_path) == ([], [])


def test_html_disfrazado_de_xls(tmp_path):
    shutil.copy(FIXTURES / "extracto_html_disfrazado.xls", tmp_path / "carlos.xls")
    destino = tmp_path / "carlos" / "extracto_html_disfrazado.xls"
    destino.parent.mkdir()
    (tmp_path / "carlos.xls").replace(destino)

    detectados, avisos = escanear_carpeta(tmp_path)

    assert detectados == []
    assert len(avisos) == 1
    assert "extracto_html_disfrazado.xls" in avisos[0]
    assert "extensión" in avisos[0]


def test_extension_no_admitida(tmp_path):
    _escribir(tmp_path / "carlos" / "notas.pdf", b"%PDF")
    detectados, avisos = escanear_carpeta(tmp_path)
    assert detectados == []
    assert "formato no admitido" in avisos[0]


def test_carpeta_inexistente(tmp_path):
    detectados, avisos = escanear_carpeta(tmp_path / "no_existe")
    assert detectados == []
    assert avisos[0].startswith("La carpeta de inputs no existe")


def test_fichero_fuera_de_carpeta_de_usuario(tmp_path):
    assert escanear_carpeta(tmp_path) == ([], [])
    _escribir(tmp_path / "suelto.csv", b"x")
    detectados, avisos = escanear_carpeta(tmp_path)
    assert detectados == []
    assert "fuera de una carpeta de usuario" in avisos[0]


def test_subcarpeta_anidada(tmp_path):
    _escribir(tmp_path / "carlos" / "2026" / "m.csv", b"m\n")
    detectados, _ = escanear_carpeta(tmp_path)
    assert detectados[0].ruta == "carlos/2026/m.csv"
    assert detectados[0].usuario == "carlos"


def test_contenido_duplicado_conserva_el_primero(tmp_path):
    _escribir(tmp_path / "carlos" / "a.csv", b"igual\n")
    _escribir(tmp_path / "conjunta" / "a.csv", b"igual\n")
    detectados, avisos = escanear_carpeta(tmp_path)
    assert [f.ruta for f in detectados] == ["carlos/a.csv"]
    assert len(avisos) == 1
    assert "idéntico" in avisos[0]


def test_fichero_ilegible(tmp_path, monkeypatch):
    _escribir(tmp_path / "carlos" / "a.csv", b"a\n")

    def _falla(_ruta):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr("finanzas.utilidades.sha256_fichero", _falla)
    detectados, avisos = escanear_carpeta(tmp_path)
    assert detectados == []
    assert "no se puede leer" in avisos[0]


def test_nodo_lee_la_carpeta_de_settings(tmp_path, monkeypatch):
    _escribir(tmp_path / "carlos" / "a.csv", b"a\n")
    monkeypatch.setenv("FINANZAS_RUTAS__INPUTS", str(tmp_path))
    salida = escanear_inputs({})
    assert [f.ruta for f in salida["ficheros_detectados"]] == ["carlos/a.csv"]
    assert salida["avisos"] == []


def test_grafo_propaga_los_avisos(tmp_path, monkeypatch):
    _escribir(tmp_path / "carlos" / "notas.pdf", b"%PDF")
    monkeypatch.setenv("FINANZAS_RUTAS__INPUTS", str(tmp_path))
    monkeypatch.setenv("PHOENIX_TELEMETRY_ENABLED", "false")
    monkeypatch.setenv("FINANZAS_RUTAS__BASE_DATOS", str(tmp_path / "t.db"))
    salida = construir_grafo_ingesta().invoke({}, construir_config())
    assert any("formato no admitido" in a for a in salida["avisos"])
