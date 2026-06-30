"""Query agent: converts natural-language requests into kuzu Cypher queries.

Uses BedrockClient (invoke_model) to generate Cypher, executes via run_read(),
and self-repairs by feeding errors back to the LLM up to max_repairs times.
"""
import re
from pathlib import Path

from agents.types import QueryResult
from graph.db import run_read
from graph.schema_doc import SCHEMA_TEXT

_PROMPT_TEMPLATE: str | None = None


def _load_prompt_template() -> str:
    global _PROMPT_TEMPLATE
    if _PROMPT_TEMPLATE is None:
        path = Path(__file__).parent / "prompts" / "query_agent.md"
        _PROMPT_TEMPLATE = path.read_text(encoding="utf-8")
    return _PROMPT_TEMPLATE


def _extract_cypher(text: str) -> str | None:
    """Extract Cypher from a ```cypher fenced block, falling back to generic."""
    match = re.search(r"```cypher\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def run_query_agent(
    client,
    conn,
    request: str,
    model_id: str,
    max_repairs: int = 3,
) -> QueryResult:
    """Generate and execute a Cypher query with self-repair on failure.

    Args:
        client: BedrockClient instance (uses .converse()).
        conn: kuzu Connection for executing queries.
        request: Natural-language data question from the user.
        model_id: Bedrock model identifier.
        max_repairs: Maximum retry attempts after query execution failure.

    Returns:
        QueryResult with cypher, rows, error (if any), and attempt count.
    """
    system = _load_prompt_template().replace("{SCHEMA_TEXT}", SCHEMA_TEXT)
    messages = [{"role": "user", "content": request}]

    for attempt in range(1, max_repairs + 2):  # 1 initial + max_repairs retries
        resp = client.converse(model_id, system, messages)
        cypher = _extract_cypher(resp["text"])

        if cypher is None:
            return QueryResult(
                cypher="", rows=[], error="No Cypher found in response", attempts=attempt,
            )

        try:
            rows = run_read(conn, cypher)
            return QueryResult(cypher=cypher, rows=rows[:50], error=None, attempts=attempt)
        except Exception as exc:
            error_msg = str(exc)
            if attempt > max_repairs:
                return QueryResult(
                    cypher=cypher, rows=[], error=error_msg, attempts=attempt,
                )
            # Feed error back for self-repair
            messages = resp["messages"]
            messages.append({
                "role": "user",
                "content": f"That query failed with error:\n{error_msg}\n\nPlease fix the Cypher query.",
            })

    return QueryResult(cypher="", rows=[], error="Max retries exceeded", attempts=max_repairs + 1)
