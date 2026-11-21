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
RUTA_SETTINGS = RAIZ_PROYECTO / "settings.yaml"
RUTA_SETTINGS_LOCAL = RAIZ_PROYECTO / "settings.local.yaml"

# Keys that may come from the git-ignored local file: private data only. Anything else in
# that file is rejected, so a stray entry cannot silently change paths, models or categories.
CLAVES_LOCALES_PERMITIDAS = frozenset({"cuentas", "cuentas_por_fichero"})


def _leer_yaml(ruta: Path) -> dict[str, Any]:
    with open(ruta, encoding="utf-8") as fichero:
        return yaml.safe_load(fichero) or {}


def _aplicar_overlay_local(datos: dict[str, Any], ruta_local: Path | None) -> dict[str, Any]:
    """Replace the allow-listed keys with those of the local file, if it exists.

    A missing file is not an error. Each key REPLACES the base value (lists are never
    concatenated), so the placeholders in settings.yaml disappear once real values exist.
    """
    if ruta_local is None or not ruta_local.is_file():
        return datos
    local = _leer_yaml(ruta_local)
    desconocidas = sorted(set(local) - CLAVES_LOCALES_PERMITIDAS)
    if desconocidas:
        # Key names only, never values: they may be private.
        raise ValueError(
            f"{ruta_local.name}: claves no permitidas {desconocidas}; "
            f"solo se admiten {sorted(CLAVES_LOCALES_PERMITIDAS)}"
        )
    return {**datos, **local}


def cargar_settings(
    ruta: str | Path | None = None, ruta_local: str | Path | None = None
) -> Settings:
    """Read the YAML with yaml.safe_load and build Settings.

    By default it uses <project root>/settings.yaml, so it works from any directory,
    merged with <project root>/settings.local.yaml when that git-ignored file exists
    (only `cuentas` and `cuentas_por_fichero`, replaced wholesale).
    With an explicit `ruta` the local overlay is skipped unless `ruta_local` is also given.
    Relative paths in `rutas` are resolved against the project root.
    Priority: FINANZAS_* environment variables > local overlay > settings.yaml
    (see settings_customise_sources).
    """
    if ruta is None:
        ruta_yaml = RUTA_SETTINGS
        local = RUTA_SETTINGS_LOCAL if ruta_local is None else Path(ruta_local)
    else:
        ruta_yaml = Path(ruta)
        local = None if ruta_local is None else Path(ruta_local)
    datos = _aplicar_overlay_local(_leer_yaml(ruta_yaml), local)
    settings = Settings(**datos)
    for campo in ("inputs", "outputs", "base_datos"):
        valor = getattr(settings.rutas, campo)
        if not valor.is_absolute():
            setattr(settings.rutas, campo, RAIZ_PROYECTO / valor)
    return settings
