"""Tests for agents.orchestrator — TDD: write tests first, implement, verify GREEN."""
import pytest
from agents.orchestrator import run_orchestrator
from agents.types import QueryResult, OrchestratorState, Evidence


# ---------------------------------------------------------------------------
# Scripted fake client (no AWS)
# ---------------------------------------------------------------------------


class FakeOrchestratorClient:
    """Scripted responses — pops from a list in order, no real API calls."""

    def __init__(self, script):
        self._script = list(script)
        self._call_idx = 0

    def converse(self, model_id, system, messages, tools=None, thinking=False, **kw):
        resp = self._script[self._call_idx]
        self._call_idx += 1
        # Attach updated messages so orchestrator can build on them
        if "messages" not in resp:
            assistant_content = []
            if resp.get("text"):
                assistant_content.append({"type": "text", "text": resp["text"]})
            for tu in resp.get("tool_uses", []):
                assistant_content.append({
                    "type": "tool_use",
                    "id": tu["id"],
                    "name": tu["name"],
                    "input": tu["input"],
                })
            resp = dict(resp)
            resp["messages"] = messages + [{"role": "assistant", "content": assistant_content}]
        return resp

    def converse_stream(self, model_id, system, messages, tools=None, thinking=False, on_event=None, **kw):
        return self.converse(model_id, system, messages, tools=tools, thinking=thinking)


def _mock_query_agent(client, conn, request, model_id, max_repairs=3):
    return QueryResult(cypher="MATCH (n) RETURN n", rows=[{"name": "test"}], error=None, attempts=1)


_CFG = {
    "bedrock": {"orchestrator_model_id": "test-model"},
    "agent": {"max_iters": 8, "min_queries": 2, "thinking_budget": 1024},
}


# ---------------------------------------------------------------------------
# Test 1: Anti-lazy enforcement — forces more queries when LLM stops early
# ---------------------------------------------------------------------------


def test_orchestrator_enforces_min_queries(monkeypatch, tmp_path):
    """LLM tries to stop after 1 query but min_queries=2 forces another round."""
    monkeypatch.setattr("agents.orchestrator.run_query_agent", _mock_query_agent)

    script = [
        # Round 1: tool call (query 1)
        {
            "text": "",
            "tool_uses": [{"id": "t1", "name": "query_data", "input": {"request": "first query"}}],
            "stop_reason": "tool_use",
        },
        # Round 2: LLM tries to stop (only 1 query < min_queries=2)
        {
            "text": "I think I have enough.",
            "tool_uses": [],
            "stop_reason": "end_turn",
        },
        # Round 3: forced to query again (query 2)
        {
            "text": "",
            "tool_uses": [{"id": "t2", "name": "query_data", "input": {"request": "second query"}}],
            "stop_reason": "tool_use",
        },
        # Round 4: now 2 queries >= min_queries=2 — allowed to stop
        {
            "text": "Final analysis: everything looks good.",
            "tool_uses": [],
            "stop_reason": "end_turn",
        },
    ]

    client = FakeOrchestratorClient(script)
    state = run_orchestrator(client, conn=None, question="What is our AUM?", cfg=_CFG)

    assert state.query_count == 2
    assert state.iterations == 4
    assert len(state.evidence) == 2
    assert state.evidence[0].request == "first query"
    assert state.evidence[1].request == "second query"


# ---------------------------------------------------------------------------
# Test 2: max_iters hard ceiling
# ---------------------------------------------------------------------------


def test_orchestrator_respects_max_iters(monkeypatch):
    """Orchestrator stops at max_iters even if LLM keeps calling tools."""
    monkeypatch.setattr("agents.orchestrator.run_query_agent", _mock_query_agent)

    # All 3 iters are tool calls — no end_turn
    script = [
        {
            "text": "",
            "tool_uses": [{"id": f"t{i}", "name": "query_data", "input": {"request": f"query {i}"}}],
            "stop_reason": "tool_use",
        }
        for i in range(10)
    ]

    cfg = dict(_CFG)
    cfg = {**_CFG, "agent": {**_CFG["agent"], "max_iters": 3}}
    client = FakeOrchestratorClient(script)
    state = run_orchestrator(client, conn=None, question="Tell me about clients", cfg=cfg)

    assert state.iterations == 3
    assert state.query_count == 3


# ---------------------------------------------------------------------------
# Test 3: Normal flow — 2 queries then concludes
# ---------------------------------------------------------------------------


def test_orchestrator_normal_flow(monkeypatch):
    """LLM does exactly min_queries queries then concludes without coercion."""
    monkeypatch.setattr("agents.orchestrator.run_query_agent", _mock_query_agent)

    script = [
        {
            "text": "",
            "tool_uses": [{"id": "t1", "name": "query_data", "input": {"request": "client list"}}],
            "stop_reason": "tool_use",
        },
        {
            "text": "",
            "tool_uses": [{"id": "t2", "name": "query_data", "input": {"request": "AUM breakdown"}}],
            "stop_reason": "tool_use",
        },
        {
            "text": "Based on the data: clients hold $5B in AUM.",
            "tool_uses": [],
            "stop_reason": "end_turn",
        },
    ]

    client = FakeOrchestratorClient(script)
    state = run_orchestrator(client, conn=None, question="Summarize AUM", cfg=_CFG)

    assert state.query_count == 2
    assert state.iterations == 3


# ---------------------------------------------------------------------------
# Test 4: Returns OrchestratorState
# ---------------------------------------------------------------------------


def test_orchestrator_returns_state_type(monkeypatch):
    """run_orchestrator always returns OrchestratorState."""
    monkeypatch.setattr("agents.orchestrator.run_query_agent", _mock_query_agent)

    script = [
        {
            "text": "",
            "tool_uses": [{"id": "t1", "name": "query_data", "input": {"request": "q1"}}],
            "stop_reason": "tool_use",
        },
        {
            "text": "",
            "tool_uses": [{"id": "t2", "name": "query_data", "input": {"request": "q2"}}],
            "stop_reason": "tool_use",
        },
        {"text": "Done.", "tool_uses": [], "stop_reason": "end_turn"},
    ]

    client = FakeOrchestratorClient(script)
    state = run_orchestrator(client, conn=None, question="q", cfg=_CFG)
    assert isinstance(state, OrchestratorState)
    assert state.question == "q"


# ---------------------------------------------------------------------------
# Test 5: Streaming mode — on_event callback fires
# ---------------------------------------------------------------------------


def test_orchestrator_streaming_fires_events(monkeypatch):
    """When on_event is provided, tool events are emitted."""
    monkeypatch.setattr("agents.orchestrator.run_query_agent", _mock_query_agent)

    script = [
        {
            "text": "",
            "tool_uses": [{"id": "t1", "name": "query_data", "input": {"request": "stream query"}}],
            "stop_reason": "tool_use",
        },
        {
            "text": "",
            "tool_uses": [{"id": "t2", "name": "query_data", "input": {"request": "stream query 2"}}],
            "stop_reason": "tool_use",
        },
        {"text": "All done.", "tool_uses": [], "stop_reason": "end_turn"},
    ]

    events = []
    client = FakeOrchestratorClient(script)
    state = run_orchestrator(
        client, conn=None, question="streaming test", cfg=_CFG,
        on_event=lambda kind, text: events.append((kind, text)),
    )

    tool_events = [e for e in events if e[0] == "tool"]
    assert len(tool_events) == 2
    assert any("stream query" in e[1] for e in tool_events)


# ---------------------------------------------------------------------------
# Test 6: Evidence accumulates correctly
# ---------------------------------------------------------------------------


def test_orchestrator_evidence_accumulates(monkeypatch):
    """Evidence list grows with each query_data call."""
    monkeypatch.setattr("agents.orchestrator.run_query_agent", _mock_query_agent)

    script = [
        {"text": "", "tool_uses": [{"id": "t1", "name": "query_data", "input": {"request": "angle 1"}}], "stop_reason": "tool_use"},
        {"text": "", "tool_uses": [{"id": "t2", "name": "query_data", "input": {"request": "angle 2"}}], "stop_reason": "tool_use"},
        {"text": "", "tool_uses": [{"id": "t3", "name": "query_data", "input": {"request": "angle 3"}}], "stop_reason": "tool_use"},
        {"text": "Done.", "tool_uses": [], "stop_reason": "end_turn"},
    ]

    cfg = {**_CFG, "agent": {**_CFG["agent"], "min_queries": 3}}
    client = FakeOrchestratorClient(script)
    state = run_orchestrator(client, conn=None, question="deep dive", cfg=cfg)

    assert len(state.evidence) == 3
    assert all(isinstance(e, Evidence) for e in state.evidence)
    requests = [e.request for e in state.evidence]
    assert requests == ["angle 1", "angle 2", "angle 3"]


# ---------------------------------------------------------------------------
# Test 7: max_tokens stop reason exits gracefully
# ---------------------------------------------------------------------------


def test_orchestrator_exits_on_max_tokens(monkeypatch):
    """Unexpected stop_reason (max_tokens) exits the loop without crashing."""
    monkeypatch.setattr("agents.orchestrator.run_query_agent", _mock_query_agent)

    script = [
        {"text": "partial...", "tool_uses": [], "stop_reason": "max_tokens"},
    ]

    client = FakeOrchestratorClient(script)
    state = run_orchestrator(client, conn=None, question="q", cfg=_CFG)

    # Should exit cleanly — no crash, iterations=1
    assert state.iterations == 1
    assert isinstance(state, OrchestratorState)
