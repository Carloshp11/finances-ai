# Synthetic fixtures

Invented data only, no real account, name or amount. Generated once with a throwaway script (not stored in the repository) using xlwt and the command:

```bash
uv run --no-project --with xlwt python gen_fixtures.py finanzas/tests/fixtures
```

- `extracto_sintetico.xls`: sheet `Movimientos` (title, empty row, header, three operations, an empty row, footer `Saldo final`) and sheet `Hoja2` (multi-sheet warning).
- `extracto_html_disfrazado.xls`: HTML saved with an `.xls` name (P6).
- `extracto_sintetico.csv`: the same three operations as the workbook, for the CSV/XLS deduplication test (EXT-5).
