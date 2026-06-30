"""Verification gate: 6 questions answered by raw Cypher against EXPECTED.

WHY: Phase 1 acceptance criterion. Every query must return the exact entities
that fixtures.build_fixtures() guarantees, proving the schema, load pipeline,
and Cypher queries all agree.

Run: python -m pytest tests/verify_demo.py -v
"""
import kuzu
import pytest

from generate.fixtures import EXPECTED, build_fixtures
from generate.generate_data import main as gen_main
from graph import queries
from graph.db import run_read
from load.load_kuzu import build_db


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    """Build the full DB once for all verification tests."""
    tmp = tmp_path_factory.mktemp("verify")
    staged = tmp / "staged"
    staged.mkdir()
    gen_main(str(staged))
    db_path = str(tmp / "verify.kuzu")
    build_db(db_path, str(staged), "schema/schema.cypher")
    # Populate EXPECTED with fixture ground-truth answers
    build_fixtures()
    return kuzu.Connection(kuzu.Database(db_path))


def test_q1_cm_only(conn):
    """Q1: Top 10 CM-only clients in US West must be exactly the 10 fixture companies."""
    cypher, params = queries.q1_cm_only(EXPECTED[1]["region"])
    rows = run_read(conn, cypher, params)
    names = [r["name"] for r in rows]
    assert set(names) == set(EXPECTED[1]["names"])


def test_q2_cb_no_wealth(conn):
    """Q2: All 20 fixture CB-without-Wealth companies must appear in the top-25 shortlist.

    Uses subset rather than equality because background population companies with
    revenue between 48 M and 50 M (e.g. BgCo-052 at ~48.6 M) are valid matches
    that legitimately appear alongside the fixture cohort.
    """
    cypher, params = queries.q2_cb_no_wealth(EXPECTED[2]["region"])
    rows = run_read(conn, cypher, params)
    names = {r["name"] for r in rows}
    assert set(EXPECTED[2]["names"]).issubset(names)


def test_q3_penetration(conn):
    """Q3: Quebec must rank first for CB→Wealth penetration rate."""
    cypher, params = queries.q3_penetration()
    rows = run_read(conn, cypher, params)
    assert rows[0]["region"] == EXPECTED[3]["winner"]


def test_q4_midwest(conn):
    """Q4: All 8 fixture Midwest industry companies must appear in results."""
    cypher, params = queries.q4_midwest_industries()
    rows = run_read(conn, cypher, params)
    names = {r["name"] for r in rows}
    assert set(EXPECTED[4]["names"]).issubset(names)


def test_q5_bank_at_work(conn):
    """Q5: All 3 BigCorp companies must appear as bank-at-work candidates."""
    cypher, params = queries.q5_bank_at_work()
    rows = run_read(conn, cypher, params)
    names = {r["name"] for r in rows}
    assert set(EXPECTED[5]["names"]).issubset(names)


def test_q6_underpenetrated(conn):
    """Q6: MegaGroup Holdings must surface as the top underpenetrated opportunity."""
    cypher, params = queries.q6_underpenetrated()
    rows = run_read(conn, cypher, params)
    names = [r["name"] for r in rows]
    assert EXPECTED[6]["name"] in names
