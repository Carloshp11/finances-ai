---
name: langgraph-graph-standards
description: Standards for organizing, composing, routing and documenting LangGraph graphs and subgraphs — graph class, contracts, conditional edges, route labels, parallel branches, fan-out and subgraph adapters.
user-invocable: true
disable-model-invocation: true
---

# LangGraph graph and subgraph standards

## Required reading

Before applying these standards, read with the Read tool:

- `.claude/conventions/langgraph/state-contracts.md`
- `.claude/conventions/langgraph/naming.md`
- `.claude/skills/langgraph-design-doc/SKILL.md` (design.md is mandatory for graphs)

Nodes used by a graph expose this interface (defined in the node standards): a class with `__call__(state)` and `conditional_edge(state)`.

## 1. Folder structure

```text
graphs/
└── <role>_<instance>/
    ├── __init__.py
    ├── <role>_<instance>.py
    ├── pydantic.py
    ├── design.md          # mandatory
    └── library/           # optional
        ├── __init__.py
        └── helpers.py
```

The location of the `graphs/` folder follows the existing repository structure.

## 2. Contracts

- Follow `.claude/conventions/langgraph/state-contracts.md` exactly: `Input`, `Output` and `State(Input, Output)`.
- The graph is built with `StateGraph(<X>State, input_schema=<X>Input, output_schema=<X>Output)`. Use the parameter names supported by the installed LangGraph version (older versions use `input=` and `output=`).
- The graph State must contain every field that its nodes read or write, with the same names and compatible types.
- If a node's contract does not fit the graph state, resolve it in the design (align field names or add a `transform_*` node). Do not hide translations inside the node.

## 3. Graph class

Each graph is one class named in PascalCase after the graph name.

- `__init__`: optional. Only for dependencies or configuration.
- `build(self)`: mandatory. Contains all the assembly logic: instantiates the node classes and child graphs, registers nodes, edges and conditional edges, and returns the uncompiled `StateGraph`.
- `compile(self, **kwargs)`: mandatory. Returns the compiled graph by calling `self.build().compile(**kwargs)`. No other side effects.
- The graph class contains no business logic. Business logic lives in the nodes.

This allows any graph to be imported, instantiated, compiled and embedded in another graph.

### Template

```python
from langgraph.graph import END, START, StateGraph

from ...nodes.extract_invoice_fields.extract_invoice_fields import ExtractInvoiceFields
from ...nodes.write_invoice_db.write_invoice_db import WriteInvoiceDb
from .pydantic import ExtractClaimDataInput, ExtractClaimDataOutput, ExtractClaimDataState


class ExtractClaimData:
    """Extracts the structured data of a claim and stores it."""

    def __init__(self, llm_client, db_client):
        self.llm_client = llm_client
        self.db_client = db_client

    def build(self) -> StateGraph:
        builder = StateGraph(
            ExtractClaimDataState,
            input_schema=ExtractClaimDataInput,
            output_schema=ExtractClaimDataOutput,
        )

        extract_invoice_fields = ExtractInvoiceFields(self.llm_client)
        write_invoice_db = WriteInvoiceDb(self.db_client)

        builder.add_node("extract_invoice_fields", extract_invoice_fields)
        builder.add_node("write_invoice_db", write_invoice_db)

        builder.add_edge(START, "extract_invoice_fields")
        builder.add_conditional_edges(
            "extract_invoice_fields",
            extract_invoice_fields.conditional_edge,
            {
                "status=ok": "write_invoice_db",
                "status=error": END,
            },
        )
        builder.add_edge("write_invoice_db", END)

        return builder

    def compile(self, **kwargs):
        return self.build().compile(**kwargs)
```

## 4. Edges and conditional routing

- Normal transitions use `add_edge`.
- Every conditional edge is registered from the `conditional_edge` method of the node that precedes it:
  `builder.add_conditional_edges("<node_name>", <node_instance>.conditional_edge, <path_map>)`
- Standalone router functions and lambdas are not allowed.
- If a node's `conditional_edge` is `pass`, it is not registered; use `add_edge`.
- The `path_map` keys are exactly the labels declared in the method's `Literal` return type. Each label maps to exactly one destination.

## 5. Route labels

Route labels are the `path_map` keys. They are the text shown on each route when the graph is drawn, so they must be readable in the diagram.

- Very short: maximum 25 characters. Never a sentence or a paragraph.
- They indicate the attribute or reason that decides the route. Preferred form: `<attribute>=<value>`.
  Examples: `status=ok`, `status=error`, `status=fallback`, `docs=empty`.
- Lowercase, no spaces.
- Within one node, prefer the same deciding attribute for all its routes.
- Do not use destination names as labels (`go_to_writer` is invalid): the edge already shows the destination.
- The graph must be drawable: `compile().get_graph().draw_mermaid()` must run and show readable labels.

## 6. Parallel execution

### 6.1. Different nodes in parallel

- Each parallel branch writes its own distinct output field. Two parallel branches never write the same field.
- Join the branches so the consolidating node waits for all of them:
  `builder.add_edge(["<branch_node_a>", "<branch_node_b>"], "merge_<instance>")`
- A `merge_<instance>` node consolidates the branch fields into the final attribute.
- No reducers are used in this pattern.

### 6.2. Same node executed many times in parallel (fan-out)

Use this pattern when the number of parallel executions is not known in advance.

1. The dispatching node's `conditional_edge` returns a `list[Send]`, one per item. Each `Send` targets the repeated node and carries an instance of that node's Input model:
   `Send("<repeated_node_name>", <RepeatedNode>Input(...))`
2. Register it with the list of possible destinations so the graph stays drawable:
   `builder.add_conditional_edges("<dispatcher_name>", <dispatcher>.conditional_edge, ["<repeated_node_name>"])`
   This is the only case where route labels are not used.
3. The repeated node's Output declares a list field (with `default_factory=list`) and the node returns a one-element list in it.
4. The graph State declares that same field as an extra field with a concatenation reducer. This is the only reducer allowed:

   ```python
   import operator
   from typing import Annotated

   analysis_results: Annotated[list[DocumentAnalysis], operator.add] = Field(
       default_factory=list,
       description="Results of every parallel document analysis, one per document.",
   )
   ```

5. A `merge_<instance>` node consolidates that list into the final attribute.
6. For review purposes, the repeated node counts as one node.

## 7. Subgraph composition

### 7.1. Direct inclusion

A child graph is embedded by compiling it and registering it as a node:

```python
builder.add_node("<child_name>", ChildGraph(...).compile())
```

Direct inclusion is allowed only when every field of the child's Input and Output exists in the parent State with the same name and a compatible type.

### 7.2. Adapter graph (incompatible contracts)

If the contracts do not fit, create an adapter graph. Do not modify the child's contracts to fit the parent.

- Name: `<child_role>_<child_instance>_for_<parent_instance>`.
- Own folder and the same structure as any graph, including its own (short) design.md.
- Contracts: Input = parent fields the adapter needs; Output = parent fields the adapter produces. The adapter State also contains the child's Input and Output fields as extra fields.
- Exactly three nodes in a line:

  ```text
  START → transform_<child_instance>_input → <child_name> → transform_<child_instance>_output → END
  ```

  - `transform_<child_instance>_input`: translates parent fields into the child's Input fields.
  - `<child_name>`: the compiled child graph.
  - `transform_<child_instance>_output`: translates the child's Output fields into parent fields.
- The transform nodes follow the node standards (class, contracts, `conditional_edge` with `pass`) and contain only translation logic.
- The parent embeds the compiled adapter like any other graph.

## 8. Design document

Mandatory for every graph, subgraph and adapter graph. Follow `.claude/skills/langgraph-design-doc/SKILL.md`.

## 9. Naming

Follow `.claude/conventions/langgraph/naming.md` for the graph and for every registered node.

## 10. PENDING — not yet defined

The following topics have no agreed standard yet. Do not invent rules. Reviewers must report them as "convention not yet specified":

- Advanced compilation and runtime configuration: checkpointers, stores, interrupts, recursion limits and runtime config.

## 11. Compliance checklist

- [ ] Own folder; folder name = main module name = `<role>_<instance>`.
- [ ] `pydantic.py` defines Input, Output and State(Input, Output); State covers all node fields.
- [ ] Graph is a class with `build()` and `compile()`; no business logic.
- [ ] Every conditional edge comes from the preceding node's `conditional_edge`; no standalone routers or lambdas.
- [ ] `path_map` keys match the `Literal` labels; labels ≤ 25 characters, `<attribute>=<value>`.
- [ ] Parallel branches write distinct fields and are consolidated by a `merge_*` node.
- [ ] Fan-out uses `Send`, a single list field with `operator.add` and a `merge_*` node.
- [ ] Child graphs are included directly only with compatible contracts; otherwise through an adapter graph.
- [ ] `design.md` exists and follows the design-doc skill.
- [ ] `compile().get_graph().draw_mermaid()` runs and labels are readable.
