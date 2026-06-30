"""End-to-end pipeline: wire orchestrator → synthesizer."""

from agents.orchestrator import run_orchestrator
from agents.synthesizer import synthesize


def answer_question(question: str, cfg: dict, conn, client, on_event=None) -> dict:
    """Wire orchestrator → synthesizer. Returns {"answer": str, "state": OrchestratorState}."""
    state = run_orchestrator(client, conn, question, cfg, on_event=on_event)
    answer = synthesize(client, question, state, cfg)
    return {"answer": answer, "state": state}
