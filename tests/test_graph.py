from langchain_core.language_models.fake_chat_models import FakeListChatModel

from local_ai.graphs.hello_world import build_graph, prepare_prompt


def test_prepare_prompt_wraps_user_input() -> None:
    result = prepare_prompt({"user_input": "  hola  ", "prompt": "", "response": ""})
    assert "User: hola" in result["prompt"]


def test_graph_has_exactly_two_nodes() -> None:
    graph = build_graph(FakeListChatModel(responses=["ok"]))
    nodes = set(graph.get_graph().nodes) - {"__start__", "__end__"}
    assert nodes == {"prepare_prompt", "generate_response"}


def test_graph_returns_model_response() -> None:
    graph = build_graph(FakeListChatModel(responses=["respuesta de prueba"]))
    result = graph.invoke({"user_input": "hola", "prompt": "", "response": ""})
    assert result["response"] == "respuesta de prueba"
    assert "User: hola" in result["prompt"]
