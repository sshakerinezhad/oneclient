"""Tests for generate.fixtures — backwards-designed per-question cohorts.

TDD: these tests must be written and run (RED) before fixtures.py exists.
"""
from generate.fixtures import build_fixtures, EXPECTED


def test_q1_cm_only_cohort_exists():
    """Q1 cohort: exactly 10 named companies exist in fixture companies."""
    fx = build_fixtures()
    assert len(EXPECTED[1]["names"]) == 10
    cm_only = {c.name for c in fx.companies if c.name in EXPECTED[1]["names"]}
    assert cm_only == set(EXPECTED[1]["names"])


def test_q1_cm_only_region():
    """Q1 companies are all in US West."""
    fx = build_fixtures()
    q1_companies = [c for c in fx.companies if c.name in EXPECTED[1]["names"]]
    assert all(c.region == "US West" for c in q1_companies)
    assert EXPECTED[1]["region"] == "US West"


def test_q1_cm_only_no_other_lobs():
    """Q1 companies have ONLY CM relationships — no CB, Wealth, or P&BB."""
    fx = build_fixtures()
    q1_ids = {c.ecif_id for c in fx.companies if c.name in EXPECTED[1]["names"]}
    lob_map: dict[str, set[str]] = {}
    for rel in fx.rel_company_lob:
        if rel.src in q1_ids:
            lob_map.setdefault(rel.src, set()).add(rel.lob)
    for ecif_id, lobs in lob_map.items():
        assert lobs == {"CM"}, f"{ecif_id} has unexpected LOBs: {lobs}"


def test_q2_cb_no_wealth_cohort_exists():
    """Q2 cohort: exactly 20 named companies exist."""
    fx = build_fixtures()
    assert len(EXPECTED[2]["names"]) == 20
    q2 = {c.name for c in fx.companies if c.name in EXPECTED[2]["names"]}
    assert q2 == set(EXPECTED[2]["names"])


def test_q2_cb_no_wealth_no_wealth_lob():
    """Q2 companies have CB but no Wealth relationship."""
    fx = build_fixtures()
    q2_ids = {c.ecif_id for c in fx.companies if c.name in EXPECTED[2]["names"]}
    for rel in fx.rel_company_lob:
        if rel.src in q2_ids:
            assert rel.lob != "Wealth", f"{rel.src} has forbidden Wealth LOB"
    cb_ids = {r.src for r in fx.rel_company_lob if r.src in q2_ids and r.lob == "CB"}
    assert cb_ids == q2_ids, "Not all Q2 companies have a CB relationship"


def test_q2_cb_no_wealth_region():
    """Q2 companies are all in US Northeast."""
    fx = build_fixtures()
    q2_companies = [c for c in fx.companies if c.name in EXPECTED[2]["names"]]
    assert EXPECTED[2]["region"] == "US Northeast"
    assert all(c.region == "US Northeast" for c in q2_companies)


def test_q3_winner_is_quebec():
    """Q3 expected winner is Quebec."""
    build_fixtures()
    assert EXPECTED[3]["winner"] == "Quebec"


def test_q3_quebec_has_cb_and_wealth():
    """Q3 fixture companies in Quebec have both CB and Wealth edges."""
    fx = build_fixtures()
    qc_companies = [c for c in fx.companies if c.region == "Quebec"]
    assert len(qc_companies) >= 5
    qc_ids = {c.ecif_id for c in qc_companies}
    lob_map: dict[str, set[str]] = {}
    for rel in fx.rel_company_lob:
        if rel.src in qc_ids:
            lob_map.setdefault(rel.src, set()).add(rel.lob)
    for ecif_id in qc_ids:
        lobs = lob_map.get(ecif_id, set())
        assert "CB" in lobs and "Wealth" in lobs, f"{ecif_id} missing CB or Wealth"


def test_q4_midwest_industry_cohort():
    """Q4 cohort exists in US Midwest with named companies."""
    fx = build_fixtures()
    assert all(n for n in EXPECTED[4]["names"])
    assert EXPECTED[4]["region"] == "US Midwest"
    assert set(EXPECTED[4]["industries"]) == {"franchisee", "auto_dealer", "equipment"}


def test_q4_midwest_industries_present():
    """Q4 companies cover all three INDUSTRIES_OF_INTEREST."""
    fx = build_fixtures()
    q4_companies = [c for c in fx.companies if c.name in EXPECTED[4]["names"]]
    assert len(q4_companies) == len(EXPECTED[4]["names"])
    industries = {c.industry for c in q4_companies}
    assert industries == {"franchisee", "auto_dealer", "equipment"}


def test_q4_midwest_cb_no_wealth():
    """Q4 companies have CB but no Wealth relationship."""
    fx = build_fixtures()
    q4_ids = {c.ecif_id for c in fx.companies if c.name in EXPECTED[4]["names"]}
    for rel in fx.rel_company_lob:
        if rel.src in q4_ids:
            assert rel.lob != "Wealth", f"{rel.src} has forbidden Wealth LOB in Q4"
    cb_ids = {r.src for r in fx.rel_company_lob if r.src in q4_ids and r.lob == "CB"}
    assert cb_ids == q4_ids


def test_q5_bank_at_work_has_employees():
    """Q5 bank-at-work companies collectively have at least 20 P&BB-linked employees."""
    fx = build_fixtures()
    baw_companies = {c.ecif_id for c in fx.companies if c.name in EXPECTED[5]["names"]}
    employed = [e for e in fx.employed_by if e.dst in baw_companies]
    assert len(employed) >= 20


def test_q5_bank_at_work_large_employee_count():
    """Q5 companies each have employee_count > 5000."""
    fx = build_fixtures()
    baw_companies = [c for c in fx.companies if c.name in EXPECTED[5]["names"]]
    assert all(c.employee_count > 5000 for c in baw_companies)


def test_q5_employees_have_pbb():
    """Employees of Q5 companies have P&BB relationships."""
    fx = build_fixtures()
    baw_ids = {c.ecif_id for c in fx.companies if c.name in EXPECTED[5]["names"]}
    emp_person_ids = {e.src for e in fx.employed_by if e.dst in baw_ids}
    pbb_person_ids = {r.src for r in fx.rel_person_lob if r.lob == "P&BB"}
    assert emp_person_ids.issubset(pbb_person_ids), "Some Q5 employees lack P&BB"


def test_q5_has_executives():
    """Q5 companies each have at least one executive."""
    fx = build_fixtures()
    baw_ids = {c.ecif_id for c in fx.companies if c.name in EXPECTED[5]["names"]}
    exec_company_ids = {e.dst for e in fx.executive_of}
    assert baw_ids.issubset(exec_company_ids)


def test_q6_underpenetrated_exists():
    """Q6 standout company exists in fixtures and its missing_lob is a valid LOB."""
    fx = build_fixtures()
    assert EXPECTED[6]["name"] in {c.name for c in fx.companies}
    assert EXPECTED[6]["missing_lob"] in ["CB", "CM", "Wealth", "P&BB"]


def test_q6_missing_wealth():
    """Q6 company has CB and CM but not Wealth."""
    fx = build_fixtures()
    q6_company = next(c for c in fx.companies if c.name == EXPECTED[6]["name"])
    lobs = {r.lob for r in fx.rel_company_lob if r.src == q6_company.ecif_id}
    assert "CB" in lobs
    assert "CM" in lobs
    assert "Wealth" not in lobs
    assert EXPECTED[6]["missing_lob"] == "Wealth"


def test_q6_has_pbb_employees():
    """Q6 standout company has P&BB-holding employees via EMPLOYED_BY."""
    fx = build_fixtures()
    q6_id = next(c.ecif_id for c in fx.companies if c.name == EXPECTED[6]["name"])
    emp_ids = {e.src for e in fx.employed_by if e.dst == q6_id}
    pbb_ids = {r.src for r in fx.rel_person_lob if r.lob == "P&BB"}
    assert len(emp_ids & pbb_ids) >= 10


def test_ecif_ids_are_unique():
    """All company and person ecif_ids are globally unique."""
    fx = build_fixtures()
    company_ids = [c.ecif_id for c in fx.companies]
    person_ids = [p.ecif_id for p in fx.persons]
    assert len(company_ids) == len(set(company_ids)), "Duplicate company ecif_ids"
    assert len(person_ids) == len(set(person_ids)), "Duplicate person ecif_ids"


def test_all_six_questions_have_expected_entries():
    """EXPECTED dict is populated for all 6 questions after build_fixtures()."""
    build_fixtures()
    assert set(EXPECTED.keys()) == {1, 2, 3, 4, 5, 6}
