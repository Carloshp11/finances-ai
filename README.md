# finances-ai

Personal project to help with my home finances using generative AI.

Este repositorio contiene el entorno local de desarrollo de IA generativa: modelos
locales con Ollama, grafos con LangGraph y trazas con Arize Phoenix. Todo se ejecuta en
el propio equipo; no se envían datos a servicios externos.

## Requisitos

- Windows 11 con Git for Windows (incluye Git Bash).
- Controlador NVIDIA reciente (`nvidia-smi` debe funcionar).
- [Ollama para Windows](https://ollama.com/download).
- [uv](https://docs.astral.sh/uv/) (gestiona Python y las dependencias).

Todos los comandos se ejecutan desde **Git Bash**, en la raíz del repositorio.

## Instalación inicial

```bash
./scripts/setup.sh
```

El script crea `.env` a partir de `.env.example` si no existe, sincroniza el entorno
con `uv sync` y descarga el modelo de Ollama (`qwen3:14b`) solo si falta.

Para instalar las herramientas por separado desde PowerShell (una sola vez):

```powershell
winget install --id astral-sh.uv -e
winget install --id Ollama.Ollama -e
```

## Configuración

La configuración está en `.env` (ignorado por Git). La plantilla versionada es `.env.example`:

| Variable | Valor por defecto | Descripción |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Servidor local de Ollama. |
| `OLLAMA_MODEL` | `qwen3:14b` | Modelo a usar. Cambiarlo no requiere tocar código. |
| `OLLAMA_TEMPERATURE` | `0` | Temperatura del modelo. |
| `OLLAMA_NUM_CTX` | `8192` | Tamaño de contexto. |
| `PHOENIX_COLLECTOR_ENDPOINT` | `http://localhost:6006/v1/traces` | Colector OTLP de Phoenix (local). |
| `PHOENIX_PROJECT_NAME` | `local-ai` | Proyecto donde aparecen las trazas. |
| `PHOENIX_TELEMETRY_ENABLED` | `false` | Telemetría propia de Phoenix (se aplica al servidor). |

## Uso

### 1. Arrancar Phoenix

En una terminal Git Bash:

```bash
./scripts/start_phoenix.sh
```

Interfaz: <http://localhost:6006>. Los datos se guardan en
`~/.local/share/finances-ai/phoenix`, fuera del repositorio (se puede cambiar con
`PHOENIX_DATA_DIR`). Para detenerlo, pulsar `Ctrl+C` en esa terminal.

### 2. Ejecutar el grafo

En otra terminal Git Bash:

```bash
./scripts/run_graph.sh "Explica en una frase qué es LangGraph."
```

El grafo tiene dos nodos (`prepare_prompt` → `generate_response`), invoca el modelo de
Ollama e imprime la respuesta. La ejecución aparece como traza en el proyecto `local-ai`
de Phoenix. Si Ollama o Phoenix no están disponibles, el programa muestra un error claro.

### Comandos útiles

```bash
uv sync                  # instalar o actualizar dependencias
uv run pytest            # pruebas
uv run ruff check .      # lint
ollama list              # modelos descargados
ollama ps                # modelos cargados y uso de GPU
```

## Estructura

```text
.
├── scripts/            # Scripts Bash (setup, Phoenix, ejecución del grafo)
├── src/local_ai/
│   ├── config.py       # Carga y validación de .env
│   ├── main.py         # Punto de entrada
│   ├── models/factory.py        # Factoría de modelos (frontera de proveedor)
│   ├── graphs/hello_world.py    # Grafo de dos nodos
│   └── observability/phoenix.py # Instrumentación OpenTelemetry → Phoenix local
└── tests/              # Pruebas que no requieren inferencia real
```

Los grafos no crean modelos directamente: reciben el modelo desde la factoría
(`create_model`), lo que permite añadir otros proveedores sin modificar los grafos.

## Desarrollo

- Dependencias de la aplicación: `uv add <paquete>`. Dependencias de desarrollo: `uv add --dev <paquete>`.
- Phoenix no es una dependencia del proyecto: se ejecuta con `uvx arize-phoenix serve`.
- Los scripts son Bash POSIX con finales de línea LF (ver `.gitattributes`).
