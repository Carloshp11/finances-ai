# Convention: LangGraph state contracts

Applies to: LangGraph nodes, graphs, subgraphs and adapter graphs.

## Three models per component

Every node and every graph defines exactly three Pydantic models in its `pydantic.py` module:

| Model | Purpose |
|---|---|
| `<Component>Input` | Fields the component needs to start. |
| `<Component>Output` | Fields the component produces for its consumer. |
| `<Component>State` | Full working state. Inherits from `Input` and `Output` and adds only the extra fields that are neither input nor output. |

`<Component>` is the PascalCase form of the component name defined by the naming convention (`.claude/conventions/langgraph/naming.md`).
Example: `extract_invoice_fields` → `ExtractInvoiceFieldsInput`, `ExtractInvoiceFieldsOutput`, `ExtractInvoiceFieldsState`.

## Rules

1. The State model must inherit from both: `class XState(XInput, XOutput)`.
2. Extra fields are declared only in the State model. A field is never declared in more than one of the three models.
3. Every field uses `Field(...)` with a clear semantic `description`. Bare annotations are not allowed.
4. Field and model names are descriptive. Avoid abbreviations that are not standard in the domain.
5. Input fields may be required.
6. Output fields and extra State fields must have a default (`default=...`, `default_factory=...` or `Optional[...] = None`), because they are empty when execution starts.
7. Descriptions explain the meaning of the data, not the implementation.
8. A reader must understand what goes in and what comes out without reading the implementation.
9. Pydantic validators are allowed only for data validation. Business logic belongs in the main module.
10. Reducers (`Annotated[..., reducer]`) are not allowed, except in the fan-out pattern defined in the graph standards.

## Example

```python
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ExtractInvoiceFieldsInput(BaseModel):
    document_text: str = Field(
        description="Raw text of the invoice document to process."
    )


class ExtractInvoiceFieldsOutput(BaseModel):
    invoice_fields: Optional[dict[str, str]] = Field(
        default=None,
        description="Extracted invoice fields keyed by field name.",
    )
    extraction_status: Optional[Literal["ok", "error"]] = Field(
        default=None,
        description="Result of the extraction, used to decide the next step.",
    )


class ExtractInvoiceFieldsState(ExtractInvoiceFieldsInput, ExtractInvoiceFieldsOutput):
    retry_count: int = Field(
        default=0,
        description="Number of extraction attempts made in the current execution.",
    )
```
