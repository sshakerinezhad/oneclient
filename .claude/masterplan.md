# OneClient — BMO Graph + Agent Demo: Implementation Plan

## Context

BMO's ECIF process produces "golden records" unifying client data across lines of business
(Commercial Banking, Capital Markets, Wealth, Personal & Business Banking). The business wants a
way to *use* that data conversationally. We're building a **demo**: a local graph DB (kuzu) loaded
with realistic mock data, queried by an **agent orchestration** (orchestrator → query agent →
synthesizer) over **AWS Bedrock**, surfaced in a **BMO-branded Streamlit UI** with a small, stylish
**pyvis** subgraph of the relevant nodes.

The real client data is sensitive and only its column structure is shared (`redacted_data_structure/`,
6 header-only CSVs). So we generate mock data — engineered **backwards** from 6 specific demo
questions so each returns a known, impressive answer, surrounded by realistic noise.

**Hard constraint:** everything must transfer to a locked-down work laptop. That machine has Python +
`pip` via a proxy (kuzu, streamlit, pyvis, boto3 all confirmed working) and AWS Bedrock access via an
IAM role with `bedrock:InvokeModel`. We develop here using the user's Bedrock keys (fallback: a
personal AWS account's Bedrock keys), and swap work creds in at transfer via one config edit.

**Goal:** a polished, reproducible, fully-testable demo that answers all 6 questions by *reasoning over
the graph* (not hallucinating), with a clean codebase that transfers by copy + `pip install` + run.

## The 6 demo questions (drive everything)

1. Top 10 **CM** clients with **no other** relationships (given region)
2. Top 20 **CB** clients **without Wealth** relationship (given region)
3. Regions with strongest **CB∩Wealth penetration** (most clients holding both CB and Wealth)
4. **Franchisee / auto-dealer / equipment** CB clients **without Wealth** (US Midwest)
5. Large CB/CM clients who are **bank-at-work** candidates (large employee base; many existing
   P&BB relationships among employees = signal)
6. Best **underpenetrated opportunity** with strong **cross-BMO** relationships to leverage + a rough plan
   (composite reasoning — the orchestrator's showcase)

## Architecture

ECIF golden record sits at the center of a typed graph; every question is a native graph pattern.

### Graph schema (kuzu typed tables)
**Node tables**
- `Company(ecif_id PK, name, country, region, industry, employee_count, revenue, net_income, rwa, roe, lending_balance, deposit_balance)`
  — `industry` + `employee_count` are **added** enrichments (defensible as ECIF-derived).
- `Person(ecif_id PK, name, country, region, customer_type)`
- `Region(name PK, country)` — US: Midwest/Northeast/South/West; CA: Ontario/Quebec/Prairies/BC/Atlantic
- `LineOfBusiness(name PK)` — `CB`, `CM`, `Wealth`, `P&BB`

**Relationship tables**
- `HAS_RELATIONSHIP(FROM Company TO LineOfBusiness, revenue, lending, deposit)` and
  `HAS_RELATIONSHIP(FROM Person TO LineOfBusiness, revenue, ...)` — replaces the sheets' `Wealth_Flg`/`CM_Flg` flags with real edges
- `EXECUTIVE_OF(FROM Person TO Company, title)` — from "Executive" columns
- `EMPLOYED_BY(FROM Person TO Company)` — from Wealth-US "Employer" / P&BB "Related Business Entity"; the bank-at-work signal
- `LOCATED_IN(FROM Company TO Region)` and `LOCATED_IN(FROM Person TO Region)`

Question → pattern mapping:
- Q1: `Company-[:HAS_RELATIONSHIP]->(CM)` AND not `->(other LOB)`, in region, top 10 by revenue
- Q2: `->(CB)` AND not `->(Wealth)`, in region, top 20 by revenue
- Q3: per region: count companies with both CB and Wealth / total CB companies → rate, rank
- Q4: Q2 + `industry IN {franchisee, auto_dealer, equipment}` + region = US Midwest
- Q5: high `employee_count` + COUNT of `EMPLOYED_BY` persons holding a `P&BB` edge
- Q6: composite — agent runs several queries across cross-BMO edges + underpenetration, then synthesizes a plan

### Runtime flow
`Streamlit UI → orchestrator (Bedrock Converse, reasoning loop) → query agent (tool) → kuzu → evidence → synthesizer → answer + pyvis subgraph`

## Data generation — backwards from answers

`generate/` builds data with a **fixed RNG seed** (fully reproducible). Two layers:

1. **Per-question fixtures** (`generate/fixtures.py`): for each of the 6 questions, a small, named cohort
   engineered backwards from the answer we want on stage (specific companies/regions with known counts,
   known ranking). These are the "guaranteed" demo results.
2. **Background population** (`generate/population.py`): ~100 companies / ~500 persons of realistic noise
   (faker + numpy, seeded) so the graph feels real and handles off-script questions without exposing the
   scaffolding. Distribution knobs in `generate/knobs.py`.

Output: canonical staged CSVs in `data/staged/` (`companies.csv`, `persons.csv`, `regions.csv`,
`lob.csv`, `rel_has_relationship_company.csv`, `rel_has_relationship_person.csv`, `rel_executive_of.csv`,
`rel_employed_by.csv`, `rel_located_in_*.csv`).

## Verification gate (test-first, no LLM)

`tests/verify_demo.py`: runs the 6 questions' underlying Cypher directly against the freshly-built DB and
asserts the **exact expected entities/counts** from the fixtures. This is the loop that guarantees the
demo lands — red means fix the fixture/knob and regenerate. Must be green before any agent work proceeds.

## Components & files

```
oneclient/
  redacted_data_structure/        # existing header-only sheets (reference)
  config.example.toml             # region, model id, creds source, paths
  requirements.txt
  README.md                       # transfer + run instructions
  schema/
    schema.cypher                 # kuzu DDL (node + rel tables)
  generate/
    knobs.py                      # distributions + seed
    fixtures.py                   # per-question backwards-designed cohorts
    population.py                 # background noise population
    generate_data.py             # entrypoint -> data/staged/*.csv
  load/
    load_kuzu.py                  # COPY FROM bulk load into local kuzu db
  llm/
    config.py                     # load config.toml / env
    bedrock.py                    # Converse wrapper: tool-use, thinking budget, retry
  graph/
    db.py                         # kuzu connection + read-only query executor (guards mutations)
    schema_doc.py                 # single source of truth: schema text for agent prompts
  agents/
    types.py                      # typed dataclasses: Evidence, QueryResult, OrchestratorState
    query_agent.py               # NL request -> Cypher -> execute -> self-repair (<=3) -> rows+query
    orchestrator.py              # reasoning loop; query agent as tool; min-evidence + self-critique
    synthesizer.py               # evidence -> formatted answer (evidence-only, anti-hallucination)
    prompts/
      orchestrator.md            # biased toward investigation; thread-following few-shots; 6-question patterns
      query_agent.md             # schema + bulletproof-cypher rules + few-shots
      synthesizer.md             # structure + "only use provided evidence"
  viz/
    subgraph.py                  # capped ~8-15 relevant nodes, icons+color per type, tuned physics -> HTML
  app/
    streamlit_app.py             # BMO UI: 6 chips, reasoning trace, answer, embedded subgraph
    assets/                      # BMO css (#0079C1 navy/white/red), logo, node icons
  tests/
    verify_demo.py               # the 6-question gate (no LLM)
    test_query_agent.py          # cypher correctness + self-repair
    test_orchestrator.py         # follows threads / hits min-evidence on the 6 questions
```

## Key design decisions (avoid bandaids/spaghetti)

- **Each agent = a pure function** (messages/state in → typed result out), independently testable. No
  shared mutable globals.
- **`graph/schema_doc.py` is the single source of schema truth** consumed by both DDL-awareness and agent
  prompts — schema never drifts between code and prompt.
- **Read-only query executor** (`graph/db.py`): rejects `CREATE/DELETE/SET/MERGE/DROP/COPY` so an agent
  can never mutate the demo DB.
- **Bedrock Converse API** (not `invoke_model`): native tool-use + unified messages, `thinking` budget on
  reasoning calls, generous `max_tokens`. Config-driven region/model/creds → trivial work-machine swap.
- **Shrewd orchestrator (anti-lazy):** prompt biased to investigate; **minimum-evidence policy** (must run
  ≥N queries and explicitly check negative space / unfollowed threads before synthesis unlocks); a
  self-critique step ("what would make this answer wrong/incomplete?") that tends to trigger another query.
  Configurable `max_iters` ceiling and `min_queries` floor.
- **Synthesizer sees only collected evidence** — cannot invent numbers; instructed to cite counts. This is
  the core anti-hallucination guard.

## Build phases

- **Phase 0 — Scaffold + Bedrock smoke test.** Project skeleton, `requirements.txt`, `config`. Tiny
  Converse call to confirm keys + model access *first* (de-risks the credential question immediately).
- **Phase 1 — Data + load + gate (no LLM).** `schema.cypher`, generator (knobs/fixtures/population),
  `load_kuzu.py`, `verify_demo.py`. Iterate until all 6 canonical queries return the designed answers.
- **Phase 2 — Query agent.** Schema-grounded Cypher writer with execute + self-repair loop; tested against
  the 6 canonical NL asks (TDD: `test_query_agent.py`).
- **Phase 3 — Orchestrator + synthesizer.** Reasoning loop with min-evidence/self-critique; end-to-end on
  all 6 questions (`test_orchestrator.py`). Verify it *follows threads* and doesn't bail early.
- **Phase 4 — pyvis subgraph.** Capped ~8–15 relevant nodes, icons/colors per node type/LOB, tuned physics.
- **Phase 5 — Streamlit BMO UI.** 6 question chips, collapsible reasoning trace, formatted answer, embedded
  subgraph; BMO branding.
- **Phase 6 — Polish + transfer dry-run + README.** Swap-creds instructions, regenerate-on-work-machine steps.

## Verification (end-to-end)

1. `python generate/generate_data.py && python load/load_kuzu.py`
2. `python tests/verify_demo.py` — all 6 designed answers assert green (the gate)
3. `pytest tests/` — query agent + orchestrator behavior (incl. anti-lazy thread-following)
4. `streamlit run app/streamlit_app.py` — click each of the 6 chips; confirm reasoning trace shows multiple
   queries, answer matches the verified entities, subgraph shows a clean handful of relevant nodes
5. Bedrock swap dry-run: change `config.toml` creds/region/model, re-run a question, confirm identical flow

## Open items to confirm during build
- Exact Bedrock model id / region for dev keys (confirm Claude model access enabled in the AWS console)
- Final BMO hex palette + logo asset (use BMO blue `#0079C1` + navy/white/red until assets provided)
- `min_queries` floor and `max_iters` ceiling values (tune in Phase 3)
