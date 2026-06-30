"""Tests for agents.synthesizer — TDD: write tests first, implement, verify GREEN."""
import pytest
from agents.types import OrchestratorState, Evidence, QueryResult


class FakeSynthClient:
    def converse(self, model_id, system, messages, **kw):
        return {
            "text": "## Headline\nBased on the evidence, here are the findings.",
            "tool_uses": [],
            "stop_reason": "end_turn",
            "messages": messages + [{"role": "assistant", "content": [{"type": "text", "text": "answer"}]}],
        }


_CFG = {"bedrock": {"orchestrator_model_id": "test-model"}}


def _state_with_evidence():
    state = OrchestratorState(question="What are top clients?")
    state.evidence.append(Evidence(
        request="find top clients",
        result=QueryResult(cypher="MATCH (c:Client) RETURN c.name", rows=[{"name": "Acme"}]),
    ))
    return state


# ---------------------------------------------------------------------------
# Test 1: Returns non-empty text
# ---------------------------------------------------------------------------


def test_synthesize_returns_text():
    from agents.synthesizer import synthesize
    result = synthesize(FakeSynthClient(), "What are top clients?", _state_with_evidence(), _CFG)
    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# Test 2: Raises on empty evidence (guard)
# ---------------------------------------------------------------------------


def test_synthesize_raises_on_empty_evidence():
    from agents.synthesizer import synthesize
    state = OrchestratorState(question="test")
    with pytest.raises(ValueError, match="evidence"):
        synthesize(FakeSynthClient(), "test", state, _CFG)


# ---------------------------------------------------------------------------
# Test 3: _serialize_evidence includes rows and cypher
# ---------------------------------------------------------------------------


def test_serialize_evidence_includes_rows():
    from agents.synthesizer import _serialize_evidence
    state = OrchestratorState(question="Q")
    state.evidence.append(Evidence(
        request="find stuff",
        result=QueryResult(cypher="MATCH (c) RETURN c", rows=[{"name": "X"}, {"name": "Y"}]),
    ))
    text = _serialize_evidence(state)
    assert "find stuff" in text
    assert '"name": "X"' in text
    assert "MATCH (c) RETURN c" in text


# ---------------------------------------------------------------------------
# Test 4: _serialize_evidence surfaces errors
# ---------------------------------------------------------------------------


def test_serialize_evidence_handles_errors():
    from agents.synthesizer import _serialize_evidence
    state = OrchestratorState(question="Q")
    state.evidence.append(Evidence(
        request="bad query",
        result=QueryResult(cypher="BAD", rows=[], error="Syntax error"),
    ))
    text = _serialize_evidence(state)
    assert "Syntax error" in text


# ---------------------------------------------------------------------------
# Test 5: _serialize_evidence truncates at 20 rows and notes the remainder
# ---------------------------------------------------------------------------


def test_serialize_evidence_truncates_large_result():
    from agents.synthesizer import _serialize_evidence
    state = OrchestratorState(question="Q")
    rows = [{"i": i} for i in range(25)]
    state.evidence.append(Evidence(
        request="big result",
        result=QueryResult(cypher="MATCH ...", rows=rows),
    ))
    text = _serialize_evidence(state)
    assert "5 more rows" in text


# ---------------------------------------------------------------------------
# Test 6: synthesize passes model_id from cfg to client
# ---------------------------------------------------------------------------


def test_synthesize_uses_correct_model_id():
    from agents.synthesizer import synthesize

    seen = {}

    class CapturingClient:
        def converse(self, model_id, system, messages, **kw):
            seen["model_id"] = model_id
            return {"text": "ok", "tool_uses": [], "stop_reason": "end_turn", "messages": messages}

    cfg = {"bedrock": {"orchestrator_model_id": "special-model"}}
    synthesize(CapturingClient(), "q", _state_with_evidence(), cfg)
    assert seen["model_id"] == "special-model"
