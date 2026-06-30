"""Tests for agents.pipeline — wiring orchestrator → synthesizer."""
import pytest
from agents.pipeline import answer_question
from agents.types import OrchestratorState, Evidence, QueryResult


class FakePipelineClient:
    """Scripted client for both orchestrator and synthesizer calls."""

    def __init__(self):
        self._call_count = 0

    def converse(self, model_id, system, messages, tools=None, thinking=False, **kw):
        self._call_count += 1
        if tools:
            # Orchestrator call with tools
            if self._call_count == 1:
                # First call: orchestrator wants to use tools
                return {
                    "text": "",
                    "tool_uses": [{"id": "t1", "name": "query_data", "input": {"request": "test"}}],
                    "stop_reason": "tool_use",
                    "messages": messages + [{"role": "assistant", "content": []}],
                }
            elif self._call_count == 2:
                # Second call: orchestrator concludes (min_queries=1)
                return {
                    "text": "Done investigating.",
                    "tool_uses": [],
                    "stop_reason": "end_turn",
                    "messages": messages + [{"role": "assistant", "content": [{"type": "text", "text": "Done"}]}],
                }
        # No tools: synthesizer call
        return {
            "text": "## Answer\nHere are the findings.",
            "tool_uses": [],
            "stop_reason": "end_turn",
            "messages": messages + [{"role": "assistant", "content": [{"type": "text", "text": "answer"}]}],
        }

    def converse_stream(self, model_id, system, messages, tools=None, thinking=False, on_event=None, **kw):
        return self.converse(model_id, system, messages, tools=tools, thinking=thinking)


_CFG = {
    "bedrock": {"orchestrator_model_id": "test-model"},
    "agent": {"max_iters": 4, "min_queries": 1, "thinking_budget": 512},
}


# ---------------------------------------------------------------------------
# Test 1: Returns dict with "answer" and "state" keys
# ---------------------------------------------------------------------------


def test_answer_question_returns_dict_with_answer_and_state(monkeypatch):
    """answer_question returns {"answer": str, "state": OrchestratorState}."""
    monkeypatch.setattr(
        "agents.orchestrator.run_query_agent",
        lambda *a, **kw: QueryResult(cypher="Q", rows=[{"x": 1}], error=None, attempts=1),
    )

    result = answer_question("test question", _CFG, None, FakePipelineClient())
    assert isinstance(result, dict)
    assert "answer" in result
    assert "state" in result


# ---------------------------------------------------------------------------
# Test 2: State is OrchestratorState instance
# ---------------------------------------------------------------------------


def test_answer_question_state_is_orchestrator_state(monkeypatch):
    """The returned state is an OrchestratorState."""
    monkeypatch.setattr(
        "agents.orchestrator.run_query_agent",
        lambda *a, **kw: QueryResult(cypher="Q", rows=[{"x": 1}], error=None, attempts=1),
    )

    result = answer_question("test question", _CFG, None, FakePipelineClient())
    assert isinstance(result["state"], OrchestratorState)
    assert result["state"].question == "test question"


# ---------------------------------------------------------------------------
# Test 3: Answer is a non-empty string
# ---------------------------------------------------------------------------


def test_answer_question_answer_is_string(monkeypatch):
    """The returned answer is a non-empty string."""
    monkeypatch.setattr(
        "agents.orchestrator.run_query_agent",
        lambda *a, **kw: QueryResult(cypher="Q", rows=[{"x": 1}], error=None, attempts=1),
    )

    result = answer_question("test question", _CFG, None, FakePipelineClient())
    assert isinstance(result["answer"], str)
    assert len(result["answer"]) > 0


# ---------------------------------------------------------------------------
# Test 4: State accumulates evidence
# ---------------------------------------------------------------------------


def test_answer_question_state_has_evidence(monkeypatch):
    """The returned state includes evidence from orchestrator."""
    monkeypatch.setattr(
        "agents.orchestrator.run_query_agent",
        lambda *a, **kw: QueryResult(cypher="Q", rows=[{"x": 1}], error=None, attempts=1),
    )

    result = answer_question("test question", _CFG, None, FakePipelineClient())
    state = result["state"]
    assert len(state.evidence) > 0
    assert isinstance(state.evidence[0], Evidence)


# ---------------------------------------------------------------------------
# Test 5: Works with on_event callback
# ---------------------------------------------------------------------------


def test_answer_question_accepts_on_event(monkeypatch):
    """answer_question accepts and passes on_event callback."""
    monkeypatch.setattr(
        "agents.orchestrator.run_query_agent",
        lambda *a, **kw: QueryResult(cypher="Q", rows=[{"x": 1}], error=None, attempts=1),
    )

    events = []
    result = answer_question(
        "test question",
        _CFG,
        None,
        FakePipelineClient(),
        on_event=lambda kind, text: events.append((kind, text)),
    )
    assert isinstance(result, dict)
    assert "answer" in result
    assert "state" in result
