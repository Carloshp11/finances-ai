"""Minimal two-node LangGraph graph used to validate the local setup.

    START -> prepare_prompt -> generate_response -> END

The graph receives its model as an argument; it does not create one itself.
"""

from __future__ import annotations

from typing import TypedDict

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph


class HelloState(TypedDict):
    user_input: str
    prompt: str
    response: str


def prepare_prompt(state: HelloState) -> dict[str, str]:
    """Build the prompt sent to the model from the raw user input."""
    user_input = state["user_input"].strip()
    prompt = f"Answer briefly and clearly.\n\nUser: {user_input}"
    return {"prompt": prompt}


def build_graph(model: BaseChatModel) -> CompiledStateGraph:
    """Compile the two-node graph using the given chat model."""

    def generate_response(state: HelloState) -> dict[str, str]:
        message = model.invoke(state["prompt"])
        content = message.content
        text = content if isinstance(content, str) else str(content)
        return {"response": text}

    builder = StateGraph(HelloState)
    builder.add_node("prepare_prompt", prepare_prompt)
    builder.add_node("generate_response", generate_response)
    builder.add_edge(START, "prepare_prompt")
    builder.add_edge("prepare_prompt", "generate_response")
    builder.add_edge("generate_response", END)
    return builder.compile()
