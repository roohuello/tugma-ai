from src.config import settings
from src.models.profile import StudentProfile

PROFILE_DIMENSIONS = [
    "primary_career",
    "career_confidence",
    "secondary_careers",
    "academic_strengths",
    "academic_weaknesses",
    "preferred_track",
    "intended_college_course",
    "hobbies",
    "extracurriculars",
    "existing_skills",
    "work_values",
    "work_environment",
    "collaboration_style",
    "needs_immediate_employment",
    "financial_constraints",
]


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


def judge_relevance(recommendations_json: str, retrieved_chunks: str) -> float | None:
    """LLM-as-judge: how well do recommendations align with retrieved chunks?

    Returns 0.0–1.0 score or None if LangFuse is not configured.
    ponytail: deferred to Day 3. Stub returns None.
    """
    return None
