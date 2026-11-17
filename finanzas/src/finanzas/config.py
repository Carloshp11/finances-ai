"""Configuration loading from settings.yaml, with overrides from environment variables.

Chosen approach: the pydantic-settings sources are reordered so that environment variables
(prefix FINANZAS_, nested with "__") win over the YAML. The YAML is passed as initial
arguments (init_settings), which by default have the highest priority; that is why
env_settings is returned before init_settings.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class RutasSettings(BaseModel):
    inputs: Path
    outputs: Path
    base_datos: Path

    @property
    def ruta_resumenes(self) -> Path:
        """Folder where the markdown summaries are published."""
        return self.outputs / "resumenes"


class FormatoSettings(BaseModel):
    modelo: str
    filas_muestra: int
    requiere_confirmacion: bool


class EnriquecimientoSettings(BaseModel):
    modelo: str
    tamano_lote: int
    max_reintentos: int
    formato_entrada: str
    version_prompt: str


class AnalisisSettings(BaseModel):
    modelo: str


class ConsultorSettings(BaseModel):
    modelo: str


class TransferenciasSettings(BaseModel):
    ventana_dias_emparejamiento: int


class CuentaConfig(BaseModel):
    iban: str
    usuario: str
    alias: str | None = None


class CuentaPorFicheroConfig(BaseModel):
    usuario: str
    patron: str
    iban: str


class CategoriaConfig(BaseModel):
    nombre: str
    descripcion: str


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FINANZAS_", env_nested_delimiter="__")

    rutas: RutasSettings
    formato: FormatoSettings
    enriquecimiento: EnriquecimientoSettings
    analisis: AnalisisSettings
    consultor: ConsultorSettings
    transferencias: TransferenciasSettings
    cuentas: list[CuentaConfig] = Field(default_factory=list)
    cuentas_por_fichero: list[CuentaPorFicheroConfig] = Field(default_factory=list)
    categorias: list[CategoriaConfig] = Field(default_factory=list)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Priority order (first wins): environment, then YAML (init), then the rest.
        return (env_settings, init_settings, dotenv_settings, file_secret_settings)


RAIZ_PROYECTO = Path(__file__).resolve().parents[2]


def cargar_settings(ruta: str | Path | None = None) -> Settings:
    """Read the YAML with yaml.safe_load and build Settings.

    By default it uses <project root>/settings.yaml, so it works from any directory.
    Relative paths in `rutas` are resolved against the project root.
    FINANZAS_* environment variables take priority over the YAML
    (see settings_customise_sources).
    """
    ruta_yaml = Path(ruta) if ruta is not None else RAIZ_PROYECTO / "settings.yaml"
    with open(ruta_yaml, encoding="utf-8") as fichero:
        datos: dict[str, Any] = yaml.safe_load(fichero) or {}
    settings = Settings(**datos)
    for campo in ("inputs", "outputs", "base_datos"):
        valor = getattr(settings.rutas, campo)
        if not valor.is_absolute():
            setattr(settings.rutas, campo, RAIZ_PROYECTO / valor)
    return settings
