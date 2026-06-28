from src.config import settings
from src.models.profile import StudentProfile

PROFILE_DIMENSIONS = list(StudentProfile.model_fields.keys())


def get_langfuse_handler():
    """Returns LangFuse CallbackHandler if configured, else None."""
    if not settings.langfuse_public_key:
        return None
    from langfuse.langchain import CallbackHandler
    return CallbackHandler()


def profile_completeness(profile: StudentProfile) -> float:
    """Ratio of non-empty/non-default profile fields. 0.0–1.0."""
    filled = 0
    total = len(PROFILE_DIMENSIONS)
    data = profile.model_dump()
    for field in PROFILE_DIMENSIONS:
        value = data.get(field)
        if field == "career_confidence":
            if value is not None:
                filled += 1
        elif field == "needs_immediate_employment":
            filled += 1  # always has a boolean value
        elif isinstance(value, list):
            if len(value) > 0:
                filled += 1
        elif value is not None and value != "":
            filled += 1
    return filled / total


async def judge_relevance(recommendations_json: str, retrieved_chunks: str) -> float | None:
    """LLM-as-judge: how well do recommendations align with retrieved chunks?

    Returns 0.0–1.0 score or None if LangFuse is not configured.
    """
    if not settings.langfuse_public_key:
        return None
    try:
        from src.core.llm import get_chat_model
        llm = get_chat_model()
        prompt = (
            "You are a curriculum alignment judge. Rate how well these SSHS elective "
            "recommendations are supported by the retrieved DepEd curriculum chunks. "
            "Score 0.0-1.0 where 1.0 = perfectly grounded in the documents, "
            "0.0 = hallucinated or unsupported.\n\n"
            "RETRIEVED CURRICULUM CHUNKS:\n{chunks}\n\n"
            "RECOMMENDATIONS:\n{recs}\n\n"
            "Return ONLY a number between 0.0 and 1.0. No explanation."
        ).format(chunks=retrieved_chunks[:8000], recs=recommendations_json[:8000])
        resp = await llm.ainvoke(prompt)
        return max(0.0, min(1.0, float(resp.content.strip())))
    except Exception:
        return None
