"""Tests for generate.generate_data — staged CSV generation.

TDD: these tests must run RED before generate_data.py exists, then GREEN after.
"""
import csv

import pytest

from graph.schema_doc import ALL_REGIONS, LOBS


def test_all_csvs_generated(tmp_path):
    from generate.generate_data import main
    main(str(tmp_path))
    expected_files = [
        "companies.csv", "persons.csv", "regions.csv", "lob.csv",
        "rel_company_lob.csv", "rel_person_lob.csv",
        "rel_executive_of.csv", "rel_employed_by.csv",
        "rel_company_located_in.csv", "rel_person_located_in.csv",
    ]
    for f in expected_files:
        assert (tmp_path / f).exists(), f"Missing: {f}"


def test_company_csv_content(tmp_path):
    from generate.generate_data import main
    main(str(tmp_path))
    with open(tmp_path / "companies.csv") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) > 100  # fixtures + background
    assert all(r["ecif_id"] for r in rows)  # no empty PKs
    assert len(set(r["ecif_id"] for r in rows)) == len(rows)  # unique PKs


def test_rel_company_lob_csv_has_valid_lobs(tmp_path):
    from generate.generate_data import main
    main(str(tmp_path))
    with open(tmp_path / "rel_company_lob.csv") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        rows = list(reader)
    lobs = {r[1] for r in rows}
    assert lobs.issubset({"CB", "CM", "Wealth", "P&BB"})


def test_located_in_csvs_derived(tmp_path):
    from generate.generate_data import main
    main(str(tmp_path))
    with open(tmp_path / "rel_company_located_in.csv") as f:
        rows = list(csv.reader(f))
    assert len(rows) > 100  # header + all companies


def test_regions_csv_correct(tmp_path):
    from generate.generate_data import main
    main(str(tmp_path))
    with open(tmp_path / "regions.csv") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == len(ALL_REGIONS)
    assert {r["name"] for r in rows} == set(ALL_REGIONS)


def test_lob_csv_correct(tmp_path):
    from generate.generate_data import main
    main(str(tmp_path))
    with open(tmp_path / "lob.csv") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == len(LOBS)
    assert {r["name"] for r in rows} == set(LOBS)


def test_person_csv_unique_pks(tmp_path):
    from generate.generate_data import main
    main(str(tmp_path))
    with open(tmp_path / "persons.csv") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) > 50
    assert all(r["ecif_id"] for r in rows)
    assert len(set(r["ecif_id"] for r in rows)) == len(rows)


def test_company_csv_headers(tmp_path):
    from generate.generate_data import main
    main(str(tmp_path))
    with open(tmp_path / "companies.csv") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
    assert header == [
        "ecif_id", "name", "country", "region", "industry",
        "employee_count", "revenue", "net_income", "rwa", "roe",
        "lending_balance", "deposit_balance",
    ]


def test_person_located_in_row_count_matches_persons(tmp_path):
    from generate.generate_data import main
    main(str(tmp_path))
    with open(tmp_path / "persons.csv") as f:
        person_count = sum(1 for _ in csv.DictReader(f))
    with open(tmp_path / "rel_person_located_in.csv") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        located_count = sum(1 for _ in reader)
    assert located_count == person_count


def test_company_located_in_row_count_matches_companies(tmp_path):
    from generate.generate_data import main
    main(str(tmp_path))
    with open(tmp_path / "companies.csv") as f:
        company_count = sum(1 for _ in csv.DictReader(f))
    with open(tmp_path / "rel_company_located_in.csv") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        located_count = sum(1 for _ in reader)
    assert located_count == company_count
