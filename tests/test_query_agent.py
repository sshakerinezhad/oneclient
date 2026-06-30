"""Tests for agents.query_agent — run BEFORE implementation to confirm RED, then GREEN."""
import pytest
from agents.query_agent import run_query_agent, _extract_cypher
from agents.types import QueryResult


# ---------------------------------------------------------------------------
# _extract_cypher unit tests (no DB, no LLM)
# ---------------------------------------------------------------------------


def test_extract_cypher_from_fenced_block():
    text = "Here's the query:\n```cypher\nMATCH (c:Company) RETURN c.name AS name\n```"
    assert _extract_cypher(text) == "MATCH (c:Company) RETURN c.name AS name"


def test_extract_cypher_returns_none_when_no_block():
    assert _extract_cypher("No code here") is None


def test_extract_cypher_fallback_generic_block():
    text = "```\nMATCH (n) RETURN n\n```"
    assert _extract_cypher(text) == "MATCH (n) RETURN n"


def test_extract_cypher_strips_whitespace():
    text = "```cypher\n  MATCH (n) RETURN n  \n```"
    assert _extract_cypher(text) == "MATCH (n) RETURN n"


# ---------------------------------------------------------------------------
# Fake LLM client (scripted responses, no AWS)
# ---------------------------------------------------------------------------


class FakeClient:
    """Scripted LLM responses — pops from a list, no real API calls."""

    def __init__(self, responses):
        self._responses = list(responses)

    def converse(self, model_id, system, messages, **kwargs):
        resp_text = self._responses.pop(0)
        return {
            "text": resp_text,
            "tool_uses": [],
            "stop_reason": "end_turn",
            "messages": messages + [
                {"role": "assistant", "content": [{"type": "text", "text": resp_text}]}
            ],
        }


# ---------------------------------------------------------------------------
# Integration tests (real kuzu DB via tmp_path)
# ---------------------------------------------------------------------------


def test_query_agent_success(tmp_path):
    """Happy path: LLM returns valid Cypher → QueryResult with rows, no error."""
    import kuzu
    db = kuzu.Database(str(tmp_path / "test.kuzu"))
    conn = kuzu.Connection(db)
    conn.execute("CREATE NODE TABLE N(id STRING, PRIMARY KEY(id))")
    conn.execute("CREATE (:N {id: 'a'})")
    conn.execute("CREATE (:N {id: 'b'})")

    fake = FakeClient(["```cypher\nMATCH (n:N) RETURN n.id AS id\n```"])
    result = run_query_agent(fake, conn, "list all nodes", "model-id")

    assert result.error is None
    assert result.attempts == 1
    assert len(result.rows) == 2
    assert result.cypher == "MATCH (n:N) RETURN n.id AS id"


def test_query_agent_self_repair(tmp_path):
    """First attempt fails on bad table name; second attempt succeeds."""
    import kuzu
    db = kuzu.Database(str(tmp_path / "test.kuzu"))
    conn = kuzu.Connection(db)
    conn.execute("CREATE NODE TABLE N(id STRING, PRIMARY KEY(id))")
    conn.execute("CREATE (:N {id: 'x'})")

    fake = FakeClient([
        "```cypher\nMATCH (n:BadTable) RETURN n.id AS id\n```",  # fails
        "```cypher\nMATCH (n:N) RETURN n.id AS id\n```",          # succeeds
    ])
    result = run_query_agent(fake, conn, "list nodes", "model-id")

    assert result.error is None
    assert result.attempts == 2
    assert len(result.rows) == 1


def test_query_agent_no_cypher_in_response(tmp_path):
    """LLM returns text without a Cypher block → error without retry."""
    import kuzu
    db = kuzu.Database(str(tmp_path / "test.kuzu"))
    conn = kuzu.Connection(db)

    fake = FakeClient(["I don't know how to write that query."])
    result = run_query_agent(fake, conn, "find stuff", "model-id")

    assert result.error is not None
    assert "No Cypher" in result.error
    assert result.attempts == 1


def test_query_agent_caps_rows(tmp_path):
    """More than 50 rows returned by kuzu are capped at 50."""
    import kuzu
    db = kuzu.Database(str(tmp_path / "test.kuzu"))
    conn = kuzu.Connection(db)
    conn.execute("CREATE NODE TABLE N(id STRING, PRIMARY KEY(id))")
    for i in range(60):
        conn.execute(f"CREATE (:N {{id: '{i}'}})")

    fake = FakeClient(["```cypher\nMATCH (n:N) RETURN n.id AS id\n```"])
    result = run_query_agent(fake, conn, "all nodes", "model-id")

    assert result.error is None
    assert len(result.rows) <= 50


def test_query_agent_exhausts_repairs(tmp_path):
    """All repair attempts fail → returns last error, correct attempt count."""
    import kuzu
    db = kuzu.Database(str(tmp_path / "test.kuzu"))
    conn = kuzu.Connection(db)

    bad = "```cypher\nMATCH (n:Ghost) RETURN n.id AS id\n```"
    fake = FakeClient([bad] * 4)  # 1 initial + 3 repairs
    result = run_query_agent(fake, conn, "find ghosts", "model-id", max_repairs=3)

    assert result.error is not None
    assert result.attempts == 4  # 1 + max_repairs


def test_query_agent_result_is_query_result():
    """run_query_agent always returns a QueryResult dataclass."""
    import kuzu, tempfile, os
    with tempfile.TemporaryDirectory() as d:
        db = kuzu.Database(os.path.join(d, "t.kuzu"))
        conn = kuzu.Connection(db)
        fake = FakeClient(["no cypher here"])
        result = run_query_agent(fake, conn, "q", "m")
        assert isinstance(result, QueryResult)
