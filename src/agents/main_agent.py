from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import StateBackend

from src.agents.tools import contradiction_check, emit_stage
from src.agents.subagents.retrieval import retrieval_subagent
from src.agents.subagents.matching import matching_subagent
from src.core.llm import get_chat_model

_PROMPT_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")


def build_agent(checkpointer, store=None):
    """Build and return a compiled Tugma Deep Agent.

    Args:
        checkpointer: LangGraph checkpointer (e.g., AsyncRedisSaver).
        store: Optional LangGraph store (e.g., RedisStore) for persistent memory.
    """
    return create_deep_agent(
        model=get_chat_model(),
        system_prompt=_load_prompt("intake"),
        subagents=[retrieval_subagent, matching_subagent],
        tools=[contradiction_check, emit_stage],
        backend=StateBackend(),
        checkpointer=checkpointer,
        store=store,
    )
