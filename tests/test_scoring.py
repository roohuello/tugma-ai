import pytest
from unittest.mock import AsyncMock, patch

from src.models.profile import StudentProfile
from src.observability.langfuse import judge_relevance, profile_completeness


def test_profile_completeness_full(sample_profile):
    score = profile_completeness(sample_profile)
    assert score >= 0.5


def test_profile_completeness_minimal():
    profile = StudentProfile(primary_career="Nurse")
    score = profile_completeness(profile)
    assert 0.0 < score < 0.5


def test_profile_completeness_empty_lists():
    profile = StudentProfile(
        primary_career="Engineer",
        academic_strengths=[],
        secondary_careers=[],
        work_values=[],
    )
    score = profile_completeness(profile)
    assert score > 0.0


@pytest.mark.asyncio
async def test_judge_relevance_returns_none_no_langfuse():
    # patching settings to have no langfuse key
    with patch("src.observability.langfuse.settings") as mock_settings:
        mock_settings.langfuse_public_key = ""
        result = await judge_relevance('{"test": 1}', "some chunks")
        assert result is None
