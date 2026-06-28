from src.agents import load_prompt
from src.core.llm import get_chat_model


matching_subagent = {
    "name": "matcher",
    "description": "Match student profile to elective recommendations with 8-rule reasoning and structured JSON output.",
    "system_prompt": load_prompt("matcher"),
    "model": get_chat_model(),
    "tools": [],
}
