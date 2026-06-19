"""Qdrant async client + hybrid search with RRF fusion."""

from qdrant_client import AsyncQdrantClient, models

from src.config import settings

COLLECTION_NAME = "sshs_documents"
VECTOR_NAME = "dense"


def get_qdrant_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)


async def hybrid_search(
    query_vector: list[float],
    query_sparse: tuple[list[int], list[float]] | None = None,
    limit: int = 10,
    filters: models.Filter | None = None,
) -> list[models.ScoredPoint]:
    client = get_qdrant_client()
    try:
        prefetch = [models.Prefetch(query=query_vector, using=VECTOR_NAME, limit=limit * 2)]
        if query_sparse:
            indices, values = query_sparse
            prefetch.append(
                models.Prefetch(
                    query=models.SparseVector(indices=indices, values=values),
                    using="sparse",
                    limit=limit * 2,
                )
            )

        results = await client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=prefetch,
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=filters,
            limit=limit,
            with_payload=True,
        )
        return results.points
    finally:
        await client.close()
