---
name: langgraph-design-doc
description: How to write or review the design.md of a LangGraph node or graph — required sections, scope and what to leave out. Use when creating, updating or reviewing a design document for a LangGraph component.
user-invocable: true
---

# LangGraph design document (design.md)

## When it is required

- Graphs, subgraphs and adapter graphs: always. Every graph has design complexity, however simple it looks.
- Nodes: only when there are relevant functional or architectural decisions that are not evident from reading the code.

The node and graph standards are authoritative on when it is required. This skill defines how to write it.

## Location

`<component_folder>/design.md`, next to the main module.

## Purpose

`design.md` answers one question: **why was this component designed this way?**

| Element | Question it answers |
|---|---|
| Pydantic contracts | What data goes in and out? |
| Docstring | What does the component do? |
| design.md | Why was it designed this way? |

Do not repeat in design.md what the contracts or the docstring already say.

## Required structure

Use these sections, in this order:

1. `# <component_name>` followed by a one-line summary.
2. `## Problem` — the problem the component solves and its context.
3. `## Approach` — the chosen approach, at a functional and architectural level.
4. `## Key decisions` — each decision with its reason.
5. `## Alternatives considered` — relevant rejected alternatives and why. If there are none, write "None relevant."
6. `## Constraints` — technical, functional or business constraints that shaped the design.
7. `## Open questions` — optional. Unresolved decisions, if any.

## Recommended sections for graphs

Add after `## Approach`:

- `## Flow` — the Mermaid diagram generated from the compiled graph (`compile().get_graph().draw_mermaid()`), plus one line per conditional route explaining what its label means.
- `## Composition` — subgraphs used, adapter graphs, parallel branches and merge nodes.

## Writing rules

- Be concise. Prefer short paragraphs and lists.
- Do not explain the implementation line by line.
- Do not include code examples that duplicate the implementation.
- Do not copy the Pydantic contracts.
- Keep it up to date: when a key decision changes, update the document in the same change.

## Review checklist

- [ ] All required sections exist, in order.
- [ ] It explains why, not how line by line.
- [ ] No duplication of contracts or docstring.
- [ ] Decisions include their reasons.
- [ ] Content matches the current implementation or proposal.
