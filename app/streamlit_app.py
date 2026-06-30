"""OneClient Intelligence — BMO Wealth Management demo UI.

Single-page Streamlit app: 6 preset questions + free-text, streams the
orchestrator's reasoning live, renders pyvis graph and answer card.
"""
import base64
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# Ensure project root is importable
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agents.pipeline import answer_question  # noqa: E402
from graph.db import connect                  # noqa: E402
from llm.bedrock import BedrockClient         # noqa: E402
from llm.config import load_config            # noqa: E402
from viz.subgraph import build_subgraph       # noqa: E402

# ── Page config (must be first Streamlit call) ──────────────────────────────

st.set_page_config(
    page_title="OneClient Intelligence — BMO Wealth Management",
    page_icon="\U0001F3E6",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Load CSS ────────────────────────────────────────────────────────────────

_CSS_PATH = Path(__file__).parent / "assets" / "bmo.css"
st.markdown(f"<style>{_CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

# ── Constants ───────────────────────────────────────────────────────────────

QUESTIONS = [
    "Top 10 CM clients with no other relationships in US West",
    "Top 20 CB clients without Wealth in US Northeast",
    "Regions with strongest CB and Wealth penetration",
    "Franchisee/auto dealer/equipment CB clients without Wealth in US Midwest",
    "Large CB/CM clients that are bank-at-work candidates",
    "Best underpenetrated opportunity with strong cross-BMO relationships",
]

# ── Cached resources ───────────────────────────────────────────────────────

@st.cache_resource
def get_config():
    return load_config()


@st.cache_resource
def get_connection():
    cfg = get_config()
    return connect(cfg["paths"]["db_path"])


@st.cache_resource
def get_client():
    cfg = get_config()
    return BedrockClient(cfg)


# ── Session state defaults ─────────────────────────────────────────────────

for key, default in {
    "current_question": None,
    "answer": None,
    "graph_html": None,
    "investigating": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ── Header ──────────────────────────────────────────────────────────────────

_LOGO_PATH = Path(__file__).parent / "assets" / "bmo_wm_logo.png"
_logo_b64 = base64.b64encode(_LOGO_PATH.read_bytes()).decode()

st.markdown(
    f"""
    <div class="bmo-header">
        <img src="data:image/png;base64,{_logo_b64}" alt="BMO">
        <h1>OneClient Intelligence</h1>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Graph canvas (hero position) ───────────────────────────────────────────

graph_placeholder = st.empty()

if st.session_state.graph_html:
    graph_placeholder.empty()
    with graph_placeholder.container():
        components.html(st.session_state.graph_html, height=450)
elif st.session_state.investigating:
    graph_placeholder.markdown(
        '<div class="graph-canvas"><div class="graph-loading">'
        "Investigating...</div></div>",
        unsafe_allow_html=True,
    )
else:
    graph_placeholder.markdown(
        '<div class="graph-canvas"><div class="graph-empty">'
        "Select a question to explore client relationships</div></div>",
        unsafe_allow_html=True,
    )

# ── Question chips ──────────────────────────────────────────────────────────

disabled = st.session_state.investigating

# Row 1
cols_1 = st.columns(3, gap="small")
for i, col in enumerate(cols_1):
    with col:
        if st.button(QUESTIONS[i], key=f"q{i}", disabled=disabled, use_container_width=True):
            st.session_state.current_question = QUESTIONS[i]
            st.session_state.answer = None
            st.session_state.graph_html = None
            st.rerun()

# Row 2
cols_2 = st.columns(3, gap="small")
for i, col in enumerate(cols_2):
    idx = i + 3
    with col:
        if st.button(QUESTIONS[idx], key=f"q{idx}", disabled=disabled, use_container_width=True):
            st.session_state.current_question = QUESTIONS[idx]
            st.session_state.answer = None
            st.session_state.graph_html = None
            st.rerun()

# Free-text input
input_col, btn_col = st.columns([5, 1], gap="small")
with input_col:
    custom_q = st.text_input(
        "Ask a question",
        placeholder="Ask a question about client relationships...",
        label_visibility="collapsed",
        disabled=disabled,
    )
with btn_col:
    st.markdown('<div class="ask-button">', unsafe_allow_html=True)
    ask_clicked = st.button("Ask", disabled=disabled, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

if ask_clicked and custom_q.strip():
    st.session_state.current_question = custom_q.strip()
    st.session_state.answer = None
    st.session_state.graph_html = None
    st.rerun()

# ── Investigation run ──────────────────────────────────────────────────────

if st.session_state.current_question and st.session_state.answer is None:
    question = st.session_state.current_question
    st.session_state.investigating = True

    # Show loading state in graph canvas
    graph_placeholder.markdown(
        '<div class="graph-canvas"><div class="graph-loading">'
        "Investigating...</div></div>",
        unsafe_allow_html=True,
    )

    # Investigation trace
    with st.status("Investigation Trace", expanded=True) as trace_status:
        thinking_placeholder = st.empty()
        trace_log = st.container()
        query_count = [0]

        def on_event(kind: str, text: str):
            if kind == "thinking":
                # Accumulate thinking tokens (st.empty overwrites each time)
                if "thinking_buffer" not in st.session_state:
                    st.session_state["thinking_buffer"] = []
                st.session_state["thinking_buffer"].append(text)
                thinking_placeholder.markdown(
                    "*" + "".join(st.session_state["thinking_buffer"]) + "*"
                )
            elif kind == "tool":
                query_count[0] += 1
                trace_log.markdown(f"**{text}**")

        try:
            cfg = get_config()
            conn = get_connection()
            client = get_client()

            st.session_state["thinking_buffer"] = []
            result = answer_question(question, cfg, conn, client, on_event=on_event)
            st.session_state.pop("thinking_buffer", None)

            st.session_state.answer = result["answer"]
            state = result["state"]

            # Extract entity IDs for subgraph
            entity_ids = set()
            for ev in state.evidence:
                for row in ev.result.rows:
                    for val in row.values():
                        if isinstance(val, str) and (
                            val.startswith("FX") or val.startswith("BG")
                        ):
                            entity_ids.add(val)

            # Build graph if we have entities
            if entity_ids:
                try:
                    html = build_subgraph(conn, list(entity_ids), cap=15)
                    st.session_state.graph_html = html
                except Exception:
                    st.session_state.graph_html = None
            else:
                st.session_state.graph_html = None

            trace_status.update(
                label=f"Investigation complete -- {query_count[0]} queries",
                state="complete",
                expanded=False,
            )

        except Exception as exc:
            trace_status.update(label="Investigation failed", state="error")
            st.error(f"Error: {exc}")

    st.session_state.investigating = False
    st.session_state.current_question = None  # consumed
    st.rerun()

# ── Answer card ─────────────────────────────────────────────────────────────

if st.session_state.answer:
    with st.container(border=True):
        st.markdown(st.session_state.answer)
