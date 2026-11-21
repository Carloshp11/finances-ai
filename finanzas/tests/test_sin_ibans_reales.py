"""Guard: tracked configuration files must not contain real IBANs."""

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
PLACEHOLDERS = {"ES0000000000000000000000", "ES1111111111111111111111"}
# Spanish IBAN with optional spaces between digits. Widen if foreign accounts appear.
PATRON_IBAN = re.compile(r"\bES(?:[ \t]?\d){22}\b", re.IGNORECASE)


@pytest.mark.parametrize("nombre", ["settings.yaml", "settings.local.example.yaml"])
def test_fichero_versionado_sin_ibans_reales(nombre):
    # Raw text on purpose: an IBAN pasted into a comment is caught too.
    texto = (RAIZ / nombre).read_text(encoding="utf-8")
    encontrados = {re.sub(r"\s", "", m.group()).upper() for m in PATRON_IBAN.finditer(texto)}
    reales = encontrados - PLACEHOLDERS
    # Count only: the message must never print the IBAN itself.
    assert not reales, f"{nombre} contiene {len(reales)} IBAN(s) que no son placeholders"
