from src.agents import load_prompt
from src.agents.tools import qdrant_hybrid_search_tool
from src.core.llm import get_chat_model


retrieval_subagent = {
    "name": "retriever",
    "description": "Search DepEd SSHS curriculum for elective subjects matching a student profile.",
    "system_prompt": load_prompt("retriever"),
    "tools": [qdrant_hybrid_search_tool],
    "model": get_chat_model(),
}
