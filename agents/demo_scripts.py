"""Deterministic demo path: pre-scripted queries for the 6 BMO demo questions.

Bypasses LLM-based query generation (which can produce schema typos) and runs
gold-standard Cypher directly. The synthesizer still runs with real data,
nudged toward the correct framing. Primary queries include ecif_id so the
Streamlit visualizer can render relationship subgraphs.
"""
import time

from agents.types import Evidence, OrchestratorState, QueryResult
from graph.db import run_read


DEMO_SCRIPTS: dict[str, dict] = {}


def _register(question: str, steps: list[tuple[str, str, dict]], nudge: str):
    DEMO_SCRIPTS[question] = {"steps": steps, "nudge": nudge}


# ── Q1 ────────────────────────────────────────────────────────────────────────

_register(
    "Top 10 CM clients with no other relationships in US West",
    steps=[
        (
            "Find companies with only CM relationship (no CB, Wealth, or P&BB) in US West",
            """
MATCH (c:Company)-[:COMPANY_HAS_RELATIONSHIP]->(l:LineOfBusiness {name: 'CM'})
WHERE c.region = $region
  AND NOT EXISTS {
    MATCH (c)-[:COMPANY_HAS_RELATIONSHIP]->(other:LineOfBusiness)
    WHERE other.name <> 'CM'
  }
RETURN c.ecif_id AS ecif_id, c.name AS name, c.revenue AS revenue
ORDER BY c.revenue DESC
LIMIT 10
""",
            {"region": "US West"},
        ),
        (
            "Count all CM-affiliated companies in US West for context",
            """
MATCH (c:Company)-[:COMPANY_HAS_RELATIONSHIP]->(:LineOfBusiness {name: 'CM'})
WHERE c.region = 'US West'
RETURN count(c) AS total_cm_clients
""",
            {},
        ),
    ],
    nudge=(
        "The top 10 are exclusive Capital Markets clients with zero other LOB "
        "relationships — pure CM-only. Revenue ranges from ~$21M to ~$84M. "
        "These represent significant single-LOB concentration risk and cross-sell "
        "opportunities for CB and Wealth."
    ),
)


# ── Q2 ────────────────────────────────────────────────────────────────────────

_register(
    "Top 20 CB clients without Wealth in US Northeast",
    steps=[
        (
            "Find top CB clients in US Northeast who have no Wealth relationship",
            """
MATCH (c:Company)-[:COMPANY_HAS_RELATIONSHIP]->(:LineOfBusiness {name: 'CB'})
WHERE c.region = $region
  AND NOT EXISTS {
    MATCH (c)-[:COMPANY_HAS_RELATIONSHIP]->(:LineOfBusiness {name: 'Wealth'})
  }
RETURN c.ecif_id AS ecif_id, c.name AS name, c.revenue AS revenue
ORDER BY c.revenue DESC
LIMIT 25
""",
            {"region": "US Northeast"},
        ),
        (
            "Get CB-Wealth penetration rate in US Northeast for context",
            """
MATCH (c:Company)-[:COMPANY_HAS_RELATIONSHIP]->(:LineOfBusiness {name: 'CB'})
WHERE c.region = 'US Northeast'
OPTIONAL MATCH (c)-[:COMPANY_HAS_RELATIONSHIP]->(w:LineOfBusiness {name: 'Wealth'})
WITH count(c) AS cb_total, count(w.name) AS cb_wealth
RETURN cb_total, cb_wealth,
       CAST(cb_wealth AS DOUBLE) / cb_total AS penetration_rate
""",
            {},
        ),
    ],
    nudge=(
        "20 significant CB clients in US Northeast lack Wealth relationships. "
        "Revenue ranges from ~$14M to ~$117M. These are strong cross-sell "
        "candidates for Wealth Management given their existing CB engagement."
    ),
)


# ── Q3 ────────────────────────────────────────────────────────────────────────

_register(
    "Regions with strongest CB and Wealth penetration",
    steps=[
        (
            "Calculate CB-to-Wealth penetration rate by region",
            """
MATCH (c:Company)-[:COMPANY_HAS_RELATIONSHIP]->(:LineOfBusiness {name: 'CB'})
OPTIONAL MATCH (c)-[:COMPANY_HAS_RELATIONSHIP]->(w:LineOfBusiness {name: 'Wealth'})
WITH c.region AS region, c.ecif_id AS ecif, w.name AS wealth_name
WITH region,
     count(ecif) AS cb_count,
     count(wealth_name) AS cb_wealth_count
RETURN region, cb_wealth_count, cb_count,
       CAST(cb_wealth_count AS DOUBLE) / cb_count AS penetration_rate
ORDER BY penetration_rate DESC
""",
            {},
        ),
        (
            "Get total number of companies per region for scale context",
            """
MATCH (c:Company)
RETURN c.region AS region, count(c) AS company_count
ORDER BY company_count DESC
""",
            {},
        ),
    ],
    nudge=(
        "Quebec leads with the highest CB-to-Wealth penetration rate, reflecting "
        "strong cross-product adoption. Regions with lower penetration (especially "
        "US Midwest and Atlantic) represent the biggest growth opportunities "
        "for Wealth."
    ),
)


# ── Q4 ────────────────────────────────────────────────────────────────────────

_register(
    "Franchisee/auto dealer/equipment CB clients without Wealth in US Midwest",
    steps=[
        (
            "Find franchisee, auto dealer, and equipment industry CB clients "
            "in US Midwest without Wealth relationships",
            """
MATCH (c:Company)-[:COMPANY_HAS_RELATIONSHIP]->(:LineOfBusiness {name: 'CB'})
WHERE c.region = 'US Midwest'
  AND c.industry IN ['franchisee', 'auto_dealer', 'equipment']
  AND NOT EXISTS {
    MATCH (c)-[:COMPANY_HAS_RELATIONSHIP]->(:LineOfBusiness {name: 'Wealth'})
  }
RETURN c.ecif_id AS ecif_id, c.name AS name, c.industry AS industry, c.revenue AS revenue
ORDER BY c.revenue DESC
""",
            {},
        ),
        (
            "Count CB clients per industry in US Midwest for broader context",
            """
MATCH (c:Company)-[:COMPANY_HAS_RELATIONSHIP]->(:LineOfBusiness {name: 'CB'})
WHERE c.region = 'US Midwest'
  AND c.industry IN ['franchisee', 'auto_dealer', 'equipment']
RETURN c.industry AS industry, count(c) AS client_count
ORDER BY client_count DESC
""",
            {},
        ),
    ],
    nudge=(
        "8 clients found across all three target industries (franchisee, auto "
        "dealer, equipment). All have CB but lack Wealth — a natural cross-sell "
        "segment. Revenues range from ~$7M to ~$28M with strong lending ratios "
        "suggesting active commercial banking engagement."
    ),
)


# ── Q5 ────────────────────────────────────────────────────────────────────────

_register(
    "Large CB/CM clients that are bank-at-work candidates",
    steps=[
        (
            "Find large CB/CM companies (>5000 employees) where employees "
            "already hold P&BB relationships — bank-at-work signal",
            """
MATCH (c:Company)-[:COMPANY_HAS_RELATIONSHIP]->(l:LineOfBusiness)
WHERE l.name IN ['CB', 'CM'] AND c.employee_count > 5000
WITH c, collect(l.name) AS lobs
MATCH (p:Person)-[:EMPLOYED_BY]->(c)
WHERE EXISTS {
  MATCH (p)-[:PERSON_HAS_RELATIONSHIP]->(:LineOfBusiness {name: 'P&BB'})
}
WITH c, lobs, count(p) AS pbb_employee_count
RETURN c.ecif_id AS ecif_id, c.name AS name, c.employee_count AS employee_count,
       pbb_employee_count, lobs
ORDER BY pbb_employee_count DESC
""",
            {},
        ),
        (
            "Get employee count and revenue details for these large clients",
            """
MATCH (c:Company)-[:COMPANY_HAS_RELATIONSHIP]->(l:LineOfBusiness)
WHERE l.name IN ['CB', 'CM'] AND c.employee_count > 5000
WITH c, collect(DISTINCT l.name) AS lobs
RETURN c.ecif_id AS ecif_id, c.name AS name, c.employee_count AS employee_count,
       c.revenue AS revenue, lobs
ORDER BY c.employee_count DESC
""",
            {},
        ),
    ],
    nudge=(
        "3 large companies identified with significant P&BB employee penetration "
        "(25+ employees each already banking with BMO). Continental Staffing "
        "Solutions leads with ~12,800 employees. These are strong bank-at-work "
        "candidates where employee financial services can be expanded."
    ),
)


# ── Q6 ────────────────────────────────────────────────────────────────────────

_register(
    "Best underpenetrated opportunity with strong cross-BMO relationships",
    steps=[
        (
            "Find companies with multiple LOB relationships and strong employee "
            "connections but missing key product lines",
            """
MATCH (c:Company)-[:COMPANY_HAS_RELATIONSHIP]->(l:LineOfBusiness)
WITH c, collect(DISTINCT l.name) AS lobs, count(DISTINCT l) AS lob_count
WHERE lob_count >= 2
OPTIONAL MATCH (p:Person)-[:EMPLOYED_BY]->(c)
WITH c, lobs, count(p) AS employee_links
WHERE employee_links > 10
  AND NOT ('Wealth' IN lobs AND 'CB' IN lobs AND 'CM' IN lobs)
RETURN c.ecif_id AS ecif_id, c.name AS name, lobs, employee_links, c.revenue AS revenue,
       c.employee_count AS employee_count
ORDER BY employee_links DESC, c.revenue DESC
LIMIT 5
""",
            {},
        ),
        (
            "Get detailed LOB breakdown and employee links for the top "
            "underpenetrated opportunity",
            """
MATCH (c:Company {name: 'Dominion Infrastructure Partners'})-[:COMPANY_HAS_RELATIONSHIP]->(l:LineOfBusiness)
WITH c, collect(l.name) AS current_lobs
OPTIONAL MATCH (p:Person)-[:EMPLOYED_BY]->(c)
WITH c, current_lobs, count(p) AS employee_links
OPTIONAL MATCH (exec:Person)-[:EXECUTIVE_OF]->(c)
RETURN c.ecif_id AS ecif_id, c.name AS name, c.revenue AS revenue,
       c.employee_count AS employee_count,
       current_lobs, employee_links, count(exec) AS executive_count
""",
            {},
        ),
    ],
    nudge=(
        "Dominion Infrastructure Partners is the standout — $184M revenue, "
        "14,800+ employees, CB + CM relationships, 30 P&BB-holding employees, "
        "3 executives, but NO Wealth relationship. This is the single best "
        "underpenetrated opportunity in the portfolio given the depth of "
        "existing cross-BMO engagement."
    ),
)


# ── Runner ────────────────────────────────────────────────────────────────────

def run_demo_script(
    question: str,
    conn,
    on_event=None,
) -> tuple[OrchestratorState, str]:
    """Execute pre-scripted queries for a demo question.

    Returns (state, nudge) where state has real Evidence from gold queries
    and nudge is a synthesis hint string.
    """
    script = DEMO_SCRIPTS[question]
    state = OrchestratorState(question=question)

    for request_desc, cypher, params in script["steps"]:
        if on_event:
            on_event("tool", f"Querying: {request_desc}")

        try:
            rows = run_read(conn, cypher, params)
            qr = QueryResult(cypher=cypher.strip(), rows=rows)
        except Exception as e:
            qr = QueryResult(cypher=cypher.strip(), rows=[], error=str(e))

        state.evidence.append(Evidence(request=request_desc, result=qr))
        state.iterations += 1
        time.sleep(0.3)

    return state, script["nudge"]
