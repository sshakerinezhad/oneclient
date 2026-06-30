from agents.types import QueryResult, Evidence, OrchestratorState


def test_query_result_defaults():
    qr = QueryResult(cypher="MATCH (c) RETURN c", rows=[{"name": "x"}])
    assert qr.error is None
    assert qr.attempts == 1


def test_evidence_structure():
    qr = QueryResult(cypher="MATCH (c) RETURN c", rows=[])
    ev = Evidence(request="find companies", result=qr)
    assert ev.request == "find companies"
    assert ev.result.rows == []


def test_orchestrator_query_count():
    state = OrchestratorState(question="test")
    assert state.query_count == 0
    qr = QueryResult(cypher="q", rows=[])
    state.evidence.append(Evidence(request="r", result=qr))
    assert state.query_count == 1
