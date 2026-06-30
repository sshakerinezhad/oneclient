"""End-to-end pipeline: wire orchestrator → synthesizer."""

from agents.demo_scripts import DEMO_SCRIPTS, run_demo_script
from agents.orchestrator import run_orchestrator
from agents.synthesizer import synthesize


def answer_question(question: str, cfg: dict, conn, client, on_event=None) -> dict:
    """Wire orchestrator → synthesizer. Returns {"answer": str, "state": OrchestratorState}."""
    if question in DEMO_SCRIPTS:
        state, nudge = run_demo_script(question, conn, on_event=on_event)
        answer = synthesize(client, question, state, cfg, nudge=nudge)
    else:
        state = run_orchestrator(client, conn, question, cfg, on_event=on_event)
        answer = synthesize(client, question, state, cfg)
    return {"answer": answer, "state": state}
