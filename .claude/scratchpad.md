# OneClient Demo — Session Scratchpad

## What this is
BMO demo: ECIF golden records → local **kuzu** graph DB → **agent orchestration** (orchestrator → query agent → synthesizer) over **AWS Bedrock** → **BMO-branded Streamlit UI** with a small **pyvis** subgraph. Built here, must transfer to locked-down work laptop.

## Status
- **Brainstorming → masterplan → detailed TDD implementation plan DONE.**
  - Architecture spec: `.claude/masterplan.md`
  - Bite-sized TDD task plan (source of truth for building): `C:\Users\User\.claude\plans\hi-so-im-working-glistening-swing.md` — read FIRST next session.
- Plan has 7 phases (0–6), ~20 tasks, each with TDD steps + commits. Used superpowers writing-plans skill.
- **Awaiting plan approval:** ExitPlanMode rejected multiple times; user keeps opening plan in editor to review. Still in plan mode. **Next session: re-present ExitPlanMode (or whatever changes user wants) before any code.**
- No code written yet. Phase 0 not started.

## 4 product decisions LOCKED this session
- **Models:** Opus on EVERY agent call (orchestrator+query+synth). Both model-id keys kept in config for one-line future cost-tune.
- **Reasoning trace:** LIVE-STREAMED to UI via `converse_stream` + `on_event(kind,text)` callback threaded orchestrator→pipeline→streamlit.
- **Viz icons:** embedded shape+color+emoji (🏢 Company, 👤 Person, 📍 Region, 🏷️ LOB), pyvis `cdn_resources='in_line'`, ZERO external assets (locked-network safe). NO font-awesome/CDN.
- **Interaction:** single-shot questions, no chat memory.

## Key decisions locked
- **Env:** work laptop has Python + pip via proxy (kuzu/streamlit/pyvis/boto3 all work). Transfer = copy folder + `pip install` + run.
- **LLM:** AWS Bedrock via boto3 **Converse API** (NOT invoke_model) — native tool-use + thinking budget. Dev with user's Bedrock keys; fallback personal AWS acct; swap work creds at transfer (one config edit). Confirm model id + Claude model access in console.
- **Agents:** Orchestrator + query-agent-as-tool + synthesizer. Each = pure, independently-testable function. NO bandaids/spaghetti — clean module boundaries, typed dataclasses, single source of schema truth (`graph/schema_doc.py`), read-only query guard.
- **Orchestrator must be SHREWD (anti-lazy):** biased to investigate, min-evidence policy (≥N queries + negative-space check before synthesis unlocks), self-critique step. Synthesizer sees only evidence (anti-hallucination).
- **Data:** ~100 companies / ~500 persons. Generate **backwards from the 6 questions** — surgical per-question fixtures (known answers) + background noise population. Fixed RNG seed. `verify_demo.py` asserts exact expected entities BEFORE any LLM (the test gate).
- **Viz:** pyvis capped **~8–15 highly-relevant nodes** only, icons+color per type. Never overwhelming.
- **Geography:** both US + CA, full regions (US Midwest needed for Q4).
- **DB transfer:** regenerate on work machine (seed = identical DB).

## The 6 demo questions (drive everything)
1. Top 10 CM clients w/ no other relationships (given region)
2. Top 20 CB clients w/o Wealth (given region)
3. Regions w/ strongest CB∩Wealth penetration
4. Franchisee/auto-dealer/equipment CB clients w/o Wealth (US Midwest)
5. Large CB/CM clients = bank-at-work candidates (large employee base + many P&BB-holding employees)
6. Best underpenetrated opportunity w/ strong cross-BMO relationships + rough plan (composite reasoning showcase)

## Schema (kuzu typed)
Nodes: `Company` (incl. added `industry`,`employee_count`), `Person`, `Region`, `LineOfBusiness`(CB/CM/Wealth/P&BB).
Edges: `HAS_RELATIONSHIP`(→LOB), `EXECUTIVE_OF`(Person→Company), `EMPLOYED_BY`(Person→Company; bank-at-work signal), `LOCATED_IN`(→Region).

## Source data
`redacted_data_structure/` = 6 header-only CSVs (CB CA ×2, P&BB CA, P&BB US, Wealth CA, Wealth US). Real data sensitive — structure only.

## Build phases (from plan)
0 Scaffold + **Bedrock smoke test** (de-risk keys first) → 1 Data+load+verify gate (no LLM) → 2 Query agent (cypher + self-repair) → 3 Orchestrator+synthesizer (anti-lazy) → 4 pyvis → 5 Streamlit BMO UI → 6 polish + transfer dry-run + README.

## Build phase order (from plan)
0 Scaffold + requirements + config + **Bedrock smoke test** (de-risk creds FIRST) →
1 schema_doc (single source) + DDL + read-only db guard + knobs + fixtures + population + generate CSVs + kuzu loader + **verify_demo gate (6 questions in raw Cypher, no LLM)** →
2 types + bedrock wrapper (buffered+streaming) + query agent (self-repair) →
3 anti-lazy streaming orchestrator (min_queries=2,max_iters=8) + evidence-only synthesizer + pipeline →
4 capped offline pyvis subgraph (≤15 nodes) →
5 BMO streaming Streamlit UI (6 chips) →
6 README + transfer dry-run.
CHECKPOINT 1 after Phase 1 (gate green). CHECKPOINT 2 after Phase 3 (all 6 answered E2E, no hallucination, ≥2 queries each).

## Next steps
1. Re-present ExitPlanMode for approval (user was reviewing plan in editor).
2. On approval, pick execution mode (subagent-driven recommended) and start Phase 0 Task 0.1.
3. EARLY de-risk: Task 0.2 Bedrock smoke test — confirm user's Bedrock keys work off work network (else personal AWS acct, swap at transfer).
