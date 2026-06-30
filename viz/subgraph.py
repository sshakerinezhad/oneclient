"""
viz/subgraph.py — build a capped pyvis network for entity neighborhoods.

Streamlit needs an HTML snippet showing which companies/persons connect
to which LOBs/Regions. Capped at ≤cap nodes to keep the graph legible;
offline-safe via cdn_resources='in_line' (vis-network.js is embedded).
"""
from __future__ import annotations

import kuzu
from pyvis.network import Network

from graph.db import run_read

# ── visual config ─────────────────────────────────────────────────────────────

_NODE_CONFIG: dict[str, dict] = {
    "Company":        {"emoji": "🏢", "size": 45, "size_answer": 55},
    "Person":         {"emoji": "👤", "size": 30, "size_answer": 35},
    "Region":         {"emoji": "📍", "size": 35, "size_answer": 40},
    "LineOfBusiness": {"emoji": "🏷️",  "size": 35, "size_answer": 40},
}

_DEFAULT_NODE = {"emoji": "⬡", "size": 30, "size_answer": 35}

_EDGE_CONFIG: dict[str, dict] = {
    "HAS_LOB":       {"color": "#0079C1", "hover": "has relationship with", "label": "LOB"},
    "LOCATED_IN":    {"color": "#FF6B35", "hover": "located in",           "label": "Region"},
    "EMPLOYED_BY":   {"color": "#2E7D32", "hover": "works at",             "label": "Employment"},
    "EXECUTIVE_OF":  {"color": "#2E7D32", "hover": "executive of",         "label": "Employment"},
}

_DEFAULT_EDGE = {"color": "#999999", "hover": "connected to", "label": "Other"}


def _node_cfg(node_type: str) -> dict:
    return _NODE_CONFIG.get(node_type, _DEFAULT_NODE)


def _edge_cfg(rel: str) -> dict:
    return _EDGE_CONFIG.get(rel, _DEFAULT_EDGE)


# ── data collection ───────────────────────────────────────────────────────────

def _fetch_edges(conn: kuzu.Connection, entity_ids: list[str]) -> list[dict]:
    """Return all 1-hop edges touching entity_ids across every rel table."""
    if not entity_ids:
        return []

    edges: list[dict] = []

    edges.extend(run_read(conn, """
        MATCH (c:Company)-[:COMPANY_HAS_RELATIONSHIP]->(l:LineOfBusiness)
        WHERE c.ecif_id IN $ids
        RETURN c.ecif_id AS src_id, c.name AS src_name, 'Company' AS src_type,
               'HAS_LOB' AS rel,
               l.name AS dst_id, l.name AS dst_name, 'LineOfBusiness' AS dst_type
    """, {"ids": entity_ids}))

    edges.extend(run_read(conn, """
        MATCH (c:Company)-[:COMPANY_LOCATED_IN]->(r:Region)
        WHERE c.ecif_id IN $ids
        RETURN c.ecif_id AS src_id, c.name AS src_name, 'Company' AS src_type,
               'LOCATED_IN' AS rel,
               r.name AS dst_id, r.name AS dst_name, 'Region' AS dst_type
    """, {"ids": entity_ids}))

    edges.extend(run_read(conn, """
        MATCH (p:Person)-[:PERSON_HAS_RELATIONSHIP]->(l:LineOfBusiness)
        WHERE p.ecif_id IN $ids
        RETURN p.ecif_id AS src_id, p.name AS src_name, 'Person' AS src_type,
               'HAS_LOB' AS rel,
               l.name AS dst_id, l.name AS dst_name, 'LineOfBusiness' AS dst_type
    """, {"ids": entity_ids}))

    edges.extend(run_read(conn, """
        MATCH (p:Person)-[:EXECUTIVE_OF]->(c:Company)
        WHERE p.ecif_id IN $ids
        RETURN p.ecif_id AS src_id, p.name AS src_name, 'Person' AS src_type,
               'EXECUTIVE_OF' AS rel,
               c.ecif_id AS dst_id, c.name AS dst_name, 'Company' AS dst_type
    """, {"ids": entity_ids}))

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
    """Collect nodes from edges, prioritized and capped."""
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


_LEGEND_HTML = """
<div style="
    position: absolute; bottom: 12px; right: 12px;
    background: rgba(255,255,255,0.92); border: 1px solid #ddd;
    border-radius: 8px; padding: 8px 14px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 12px; line-height: 20px; z-index: 10;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
">
    <div style="font-weight: 600; margin-bottom: 4px; color: #333;">Connections</div>
    <div><span style="display:inline-block;width:18px;height:3px;background:#0079C1;vertical-align:middle;margin-right:6px;border-radius:2px;"></span>Line of Business</div>
    <div><span style="display:inline-block;width:18px;height:3px;background:#FF6B35;vertical-align:middle;margin-right:6px;border-radius:2px;"></span>Region</div>
    <div><span style="display:inline-block;width:18px;height:3px;background:#2E7D32;vertical-align:middle;margin-right:6px;border-radius:2px;"></span>Employment</div>
</div>
"""


# ── public API ────────────────────────────────────────────────────────────────

def build_subgraph(
    conn: kuzu.Connection,
    entity_ids: list[str],
    cap: int = 15,
) -> str:
    """Build a pyvis network for the 1-hop neighborhood of entity_ids.

    Returns HTML string for Streamlit's st.components.html.
    """
    id_set = set(entity_ids)
    edges = _fetch_edges(conn, entity_ids)
    nodes = _select_nodes(edges, id_set, cap)

    net = Network(height="420px", width="100%", cdn_resources="in_line")

    for nid, meta in nodes.items():
        cfg = _node_cfg(meta["type"])
        is_answer = nid in id_set
        size = cfg["size_answer"] if is_answer else cfg["size"]
        name = meta["label"]
        if len(name) > 22:
            name = name[:20] + "..."
        net.add_node(
            nid,
            label=f"{cfg['emoji']}\n{name}",
            title=meta["label"],
            shape="text",
            font={
                "size": size,
                "face": "Apple Color Emoji, Segoe UI Emoji, Noto Color Emoji, sans-serif",
                "multi": "html",
            },
        )

    for e in edges:
        if e["src_id"] in nodes and e["dst_id"] in nodes:
            ecfg = _edge_cfg(e["rel"])
            src_name = nodes[e["src_id"]]["label"]
            dst_name = nodes[e["dst_id"]]["label"]
            net.add_edge(
                e["src_id"],
                e["dst_id"],
                title=f"{src_name} {ecfg['hover']} {dst_name}",
                color=ecfg["color"],
                width=2,
                smooth={"type": "curvedCW", "roundness": 0.15},
            )

    net.set_options("""{
        "layout": {
            "hierarchical": {
                "enabled": true,
                "direction": "UD",
                "sortMethod": "hubsize",
                "levelSeparation": 180,
                "nodeSpacing": 200,
                "treeSpacing": 250
            }
        },
        "physics": {
            "enabled": false
        },
        "interaction": {
            "hover": true,
            "tooltipDelay": 100,
            "dragNodes": true
        }
    }""")

    html = net.generate_html()
    html = html.replace("</body>", _LEGEND_HTML + "</body>")
    return html
