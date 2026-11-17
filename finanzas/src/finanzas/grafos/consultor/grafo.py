"""S3 subgraph: consultor agent, one turn per invocation, memory kept by the checkpointer.

The `agente` node is DUMMY. The `herramientas` node is a real ToolNode.
"""

from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from finanzas.grafos.consultor.herramientas import HERRAMIENTAS
from finanzas.modelos.estados import EstadoConsultor
from finanzas.trazas import traza

_GRAFO = "consultor"


def agente(state: EstadoConsultor) -> dict:
    traza(_GRAFO, "agente")
    # Future: LLM (settings.consultor.modelo) bound to HERRAMIENTAS, with a system prompt that
    # explains the tables, the categories and the aviso_inicial when there is one.
    ultimo = state["messages"][-1]
    if isinstance(ultimo, HumanMessage) and ultimo.content.startswith("/tool"):
        llamada = {
            "name": "leer_resumen",
            "args": {"tipo": "mes", "periodo": "2026-11"},
            "id": f"dummy-{uuid4().hex[:8]}",  # unique per call, so repeated turns do not clash
        }
        return {"messages": [AIMessage(content="", tool_calls=[llamada])]}
    if isinstance(ultimo, ToolMessage):
        texto = f"(dummy) La herramienta respondió: {ultimo.content}"
        return {"messages": [AIMessage(content=texto)]}
    return {"messages": [AIMessage(content=f"(dummy) He recibido: {ultimo.content}")]}


def construir_grafo_consultor(checkpointer):
    """Build the consultor graph with the given checkpointer (memory per thread_id)."""
    builder = StateGraph(EstadoConsultor)
    builder.add_node("agente", agente)
    builder.add_node("herramientas", ToolNode(HERRAMIENTAS))
    builder.add_edge(START, "agente")
    builder.add_conditional_edges("agente", tools_condition, {"tools": "herramientas", END: END})
    builder.add_edge("herramientas", "agente")
    return builder.compile(checkpointer=checkpointer)
