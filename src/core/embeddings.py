"""Jina embeddings — v5-text-small via llama-index adapter."""

from llama_index.embeddings.jinaai import JinaEmbedding

from src.config import settings

EMBEDDING_MODEL = "jina-embeddings-v5-text-small"
EMBEDDING_DIM = 1024


def get_embeddings() -> JinaEmbedding:
    return JinaEmbedding(
        model=EMBEDDING_MODEL,
        api_key=settings.jina_api_key,
        task="retrieval.passage",
        embed_batch_size=16,
    )
