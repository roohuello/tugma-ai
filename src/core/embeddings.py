"""Jina embeddings — HTTP, no SDK. Uses OpenAI-compatible /v1/embeddings endpoint."""

from langchain_openai import OpenAIEmbeddings

from src.config import settings

JINA_BASE_URL = "https://api.jina.ai/v1"
EMBEDDING_MODEL = "jina-embeddings-v5-text-small"
EMBEDDING_DIM = 1024


def get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        base_url=JINA_BASE_URL,
        api_key=settings.jina_api_key,
        dimensions=EMBEDDING_DIM,
    )
