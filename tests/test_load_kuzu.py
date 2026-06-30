"""Tests for load.load_kuzu.build_db — TDD.

RED: fails before load/load_kuzu.py exists.
GREEN: passes after implementation.
"""
import kuzu
import pytest

from generate.generate_data import main as gen_main
from load.load_kuzu import build_db


def test_build_db_creates_tables(tmp_path):
    staged = tmp_path / "staged"
    staged.mkdir()
    db_path = str(tmp_path / "test.kuzu")

    gen_main(str(staged))
    build_db(db_path, str(staged), "schema/schema.cypher")

    conn = kuzu.Connection(kuzu.Database(db_path))

    res = conn.execute("MATCH (c:Company) RETURN count(*) AS cnt")
    assert res.get_next()[0] > 100

    res = conn.execute(
        "MATCH (:Company)-[:COMPANY_HAS_RELATIONSHIP]->(l:LineOfBusiness {name:'CB'}) "
        "RETURN count(*) AS cnt"
    )
    assert res.get_next()[0] > 0

    res = conn.execute("MATCH (:Person)-[:EMPLOYED_BY]->(:Company) RETURN count(*) AS cnt")
    assert res.get_next()[0] > 0

    res = conn.execute(
        "MATCH (:Company)-[:COMPANY_LOCATED_IN]->(:Region) RETURN count(*) AS cnt"
    )
    assert res.get_next()[0] > 0
