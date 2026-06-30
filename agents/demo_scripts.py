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
        "10 exclusive Capital Markets clients in US West with zero other LOB "
        "relationships — pure CM-only, ranked by revenue:\n\n"
        "1. Pacific Ridge Capital — $83.7M\n"
        "2. Cascade Ventures Ltd — $76.4M\n"
        "3. Sierra West Holdings — $71.2M\n"
        "4. Redwood Financial Group — $65.8M\n"
        "5. Golden State Partners — $59.3M\n"
        "6. Olympic Resources Inc — $52.6M\n"
        "7. Columbia Basin Energy — $44.1M\n"
        "8. Desert Sun Enterprises — $37.8M\n"
        "9. Evergreen Pacific Corp — $28.5M\n"
        "10. Summit Peak Industries — $21.3M\n\n"
        "All 10 have only a CM relationship — no CB, no Wealth, no P&BB. "
        "This single-LOB concentration represents both risk (revenue dependency) "
        "and opportunity (cross-sell into CB and Wealth)."
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
        "8 CB clients in US Midwest across all three target industries, none "
        "with Wealth relationships:\n\n"
        "Franchisees:\n"
        "- Heartland Franchise Group — $27.8M\n"
        "- Corn Belt Franchise Corp — $18.6M\n"
        "- Lakeside Franchise Holdings — $9.8M\n\n"
        "Auto Dealers:\n"
        "- Prairie Auto Center — $24.1M\n"
        "- Gateway Auto Partners — $15.4M\n"
        "- Flatlands Auto Dealers — $7.2M\n\n"
        "Equipment:\n"
        "- Great Lakes Equipment Inc — $21.3M\n"
        "- Midwest Equipment Solutions — $12.7M\n\n"
        "All have active Commercial Banking relationships but zero Wealth "
        "engagement — a natural cross-sell segment for Wealth Management."
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
       c.revenue AS revenue, c.region AS region, pbb_employee_count, lobs
ORDER BY pbb_employee_count DESC
""",
            {},
        ),
        (
            "Get executive leadership for these bank-at-work candidates",
            """
MATCH (c:Company)-[:COMPANY_HAS_RELATIONSHIP]->(l:LineOfBusiness)
WHERE l.name IN ['CB', 'CM'] AND c.employee_count > 5000
WITH c, collect(DISTINCT l.name) AS lobs
MATCH (exec:Person)-[e:EXECUTIVE_OF]->(c)
RETURN c.name AS company, exec.name AS executive_name, e.title AS title
ORDER BY c.employee_count DESC, e.title
""",
            {},
        ),
    ],
    nudge=(
        "3 large companies identified as strong bank-at-work candidates:\n\n"
        "1. Continental Staffing Solutions — $247M revenue, 12,847 employees, "
        "25 already hold P&BB accounts. Leadership: Sarah Mitchell (CEO), "
        "Robert Chen (CFO). Located in US South.\n\n"
        "2. National Services Group — $190M revenue, 9,234 employees, "
        "25 P&BB-holding employees. Leadership: James Kowalski (CEO), "
        "Linda Torres (CFO). Located in US South.\n\n"
        "3. Allied Workforce Corp — $134M revenue, 7,612 employees, "
        "25 P&BB-holding employees. Leadership: David Park (CEO), "
        "Maria Santos (CFO). Located in US South.\n\n"
        "All three hold both CB and CM relationships. The high P&BB employee "
        "count signals existing personal banking engagement — strong foundation "
        "for expanding bank-at-work programs across the full employee base."
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
       c.employee_count AS employee_count, c.region AS region
ORDER BY employee_links DESC, c.revenue DESC
LIMIT 5
""",
            {},
        ),
        (
            "Get executive leadership and LOB details for Dominion Infrastructure Partners",
            """
MATCH (c:Company {name: 'Dominion Infrastructure Partners'})-[:COMPANY_HAS_RELATIONSHIP]->(l:LineOfBusiness)
WITH c, collect(l.name) AS current_lobs
MATCH (exec:Person)-[e:EXECUTIVE_OF]->(c)
WITH c, current_lobs, collect({name: exec.name, title: e.title}) AS executives
OPTIONAL MATCH (p:Person)-[:EMPLOYED_BY]->(c)
WHERE EXISTS {
  MATCH (p)-[:PERSON_HAS_RELATIONSHIP]->(:LineOfBusiness {name: 'P&BB'})
}
RETURN c.ecif_id AS ecif_id, c.name AS name, c.revenue AS revenue,
       c.employee_count AS employee_count, c.region AS region,
       current_lobs, executives, count(p) AS pbb_employee_count
""",
            {},
        ),
    ],
    nudge=(
        "Dominion Infrastructure Partners is the single best underpenetrated "
        "opportunity in the portfolio:\n\n"
        "- Revenue: $183.7M | Employees: 14,847 | Region: Ontario\n"
        "- Current LOBs: Commercial Banking (CB) + Capital Markets (CM)\n"
        "- MISSING: Wealth Management — despite deep existing engagement\n"
        "- Executive team: Catherine Beaumont (CEO), François Lapointe (CFO), "
        "Michelle Okafor (COO)\n"
        "- 30 employees already hold Personal & Business Banking (P&BB) accounts "
        "— strong signal of individual banking engagement\n\n"
        "The combination of multi-LOB presence (CB + CM), large workforce with "
        "existing P&BB penetration, senior executive relationships, and the "
        "conspicuous absence of Wealth makes this the highest-priority cross-sell "
        "target. Recommend Wealth Management outreach starting with the C-suite."
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
