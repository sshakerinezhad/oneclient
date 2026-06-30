"""Orchestrator: anti-lazy reasoning loop for business question analysis.

Drives a BedrockClient through a tool-use loop where query_data calls are
dispatched to the query agent. Enforces min_queries (anti-lazy) and max_iters
(runaway prevention) before returning an OrchestratorState with all evidence.
"""
import json
import time
from pathlib import Path

from agents.query_agent import run_query_agent
from agents.types import Evidence, OrchestratorState

def _log(msg: str):
    print(f"\033[36m[orchestrator]\033[0m {msg}", flush=True)

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

    _log(f"question: {question}")
    _log(f"config: max_iters={max_iters}, min_queries={min_queries}")
    t_start = time.time()

    for _ in range(max_iters):
        state.iterations += 1
        _log(f"--- iteration {state.iterations} ---")
        t_iter = time.time()

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

        _log(f"LLM responded in {time.time() - t_iter:.1f}s, stop_reason={resp['stop_reason']}")

        if resp["stop_reason"] == "tool_use" and resp.get("tool_uses"):
            _log(f"tool calls: {len(resp['tool_uses'])}")
            tool_results = []
            for tu in resp["tool_uses"]:
                if tu["name"] != "query_data":
                    _log(f"  unknown tool: {tu['name']}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu["id"],
                        "is_error": True,
                        "content": f"Unknown tool: {tu['name']}",
                    })
                    continue
                request = tu["input"].get("request", "")
                _log(f"  query_data: {request}")
                if on_event:
                    on_event("tool", f"Querying: {request}")

                t_query = time.time()
                qr = run_query_agent(client, conn, request, query_model)
                state.evidence.append(Evidence(request=request, result=qr))

                if qr.error:
                    _log(f"  -> ERROR ({time.time() - t_query:.1f}s): {qr.error}")
                else:
                    _log(f"  -> {len(qr.rows)} rows ({time.time() - t_query:.1f}s, {qr.attempts} attempt{'s' if qr.attempts != 1 else ''})")

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
                _log(f"anti-lazy: {state.query_count}/{min_queries} queries, forcing another round")
                messages = resp["messages"] + [{
                    "role": "user",
                    "content": (
                        f"You've only made {state.query_count} quer"
                        f"{'y' if state.query_count == 1 else 'ies'} but need at least "
                        f"{min_queries}. What other angles should we investigate?"
                    ),
                }]
                continue
            _log(f"done: {state.query_count} queries in {state.iterations} iterations")
            break

        else:
            _log(f"exiting: stop_reason={resp['stop_reason']}")
            break

    _log(f"total time: {time.time() - t_start:.1f}s")
    return state
