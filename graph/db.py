"""
graph/db.py — kuzu connection helper and read-only query executor.

WHY: All runtime graph queries flow through run_read(). This ensures agents
can never mutate the database — the keyword guard rejects any Cypher that
contains DDL/DML verbs before the query even reaches kuzu.
"""
import re

import kuzu

MUTATING = {"CREATE", "DELETE", "SET", "MERGE", "DROP", "COPY", "ALTER", "DETACH"}


def connect(db_path: str) -> kuzu.Connection:
    """Open (or create) a kuzu database at db_path and return a Connection."""
    return kuzu.Connection(kuzu.Database(db_path))


def _is_mutating(cypher: str) -> bool:
    tokens = set(re.findall(r"[A-Za-z]+", cypher.upper()))
    return bool(tokens & MUTATING)


def run_read(conn: kuzu.Connection, cypher: str, params: dict | None = None) -> list[dict]:
    """
    Execute a read-only Cypher query and return rows as a list of dicts.

    Raises ValueError for any query containing mutating keywords so that
    agents cannot accidentally (or maliciously) modify the graph.
    """
    if _is_mutating(cypher):
        raise ValueError(f"Refusing mutating Cypher: {cypher[:80]}")
    result = conn.execute(cypher, parameters=params or {})
    cols = result.get_column_names()
    rows = []
    while result.has_next():
        rows.append(dict(zip(cols, result.get_next())))
    return rows
