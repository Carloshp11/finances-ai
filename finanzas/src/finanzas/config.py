"""Carga de la configuración desde settings.yaml con sobreescritura por variables de entorno.

Opción elegida: se reordenan las fuentes de pydantic-settings para que las variables de
entorno (prefijo FINANZAS_, anidado con "__") ganen al YAML. El YAML se pasa como
argumentos iniciales (init_settings), que por defecto tienen prioridad máxima; por eso
se devuelve env_settings antes que init_settings.
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
        """Carpeta donde se publican los resúmenes en markdown."""
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
        # Orden de prioridad (primero gana): entorno, luego YAML (init), luego el resto.
        return (env_settings, init_settings, dotenv_settings, file_secret_settings)


def cargar_settings(ruta: str | Path = "settings.yaml") -> Settings:
    """Lee el YAML con yaml.safe_load y construye Settings.

    Las variables de entorno FINANZAS_* tienen prioridad sobre el YAML
    (ver settings_customise_sources).
    """
    with open(ruta, encoding="utf-8") as fichero:
        datos: dict[str, Any] = yaml.safe_load(fichero) or {}
    return Settings(**datos)
