"""Console trace helper for the graph nodes."""

from datetime import datetime


def traza(grafo: str, nodo: str, detalle: str = "") -> None:
    """Print that a node was reached. Call it as the FIRST line of each node."""
    marca = datetime.now().isoformat(timespec="seconds")
    extra = f" — {detalle}" if detalle else ""
    print(f"[{marca}] {grafo}.{nodo}: he pasado por aquí{extra}", flush=True)
