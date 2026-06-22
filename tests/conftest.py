from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from src.models.profile import StudentProfile


@pytest.fixture
def sample_profile():
    return StudentProfile(
        primary_career="Nurse",
        career_confidence=0.8,
        academic_strengths=["Science", "Math"],
        academic_weaknesses=["Public Speaking"],
        preferred_track="Academic",
        hobbies=["Reading", "Volunteering"],
        work_values=["Helping others", "Job security"],
        secondary_careers=["Medical Technologist"],
        needs_immediate_employment=False,
    )


class FakeChatOpenAI:
    """Drop-in mock that returns canned AIMessage responses per turn."""

    def __init__(self, responses=None):
        self.responses = responses or []
        self._idx = 0

    async def ainvoke(self, messages, **kwargs):
        if self._idx < len(self.responses):
            resp = self.responses[self._idx]
            self._idx += 1
            return AIMessage(content=resp)
        return AIMessage(content="Default mock response")

    def bind_tools(self, *args, **kwargs):
        return self

    def __or__(self, other):
        return self


@pytest.fixture
def mock_llm():
    return FakeChatOpenAI()


@pytest.fixture
def captured_events():
    """Capture custom events emitted via get_stream_writer."""
    events = []
    writer = MagicMock()

    def capture(event):
        events.append(event)

    writer.side_effect = capture
    with patch("src.agents.tools.get_stream_writer", return_value=writer):
        yield events
