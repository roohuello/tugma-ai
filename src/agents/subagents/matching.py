from pathlib import Path

from src.agents.tools import emit_recommendations
from src.core.llm import get_chat_model

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")


matching_subagent = {
    "name": "matcher",
    "description": "Match student profile to elective recommendations with 8-rule reasoning and structured JSON output.",
    "system_prompt": _load_prompt("matcher"),
    "model": get_chat_model(),
    "tools": [emit_recommendations],
}
