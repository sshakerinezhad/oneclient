"""OneClient Intelligence — BMO Wealth Management demo UI.

Chat-style interface: suggestion chips + free-text input, streams the
orchestrator's reasoning live inside chat messages, renders pyvis graph
and answer inline.
"""
import base64
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agents.pipeline import answer_question  # noqa: E402
from graph.db import connect                  # noqa: E402
from llm.bedrock import BedrockClient         # noqa: E402
from llm.config import load_config            # noqa: E402
from pdf.report import build_report           # noqa: E402
from viz.subgraph import build_subgraph       # noqa: E402

# ── Page config ────────────────────────────────────────────────────────

st.set_page_config(
    page_title="OneClient Intelligence",
    page_icon="\U0001F3E6",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Load CSS ───────────────────────────────────────────────────────────

_CSS_PATH = Path(__file__).parent / "assets" / "bmo.css"
st.markdown(
    f"<style>{_CSS_PATH.read_text(encoding='utf-8')}</style>",
    unsafe_allow_html=True,
)

# ── Constants ──────────────────────────────────────────────────────────

QUESTIONS = [
    "Top 10 CM clients with no other relationships in US West",
    "Top 20 CB clients without Wealth in US Northeast",
    "Regions with strongest CB and Wealth penetration",
    "Franchisee/auto dealer/equipment CB clients without Wealth in US Midwest",
    "Large CB/CM clients that are bank-at-work candidates",
    "Best underpenetrated opportunity with strong cross-BMO relationships",
]

# ── Cached resources ──────────────────────────────────────────────────

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


# ── Session state ─────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []
if "processing" not in st.session_state:
    st.session_state.processing = False

# ── Header ─────────────────────────────────────────────────────────────

_LOGO_PATH = Path(__file__).parent / "assets" / "bmo_wm_logo.png"
_logo_b64 = base64.b64encode(_LOGO_PATH.read_bytes()).decode()

st.markdown(
    f"""
    <div class="bmo-header">
        <img src="data:image/png;base64,{_logo_b64}" alt="BMO">
        <span class="bmo-header-title">OneClient Intelligence</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Helpers ────────────────────────────────────────────────────────────


def _extract_entity_ids(state):
    ids = set()
    for ev in state.evidence:
        for row in ev.result.rows:
            for val in row.values():
                if isinstance(val, str) and (
                    val.startswith("FX") or val.startswith("BG")
                ):
                    ids.add(val)
    return ids


def _render_suggestions(key_prefix):
    """Render the 6 suggestion chips in a 2x3 grid."""
    disabled = st.session_state.processing
    row1 = st.columns(3, gap="small")
    for i, col in enumerate(row1):
        with col:
            if st.button(
                QUESTIONS[i],
                key=f"{key_prefix}_q{i}",
                disabled=disabled,
                use_container_width=True,
            ):
                st.session_state.messages.append(
                    {"role": "user", "content": QUESTIONS[i]}
                )
                st.session_state.processing = True
                st.rerun()

    row2 = st.columns(3, gap="small")
    for i, col in enumerate(row2):
        idx = i + 3
        with col:
            if st.button(
                QUESTIONS[idx],
                key=f"{key_prefix}_q{idx}",
                disabled=disabled,
                use_container_width=True,
            ):
                st.session_state.messages.append(
                    {"role": "user", "content": QUESTIONS[idx]}
                )
                st.session_state.processing = True
                st.rerun()


def _run_pipeline():
    """Execute the investigation pipeline, streaming results into a chat bubble."""
    question = st.session_state.messages[-1]["content"]

    with st.chat_message("assistant"):
        with st.status("Investigating…", expanded=True) as trace:
            thinking_ph = st.empty()
            trace_log = st.container()
            query_count = [0]
            thinking_buf = []

            def on_event(kind, text):
                if kind == "thinking":
                    thinking_buf.append(text)
                    thinking_ph.markdown(
                        "*" + "".join(thinking_buf) + "*"
                    )
                elif kind == "tool":
                    query_count[0] += 1
                    trace_log.markdown(f"**{text}**")

            try:
                cfg = get_config()
                conn = get_connection()
                client = get_client()

                result = answer_question(
                    question, cfg, conn, client, on_event=on_event
                )
                answer = result["answer"]
                state = result["state"]

                entity_ids = _extract_entity_ids(state)
                graph_html = None
                if entity_ids:
                    try:
                        graph_html = build_subgraph(
                            conn, list(entity_ids), cap=15
                        )
                    except Exception:
                        pass

                pdf_bytes = build_report(question, answer)

                trace.update(
                    label=f"Investigation complete — {query_count[0]} queries",
                    state="complete",
                    expanded=False,
                )

                st.markdown(answer.replace("$", "\\$"))

                if graph_html:
                    components.html(graph_html, height=420)

                st.download_button(
                    "Export PDF",
                    data=pdf_bytes,
                    file_name="oneclient_report.pdf",
                    mime="application/pdf",
                    key="pdf_live",
                )

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "graph_html": graph_html,
                    "pdf_bytes": pdf_bytes,
                    "question": question,
                })

            except Exception as exc:
                trace.update(label="Investigation failed", state="error")
                st.error(f"Investigation failed: {exc}")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": str(exc),
                    "is_error": True,
                })

    st.session_state.processing = False
    st.rerun()


# ── Render chat history ───────────────────────────────────────────────

for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        elif msg.get("is_error"):
            st.error(msg["content"])
        else:
            st.markdown(msg["content"].replace("$", "\\$"))
            if msg.get("graph_html"):
                components.html(msg["graph_html"], height=420)
            if msg.get("pdf_bytes"):
                st.download_button(
                    "Export PDF",
                    data=msg["pdf_bytes"],
                    file_name="oneclient_report.pdf",
                    mime="application/pdf",
                    key=f"pdf_{idx}",
                )

# ── Welcome state or post-response suggestions ───────────────────────

if not st.session_state.messages:
    st.markdown(
        """
        <div class="welcome-container">
            <div class="welcome-icon">\U0001F3E6</div>
            <h2>OneClient Intelligence</h2>
            <p>Ask questions about client relationships across BMO business lines</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _render_suggestions("welcome")
elif not st.session_state.processing:
    _render_suggestions("suggest")

# ── Chat input ────────────────────────────────────────────────────────

if prompt := st.chat_input(
    "Ask about client relationships…",
    disabled=st.session_state.processing,
):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.processing = True
    st.rerun()

# ── Process pending question ──────────────────────────────────────────

if st.session_state.processing:
    _run_pipeline()
