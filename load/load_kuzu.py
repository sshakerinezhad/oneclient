"""
load/load_kuzu.py — bulk-loads staged CSVs into a kuzu graph database.

WHY: Separates data generation from database construction so each concern
is independently testable. Uses kuzu COPY for O(n) ingestion rather than
row-by-row INSERT, which scales to millions of nodes/edges.

Load order: Region → LineOfBusiness → Company → Person, then all rel tables.
Nodes must exist before any relationship referencing them can be loaded.
"""
import shutil
from pathlib import Path

import kuzu

# Nodes loaded in dependency order (no FK deps first).
_NODE_TABLES = [
    ("Region", "regions.csv"),
    ("LineOfBusiness", "lob.csv"),
    ("Company", "companies.csv"),
    ("Person", "persons.csv"),
]

# Rel tables loaded after all nodes are present.
_REL_TABLES = [
    ("COMPANY_HAS_RELATIONSHIP", "rel_company_lob.csv"),
    ("PERSON_HAS_RELATIONSHIP", "rel_person_lob.csv"),
    ("EXECUTIVE_OF", "rel_executive_of.csv"),
    ("EMPLOYED_BY", "rel_employed_by.csv"),
    ("COMPANY_LOCATED_IN", "rel_company_located_in.csv"),
    ("PERSON_LOCATED_IN", "rel_person_located_in.csv"),
]


def build_db(
    db_path: str,
    staged_dir: str = "data/staged",
    schema_path: str = "schema/schema.cypher",
) -> None:
    """
    Drop any existing database at db_path, execute DDL, then bulk-COPY all CSVs.

    Absolute forward-slash paths are passed to COPY for Windows compatibility.
    """
    shutil.rmtree(db_path, ignore_errors=True)

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    _execute_schema(conn, schema_path)
    _copy_tables(conn, staged_dir, _NODE_TABLES)
    _copy_tables(conn, staged_dir, _REL_TABLES)


def _execute_schema(conn: kuzu.Connection, schema_path: str) -> None:
    """Parse and execute each semicolon-delimited DDL statement."""
    ddl = Path(schema_path).read_text(encoding="utf-8")
    for stmt in ddl.split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)


def _abs_fwd(staged_dir: str, filename: str) -> str:
    """Return an absolute path with forward slashes for kuzu COPY."""
    return str((Path(staged_dir).resolve() / filename)).replace("\\", "/")


def _copy_tables(conn: kuzu.Connection, staged_dir: str, tables: list[tuple[str, str]]) -> None:
    for table, csv_file in tables:
        path = _abs_fwd(staged_dir, csv_file)
        conn.execute(f"COPY {table} FROM '{path}' (HEADER=true)")
