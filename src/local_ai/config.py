"""Application configuration loaded from the environment and an optional .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = REPO_ROOT / ".env"


class ConfigError(ValueError):
    """Raised when configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str
    ollama_model: str
    ollama_temperature: float
    ollama_num_ctx: int
    phoenix_collector_endpoint: str
    phoenix_project_name: str
    phoenix_telemetry_enabled: bool


def _get(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def _parse_float(name: str, raw: str) -> float:
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc


def _parse_int(name: str, raw: str, minimum: int = 1) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc
    if value < minimum:
        raise ConfigError(f"{name} must be >= {minimum}, got {value}")
    return value


def _parse_bool(name: str, raw: str) -> bool:
    normalized = raw.lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be true or false, got {raw!r}")


def load_settings(env_file: Path | None = None) -> Settings:
    """Load settings from the environment, reading the .env file first if present.

    Variables already set in the real environment take precedence over .env.
    Nodes of the graph must not read the environment directly; they receive
    what they need from the entry point.
    """
    path = env_file if env_file is not None else DEFAULT_ENV_FILE
    if path.is_file():
        load_dotenv(path, override=False)

    return Settings(
        ollama_base_url=_get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
        ollama_model=_get("OLLAMA_MODEL", "qwen3:14b"),
        ollama_temperature=_parse_float("OLLAMA_TEMPERATURE", _get("OLLAMA_TEMPERATURE", "0")),
        ollama_num_ctx=_parse_int("OLLAMA_NUM_CTX", _get("OLLAMA_NUM_CTX", "8192")),
        phoenix_collector_endpoint=_get(
            "PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces"
        ),
        phoenix_project_name=_get("PHOENIX_PROJECT_NAME", "local-ai"),
        phoenix_telemetry_enabled=_parse_bool(
            "PHOENIX_TELEMETRY_ENABLED", _get("PHOENIX_TELEMETRY_ENABLED", "false")
        ),
    )
