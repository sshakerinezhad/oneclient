"""Per-question fixture cohorts — backwards-designed from the 6 BMO demo questions.

Each _qN_* helper appends exactly the rows needed to guarantee the question's
expected answer, then records that answer in EXPECTED[N].  The background
population (Task 1.5) generates the bulk; these fixtures anchor the data.
"""
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Company:
    ecif_id: str
    name: str
    country: str
    region: str
    industry: str
    employee_count: int
    revenue: float
    net_income: float = 0.0
    rwa: float = 0.0
    roe: float = 0.0
    lending_balance: float = 0.0
    deposit_balance: float = 0.0


@dataclass
class Person:
    ecif_id: str
    name: str
    country: str
    region: str
    customer_type: str


@dataclass
class RelLob:
    src: str
    lob: str
    revenue: float = 0.0
    lending: float = 0.0
    deposit: float = 0.0


@dataclass
class Edge:
    src: str
    dst: str
    title: str = ""


@dataclass
class Fixtures:
    companies: list = field(default_factory=list)
    persons: list = field(default_factory=list)
    rel_company_lob: list = field(default_factory=list)
    rel_person_lob: list = field(default_factory=list)
    executive_of: list = field(default_factory=list)
    employed_by: list = field(default_factory=list)


# Module-level dict populated as a side effect of build_fixtures().
EXPECTED: dict = {}


# ---------------------------------------------------------------------------
# Per-question helpers
# ---------------------------------------------------------------------------

def _q1_cm_only(fx: Fixtures) -> None:
    """Q1: Top-10 CM-only clients in US West.

    10 companies with CM and NO other LOB.  Revenue descending so top-10 rank
    is deterministic even after background population is merged.
    """
    names = [f"WestCM-{i:02d}" for i in range(1, 11)]
    for i, name in enumerate(names, 1):
        ecif_id = f"FX1-{i:03d}"
        revenue = 450_000_000.0 - (i - 1) * 30_000_000.0
        fx.companies.append(Company(
            ecif_id=ecif_id, name=name, country="US", region="US West",
            industry="manufacturing", employee_count=1000 + i * 100,
            revenue=revenue, net_income=revenue * 0.08,
            lending_balance=revenue * 0.15, deposit_balance=revenue * 0.20,
        ))
        fx.rel_company_lob.append(RelLob(src=ecif_id, lob="CM", revenue=revenue * 0.05))

    EXPECTED[1] = {"region": "US West", "names": names}


def _q2_cb_no_wealth(fx: Fixtures) -> None:
    """Q2: Top-20 CB clients without Wealth in US Northeast.

    20 companies with CB only (no Wealth).  Revenue descending to give a
    deterministic top-20 ranking.
    """
    names = [f"NorthCB-{i:02d}" for i in range(1, 21)]
    for i, name in enumerate(names, 1):
        ecif_id = f"FX2-{i:03d}"
        revenue = 200_000_000.0 - (i - 1) * 8_000_000.0
        fx.companies.append(Company(
            ecif_id=ecif_id, name=name, country="US", region="US Northeast",
            industry="retail", employee_count=500 + i * 50,
            revenue=revenue, net_income=revenue * 0.06,
            lending_balance=revenue * 0.12, deposit_balance=revenue * 0.18,
        ))
        fx.rel_company_lob.append(RelLob(src=ecif_id, lob="CB", revenue=revenue * 0.04))

    EXPECTED[2] = {"region": "US Northeast", "names": names}


def _q3_penetration(fx: Fixtures) -> None:
    """Q3: Quebec must have the strongest CB∩Wealth penetration.

    5 anchor companies in Quebec each with CB and Wealth.  The background
    population (Task 1.5) applies knobs.PENETRATION[Quebec]=0.70 to generate
    the bulk; these fixtures ensure Quebec has visible signal even in isolation.
    """
    for i in range(1, 6):
        ecif_id = f"FX3-{i:03d}"
        revenue = 80_000_000.0 - i * 5_000_000.0
        fx.companies.append(Company(
            ecif_id=ecif_id, name=f"QuebecBMO-{i:02d}", country="CA", region="Quebec",
            industry="manufacturing", employee_count=200 + i * 50,
            revenue=revenue, net_income=revenue * 0.07,
            lending_balance=revenue * 0.10, deposit_balance=revenue * 0.15,
        ))
        fx.rel_company_lob.append(RelLob(src=ecif_id, lob="CB", revenue=revenue * 0.03))
        fx.rel_company_lob.append(RelLob(src=ecif_id, lob="Wealth", revenue=revenue * 0.02))

    EXPECTED[3] = {"winner": "Quebec"}


def _q4_midwest(fx: Fixtures) -> None:
    """Q4: Franchisee/auto_dealer/equipment CB clients without Wealth in US Midwest.

    8 companies covering all three INDUSTRIES_OF_INTEREST, each with CB and
    no Wealth relationship.
    """
    # Cycle through the three target industries so each appears at least twice.
    industries = [
        "franchisee", "auto_dealer", "equipment",
        "franchisee", "auto_dealer", "equipment",
        "franchisee", "auto_dealer",
    ]
    names = [f"MidwestInd-{i:02d}" for i in range(1, 9)]
    for i, (name, industry) in enumerate(zip(names, industries), 1):
        ecif_id = f"FX4-{i:03d}"
        revenue = 50_000_000.0 - i * 2_000_000.0
        fx.companies.append(Company(
            ecif_id=ecif_id, name=name, country="US", region="US Midwest",
            industry=industry, employee_count=150 + i * 30,
            revenue=revenue, net_income=revenue * 0.05,
            lending_balance=revenue * 0.20, deposit_balance=revenue * 0.10,
        ))
        fx.rel_company_lob.append(RelLob(src=ecif_id, lob="CB", revenue=revenue * 0.04))

    EXPECTED[4] = {
        "region": "US Midwest",
        "names": names,
        "industries": ["franchisee", "auto_dealer", "equipment"],
    }


def _q5_bank_at_work(fx: Fixtures) -> None:
    """Q5: Large CB/CM clients with many P&BB-holding employees (bank-at-work signal).

    3 companies each with employee_count > 5000.  Each has 2 executives and
    25 individual employees who hold P&BB relationships via rel_person_lob.
    """
    company_names = ["BigCorp-01", "BigCorp-02", "BigCorp-03"]
    person_counter = 1

    for j, cname in enumerate(company_names, 1):
        c_ecif = f"FX5-{j:03d}"
        revenue = 300_000_000.0 - j * 20_000_000.0
        fx.companies.append(Company(
            ecif_id=c_ecif, name=cname, country="US", region="US South",
            industry="healthcare", employee_count=8000 + j * 1000,
            revenue=revenue, net_income=revenue * 0.09,
            lending_balance=revenue * 0.25, deposit_balance=revenue * 0.30,
        ))
        fx.rel_company_lob.append(RelLob(src=c_ecif, lob="CB", revenue=revenue * 0.05))
        fx.rel_company_lob.append(RelLob(src=c_ecif, lob="CM", revenue=revenue * 0.03))

        # 2 executives per company
        for k, title in enumerate(["CEO", "CFO"], 1):
            p_ecif = f"FX5P-{person_counter:03d}"
            person_counter += 1
            fx.persons.append(Person(
                ecif_id=p_ecif, name=f"{cname}-{title}",
                country="US", region="US South", customer_type="executive",
            ))
            fx.executive_of.append(Edge(src=p_ecif, dst=c_ecif, title=title))

        # 25 P&BB-holding employees per company
        for _ in range(25):
            p_ecif = f"FX5P-{person_counter:03d}"
            person_counter += 1
            fx.persons.append(Person(
                ecif_id=p_ecif, name=f"Employee-{p_ecif}",
                country="US", region="US South", customer_type="individual",
            ))
            fx.rel_person_lob.append(RelLob(src=p_ecif, lob="P&BB", revenue=5_000.0))
            fx.employed_by.append(Edge(src=p_ecif, dst=c_ecif))

    EXPECTED[5] = {"names": company_names}


def _q6_underpenetrated(fx: Fixtures) -> None:
    """Q6: Best underpenetrated opportunity — strong cross-BMO presence but missing Wealth.

    One standout company with CB + CM + many P&BB-holding employees, but
    conspicuously absent Wealth relationship.  This is the obvious gap the
    orchestrator should surface in the composite-reasoning showcase.
    """
    c_ecif = "FX6-001"
    fx.companies.append(Company(
        ecif_id=c_ecif, name="MegaGroup Holdings", country="CA", region="Ontario",
        industry="manufacturing", employee_count=15_000,
        revenue=450_000_000.0, net_income=50_000_000.0, rwa=200_000_000.0, roe=0.18,
        lending_balance=120_000_000.0, deposit_balance=90_000_000.0,
    ))
    fx.rel_company_lob.append(RelLob(src=c_ecif, lob="CB", revenue=18_000_000.0))
    fx.rel_company_lob.append(RelLob(src=c_ecif, lob="CM", revenue=12_000_000.0))

    # 3 executives
    for k, title in enumerate(["CEO", "CFO", "COO"], 1):
        p_ecif = f"FX6P-{k:03d}"
        fx.persons.append(Person(
            ecif_id=p_ecif, name=f"MegaGroup-{title}",
            country="CA", region="Ontario", customer_type="executive",
        ))
        fx.executive_of.append(Edge(src=p_ecif, dst=c_ecif, title=title))

    # 30 P&BB-holding employees (ids FX6P-004 through FX6P-033)
    for i in range(1, 31):
        p_ecif = f"FX6P-{i + 3:03d}"
        fx.persons.append(Person(
            ecif_id=p_ecif, name=f"MegaEmployee-{i:03d}",
            country="CA", region="Ontario", customer_type="individual",
        ))
        fx.rel_person_lob.append(RelLob(src=p_ecif, lob="P&BB", revenue=6_000.0))
        fx.employed_by.append(Edge(src=p_ecif, dst=c_ecif))

    EXPECTED[6] = {"name": "MegaGroup Holdings", "missing_lob": "Wealth"}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_fixtures() -> Fixtures:
    """Build all per-question fixture cohorts and populate EXPECTED.

    Idempotent: calling multiple times rebuilds from scratch each time.
    EXPECTED is repopulated on every call with identical data.
    """
    fx = Fixtures()
    _q1_cm_only(fx)
    _q2_cb_no_wealth(fx)
    _q3_penetration(fx)
    _q4_midwest(fx)
    _q5_bank_at_work(fx)
    _q6_underpenetrated(fx)
    return fx
