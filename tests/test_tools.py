import json

import pytest


def test_contradiction_check():
    from src.agents.tools import contradiction_check

    result = contradiction_check.invoke({
        "reason": "Nursing needs science but student hates it",
        "suggestion": "Try healthcare administration",
    })
    assert "Contradiction flagged" in result


def test_emit_stage(captured_events):
    from src.agents.tools import emit_stage

    result = emit_stage.invoke({"name": "Translating..."})
    assert "Stage set to" in result
    assert len(captured_events) == 1
    assert captured_events[0] == {"type": "stage", "name": "Translating..."}


def test_emit_recommendations(captured_events):
    from src.agents.tools import emit_recommendations

    recs = json.dumps({
        "profile": {"primary_career": "Nurse"},
        "recommendations": [],
        "doorway_electives": [],
        "contradictions": [],
        "career_pathway": "Pre-Med",
        "overall_confidence": 0.7,
    })
    chunks = "## Result 1\n- **Subject:** Science\n- **Content:** Biology curriculum..."

    result = emit_recommendations.invoke({
        "recommendations_json": recs,
        "retrieved_chunks": chunks,
    })
    assert "Recommendations emitted" in result
    assert len(captured_events) == 2
    assert captured_events[0] == {"type": "stage", "name": "Your recommendations"}
    assert captured_events[1]["type"] == "recommendations"
    assert captured_events[1]["data"]["profile"]["primary_career"] == "Nurse"
    assert captured_events[1]["retrieved_chunks"] == chunks


def test_emit_recommendations_invalid_json(captured_events):
    from src.agents.tools import emit_recommendations

    with pytest.raises(json.JSONDecodeError):
        emit_recommendations.invoke({
            "recommendations_json": "not valid json",
            "retrieved_chunks": "some chunks",
        })
