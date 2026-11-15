"""Chat model factory.

This module is the provider integration boundary. Graphs must obtain their
models from here and never instantiate ChatOllama (or any provider class)
directly. Today only the local Ollama runtime is supported. Future providers
can be added here through LangChain integrations or native APIs without
coupling application graphs to a specific provider.
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_NUM_CTX = 8192


def create_model(
    model_name: str,
    temperature: float = 0.0,
    base_url: str = DEFAULT_BASE_URL,
    num_ctx: int = DEFAULT_NUM_CTX,
    **kwargs: object,
) -> BaseChatModel:
    """Create a chat model backed by the local Ollama runtime."""
    return ChatOllama(
        model=model_name,
        temperature=temperature,
        base_url=base_url,
        num_ctx=num_ctx,
        **kwargs,
    )
