# Session Handoff — Demo Visualization & Formatting Fixes

## Status: COMPLETE & MERGED
- Work commit `586b82d` → **PR #2 merged into `master`** (merge commit `60d7c18`).
- Branch worked on: `claude/demo-visualization-issues-dk6rlj` (now deleted locally).

## Original request
Three demo defects reported:
1. Demo 2 not showing connections between nodes and the Line of Business node.
2. Answer text formatting "wonky" — too big, scrunched, green-and-black.
3. Demo 3 returns no visualizer graph.
User asked for systematic root-causing, "no bandaids."

## Root causes (verified by reading code, not guessing)
1. **Demo 2 — LOB hub evicted by node cap.** `viz/subgraph.py::_select_nodes`
   capped graph at 15 nodes with answer-companies at top priority. Demo 2 returns
   ~25 companies → they consumed every slot → shared `CB` LineOfBusiness hub dropped.
   Edges only render when BOTH endpoints survive (subgraph.py line ~178), so all
   company→CB edges silently disappeared.
2. **Demo 3 — no entities to graph.** Q3 Cypher (`agents/demo_scripts.py`) aggregates
   by region and discards `ecif_id`. App extracts graph entities by scanning rows for
   strings starting with `FX`/`BG` (`app/streamlit_app.py` ~line 206-213) → none found
   → `graph_html = None`.
3. **Formatting.** (a) `$117.4M…$109.8M` in answers parsed as LaTeX/KaTeX math by
   `st.markdown` → oversized serif/scrunched. (b) No `.streamlit/config.toml` → app
   inherited browser DARK theme → green/black code rendering. (c) Answer-card CSS
   (`app/assets/bmo.css`) only sized `h2`; synthesizer emits `###` (h3) → default sizes.

## Fixes applied
- `viz/subgraph.py` — rewrote `_select_nodes`: split hubs (LineOfBusiness/Region) vs
  spokes (Company/Person); cap the SPOKES (answer entities first), always keep hubs
  that connect to a kept spoke, within `cap`. Added module const `_HUB_TYPES`.
- `agents/demo_scripts.py` — added 2 exemplar steps to Q3 ("Regions with strongest CB
  and Wealth penetration"): top-3 Quebec CB+Wealth and top-3 US Northeast CB-only.
  Returns real ecif_ids (FX3-00x / FX2-00x) so the graph renders a "mixed" best-vs-worst
  story. (User chose "Both / mixed" for Demo 3 graph.)
- `app/streamlit_app.py` — escape `$`→`\$` only at the `st.markdown(answer)` render site
  (line ~244). PDF still uses raw text.
- `.streamlit/config.toml` (NEW) — pin light theme + BMO palette.
- `.gitignore` — changed `.streamlit/` → `.streamlit/*` + `!.streamlit/config.toml` so
  the config is tracked but secrets.toml etc. stay ignored.
- `app/assets/bmo.css` — added h1/h3 font-size in answer card; styled code/pre inside
  the card (light bg, brand text, 14px).
- `agents/prompts/synthesizer.md` — added rule: no code fences / inline code / tables.

## Verification done
- Rebuilt DB: `python -m generate.generate_data` then
  `python -c "from load.load_kuzu import build_db; import shutil; shutil.rmtree('data/oneclient.kuzu', True); build_db('data/oneclient.kuzu','data/staged','schema/schema.cypher')"`
  (NOTE: `python -m load.load_kuzu` alone did NOT build the DB — use build_db directly.)
- Offline graph checks vs real DB: Demo 2 keeps `CB` hub + 12 rendered LOB edges;
  Demo 3 yields FX3+FX2 ids, graph shows both CB & Wealth hubs across Quebec/US Northeast.
- `python -m pytest tests/verify_demo.py` → 6/6 pass (demo gate).
- Full suite: **91/92 pass**.

## Open items / gotchas for next agent
- ⚠️ **Pre-existing failing test:** `tests/test_subgraph.py::test_subgraph_node_types_colored`
  asserts colored LOB nodes (`#7B2D8E`). Fails on `master` independent of this work —
  the viz was deliberately redesigned to emoji TEXT nodes with colored EDGES (commit
  4e6cb75), so nodes have no fill color. Left untouched. DECISION NEEDED: update the
  stale test, or restore colored nodes.
- ⚠️ **Remote branch `claude/demo-visualization-issues-dk6rlj` NOT deleted.** Push-delete
  returns HTTP 403 (org egress policy) from this environment, and no GitHub branch-delete
  tool is available here. User to delete via GitHub UI (PR #2 → "Delete branch"). Do NOT
  retry push-delete — proxy README says don't retry 403/407 policy denials.
- ℹ️ **`.streamlit/config.toml` is in a hidden dir.** It IS in the repo (confirmed in
  origin/master); OS file browsers (macOS Finder / Windows Explorer) hide dot-folders by
  default. When copying to another machine, enable "show hidden files."
- ℹ️ **Local repo is on stale pre-merge `master`.** Run `git pull origin master` to sync;
  the merge happened server-side via the PR.
- ℹ️ **No DB rebuild needed** for these changes in normal use (they query existing
  fixtures). Restart Streamlit to pick up the theme config (not hot-reloaded).

## Key files & how things flow
- Demo path: `agents/pipeline.py::answer_question` → if question in `DEMO_SCRIPTS`
  (`agents/demo_scripts.py`) → `run_demo_script` (deterministic Cypher) →
  `agents/synthesizer.py::synthesize` (LLM, nudged) → answer.
- Graph: `app/streamlit_app.py` extracts FX/BG ids from evidence →
  `viz/subgraph.py::build_subgraph` (pyvis, emoji text nodes, colored edges, physics
  freeze after stabilization) → `components.html`.
- Fixtures: `generate/fixtures.py` — FX2-001..020 = US Northeast CB-only;
  FX3-001..005 = Quebec CB+Wealth.

## Project conventions (from CLAUDE.md)
- Bedrock uses invoke_model (NOT Converse). Anthropic Messages API format.
- kuzu v0.7.1: split rel tables — COMPANY_HAS_RELATIONSHIP / PERSON_HAS_RELATIONSHIP,
  COMPANY_LOCATED_IN / PERSON_LOCATED_IN. No multi-FROM; all Cypher uses split names.
- AWS creds: temporary ASIA... keys in config.toml, expire hourly.
- Tests: `python -m pytest tests/ -v --tb=short`. Demo gate: `tests/verify_demo.py`.
- NEVER add AI attribution / Co-Authored-By to git artifacts.
