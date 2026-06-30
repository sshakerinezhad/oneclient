"""Background noise population for the Fixtures container.

Appends ~N_COMPANIES companies and ~N_PERSONS persons with seeded randomness
so the graph has realistic noise beyond the per-question fixture cohorts.

Constraints (must not break fixture-based query answers):
  - Revenue <= $50M (fixture companies go up to $450M)
  - employee_count < 5000 (Q5 fixture companies have 8000–11000)
  - PENETRATION rates enforced per region (Quebec CB→Wealth highest)
"""
import numpy as np
from faker import Faker

from generate import knobs
from generate.fixtures import Company, Edge, Fixtures, Person, RelLob
from graph.schema_doc import (
    ALL_REGIONS,
    INDUSTRIES_OF_INTEREST,
    OTHER_INDUSTRIES,
    US_REGIONS,
)

# Weight industries 3:1 toward OTHER so INDUSTRIES_OF_INTEREST remain distinctive
_INDUSTRY_POOL = OTHER_INDUSTRIES * 3 + INDUSTRIES_OF_INTEREST


def build_population(fx: Fixtures) -> None:
    """Append background companies and persons to fx (mutates in place).

    Deterministic: all randomness flows through knobs.rng() (seed=42) and
    a seeded Faker instance so repeated calls produce identical data.
    """
    rng = knobs.rng()
    Faker.seed(knobs.SEED)
    fake = Faker()

    bg_company_ids = [f"BG-C-{i:03d}" for i in range(1, knobs.N_COMPANIES + 1)]
    _add_companies(fx, rng, bg_company_ids)
    _add_persons(fx, rng, fake, bg_company_ids)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _add_companies(fx: Fixtures, rng: np.random.Generator, ids: list[str]) -> None:
    """Generate N_COMPANIES background companies with LOB edges."""
    n = knobs.N_COMPANIES
    regions = rng.choice(ALL_REGIONS, size=n)
    industries = rng.choice(_INDUSTRY_POOL, size=n)
    emp_counts = rng.integers(50, 4999, size=n)        # exclusive upper → max 4998 < 5000
    revenues = rng.uniform(1_000_000, 50_000_000, size=n)  # max just under $50M
    has_cb_draw = rng.random(size=n)                   # < 0.60 → CB as primary LOB
    extra_cm_draw = rng.random(size=n)                 # < 0.30 → also get CM (when CB)
    penetration_draw = rng.random(size=n)              # < PENETRATION[region] → Wealth

    for i in range(n):
        ecif_id = ids[i]
        region = str(regions[i])
        country = "US" if region in US_REGIONS else "CA"
        revenue = float(revenues[i])

        fx.companies.append(Company(
            ecif_id=ecif_id,
            name=f"BgCo-{i + 1:03d}",
            country=country,
            region=region,
            industry=str(industries[i]),
            employee_count=int(emp_counts[i]),
            revenue=revenue,
            net_income=revenue * 0.07,
            lending_balance=revenue * 0.15,
            deposit_balance=revenue * 0.20,
        ))

        cb = has_cb_draw[i] < 0.60
        # Guarantee at least one LOB: if no CB, always assign CM
        cm = (not cb) or (extra_cm_draw[i] < 0.30)

        if cb:
            fx.rel_company_lob.append(RelLob(src=ecif_id, lob="CB", revenue=revenue * 0.04))
            pen = knobs.PENETRATION.get(region, 0.25)
            if penetration_draw[i] < pen:
                fx.rel_company_lob.append(RelLob(src=ecif_id, lob="Wealth", revenue=revenue * 0.02))

        if cm:
            fx.rel_company_lob.append(RelLob(src=ecif_id, lob="CM", revenue=revenue * 0.03))


def _add_persons(
    fx: Fixtures,
    rng: np.random.Generator,
    fake: Faker,
    bg_ids: list[str],
) -> None:
    """Generate N_PERSONS background persons with optional LOB / employment edges."""
    n = knobs.N_PERSONS
    n_cos = len(bg_ids)

    regions = rng.choice(ALL_REGIONS, size=n)
    is_individual = rng.random(size=n) < 0.75
    has_pbb = rng.random(size=n) < 0.60
    pbb_rev = rng.uniform(1_000, 50_000, size=n)
    has_wealth = rng.random(size=n) < 0.20
    wealth_rev = rng.uniform(5_000, 200_000, size=n)
    has_job = rng.random(size=n) < 0.30
    job_idx = rng.integers(0, n_cos, size=n)
    is_exec = rng.random(size=n) < 0.02
    exec_idx = rng.integers(0, n_cos, size=n)

    for i in range(n):
        ecif_id = f"BG-P-{i + 1:03d}"
        region = str(regions[i])
        country = "US" if region in US_REGIONS else "CA"

        fx.persons.append(Person(
            ecif_id=ecif_id,
            name=fake.name(),
            country=country,
            region=region,
            customer_type="individual" if is_individual[i] else "business",
        ))

        if has_pbb[i]:
            fx.rel_person_lob.append(RelLob(src=ecif_id, lob="P&BB", revenue=float(pbb_rev[i])))

        if has_wealth[i]:
            fx.rel_person_lob.append(RelLob(src=ecif_id, lob="Wealth", revenue=float(wealth_rev[i])))

        if has_job[i]:
            fx.employed_by.append(Edge(src=ecif_id, dst=bg_ids[int(job_idx[i])]))

        if is_exec[i]:
            fx.executive_of.append(Edge(src=ecif_id, dst=bg_ids[int(exec_idx[i])], title="Director"))
