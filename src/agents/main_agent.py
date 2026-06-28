from deepagents import create_deep_agent
from deepagents.backends import StateBackend

from src.agents import load_prompt
from src.agents.tools import emit_stage
from src.agents.subagents.retrieval import retrieval_subagent
from src.agents.subagents.matching import matching_subagent
from src.core.llm import get_chat_model


def build_agent(checkpointer, store=None):
    """Build and return a compiled Tugma Deep Agent.

    Args:
        checkpointer: LangGraph checkpointer (e.g., AsyncRedisSaver).
        store: Optional LangGraph store (e.g., RedisStore) for persistent memory.
    """
    return create_deep_agent(
        model=get_chat_model(),
        system_prompt=load_prompt("intake"),
        subagents=[retrieval_subagent, matching_subagent],
        tools=[emit_stage],
        backend=StateBackend(),
        checkpointer=checkpointer,
        store=store,
    )
