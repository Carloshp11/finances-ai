"""Command-line interface: procesar, reenriquecer, consultar and etiquetas."""

import argparse
import sys
from datetime import date
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from finanzas.config import cargar_settings
from finanzas.db.conexion import inicializar_bd, obtener_conexion
from finanzas.grafos.comunes import comprobar_pendientes
from finanzas.grafos.consultor.grafo import construir_grafo_consultor
from finanzas.grafos.raiz import construir_grafo_raiz
from finanzas.modelos.dominio import FiltroEnriquecimiento
from finanzas.observabilidad import construir_config, vaciar_trazas
from finanzas.utilidades import normalizar_texto

_SALIDAS = {"salir", "exit", "quit"}


def _fecha(texto: str) -> date:
    try:
        return date.fromisoformat(texto)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"fecha no válida '{texto}' (usa YYYY-MM-DD)") from error


def _construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="finanzas", description="Finanzas del hogar")
    subcomandos = parser.add_subparsers(dest="comando", required=True)

    subcomandos.add_parser("procesar", help="Ingesta de extractos y análisis")

    reenr = subcomandos.add_parser("reenriquecer", help="Reenriquecer un rango de fechas")
    reenr.add_argument("--desde", type=_fecha, required=True, help="YYYY-MM-DD")
    reenr.add_argument("--hasta", type=_fecha, required=True, help="YYYY-MM-DD")
    reenr.add_argument("--usuario", default=None, help="Limitar a un usuario")

    consultar = subcomandos.add_parser("consultar", help="Consultor interactivo (REPL)")
    consultar.add_argument("--hilo", default=None, help="Identificador de la conversación")

    etiq = subcomandos.add_parser("etiquetas", help="Listar etiquetas libres")
    etiq.add_argument("--min", type=int, default=1, help="Mínimo de apariciones")
    return parser


def _cmd_procesar() -> int:
    grafo = construir_grafo_raiz()
    grafo.invoke({"modo": "procesar"}, construir_config())
    return 0


def _cmd_reenriquecer(args: argparse.Namespace) -> int:
    if args.desde > args.hasta:
        print("Error: --desde debe ser anterior o igual a --hasta.", file=sys.stderr)
        return 2
    filtro = FiltroEnriquecimiento(
        modo="rango", desde=args.desde, hasta=args.hasta, usuario=args.usuario
    )
    grafo = construir_grafo_raiz()
    grafo.invoke({"modo": "reenriquecer", "filtro_reenriquecimiento": filtro}, construir_config())
    return 0


def _cmd_consultar(args: argparse.Namespace) -> int:
    # The consultor never goes through the root graph and never blocks on pending work.
    inicializar_bd(cargar_settings())
    aviso = comprobar_pendientes()
    if aviso:
        print(f"AVISO: {aviso}")
    grafo = construir_grafo_consultor(InMemorySaver())
    cfg = construir_config(thread_id=args.hilo or str(uuid4()))
    primera = True
    while True:
        try:
            texto = input("tú> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if texto in _SALIDAS:
            break
        if not texto:
            continue
        entrada: dict = {"messages": [HumanMessage(texto)]}
        if primera:
            entrada["aviso_inicial"] = aviso
            primera = False
        salida = grafo.invoke(entrada, cfg)
        print(f"finanzas> {salida['messages'][-1].content}")
    return 0


def _cmd_etiquetas(args: argparse.Namespace) -> int:
    settings = cargar_settings()
    inicializar_bd(settings)
    conn = obtener_conexion(settings.rutas.base_datos)
    try:
        filas = conn.execute(
            """
            SELECT etiqueta_libre, COUNT(*) AS n FROM operaciones
            WHERE etiqueta_libre IS NOT NULL
            GROUP BY etiqueta_libre HAVING n >= ?
            ORDER BY n DESC
            """,
            (args.min,),
        ).fetchall()
        nombres = conn.execute("SELECT nombre FROM categorias").fetchall()
        categorias = {normalizar_texto(f["nombre"]) for f in nombres}
    finally:
        conn.close()

    if not filas:
        print("No hay etiquetas libres todavía.")
        return 0
    for fila in filas:
        marca = " " if normalizar_texto(fila["etiqueta_libre"]) in categorias else "*"
        print(f"{marca} {fila['etiqueta_libre']}: {fila['n']}")
    print("(* = no coincide con ninguna categoría de la lista cerrada)")
    return 0


def main(argv: list[str] | None = None) -> None:
    # Windows consoles can use a legacy code page; force UTF-8 so accents and symbols print.
    sys.stdout.reconfigure(encoding="utf-8")
    args = _construir_parser().parse_args(argv)
    try:
        if args.comando == "procesar":
            codigo = _cmd_procesar()
        elif args.comando == "reenriquecer":
            codigo = _cmd_reenriquecer(args)
        elif args.comando == "consultar":
            codigo = _cmd_consultar(args)
        else:
            codigo = _cmd_etiquetas(args)
    finally:
        vaciar_trazas()
    sys.exit(codigo)
