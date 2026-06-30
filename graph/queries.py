"""Canonical Cypher queries for the 6 BMO demo questions.

Each function returns (cypher, params) for use with graph.db.run_read().
WHY: Centralised here so the query agent (Task 2.3) can use these as
few-shot gold answers, and so the verification gate has a single source
of truth for what each question means in raw Cypher.
"""


def q1_cm_only(region: str) -> tuple[str, dict]:
    """Q1: Top 10 CM-only clients (no other LOBs) in a given region."""
    cypher = """
MATCH (c:Company)-[:COMPANY_HAS_RELATIONSHIP]->(l:LineOfBusiness {name: 'CM'})
WHERE c.region = $region
  AND NOT EXISTS {
    MATCH (c)-[:COMPANY_HAS_RELATIONSHIP]->(other:LineOfBusiness)
    WHERE other.name <> 'CM'
  }
RETURN c.name AS name, c.revenue AS revenue
ORDER BY c.revenue DESC
LIMIT 10
"""
    return cypher, {"region": region}


def q2_cb_no_wealth(region: str) -> tuple[str, dict]:
    """Q2: Top CB clients without a Wealth relationship in a given region.

    Returns top 25 to account for background population overlap near the
    revenue boundary; callers should treat the result as a broad shortlist
    rather than a hard-ranked 20.
    """
    cypher = """
MATCH (c:Company)-[:COMPANY_HAS_RELATIONSHIP]->(:LineOfBusiness {name: 'CB'})
WHERE c.region = $region
  AND NOT EXISTS {
    MATCH (c)-[:COMPANY_HAS_RELATIONSHIP]->(:LineOfBusiness {name: 'Wealth'})
  }
RETURN c.name AS name, c.revenue AS revenue
ORDER BY c.revenue DESC
LIMIT 25
"""
    return cypher, {"region": region}


def q3_penetration() -> tuple[str, dict]:
    """Q3: Regions ranked by CB→Wealth penetration rate (highest first)."""
    cypher = """
MATCH (c:Company)-[:COMPANY_HAS_RELATIONSHIP]->(:LineOfBusiness {name: 'CB'})
OPTIONAL MATCH (c)-[:COMPANY_HAS_RELATIONSHIP]->(w:LineOfBusiness {name: 'Wealth'})
WITH c.region AS region, c.ecif_id AS ecif, w.name AS wealth_name
WITH region,
     count(ecif) AS cb_count,
     count(wealth_name) AS cb_wealth_count
RETURN region, cb_wealth_count, cb_count,
       CAST(cb_wealth_count AS DOUBLE) / cb_count AS penetration_rate
ORDER BY penetration_rate DESC
"""
    return cypher, {}


def q4_midwest_industries() -> tuple[str, dict]:
    """Q4: CB clients in franchisee/auto_dealer/equipment industries (US Midwest) without Wealth."""
    cypher = """
MATCH (c:Company)-[:COMPANY_HAS_RELATIONSHIP]->(:LineOfBusiness {name: 'CB'})
WHERE c.region = 'US Midwest'
  AND c.industry IN ['franchisee', 'auto_dealer', 'equipment']
  AND NOT EXISTS {
    MATCH (c)-[:COMPANY_HAS_RELATIONSHIP]->(:LineOfBusiness {name: 'Wealth'})
  }
RETURN c.name AS name, c.industry AS industry, c.revenue AS revenue
ORDER BY c.revenue DESC
"""
    return cypher, {}


def q5_bank_at_work() -> tuple[str, dict]:
    """Q5: Large CB/CM clients (>5000 employees) with P&BB-holding employees — bank-at-work signal."""
    cypher = """
MATCH (c:Company)-[:COMPANY_HAS_RELATIONSHIP]->(l:LineOfBusiness)
WHERE l.name IN ['CB', 'CM'] AND c.employee_count > 5000
WITH c, collect(l.name) AS lobs
MATCH (p:Person)-[:EMPLOYED_BY]->(c)
WHERE EXISTS {
  MATCH (p)-[:PERSON_HAS_RELATIONSHIP]->(:LineOfBusiness {name: 'P&BB'})
}
WITH c, lobs, count(p) AS pbb_employee_count
RETURN c.name AS name, c.employee_count AS employee_count,
       pbb_employee_count, lobs
ORDER BY pbb_employee_count DESC
"""
    return cypher, {}


def q6_underpenetrated() -> tuple[str, dict]:
    """Q6: Top underpenetrated opportunities — multi-LOB presence with strong employee signal but missing products."""
    cypher = """
MATCH (c:Company)-[:COMPANY_HAS_RELATIONSHIP]->(l:LineOfBusiness)
WITH c, collect(DISTINCT l.name) AS lobs, count(DISTINCT l) AS lob_count
WHERE lob_count >= 2
OPTIONAL MATCH (p:Person)-[:EMPLOYED_BY]->(c)
WITH c, lobs, count(p) AS employee_links
WHERE employee_links > 10
  AND NOT ('Wealth' IN lobs AND 'CB' IN lobs AND 'CM' IN lobs)
RETURN c.name AS name, lobs, employee_links, c.revenue AS revenue,
       c.employee_count AS employee_count
ORDER BY employee_links DESC, c.revenue DESC
LIMIT 5
"""
    return cypher, {}
