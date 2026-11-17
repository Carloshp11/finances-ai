---
name: langgraph-node-standards
description: Standards for organizing and implementing LangGraph nodes — folder structure, node class interface, Pydantic contracts, helper libraries and design documentation.
user-invocable: true
disable-model-invocation: true
---

# LangGraph node standards

## Required reading

Before applying these standards, read with the Read tool:

- `.claude/conventions/langgraph/state-contracts.md`
- `.claude/conventions/langgraph/naming.md`

If the node needs a design.md, also read `.claude/skills/langgraph-design-doc/SKILL.md`.

## 1. Folder structure

Each node lives in its own folder. The folder name equals the main module name and the node name (`<role>_<instance>`).

```text
nodes/
└── <role>_<instance>/
    ├── __init__.py
    ├── <role>_<instance>.py
    ├── pydantic.py
    ├── design.md          # optional
    └── library/           # optional
        ├── __init__.py
        └── helpers.py
```

The location of the `nodes/` folder follows the existing repository structure.
Optional elements are created only when justified.

## 2. Responsibilities

| File | Responsibility |
|---|---|
| `<role>_<instance>.py` | The node class: main logic and orchestration. |
| `pydantic.py` | Input, Output and State contracts, following the state-contracts convention. |
| `library/` | Helper functions that materially improve readability and modularity. |
| `design.md` | Relevant functional or architectural decisions. |

## 3. Contracts

Follow `.claude/conventions/langgraph/state-contracts.md` exactly: three models (`Input`, `Output`, `State(Input, Output)`), every field with `Field(description=...)`.

## 4. Node class

Each node is one class named in PascalCase after the node name.

- `__init__`: optional. Only for dependencies or configuration (LLM client, prompts, settings). Omit it if there is nothing to initialize.
- `__call__(self, state)`: mandatory. Contains the main logic of the node. It reads the fields it needs and returns a dict with only the fields it updates, which must belong to the node's Output or extra State fields.
- `conditional_edge(self, state)`: mandatory, always present.
  - If the node has no conditional routing, its body is `pass` with a one-line docstring, so the absence is explicit.
  - If the node has conditional routing, it returns one short route label declared in a `Literal[...]` return type. Labels follow the route label rules of the graph standards: short and indicating the deciding attribute, for example `status=ok`.
  - In the fan-out pattern, it returns a list of `Send` instead of a label (see graph standards).
  - It only decides. It never mutates state and never performs heavy work. The attribute it decides on (for example `extraction_status`) is computed in `__call__` and written to state.

The routing logic lives in the same class as the node so that the node is a self-contained package.

### Template with routing

```python
from typing import Literal

from .pydantic import ExtractInvoiceFieldsOutput, ExtractInvoiceFieldsState


class ExtractInvoiceFields:
    """Extracts the key fields of an invoice from its raw text.

    Stages: prepares the extraction prompt, calls the LLM, normalizes the
    returned fields and records whether the extraction succeeded.

    Produces the extracted fields and an extraction status.
    """

    def __init__(self, llm_client):
        self.llm_client = llm_client

    def __call__(self, state: ExtractInvoiceFieldsState) -> dict:
        ...
        return ExtractInvoiceFieldsOutput(
            invoice_fields=fields,
            extraction_status="ok",
        ).model_dump()

    def conditional_edge(
        self, state: ExtractInvoiceFieldsState
    ) -> Literal["status=ok", "status=error"]:
        if state.extraction_status == "ok":
            return "status=ok"
        return "status=error"
```

### Template without routing

```python
    def conditional_edge(self, state: CleanAddressState) -> None:
        """No conditional routing: execution continues through a normal edge."""
        pass
```

## 5. Docstring

The class docstring explains functionally:

- What problem the node solves.
- Its main stages.
- What result it produces.

It does not contain code examples and does not duplicate the Pydantic contracts.

## 6. Helper library

Extract helper functions to `library/` when they materially improve the readability of the main module.
Avoid unnecessary abstractions and artificial fragmentation.

## 7. Design document

Optional for nodes. Create `design.md` when there are relevant functional or architectural decisions that are not evident from the code.
When created, follow `.claude/skills/langgraph-design-doc/SKILL.md`.

## 8. Documentation separation

| Element | Question it answers |
|---|---|
| Pydantic | What data goes in and out? |
| Docstring | What does the node do? |
| design.md | Why was it designed this way? |

## 9. Naming

Follow `.claude/conventions/langgraph/naming.md`. The folder, main module and name registered in the graph are all exactly `<role>_<instance>`.

## 10. Compliance checklist

- [ ] Own folder; folder name = main module name = `<role>_<instance>`.
- [ ] Role is standard, or marked as `NEW ROLE (pending approval)`.
- [ ] `pydantic.py` defines Input, Output and State(Input, Output).
- [ ] Every field uses `Field(description=...)`; Output and extra fields have defaults.
- [ ] Node is a class with `__call__` and `conditional_edge`; `__init__` only if needed.
- [ ] `conditional_edge` is `pass` when there is no routing, or returns short labels declared in a `Literal`.
- [ ] `conditional_edge` does not mutate state.
- [ ] Class docstring covers problem, stages and result, without code.
- [ ] `library/` only when it materially improves readability.
- [ ] `design.md`, if present, follows the design-doc skill.
