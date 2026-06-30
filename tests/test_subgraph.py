"""tests/test_subgraph.py — TDD for viz.subgraph.build_subgraph.

RED: fails before viz/subgraph.py is implemented.
GREEN: passes after implementation.
"""
import re

import kuzu
import pytest

from generate.generate_data import main as gen_main
from load.load_kuzu import build_db
from viz.subgraph import build_subgraph


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def conn(tmp_path):
    staged = tmp_path / "staged"
    staged.mkdir()
    gen_main(str(staged))
    db_path = str(tmp_path / "test.kuzu")
    build_db(db_path, str(staged), "schema/schema.cypher")
    return kuzu.Connection(kuzu.Database(db_path))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_subgraph_returns_html(conn):
    """build_subgraph returns a non-empty HTML document for a known fixture company."""
    html = build_subgraph(conn, ["FX1-001"])
    assert "<html" in html.lower() or "<div" in html.lower()
    # Company name or ecif_id must appear in the inlined JS node data
    assert "WestCM-01" in html or "FX1-001" in html


def test_subgraph_respects_cap(conn):
    """Total distinct node ids in the generated HTML must not exceed cap * 2 (generous bound)."""
    html = build_subgraph(conn, ["FX5-001", "FX5-002", "FX5-003"], cap=15)
    # pyvis serialises nodes as {"id": "...", ...} — extract unique id values
    unique_ids = set(re.findall(r'"id":\s*"([^"]+)"', html))
    # Generous bound: some pyvis config sections also emit "id" keys
    assert len(unique_ids) <= 30


def test_subgraph_no_external_urls(conn):
    """The generated HTML must not reference external CDN URLs (offline requirement)."""
    html = build_subgraph(conn, ["FX1-001"])
    assert "cdnjs" not in html
    # vis-network JS must be inlined — output will be >> 10 KB
    assert len(html) > 10_000


def test_subgraph_empty_entity_ids(conn):
    """An empty entity_ids list returns valid HTML (empty graph, no crash)."""
    html = build_subgraph(conn, [])
    assert "<html" in html.lower() or "<div" in html.lower()


def test_subgraph_node_types_colored(conn):
    """LOB and Region nodes use distinct colors from Company nodes."""
    # FX1-001 → LOB "CM" and Region "US West" should both appear
    html = build_subgraph(conn, ["FX1-001"])
    # Blue for Company, purple for LOB, orange for Region
    assert "#0079C1" in html  # Company color
    assert "#7B2D8E" in html  # LineOfBusiness color
    assert "#FF6B35" in html  # Region color
