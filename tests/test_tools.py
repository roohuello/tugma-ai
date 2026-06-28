def test_emit_stage(captured_events):
    from src.agents.tools import emit_stage

    result = emit_stage.invoke({"name": "Translating..."})
    assert "Stage set to" in result
    assert len(captured_events) == 1
    assert captured_events[0] == {"type": "stage", "name": "Translating..."}


