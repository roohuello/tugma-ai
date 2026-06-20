from pathlib import Path

from src.core.llm import get_chat_model

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")


translation_subagent = {
    "name": "translator",
    "description": "Translate Tagalog/Taglish profile text to English.",
    "system_prompt": _load_prompt("translator"),
    "model": get_chat_model(),
    "tools": [],
}
