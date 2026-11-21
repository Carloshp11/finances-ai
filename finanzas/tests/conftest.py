"""Shared fixtures."""

import pytest
from finanzas import config


@pytest.fixture(autouse=True)
def sin_settings_locales(tmp_path, monkeypatch):
    """A developer's real settings.local.yaml must never leak into the tests."""
    monkeypatch.setattr(config, "RUTA_SETTINGS_LOCAL", tmp_path / "no_existe.yaml")
