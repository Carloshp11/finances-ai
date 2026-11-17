"""SQLite connection, schema creation and idempotent start-up synchronisation.

Each thread or parallel branch must open its own connection with obtener_conexion().
Connections are never shared between branches.
"""

import sqlite3
from pathlib import Path

from finanzas.config import CategoriaConfig, CuentaConfig, Settings

_ESQUEMA = Path(__file__).parent / "esquema.sql"


def _normalizar_iban(iban: str) -> str:
    # Temporary local copy; replaced by finanzas.utilidades.normalizar_iban in Phase 3.
    return iban.replace(" ", "").upper()


def obtener_conexion(ruta_bd: Path) -> sqlite3.Connection:
    """Open a connection with WAL, foreign keys and busy_timeout.

    Each thread or parallel branch must open ITS OWN connection.
    """
    ruta_bd = Path(ruta_bd)
    ruta_bd.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ruta_bd, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def crear_esquema(conn: sqlite3.Connection) -> None:
    """Run esquema.sql. Every statement uses IF NOT EXISTS, so it is idempotent."""
    conn.executescript(_ESQUEMA.read_text(encoding="utf-8"))


def sincronizar_cuentas(conn: sqlite3.Connection, cuentas: list[CuentaConfig]) -> None:
    """UPSERT each account. IBANs are normalised.

    Accounts in the database but absent from settings are NOT deleted; only a warning is printed.
    """
    ibans_config = set()
    for cuenta in cuentas:
        iban = _normalizar_iban(cuenta.iban)
        ibans_config.add(iban)
        conn.execute(
            """
            INSERT INTO cuentas (iban, usuario, alias) VALUES (?, ?, ?)
            ON CONFLICT(iban) DO UPDATE SET usuario = excluded.usuario, alias = excluded.alias
            """,
            (iban, cuenta.usuario, cuenta.alias),
        )
    for fila in conn.execute("SELECT iban FROM cuentas"):
        if fila["iban"] not in ibans_config:
            print(f"Aviso: la cuenta {fila['iban']} está en la BD pero no en settings.yaml")


def sincronizar_categorias(conn: sqlite3.Connection, categorias: list[CategoriaConfig]) -> None:
    """UPSERT each category with activa=1.

    Categories in the database but absent from settings are set to activa=0, never deleted,
    because operaciones references them through a foreign key.
    """
    nombres_config = set()
    for categoria in categorias:
        nombres_config.add(categoria.nombre)
        conn.execute(
            """
            INSERT INTO categorias (nombre, descripcion, activa) VALUES (?, ?, 1)
            ON CONFLICT(nombre) DO UPDATE SET descripcion = excluded.descripcion, activa = 1
            """,
            (categoria.nombre, categoria.descripcion),
        )
    for fila in conn.execute("SELECT nombre FROM categorias"):
        if fila["nombre"] not in nombres_config:
            conn.execute("UPDATE categorias SET activa = 0 WHERE nombre = ?", (fila["nombre"],))


def inicializar_bd(settings: Settings) -> None:
    """Open a connection, create the schema, sync accounts and categories, then close. Idempotent."""
    conn = obtener_conexion(settings.rutas.base_datos)
    try:
        with conn:
            crear_esquema(conn)
            sincronizar_cuentas(conn, settings.cuentas)
            sincronizar_categorias(conn, settings.categorias)
    finally:
        conn.close()
