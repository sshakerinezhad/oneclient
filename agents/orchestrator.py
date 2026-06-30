"""Orchestrator: anti-lazy reasoning loop for business question analysis.

Drives a BedrockClient through a tool-use loop where query_data calls are
dispatched to the query agent. Enforces min_queries (anti-lazy) and max_iters
(runaway prevention) before returning an OrchestratorState with all evidence.
"""
import json
from pathlib import Path

from agents.query_agent import run_query_agent
from agents.types import Evidence, OrchestratorState

QUERY_TOOL = {
    "name": "query_data",
    "description": (
        "Query the client graph database. Pass a natural language request "
        "describing what data you need. Returns rows from the graph."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "request": {
                "type": "string",
                "description": "Natural language description of the data needed",
            }
        },
        "required": ["request"],
    },
}


def _load_prompt(cfg: dict) -> str:
    path = Path(__file__).parent / "prompts" / "orchestrator.md"
    template = path.read_text(encoding="utf-8")
    min_q = cfg.get("agent", {}).get("min_queries", 2)
    return template.replace("{min_queries}", str(min_q))


def run_orchestrator(
    client,
    conn,
    question: str,
    cfg: dict,
    on_event=None,
) -> OrchestratorState:
    """Run the anti-lazy orchestrator reasoning loop.

    Args:
        client: BedrockClient (converse / converse_stream).
        conn: kuzu Connection passed through to the query agent.
        question: Business question to investigate.
        cfg: Config dict with bedrock.orchestrator_model_id, agent.max_iters,
             agent.min_queries, agent.thinking_budget.
        on_event: Optional callback(kind, text) for streaming UI events.
                  Kinds: 'tool' (query dispatched), plus whatever the client emits.

    Returns:
        OrchestratorState with accumulated evidence and iteration count.
    """
    system = _load_prompt(cfg)
    orch_model = cfg["bedrock"]["orchestrator_model_id"]
    query_model = cfg["bedrock"].get("query_model_id", orch_model)
    max_iters = cfg.get("agent", {}).get("max_iters", 8)
    min_queries = cfg.get("agent", {}).get("min_queries", 2)

    state = OrchestratorState(question=question)
    messages = [{"role": "user", "content": question}]

    for _ in range(max_iters):
        state.iterations += 1

        if on_event:
            resp = client.converse_stream(
                orch_model, system, messages,
                tools=[QUERY_TOOL], thinking=True,
                on_event=on_event,
            )
        else:
            resp = client.converse(
                orch_model, system, messages,
                tools=[QUERY_TOOL], thinking=True,
            )

        if resp["stop_reason"] == "tool_use" and resp.get("tool_uses"):
            tool_results = []
            for tu in resp["tool_uses"]:
                if tu["name"] != "query_data":
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu["id"],
                        "is_error": True,
                        "content": f"Unknown tool: {tu['name']}",
                    })
                    continue
                request = tu["input"].get("request", "")
                if on_event:
                    on_event("tool", f"Querying: {request}")

                qr = run_query_agent(client, conn, request, query_model)
                state.evidence.append(Evidence(request=request, result=qr))

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu["id"],
                    "content": json.dumps({
                        "rows": qr.rows[:20],
                        "row_count": len(qr.rows),
                        "cypher": qr.cypher,
                        "error": qr.error,
                    }),
                })

            messages = resp["messages"] + [{
                "role": "user",
                "content": tool_results,
            }]

        elif resp["stop_reason"] == "end_turn":
            if state.query_count < min_queries:
                # Anti-lazy: force another investigation round
                messages = resp["messages"] + [{
                    "role": "user",
                    "content": (
                        f"You've only made {state.query_count} quer"
                        f"{'y' if state.query_count == 1 else 'ies'} but need at least "
                        f"{min_queries}. What other angles should we investigate?"
                    ),
                }]
                continue
            break

        else:
            # max_tokens or unrecognised stop reason — exit cleanly
            break

    return state
