# finanzas

LangGraph system for household finances. It ingests bank statements, enriches each operation
with a local LLM, produces weekly and monthly summaries, and offers a conversational consultant
in the terminal.

**Status:** skeleton. The topology of the graphs, the CLI and the database are real. The logic
inside each node is a dummy that prints a trace and returns fixed values. See
`../implementation_plans/plan_implementacion_grafo_finanzas.md`.

## Requirements

- [uv](https://docs.astral.sh/uv/) (manages Python 3.11 and the dependencies).
- Optional: Langfuse, configured through the standard environment variables.

## Setup

```bash
uv sync
```

Put statements in `data/inputs/<user>/`, one subfolder per person. The subfolder name is the user
identifier. Accounts and categories are defined in `settings.yaml`. Environment variables with the
`FINANZAS_` prefix override any setting, using `__` for nesting, for example:

```bash
FINANZAS_ENRIQUECIMIENTO__TAMANO_LOTE=50 uv run finanzas procesar
```

## Commands

```bash
uv run finanzas procesar
uv run finanzas reenriquecer --desde 2026-10-01 --hasta 2026-11-15 [--usuario carlos]
uv run finanzas consultar [--hilo ID]
uv run finanzas etiquetas [--min N]
```

- `procesar`: ingests new files, enriches pending operations and regenerates the summaries.
- `reenriquecer`: re-enriches a date range and always regenerates the affected periods.
- `consultar`: interactive consultant (type `salir` to leave).
- `etiquetas`: lists the free-text labels proposed by the LLM. `*` marks labels that do not match
  any category in the closed list.

## Tracing (Langfuse)

Traces are sent only when `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set. Point
`LANGFUSE_HOST` (or `LANGFUSE_BASE_URL`) at a local or self-hosted instance, so that data stays on
this machine. Without these variables nothing leaves the machine.

## Tests

```bash
uv run pytest
uv run --with ruff ruff check src tests
```

The tests use a temporary database and never touch `data/finanzas.db`.

## Open points

| ID | Point | Current handling |
|---|---|---|
| P1 | Origin of the statements: whether the bank's web app exports CSV/XLSX, or another route is needed (for example a PSD2 aggregator). | `leer_fichero` is isolated (`TODO(P1)`). |
| P2 | Whether the CSV contains the account IBAN and the counterparty IBAN. | Fallback mapping in `settings.yaml` (`cuentas_por_fichero`) and matching by opposite amount within ±2 days (`TODO(P2)` in `consolidar`). |
| P3 | Concrete local models. | `modelo: PENDIENTE` in `settings.yaml` (`TODO(P3)`). |
| P4 | Whether new formats must be confirmed by hand. | `formato.requiere_confirmacion: true` by default (`TODO(P4)`). The confirmation command is out of scope for now. |
