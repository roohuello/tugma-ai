from langgraph.checkpoint.memory import MemorySaver

from src.agents.main_agent import build_agent
from src.agents.subagents.matching import matching_subagent
from src.agents.subagents.retrieval import retrieval_subagent


def test_retrieval_subagent_structure():
    assert retrieval_subagent["name"] == "retriever"
    assert "system_prompt" in retrieval_subagent
    assert len(retrieval_subagent["tools"]) == 1


def test_matching_subagent_has_emit_recommendations():
    assert matching_subagent["name"] == "matcher"
    assert len(matching_subagent["tools"]) == 1
    tool = matching_subagent["tools"][0]
    assert tool.name == "emit_recommendations"


def test_agent_builds():
    agent = build_agent(checkpointer=MemorySaver())
    assert agent is not None
