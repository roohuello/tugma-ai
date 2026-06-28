from langchain_core.tools import tool
from langgraph.config import get_stream_writer
from fastembed import SparseTextEmbedding

from src.core.embeddings import get_embeddings
from src.core.qdrant import hybrid_search
from src.core.reranker import rerank

# ponytail: module-level lazy init. Models load once, ~200MB.
_sparse_model: SparseTextEmbedding | None = None
_embed_model = None


def _get_sparse_model() -> SparseTextEmbedding:
    global _sparse_model
    if _sparse_model is None:
        _sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
    return _sparse_model


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        _embed_model = get_embeddings()
    return _embed_model


@tool
async def qdrant_hybrid_search_tool(
    query: str,
    limit: int = 10,
    subject_area: str = "",
) -> str:
    """Search DepEd SSHS curriculum documents using hybrid (dense + sparse) search with optional reranking.

    Use this to find elective subjects, career pathways, and prototype programs of study
    that match a student's profile.

    Args:
        query: Natural language search query (e.g., "nursing career electives biology")
        limit: Maximum number of results to return (default 10)
        subject_area: Optional filter by subject area (e.g., "Science")
    """
    embed = _get_embed_model()
    sparse = _get_sparse_model()

    query_vector = await embed._aget_query_embedding(query)

    sparse_embeddings = list(sparse.query_embed([query]))
    query_sparse = None
    if sparse_embeddings:
        se = sparse_embeddings[0]
        query_sparse = (se.indices.tolist(), se.values.tolist())

    # ponytail: build filter from non-empty params only
    from qdrant_client import models
    must_conditions = []
    if subject_area:
        must_conditions.append(models.FieldCondition(key="subject_area", match=models.MatchValue(value=subject_area)))
    qdrant_filter = models.Filter(must=must_conditions) if must_conditions else None

    points = await hybrid_search(
        query_vector=query_vector,
        query_sparse=query_sparse,
        limit=min(limit, 50),
        filters=qdrant_filter,
    )

    if not points:
        return "No matching curriculum documents found."

    documents = [p.payload.get("text", "") for p in points]
    top_n = min(limit, len(documents))
    preview_docs = [d[:200] for d in documents[: top_n * 2]]
    reranked = await rerank(query=query, documents=preview_docs, top_n=top_n)

    lines = []
    for i, result in enumerate(reranked):
        idx = result["index"]
        score = result.get("relevance_score", 0)
        payload = points[idx].payload
        lines.append(
            f"## Result {i + 1} (score: {score:.3f})\n"
            f"- **Subject:** {payload.get('subject_area', 'N/A')}\n"
            f"- **Track:** {payload.get('track', 'N/A')}\n"
            f"- **Cluster:** {payload.get('cluster', 'N/A')}\n"
            f"- **Source:** {payload.get('source_document', 'N/A')} (page {payload.get('page', 'N/A')})\n"
            f"- **Content:** {payload.get('text', 'N/A')}\n"
        )

    return "\n".join(lines)


@tool
def emit_stage(name: str) -> str:
    """Signal a stage transition in the pipeline UI.

    Call BEFORE delegating to a subagent.

    Args:
        name: Stage display name, e.g. "Translating..."
              or "Searching curriculum..."
    """
    writer = get_stream_writer()
    writer({"type": "stage", "name": name})
    return f"Stage set to: {name}"

