from pathlib import Path

from src.agents.tools import qdrant_hybrid_search_tool
from src.core.llm import get_chat_model

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")


retrieval_subagent = {
    "name": "retriever",
    "description": "Search DepEd SSHS curriculum for elective subjects matching a student profile.",
    "system_prompt": _load_prompt("retriever"),
    "tools": [qdrant_hybrid_search_tool],
    "model": get_chat_model(),
}
