import pytest
from graph.db import run_read, connect


def test_mutating_cypher_rejected(tmp_path):
    conn = connect(str(tmp_path / "t.kuzu"))
    with pytest.raises(ValueError):
        run_read(conn, "CREATE NODE TABLE X(id STRING, PRIMARY KEY(id))")
    with pytest.raises(ValueError):
        run_read(conn, "MATCH (c:Company) DELETE c")


def test_read_returns_dicts(tmp_path):
    import kuzu
    db = kuzu.Database(str(tmp_path / "r.kuzu"))
    c = kuzu.Connection(db)
    c.execute("CREATE NODE TABLE N(id STRING, PRIMARY KEY(id))")
    c.execute("CREATE (:N {id: 'a'})")
    rows = run_read(c, "MATCH (n:N) RETURN n.id AS id")
    assert rows == [{"id": "a"}]
