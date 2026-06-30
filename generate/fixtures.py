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
    Background cap is $10M; Q1 minimum is $21.3M — no background company can
    displace a fixture in the LIMIT 10 result.
    """
    names = [
        "Pacific Ridge Capital", "Cascade Ventures Ltd", "Sierra West Holdings",
        "Redwood Financial Group", "Golden State Partners", "Olympic Resources Inc",
        "Columbia Basin Energy", "Desert Sun Enterprises", "Evergreen Pacific Corp",
        "Summit Peak Industries",
    ]
    revenues = [
        83_700_000.0, 76_400_000.0, 71_200_000.0, 65_800_000.0, 59_300_000.0,
        52_600_000.0, 44_100_000.0, 37_800_000.0, 28_500_000.0, 21_300_000.0,
    ]
    emp_counts = [4847, 3921, 3312, 2876, 2543, 2187, 1934, 1672, 1289, 847]
    ni_ratios   = [0.09, 0.07, 0.11, 0.08, 0.10, 0.06, 0.09, 0.08, 0.07, 0.10]
    lend_ratios = [0.18, 0.14, 0.20, 0.16, 0.13, 0.22, 0.17, 0.15, 0.19, 0.12]
    dep_ratios  = [0.22, 0.19, 0.25, 0.17, 0.21, 0.28, 0.23, 0.16, 0.20, 0.24]

    for i, name in enumerate(names):
        ecif_id = f"FX1-{i + 1:03d}"
        rev = revenues[i]
        fx.companies.append(Company(
            ecif_id=ecif_id, name=name, country="US", region="US West",
            industry="manufacturing", employee_count=emp_counts[i],
            revenue=rev, net_income=rev * ni_ratios[i],
            lending_balance=rev * lend_ratios[i], deposit_balance=rev * dep_ratios[i],
        ))
        fx.rel_company_lob.append(RelLob(src=ecif_id, lob="CM", revenue=rev * 0.05))

    EXPECTED[1] = {"region": "US West", "names": names}


def _q2_cb_no_wealth(fx: Fixtures) -> None:
    """Q2: Top-20 CB clients without Wealth in US Northeast.

    20 companies with CB only (no Wealth).  Revenue descending.
    Background cap is $10M; Q2 minimum is $14.2M — all 20 fixtures rank above
    all background companies, so all 20 appear in the top-25 subset check.
    """
    names = [
        "Atlantic Seaboard Trading", "Harbor Point Financial", "Beacon Hill Associates",
        "Liberty Square Capital", "Concord Bridge Partners", "Minuteman Industries",
        "Pilgrim State Resources", "Lexington Commerce Group", "Bunker Hill Manufacturing",
        "New England Merchant Corp", "Narragansett Bay Ventures", "Mystic River Holdings",
        "Fenway Capital Partners", "Copley Square Advisors", "Cambridge Research Group",
        "Quincy Market Associates", "Commonwealth Financial Corp", "Yankee Clipper Industries",
        "Old North Trading Co", "Bay State Enterprises",
    ]
    revenues = [
        117_400_000.0, 109_800_000.0, 102_300_000.0,  96_700_000.0,  89_400_000.0,
         83_100_000.0,  77_600_000.0,  71_200_000.0,  65_400_000.0,  59_800_000.0,
         54_300_000.0,  49_700_000.0,  44_100_000.0,  39_500_000.0,  35_200_000.0,
         31_700_000.0,  27_400_000.0,  23_600_000.0,  18_900_000.0,  14_200_000.0,
    ]
    emp_counts = [
        8312, 7641, 6894, 6243, 5817,
        5321, 4876, 4312, 3891, 3456,
        3012, 2678, 2341, 2087, 1834,
        1567, 1289,  987,  734,  512,
    ]
    ni_ratios = [
        0.08, 0.06, 0.09, 0.07, 0.10, 0.06, 0.08, 0.07, 0.09, 0.06,
        0.08, 0.07, 0.06, 0.09, 0.08, 0.07, 0.06, 0.09, 0.08, 0.07,
    ]
    lend_ratios = [
        0.14, 0.12, 0.16, 0.13, 0.15, 0.11, 0.14, 0.12, 0.16, 0.13,
        0.15, 0.12, 0.14, 0.11, 0.13, 0.16, 0.12, 0.14, 0.11, 0.15,
    ]
    dep_ratios = [
        0.20, 0.18, 0.22, 0.19, 0.21, 0.17, 0.20, 0.18, 0.22, 0.19,
        0.21, 0.18, 0.20, 0.17, 0.19, 0.22, 0.18, 0.20, 0.17, 0.21,
    ]

    for i, name in enumerate(names):
        ecif_id = f"FX2-{i + 1:03d}"
        rev = revenues[i]
        fx.companies.append(Company(
            ecif_id=ecif_id, name=name, country="US", region="US Northeast",
            industry="retail", employee_count=emp_counts[i],
            revenue=rev, net_income=rev * ni_ratios[i],
            lending_balance=rev * lend_ratios[i], deposit_balance=rev * dep_ratios[i],
        ))
        fx.rel_company_lob.append(RelLob(src=ecif_id, lob="CB", revenue=rev * 0.04))

    EXPECTED[2] = {"region": "US Northeast", "names": names}


def _q3_penetration(fx: Fixtures) -> None:
    """Q3: Quebec must have the strongest CB∩Wealth penetration.

    5 anchor companies in Quebec each with CB and Wealth.  The background
    population applies knobs.PENETRATION[Quebec]=0.70 to generate the bulk;
    these fixtures ensure Quebec has visible signal even in isolation.
    """
    names = [
        "Groupe Laurentien Inc", "Société Montréal Capital", "Québec Industriel Ltée",
        "Fleuve Saint-Laurent Corp", "Alliance Capitale Québec",
    ]
    revenues   = [47_300_000.0, 41_800_000.0, 35_200_000.0, 28_700_000.0, 22_400_000.0]
    emp_counts = [1847, 1523, 1234, 976, 712]
    ni_ratios   = [0.08, 0.07, 0.09, 0.07, 0.08]
    lend_ratios = [0.12, 0.14, 0.11, 0.13, 0.10]
    dep_ratios  = [0.17, 0.15, 0.18, 0.16, 0.14]

    for i, name in enumerate(names):
        ecif_id = f"FX3-{i + 1:03d}"
        rev = revenues[i]
        fx.companies.append(Company(
            ecif_id=ecif_id, name=name, country="CA", region="Quebec",
            industry="manufacturing", employee_count=emp_counts[i],
            revenue=rev, net_income=rev * ni_ratios[i],
            lending_balance=rev * lend_ratios[i], deposit_balance=rev * dep_ratios[i],
        ))
        fx.rel_company_lob.append(RelLob(src=ecif_id, lob="CB", revenue=rev * 0.03))
        fx.rel_company_lob.append(RelLob(src=ecif_id, lob="Wealth", revenue=rev * 0.02))

    EXPECTED[3] = {"winner": "Quebec"}


def _q4_midwest(fx: Fixtures) -> None:
    """Q4: Franchisee/auto_dealer/equipment CB clients without Wealth in US Midwest.

    8 companies covering all three INDUSTRIES_OF_INTEREST, each with CB and
    no Wealth relationship.  Query has no LIMIT and test uses subset check, so
    Q4 fixtures appear in results regardless of background company revenues.
    """
    industries = [
        "franchisee", "auto_dealer", "equipment",
        "franchisee", "auto_dealer", "equipment",
        "franchisee", "auto_dealer",
    ]
    names = [
        "Heartland Franchise Group", "Prairie Auto Center", "Great Lakes Equipment Inc",
        "Corn Belt Franchise Corp", "Gateway Auto Partners", "Midwest Equipment Solutions",
        "Lakeside Franchise Holdings", "Flatlands Auto Dealers",
    ]
    revenues   = [27_800_000.0, 24_100_000.0, 21_300_000.0, 18_600_000.0,
                  15_400_000.0, 12_700_000.0,  9_800_000.0,  7_200_000.0]
    emp_counts = [1234, 1087, 934, 812, 687, 543, 421, 312]
    ni_ratios   = [0.06, 0.07, 0.05, 0.07, 0.06, 0.05, 0.07, 0.06]
    lend_ratios = [0.22, 0.20, 0.24, 0.19, 0.21, 0.23, 0.20, 0.22]
    dep_ratios  = [0.12, 0.10, 0.14, 0.11, 0.13, 0.10, 0.12, 0.11]

    for i, (name, industry) in enumerate(zip(names, industries)):
        ecif_id = f"FX4-{i + 1:03d}"
        rev = revenues[i]
        fx.companies.append(Company(
            ecif_id=ecif_id, name=name, country="US", region="US Midwest",
            industry=industry, employee_count=emp_counts[i],
            revenue=rev, net_income=rev * ni_ratios[i],
            lending_balance=rev * lend_ratios[i], deposit_balance=rev * dep_ratios[i],
        ))
        fx.rel_company_lob.append(RelLob(src=ecif_id, lob="CB", revenue=rev * 0.04))

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
    company_names = [
        "Continental Staffing Solutions",
        "National Services Group",
        "Allied Workforce Corp",
    ]
    exec_names = [
        ("Sarah Mitchell", "Robert Chen"),
        ("James Kowalski", "Linda Torres"),
        ("David Park", "Maria Santos"),
    ]
    revenues   = [247_300_000.0, 189_600_000.0, 134_200_000.0]
    emp_counts = [12847, 9234, 7612]
    ni_ratios   = [0.10, 0.09, 0.08]
    lend_ratios = [0.26, 0.24, 0.22]
    dep_ratios  = [0.31, 0.29, 0.27]

    person_counter = 1

    for j, cname in enumerate(company_names):
        c_ecif = f"FX5-{j + 1:03d}"
        rev = revenues[j]
        fx.companies.append(Company(
            ecif_id=c_ecif, name=cname, country="US", region="US South",
            industry="healthcare", employee_count=emp_counts[j],
            revenue=rev, net_income=rev * ni_ratios[j],
            lending_balance=rev * lend_ratios[j], deposit_balance=rev * dep_ratios[j],
        ))
        fx.rel_company_lob.append(RelLob(src=c_ecif, lob="CB", revenue=rev * 0.05))
        fx.rel_company_lob.append(RelLob(src=c_ecif, lob="CM", revenue=rev * 0.03))

        # 2 executives per company
        for title, exec_name in zip(["CEO", "CFO"], exec_names[j]):
            p_ecif = f"FX5P-{person_counter:03d}"
            person_counter += 1
            fx.persons.append(Person(
                ecif_id=p_ecif, name=exec_name,
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
        ecif_id=c_ecif, name="Dominion Infrastructure Partners",
        country="CA", region="Ontario",
        industry="manufacturing", employee_count=14_847,
        revenue=183_700_000.0, net_income=20_200_000.0, rwa=119_400_000.0, roe=0.17,
        lending_balance=64_300_000.0, deposit_balance=51_400_000.0,
    ))
    fx.rel_company_lob.append(RelLob(src=c_ecif, lob="CB", revenue=13_200_000.0))
    fx.rel_company_lob.append(RelLob(src=c_ecif, lob="CM", revenue=9_400_000.0))

    # 3 executives — each with personal BMO relationships that strengthen
    # the cross-sell case for Wealth at the company level.
    exec_names = ["Catherine Beaumont", "François Lapointe", "Michelle Okafor"]
    for k, (title, exec_name) in enumerate(zip(["CEO", "CFO", "COO"], exec_names), 1):
        p_ecif = f"FX6P-{k:03d}"
        fx.persons.append(Person(
            ecif_id=p_ecif, name=exec_name,
            country="CA", region="Ontario", customer_type="executive",
        ))
        fx.executive_of.append(Edge(src=p_ecif, dst=c_ecif, title=title))

    # Catherine Beaumont (CEO) — personal Wealth + P&BB accounts.
    # The CEO already banks personally with BMO Wealth — warm intro pathway.
    fx.rel_person_lob.append(RelLob(src="FX6P-001", lob="Wealth", revenue=42_000.0))
    fx.rel_person_lob.append(RelLob(src="FX6P-001", lob="P&BB", revenue=8_500.0))

    # François Lapointe (CFO) — board member at Continental Staffing Solutions
    # (Q5 company, FX5-001). Cross-company intelligence link. Has P&BB.
    fx.executive_of.append(Edge(src="FX6P-002", dst="FX5-001", title="Board Member"))
    fx.rel_person_lob.append(RelLob(src="FX6P-002", lob="P&BB", revenue=7_200.0))

    # Michelle Okafor (COO) — personal CB + P&BB accounts.
    fx.rel_person_lob.append(RelLob(src="FX6P-003", lob="CB", revenue=15_000.0))
    fx.rel_person_lob.append(RelLob(src="FX6P-003", lob="P&BB", revenue=6_800.0))

    # 30 P&BB-holding employees (ids FX6P-004 through FX6P-033)
    for i in range(1, 31):
        p_ecif = f"FX6P-{i + 3:03d}"
        fx.persons.append(Person(
            ecif_id=p_ecif, name=f"Employee-{p_ecif}",
            country="CA", region="Ontario", customer_type="individual",
        ))
        fx.rel_person_lob.append(RelLob(src=p_ecif, lob="P&BB", revenue=6_000.0))
        fx.employed_by.append(Edge(src=p_ecif, dst=c_ecif))

    EXPECTED[6] = {"name": "Dominion Infrastructure Partners", "missing_lob": "Wealth"}


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
