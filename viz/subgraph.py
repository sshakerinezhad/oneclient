"""
viz/subgraph.py — build a capped pyvis network for entity neighborhoods.

WHY: Streamlit needs an HTML snippet showing which companies/persons connect
to which LOBs/Regions.  Capped at ≤cap nodes to keep the graph legible;
offline-safe via cdn_resources='in_line' (vis-network.js is embedded, no CDN).
"""
from __future__ import annotations

import kuzu
from pyvis.network import Network

from graph.db import run_read

# ── visual config ─────────────────────────────────────────────────────────────

_TYPE_CONFIG: dict[str, dict] = {
    "Company":        {"color": "#0079C1", "shape": "dot",     "emoji": "🏢"},
    "Person":         {"color": "#2E7D32", "shape": "dot",     "emoji": "👤"},
    "Region":         {"color": "#FF6B35", "shape": "diamond", "emoji": "📍"},
    "LineOfBusiness": {"color": "#7B2D8E", "shape": "square",  "emoji": "🏷️"},
}

_DEFAULT_CFG = {"color": "#888888", "shape": "dot", "emoji": ""}


def _cfg(node_type: str) -> dict:
    return _TYPE_CONFIG.get(node_type, _DEFAULT_CFG)


# ── data collection ───────────────────────────────────────────────────────────

def _fetch_edges(conn: kuzu.Connection, entity_ids: list[str]) -> list[dict]:
    """
    Return all 1-hop edges touching entity_ids across every rel table.

    WHY separate queries per rel table: kuzu v0.7 does not support label(n)
    or type(r) in generic MATCH patterns, so we query each typed rel explicitly.
    """
    if not entity_ids:
        return []

    edges: list[dict] = []

    # Company → LOB
    edges.extend(run_read(conn, """
        MATCH (c:Company)-[:COMPANY_HAS_RELATIONSHIP]->(l:LineOfBusiness)
        WHERE c.ecif_id IN $ids
        RETURN c.ecif_id AS src_id, c.name AS src_name, 'Company' AS src_type,
               'HAS_LOB' AS rel,
               l.name AS dst_id, l.name AS dst_name, 'LineOfBusiness' AS dst_type
    """, {"ids": entity_ids}))

    # Company → Region
    edges.extend(run_read(conn, """
        MATCH (c:Company)-[:COMPANY_LOCATED_IN]->(r:Region)
        WHERE c.ecif_id IN $ids
        RETURN c.ecif_id AS src_id, c.name AS src_name, 'Company' AS src_type,
               'LOCATED_IN' AS rel,
               r.name AS dst_id, r.name AS dst_name, 'Region' AS dst_type
    """, {"ids": entity_ids}))

    # Person → LOB
    edges.extend(run_read(conn, """
        MATCH (p:Person)-[:PERSON_HAS_RELATIONSHIP]->(l:LineOfBusiness)
        WHERE p.ecif_id IN $ids
        RETURN p.ecif_id AS src_id, p.name AS src_name, 'Person' AS src_type,
               'HAS_LOB' AS rel,
               l.name AS dst_id, l.name AS dst_name, 'LineOfBusiness' AS dst_type
    """, {"ids": entity_ids}))

    # Person → Company (executive role)
    edges.extend(run_read(conn, """
        MATCH (p:Person)-[:EXECUTIVE_OF]->(c:Company)
        WHERE p.ecif_id IN $ids
        RETURN p.ecif_id AS src_id, p.name AS src_name, 'Person' AS src_type,
               'EXECUTIVE_OF' AS rel,
               c.ecif_id AS dst_id, c.name AS dst_name, 'Company' AS dst_type
    """, {"ids": entity_ids}))

    # Person → Company (employment)
    edges.extend(run_read(conn, """
        MATCH (p:Person)-[:EMPLOYED_BY]->(c:Company)
        WHERE p.ecif_id IN $ids
        RETURN p.ecif_id AS src_id, p.name AS src_name, 'Person' AS src_type,
               'EMPLOYED_BY' AS rel,
               c.ecif_id AS dst_id, c.name AS dst_name, 'Company' AS dst_type
    """, {"ids": entity_ids}))

    return edges


def _select_nodes(
    edges: list[dict],
    entity_ids: set[str],
    cap: int,
) -> dict[str, dict]:
    """
    Collect nodes from edges and cap at `cap` total nodes.

    Priority ordering (lower = higher priority):
      0 — answer entities (passed in by the caller)
      1 — LineOfBusiness nodes (most useful for LOB analysis)
      2 — Region nodes
      3 — any other connected node (persons, secondary companies)
    """
    all_nodes: dict[str, dict] = {}
    for e in edges:
        for prefix in ("src", "dst"):
            nid = e[f"{prefix}_id"]
            if nid not in all_nodes:
                all_nodes[nid] = {
                    "id":    nid,
                    "label": e[f"{prefix}_name"],
                    "type":  e[f"{prefix}_type"],
                }

    def _priority(nid: str) -> int:
        if nid in entity_ids:
            return 0
        t = all_nodes[nid]["type"]
        if t == "LineOfBusiness":
            return 1
        if t == "Region":
            return 2
        return 3

    ordered = sorted(all_nodes, key=_priority)
    kept = ordered[:cap]
    return {nid: all_nodes[nid] for nid in kept}


# ── public API ────────────────────────────────────────────────────────────────

def build_subgraph(
    conn: kuzu.Connection,
    entity_ids: list[str],
    cap: int = 15,
) -> str:
    """
    Build a pyvis network for the 1-hop neighborhood of entity_ids, capped at `cap` nodes.

    Returns an HTML string (suitable for Streamlit's st.components.html).
    cdn_resources='in_line' embeds vis-network.js so the graph works on
    air-gapped / locked corporate networks.
    """
    id_set = set(entity_ids)
    edges = _fetch_edges(conn, entity_ids)
    nodes = _select_nodes(edges, id_set, cap)

    net = Network(height="400px", width="100%", cdn_resources="in_line")

    for nid, meta in nodes.items():
        cfg = _cfg(meta["type"])
        label = f"{cfg['emoji']} {meta['label']}" if cfg["emoji"] else meta["label"]
        net.add_node(nid, label=label, color=cfg["color"], shape=cfg["shape"])

    # Only add edges where both endpoints survived the cap
    for e in edges:
        if e["src_id"] in nodes and e["dst_id"] in nodes:
            net.add_edge(e["src_id"], e["dst_id"], title=e["rel"])

    net.set_options("""{
        "physics": {
            "barnesHut": {"gravitationalConstant": -3000, "springLength": 100}
        }
    }""")

    return net.generate_html()
