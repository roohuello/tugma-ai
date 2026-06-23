from langchain_openai import ChatOpenAI

from src.config import settings


def get_chat_model(model: str | None = None) -> ChatOpenAI:
    return ChatOpenAI(
        model=model or settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        temperature=0
    )
