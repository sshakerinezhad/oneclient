"""Tests for generate.population — background noise population.

TDD: tests written first, run RED before implementation exists.
"""
from generate.fixtures import build_fixtures
from generate.population import build_population
from generate.knobs import N_COMPANIES, N_PERSONS, PENETRATION


def test_population_adds_companies():
    fx = build_fixtures()
    n_before = len(fx.companies)
    build_population(fx)
    assert len(fx.companies) >= n_before + N_COMPANIES


def test_population_adds_persons():
    fx = build_fixtures()
    n_before = len(fx.persons)
    build_population(fx)
    assert len(fx.persons) >= n_before + N_PERSONS


def test_every_company_has_lob():
    fx = build_fixtures()
    build_population(fx)
    company_ids = {c.ecif_id for c in fx.companies}
    lob_company_ids = {r.src for r in fx.rel_company_lob}
    assert company_ids.issubset(lob_company_ids)


def test_penetration_rates_approximate():
    fx = build_fixtures()
    build_population(fx)
    # Check Quebec has noticeably higher CB∩Wealth rate than US Midwest
    # (exact rates may vary with noise, so just check relative ordering)
    bg_companies = {c.ecif_id: c.region for c in fx.companies if c.ecif_id.startswith("BG")}
    lob_map = {}
    for r in fx.rel_company_lob:
        if r.src in bg_companies:
            lob_map.setdefault(r.src, set()).add(r.lob)

    def rate(region):
        region_cos = [cid for cid, reg in bg_companies.items() if reg == region]
        if not region_cos:
            return 0.0
        cb_cos = [c for c in region_cos if "CB" in lob_map.get(c, set())]
        if not cb_cos:
            return 0.0
        return sum(1 for c in cb_cos if "Wealth" in lob_map.get(c, set())) / len(cb_cos)

    # Quebec should have higher rate than US Midwest (0.70 vs 0.18)
    assert rate("Quebec") > rate("US Midwest")


def test_background_revenue_capped():
    fx = build_fixtures()
    build_population(fx)
    bg = [c for c in fx.companies if c.ecif_id.startswith("BG")]
    assert all(c.revenue <= 50_000_000 for c in bg), "Background revenue must be capped at $50M"


def test_background_employee_count_capped():
    fx = build_fixtures()
    build_population(fx)
    bg = [c for c in fx.companies if c.ecif_id.startswith("BG")]
    assert all(c.employee_count < 5000 for c in bg), "Background employees must be < 5000"
