# Implementation status and roadmap — `finanzas`

> **READ THIS FIRST (instructions for any agent opening a session).**
>
> **Purpose of this document.** It is the single, living reference for the `finanzas` implementation. It says *where the project stands now*, *what to do next* and *how to check it*, so that you can start a session by reading only this file and carry on from the current point. It does not repeat the designs: it points to them.
>
> **How to use it.**
> 1. Read sections 1 to 4 (rules, snapshot, roadmap, next task). Pick the first task in section 3 that is not `[x]` and is not blocked, unless the user says otherwise.
> 2. For the design details of a task, open the plan named in its `Design:` line. Do not invent logic the plans do not describe: leave `# TODO(<id>)` and ask the user.
> 3. Before implementing anything non-trivial, follow the root `CLAUDE.md` (consult the `code-architect` subagent first; you, the main agent, make the edits).
> 4. **When you finish a task, update this file in the same session**: change its checkbox, fill `Verified:` with the command you ran and its result, add a row to the change log (section 8), and refresh the snapshot (section 2) if what is real or dummy changed. Update the "Last updated" line.
> 5. Never mark a task `[x]` without running its `Verified:` command.
>
> **Last updated:** 2026-11-21 · branch `feat/langgraph-standards` · HEAD `c9ab117` (EXT-1 to EXT-3 and the private settings overlay are committed; T0.3 is uncommitted). This file is versioned; the rest of `implementation_plans/` is git-ignored (root `.gitignore` ignores the folder contents except this file), so the other plans exist only on the user's disk.

---

## 0. Document map

| Document | Role |
|---|---|
| `CLAUDE.md` (repo root) | Working rules: British English, subagents, constraints, commands. **Binding.** |
| `implementation_plans/plan_implementacion_grafo_finanzas.md` | Base plan: graph topology, state, schema, phases 0 to 12 (all done, with dummy node logic) and Annex C (real logic, still to do). |
| `implementation_plans/plan_extension_xls_finanzas.md` | Excel extension: decisions X1 to X10, open points P5 to P9, phases EXT-0 to EXT-6. |
| `implementation_plans/estado_implementacion_finanzas.md` | **This file**: status, roadmap, next task, change log. |
| `implementation_plans/local_ai_design.md`, `implementacion-estandares-langgraph.md` | Context for the sibling `local_ai` project and the LangGraph standards (`.claude/skills/langgraph-*`). |

Language: documentation, comments, docstrings, commit messages and subagent briefs in **British English**. Identifiers keep the existing Spanish domain naming (`leer_fichero`, `importe_centimos`). Messages shown to the user (CLI output, `avisos`) stay in **Spanish**.

---

## 1. Standing rules (short form; the binding source is `CLAUDE.md`)

- Everything runs locally. Ollama and Phoenix on localhost only. No external services, no LiteLLM, Docker, WSL2, extra databases or chat UIs.
- **Real financial data never enters git.** `finanzas/data/` and `extractos/` are git-ignored; root `/*.xls`, `/*.xlsx`, `/*.pdf` too. Before any commit run `git status` and confirm nothing from `data/`, `.db`, `.env` is staged. Tests use synthetic fixtures only.
- **Private account data (IBANs, file patterns) lives only in `finanzas/settings.local.yaml`** (git-ignored; template: `finanzas/settings.local.example.yaml`). `cargar_settings()` merges it over `settings.yaml`; only `cuentas` and `cuentas_por_fichero` are accepted and each replaces the base value. **Never open, print or paste that file or `.env`, `finanzas/data/**` or `extractos/**`**: project deny rules in `.claude/settings.json` block the Read and Edit tools, and you must not work around them through the shell or by running code that prints those values. Mask IBANs in any output (first two characters and last four at most). `tests/test_sin_ibans_reales.py` fails if a tracked YAML contains a non-placeholder IBAN. Limit: the deny rules do not stop a subprocess such as `uv run python`, so this relies on you not printing these fields.
- Money is **integer cents**, never `float` (use `Decimal`, `ROUND_HALF_UP`).
- One SQLite connection per parallel branch (`obtener_conexion()`); never share one.
- Always pass `construir_config()` (`recursion_limit=1000`) when invoking graphs, and pass `config` through nested `invoke` calls.
- Commit **only when the user asks**, and only validated work. Commit trailer is set by the harness.
- Scripts are POSIX Bash with LF endings. Run `uv run pytest` and `uv run ruff check .` before declaring a task done.

---

## 2. Snapshot of the current state (2026-11-21)

### 2.1 What is real and what is dummy

| Component | Location (under `finanzas/src/finanzas/`) | State |
|---|---|---|
| Settings loading | `config.py`, `../settings.yaml` | **Real.** `formato.hoja_excel` is **not** there yet (EXT-4). `cuentas_por_fichero` is empty; the IBANs in `cuentas` are placeholders. |
| SQLite schema and connection (WAL) | `db/esquema.sql`, `db/conexion.py` | **Real.** `operaciones.fichero_id` is `NOT NULL` while the `Operacion` model carries `fichero_sha256`: `persistir` must resolve the id. `ficheros.formato` comment lists `csv \| tsv \| desconocido` (no CHECK, so `xls`/`xlsx` work; update the comment). |
| Domain models and states | `modelos/dominio.py`, `modelos/estados.py` | **Real.** `FormatoFichero` already has `xls`/`xlsx` (uncommitted). `EstadoExtraccion` and `ResultadoExtraccion` have **no `avisos`** yet (EXT-4). |
| Pure helpers | `utilidades.py` | **Real**, uncommitted additions: `detectar_formato_por_contenido`, `formato_de_fichero`, `importe_a_centimos`, `fecha_a_date`, `celda_a_texto`. |
| Excel reader | `lectura/excel.py` (new, uncommitted) | **Real.** `leer_excel`, `localizar_cabecera`. **Not wired into any graph node.** |
| Root graph | `grafos/raiz.py` | Topology real; `nodo_marcar_obsoletos` dummy. |
| Ingestion S1 | `grafos/ingesta/grafo.py` | Topology and fan-out real. **Dummy:** `recuperar_en_proceso`, `escanear_inputs` (returns two fixed fake files), `filtrar_pendientes`, `consolidar` (only the period union and avisos are real), and the `enriquecer` call. |
| Extraction S1.1 | `grafos/ingesta/extraccion.py` | Topology real. **Dummy:** `marcar_en_proceso`, `leer_fichero`, `normalizar`, `validar`, `persistir`. `resolver_formato` computes the real signature but the mapping is fixed. Nothing is written to the database. |
| Enrichment S1.2 | `grafos/ingesta/enriquecimiento.py` | Topology real, logic dummy (no LLM call). |
| Analysis S2, consultant S3 | `grafos/analisis.py`, `grafos/consultor/` | Dummy. |
| `comprobar_pendientes` | `grafos/comunes.py` | Dummy: returns a fixed warning text. |
| CLI | `cli.py` | Real wrappers (`procesar`, `reenriquecer`, `consultar`, `etiquetas`) over dummy graphs. |
| Tracing | `observabilidad.py`, `trazas.py` | Real. Skips registration when Phoenix does not answer (T0.3 done, uncommitted). |

### 2.2 Evidence from the first end-to-end run (2026-11-21)

- `uv run pytest` → **143 passed**.
- `finanzas procesar` with `PHOENIX_TELEMETRY_ENABLED=false` ends in under a second and traverses root, ingestion (two parallel extractions), enrichment (2 batches), analysis and close, **on dummy data**. The summary "Operaciones enriquecidas: 4 / Resúmenes generados: 2" is fixed output.
- After the run the database holds `ficheros 0`, `operaciones 0`, `resumenes 0`, `cuentas 2`, `categorias 15`.
- With tracing on and no Phoenix, the process did not exit within 2 minutes: `vaciar_trazas()` calls `_provider.force_flush()`, which blocks against `localhost:6006`.
- `leer_excel` reads all three real files (layout only checked, no values recorded here).

### 2.3 Real extracts (layout only, no personal data)

Files now live in `finanzas/data/inputs/<usuario>/` (moved 2026-11-21, decision P8).

| File | Sheet | Header | Data rows | Notes |
|---|---|---|---|---|
| `carlos/main_octubre.xls` | `Listado` | `fecha`, `concepto`, `fecha valor`, `importe`, `saldo` | 24 | Account layout. Dates are text `dd/mm/yyyy`; amounts numeric (`int`/`float`); balance numeric. |
| `conjunta/conjunta_octubre.xls` | `Listado` | same as above | 15 | **Same signature** as `main_octubre.xls`, so one mapping serves both. |
| `carlos/extracto_noviembre.xls` | `Listado` | `fecha de operación`, `fecha de proceso`, `concepto`, `importe`, `tarjeta` | 17 | Card layout, **different signature**, no balance column. 3 rows have no date (the "saldo anterior" row and trailing footer rows): skip them and report (X10). `tarjeta` holds card numbers as text: an identifier, never an amount, keep out of logs. The header cell `fecha de operación` contains a replacement character in the stored text; mappings must use that exact stored text. |

None contains an IBAN, so the account must come from `cuentas_por_fichero` (P2a answered). Negative amounts are expenses in all three (P9, closed).

---

## 3. Roadmap and checklist

Legend: `[ ]` pending · `[~]` in progress · `[x]` done · `[!]` blocked (reason given). Each task lists its design source and how to verify it.

### R0 — Hygiene

- [x] **T0.0 Format the codebase (first step).** Seven pre-existing files failed `ruff format --check`: `src/finanzas/cli.py`, `grafos/analisis.py`, `grafos/ingesta/extraccion.py`, `grafos/ingesta/grafo.py`, `observabilidad.py`, `tests/test_excel.py`, `tests/test_smoke.py`. Run `uv run ruff format .` from `finanzas/`, then re-run the checks. Whitespace and line-wrapping only, no logic change. *Done 2026-11-21.* Verified: `ruff format --check .` → 35 files already formatted; `ruff check .` clean; `uv run pytest` → 150 passed. Rule from now on: run `ruff format .` before declaring any task done, so this does not build up again.
- [x] **T0.1 Move the extracts** into `finanzas/data/inputs/carlos/` and `finanzas/data/inputs/conjunta/` (P8). *Done 2026-11-21.* Verified: `git status` shows no `.xls`; three files listed under `data/inputs`. `extractos/` now holds only an empty `carlota/` folder and empty folders; `Invoice-9BF0758D-14284193.pdf` stays in the repo root (not an extract, git-ignored).
- [x] **T0.2 Commit the EXT-1 to EXT-3 work** — *done 2026-11-21 in three commits: `8184d95` (Excel support), `f5a8742` (private settings overlay), `a0ac5ec` (ruff format). Working tree clean.* Original scope: (`utilidades.py`, `dominio.py`, `lectura/`, tests, fixtures, `pyproject.toml`, `uv.lock`, `.gitignore`, `.gitattributes`). Only when the user asks. Suggested split follows the plan's commit messages (EXT-1, EXT-2, EXT-3). Verified: `uv run pytest` and `uv run ruff check .` pass; `git status` clean of `data/`.
- [x] **T0.3 Fix the Phoenix hang on exit.** *Done 2026-11-21:* `_collector_accesible` (1 s TCP probe) skips `register()` with a Spanish warning when the collector does not answer, and `force_flush(timeout_millis=3000)` bounds the flush. Verified: `uv run pytest` → 153 passed; `ruff check` and `ruff format` clean; `uv run finanzas procesar` with Phoenix stopped exits in 2.8 s. Not checked: traces arriving with Phoenix running. Original scope: Bound `force_flush()` with a short timeout (for example `timeout_millis=3000`) in `vaciar_trazas`, and/or skip `register()` when `localhost:6006` does not answer; keep the "never break a run" rule. Design: `observabilidad.py` docstring ("if Phoenix is not running… the run continues"). Verified: `uv run finanzas procesar` with Phoenix stopped exits in seconds and prints only the warning; with Phoenix running, traces still arrive in project `finanzas`. Add a test with an unreachable endpoint.
- [ ] **T0.4 Documentation drift.** `finanzas/README.md`: `qwen3:27b` → `qwen3:32b` (see commit `2570d82`), status line, supported formats, input folder layout; `ficheros.formato` comment in `esquema.sql`. Overlaps EXT-6.

### R1 — Real extraction, S1.1 and S1 (base Annex C items 1 and 2, plus EXT-4)

Design: base plan phases 5 and 7 and Annex C; `plan_extension_xls_finanzas.md` EXT-1 step 4 and EXT-4; decisions X4 to X10. **Consult `code-architect` before starting** (several modules, `effort: high`). Suggested order inside R1:

- [ ] **T1.1 `escanear_inputs` real.** Walk `rutas.inputs/*/`; each subfolder is a `usuario`. For each file use `formato_de_fichero` (extension plus signature); unknown formats go to `avisos` and are ignored; compute `sha256_fichero`; `ruta` relative to `rutas.inputs`. Also add the EXT-1 step 4 behaviour (aviso per rejected file). Verified: run against `data/inputs` returns the 3 files with formats `xls`; a renamed HTML file yields `desconocido` plus an aviso.
- [ ] **T1.2 `recuperar_en_proceso` and `filtrar_pendientes` against the database.** `UPDATE ficheros SET estado='pendiente' WHERE estado='en_proceso'` with a Spanish aviso; drop files whose `sha256` is already `procesado` or `pendiente_confirmacion`. Own connection per node.
- [ ] **T1.3 `marcar_en_proceso` and `persistir` real.** UPSERT into `ficheros`; `persistir` in **one transaction**: resolve `fichero_id` from `sha256`, `INSERT OR IGNORE` operations by `hash_operacion`, set `ficheros.estado='procesado'`, `n_operaciones`, `procesado_en`. `marcar_error` and `marcar_pendiente_confirmacion` write `ficheros.estado`/`error`. Mind: `n_operaciones` should count rows actually inserted vs offered (decide and document).
- [ ] **T1.4 `leer_fichero` dispatch.** Excel branch uses `leer_excel(ruta, hoja=settings.formato.hoja_excel)`; add `formato.hoja_excel: 0 # TODO(P5)` to `settings.yaml` and `FormatoSettings`; add `avisos` to `EstadoExtraccion` (reducer `operator.add`) and `ResultadoExtraccion`. CSV/TSV branch (pandas, delimiter and encoding detection) is the base Annex C item 2 part. `# TODO(P1)` stays for PDF.
- [ ] **T1.5 `resolver_formato` real.** Look the signature up in `formatos_extracto`; if absent, an LLM (`settings.formato.modelo`, via local Ollama) proposes a `FormatoExtracto` from `filas_muestra` rows rendered with `celda_a_texto`; store with `confirmado = not requiere_confirmacion`; `formato_ok = formato.confirmado`. **Blocked on P4 follow-up**: with `requiere_confirmacion: true` a new signature stops at `pendiente_confirmacion` until the confirmation command exists (T3.3). Until then, allow seeding the two known mappings (account layout, card layout) so the real files can flow; record this as a decision here when taken.
- [ ] **T1.6 `normalizar` real.** `fecha_a_date`, `importe_a_centimos`, `celda_a_texto`; `columna_importe` or `columna_cargo`/`columna_abono`; skip rows with an empty date and count them; unparseable non-empty date or amount → `errores_validacion` with row number and column, never raise; `cuenta_iban` from `cuentas_por_fichero` (P2a); `calcular_hash_operacion` unchanged (X9). Duplicated identical rows in one file must stay distinct: check how the last argument of `calcular_hash_operacion` (occurrence index) is meant to be used.
- [ ] **T1.7 `validar` real.** Append to (never overwrite) `errores_validacion`; missing mapped column; reasonable date range; balance reconciliation when `columna_saldo` is mapped (account files only; the card file has none); footer count to `avisos`.
- [ ] **T1.8 Cross-check on the real files.** Run S1 on `data/inputs`. Expected: 3 files `procesado`, 24 + 15 + 14 operations (the card file has 17 rows, 3 without a date), no errors. Verified: row counts in `operaciones`, rerun yields zero new rows (idempotent), `finanzas procesar` summary no longer shows fixed numbers.

### R2 — Accounts and users (partly blocked on the user)

- [!] **T2.1 `cuentas_por_fichero` and real `cuentas`.** Blocked: the user will supply the real IBANs and file patterns later ("luego los meto"), **in `finanzas/settings.local.yaml`** (copy `settings.local.example.yaml`), not in `settings.yaml`. **Do not invent IBANs or patterns, and do not read that file.** Needed entries: `carlos` (account file pattern, card file pattern) and `conjunta`; replace the placeholder users `carlos`/`usuario2` in `cuentas` with the real users (`carlos`, `conjunta`, and `carlota` if she has an account; see O2). Until supplied, operations keep `cuenta_iban = NULL` and R1 must still work.
- [ ] **T2.2 Resolve `cuenta_iban` in `normalizar`** from the mapping once T2.1 is filled; unmapped file → aviso, `NULL` IBAN.

### R3 — Consolidation and enrichment

- [ ] **T3.1 `consolidar` real** (base Annex C item 3): classify `tipo_transferencia`; `carlos` ↔ `conjunta` is `entre_personas`, not `interna_propia` (P7, closed). Fallback without counterparty IBAN: opposite amount within `ventana_dias_emparejamiento`. Depends on T2.1. `# TODO(P2)`.
- [ ] **T3.2 Real enrichment S1.2** (Annex C item 4): JSONL batches, closed category list, `max_reintentos`, normalised `etiqueta_libre`, one transaction per batch, cursor pagination. Needs Ollama running with `qwen3:14b`. Verified with a stub model in tests plus one real run.
- [ ] **T3.3 `finanzas formatos confirmar <firma>`** (Annex C item 7, P4).

### R4 — Closing the Excel extension

- [ ] **T4.1 EXT-5** tests: `tests/test_extraccion_excel.py` (XLS/CSV same hash, end-to-end, footer ignored, multi-sheet warning, HTML disguised as XLS, no duplicates on reprocess and across CSV/XLS). Tests that need the real CSV reader may be skipped with a stated reason.
- [ ] **T4.2 EXT-6** README and plan updates (P1: XLS confirmed, PDF open).

### R5 — Later (out of scope for now)

- [ ] `comprobar_pendientes` real (Annex C item 1); S2 real; S3 real; persistent checkpointer; PDF reader (own plan). See base plan Annex C items 5, 6, 8, 9.

---

## 4. Next task

> **Next:** R1 starting at T1.1 (consult `code-architect` first, `effort: high`). T0.4 (README drift) is small and can go before or alongside.
> **Blocked on the user:** real IBANs and file patterns (T2.1); commit requests (T0.2).

---

## 5. Open points and decisions

| ID | Point | Status |
|---|---|---|
| P1 | Origin of extracts | **XLS confirmed**; PDF open (own plan). |
| P2 | IBAN in the extract | (a) **No IBAN in the files**: use `cuentas_por_fichero` (decided; values pending from the user). (b) Counterparty IBAN: open, fallback by opposite amount and date. |
| P3 | Local models | **Decided:** `qwen3:14b` (format mapping, enrichment), `qwen3:32b` (analysis, consultant). |
| P4 | Confirm new formats by hand | **Decided:** yes (`requiere_confirmacion: true`). Confirmation command not built (T3.3). |
| P5 | Layout of the real XLS | **Answered** (section 2.3). Open: whether the bank's other exports match. |
| P6 | HTML disguised as `.xls` | Rejected with a clear message; add a reader only if a real file needs it. |
| P7 | Joint account | **Closed:** its own user `conjunta`; transfers with `carlos` are `entre_personas`. |
| P8 | File ownership | **Closed and executed:** `finanzas/data/inputs/carlos/`, `finanzas/data/inputs/conjunta/`. |
| P9 | Card sign convention | **Closed:** negative = expense. |
| O1 | Phoenix not running blocks process exit | **Fixed 2026-11-21** (T0.3). |
| O2 | User naming: `settings.yaml` has `carlos`/`usuario2`, folders were `carlos`/`carlota`/`conjunta` | Open, ask the user. `extractos/carlota/` is empty and was left alone. |
| O4 | `finanzas/settings.yaml` line 19 reads `qwen3:3 2b` (stray space; should be `qwen3:32b`). An uncommitted edit not made by an agent. | **Fixed 2026-11-21** (now `qwen3:32b`). The line changed twice during the session (`3 2b`, then `3 32b`), so something outside the agents was editing it: re-check it after the next editor session. |
| O5 | Deny rules only block the Read/Edit tools, not subprocesses (`uv run python`, shell) | Known limit; an OS-level sandbox would be the only hard block (not evaluated on Windows). |
| O3 | `Invoice-9BF0758D-14284193.pdf` in the repo root | Not an extract; left in place (git-ignored). Ask the user where it belongs. |

---

## 6. Code map

```
finanzas/
  settings.yaml                        rutas.inputs = data/inputs (relative to finanzas/)
  data/inputs/<usuario>/*.xls|csv      real statements (git-ignored)
  data/finanzas.db                     real database (git-ignored)
  src/finanzas/
    cli.py                             procesar | reenriquecer | consultar | etiquetas
    config.py  observabilidad.py  trazas.py  utilidades.py
    db/esquema.sql  db/conexion.py
    modelos/dominio.py  modelos/estados.py
    lectura/excel.py                   leer_excel (real, not yet wired)
    grafos/raiz.py  comunes.py  analisis.py
    grafos/ingesta/grafo.py            S1 (fan-out with Send)
    grafos/ingesta/extraccion.py       S1.1 (per file)
    grafos/ingesta/enriquecimiento.py  S1.2 (batch loop with cursor)
    grafos/consultor/
  tests/                               143 tests; fixtures/ synthetic only
```

---

## 7. Verification commands

Run from `finanzas/` (the shell may warn that `VIRTUAL_ENV` points to the repo-root venv; it is harmless).

```bash
uv run pytest                                   # all tests, no real inference
uv run ruff check . && uv run ruff format --check .
PHOENIX_TELEMETRY_ENABLED=false uv run finanzas procesar   # full flow without tracing
git status                                      # nothing from data/, .db or .env staged
```

Row counts in the real database:

```bash
uv run python -c "
import sqlite3
c = sqlite3.connect('data/finanzas.db')
for t in ['ficheros','formatos_extracto','cuentas','categorias','operaciones','resumenes']:
    print(t, c.execute(f'select count(*) from {t}').fetchone()[0])
"
```

Do not print amounts, concepts, card numbers or IBANs from real files into logs or into this document.

---

## 8. Change log

| Date | Task | Commit | Notes |
|---|---|---|---|
| 2026-11-21 | Reconnaissance run of `finanzas procesar`, tests and `leer_excel` on the real files | — | Findings in section 2.2. No code changed. |
| 2026-11-21 | T0.1 Moved the three `.xls` files to `finanzas/data/inputs/{carlos,conjunta}/` | — (git-ignored) | P8 executed. |
| 2026-11-21 | Created this document | — | Not committed. |
| 2026-11-21 | Private settings overlay: `config.py` (`settings.local.yaml`, allow-list, lists replaced, skipped with explicit `ruta`), ignore rules, `settings.local.example.yaml`, `tests/conftest.py` (hermetic), `test_config_local.py`, `test_sin_ibans_reales.py`, `.claude/settings.json` deny rules, masked IBAN in the `conexion.py` warning | — (uncommitted) | `uv run pytest` → 150 passed; `ruff check` clean. The `Read` deny was seen to work; the default-path overlay was not run end to end with a real file on purpose. The 7 older files that failed `ruff format --check` were fixed afterwards (T0.0). |
| 2026-11-21 | T0.2 Committed everything pending | `8184d95`, `f5a8742`, `a0ac5ec` | EXT-1 to EXT-3, private settings overlay, formatting. Fixed `qwen3:32b` typo in `settings.yaml` beforehand (O4). |
| 2026-11-21 | Versioned this document (`.gitignore` exception) | `c9ab117` | The other plans stay ignored. |
| 2026-11-21 | T0.3 Phoenix hang: reachability probe and bounded flush in `observabilidad.py`, new `tests/test_observabilidad.py` | — (uncommitted) | 153 tests pass; `procesar` exits in 2.8 s without Phoenix. |
| 2026-11-21 | T0.0 `ruff format .` over 7 files | `a0ac5ec` | Formatting only. `ruff format --check` clean, `ruff check` clean, 150 tests pass. |
