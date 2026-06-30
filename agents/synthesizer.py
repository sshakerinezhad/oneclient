"""Synthesizer: single LLM call that turns accumulated evidence into a grounded answer.

No tools, no loop. Raises ValueError if evidence is empty — the caller must
ensure the orchestrator has gathered data before invoking.
"""
import json
from pathlib import Path

from agents.types import OrchestratorState

_PROMPT_PATH = Path(__file__).parent / "prompts" / "synthesizer.md"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _serialize_evidence(state: OrchestratorState) -> str:
    """Serialize evidence into a readable block for the LLM user message."""
    parts = [f"Question: {state.question}\n"]
    for i, ev in enumerate(state.evidence, 1):
        parts.append(f"--- Query {i}: {ev.request} ---")
        parts.append(f"Cypher: {ev.result.cypher}")
        if ev.result.error:
            parts.append(f"Error: {ev.result.error}")
        else:
            parts.append(f"Rows ({len(ev.result.rows)} results):")
            for row in ev.result.rows[:20]:
                parts.append(f"  {json.dumps(row)}")
            if len(ev.result.rows) > 20:
                parts.append(f"  ... and {len(ev.result.rows) - 20} more rows")
        parts.append("")
    return "\n".join(parts)


def synthesize(client, question: str, state: OrchestratorState, cfg: dict,
               nudge: str | None = None) -> str:
    """Produce a grounded markdown answer from accumulated evidence.

    Single call — no tools, no loop. The LLM is constrained by the system prompt
    to quote-extract before reasoning (36% error reduction, Anthropic research).

    Args:
        nudge: Optional analyst hint appended to evidence for demo questions.

    Raises:
        ValueError: if state.evidence is empty.
    """
    if not state.evidence:
        raise ValueError("Cannot synthesize without evidence")

    model_id = cfg["bedrock"]["orchestrator_model_id"]
    system = _load_prompt()
    evidence_text = _serialize_evidence(state)
    if nudge:
        evidence_text += f"\n--- Analyst Note ---\n{nudge}\n"
    messages = [{"role": "user", "content": evidence_text}]

    resp = client.converse(model_id, system, messages)
    return resp["text"]
