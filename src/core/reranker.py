"""Jina v3 reranker — HTTP, no SDK."""

import httpx

from src.config import settings

JINA_RERANK_URL = "https://api.jina.ai/v1/rerank"
RERANKER_MODEL = "jina-reranker-v3"


async def rerank(
    query: str,
    documents: list[str],
    top_n: int = 5,
    return_documents: bool = False,
) -> list[dict]:
    headers = {
        "Authorization": f"Bearer {settings.jina_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": RERANKER_MODEL,
        "query": query,
        "documents": documents,
        "top_n": top_n,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(JINA_RERANK_URL, json=body, headers=headers)
        resp.raise_for_status()
        return resp.json()["results"]
