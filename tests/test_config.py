from pathlib import Path

import pytest

from local_ai.config import ConfigError, load_settings

ENV_KEYS = [
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
    "OLLAMA_TEMPERATURE",
    "OLLAMA_NUM_CTX",
    "PHOENIX_COLLECTOR_ENDPOINT",
    "PHOENIX_PROJECT_NAME",
    "PHOENIX_TELEMETRY_ENABLED",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_defaults_when_no_env_file(tmp_path: Path) -> None:
    settings = load_settings(tmp_path / "missing.env")
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.ollama_model == "qwen3:14b"
    assert settings.ollama_num_ctx == 8192
    assert settings.phoenix_telemetry_enabled is False


def test_env_file_is_read(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OLLAMA_MODEL=llama3.2:3b\nOLLAMA_NUM_CTX=4096\n", encoding="utf-8")
    settings = load_settings(env_file)
    assert settings.ollama_model == "llama3.2:3b"
    assert settings.ollama_num_ctx == 4096


def test_invalid_integer_raises_clear_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OLLAMA_NUM_CTX", "lots")
    with pytest.raises(ConfigError, match="OLLAMA_NUM_CTX must be an integer"):
        load_settings(tmp_path / "missing.env")


def test_invalid_bool_raises_clear_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PHOENIX_TELEMETRY_ENABLED", "maybe")
    with pytest.raises(ConfigError, match="PHOENIX_TELEMETRY_ENABLED must be true or false"):
        load_settings(tmp_path / "missing.env")
