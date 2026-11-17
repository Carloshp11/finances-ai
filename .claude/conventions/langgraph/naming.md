# Convention: LangGraph component naming

Applies to: nodes, graphs, subgraphs and adapter graphs.

## Format

`<role>_<instance>` in English snake_case.

- `<role>`: exactly one standard role from the table below. It tells what kind of operation the component performs.
- `<instance>`: the specific object or purpose of this component. One or more words.

Examples: `extract_invoice_fields`, `analyze_claim_coverage`, `write_results_db`, `merge_policy_findings`.

For graphs, the role describes the primary intent of the whole graph.

## Derived names

| Element | Form | Example |
|---|---|---|
| Folder and main module | `<role>_<instance>` | `extract_invoice_fields/extract_invoice_fields.py` |
| Class | PascalCase of the name | `ExtractInvoiceFields` |
| Pydantic models | Class name + `Input` / `Output` / `State` | `ExtractInvoiceFieldsInput` |
| Name registered in a graph (`add_node`) | Exactly `<role>_<instance>` | `"extract_invoice_fields"` |

## Standard roles

| Role | Use when |
|---|---|
| `extract` | The primary intent is to pull structured data out of some content. |
| `analyze` | Cognitive reasoning or judgement whose primary intent is not extraction. |
| `generate` | Produces new content (text, answer, summary). |
| `classify` | Assigns a category or decides a label. |
| `clean` | Normalizes, cleans or deduplicates data. |
| `transform` | Changes format or structure without interpreting the content. |
| `merge` | Consolidates the results of several parallel operations into one consolidated state attribute. |
| `read` | Reads from an external source (database, API, file). |
| `write` | Writes to an external destination. |
| `validate` | Checks rules or quality and returns a verdict. |
| `route` | Its main purpose is to decide the execution path. |

## Choosing a role

- Choose by primary intent. With generative AI, a step that pulls structured data is `extract`; a step that reasons or judges is `analyze`.
- Use a single role. Combined roles such as `extract_analyze_invoice` are not allowed.

## When no standard role fits

1. Propose a new role: one lowercase English verb.
2. Mark it in the proposal exactly like this:
   `NEW ROLE (pending approval): <role> — <one-sentence justification>`
3. Tell the agent you report to that the user must approve the new role before it is added to this convention.
4. Only the user approves new roles. No agent edits this file to add a role without explicit user approval.
5. Once approved, add the role to the table above with its "Use when" description.
