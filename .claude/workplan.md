# OneClient Demo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local, reproducible BMO demo that answers 6 specific business questions by reasoning over a kuzu graph of ECIF client data, via a Bedrock orchestrator→query-agent→synthesizer loop, surfaced in a BMO-branded Streamlit UI with a capped pyvis subgraph.

**Architecture:** Mock data is engineered *backwards* from the 6 questions (per-question fixtures + noise) → staged CSVs → bulk-loaded into a typed kuzu graph. A test gate (`verify_demo.py`) asserts the designed answers with raw Cypher before any LLM. Then a Bedrock **Converse** orchestrator reasons in a loop, calling a query agent (own schema/cypher prompt, self-repairing) as a tool, gated by a minimum-evidence policy, then a synthesizer formats an evidence-only answer. UI shows reasoning trace + answer + relevant subgraph.

**Tech Stack:** Python 3.11+, kuzu, boto3 (bedrock-runtime Converse), streamlit, pyvis, faker, numpy, pytest.

**Locked product decisions:** Opus on every agent call · orchestrator reasoning + each Cypher **live-streamed** to the UI (`converse_stream`) · pyvis nodes rendered with **embedded shape + color + emoji** (zero CDN/external assets — safe on the locked network) · **single-shot** questions (each chip/typed question answered independently, no chat memory).

## Global Constraints

- **Must transfer to a locked-down work laptop:** copy folder + `pip install -r requirements.txt` (proxy) + run. No Docker, no system services.
- **Determinism:** every generator uses a single fixed seed `SEED = 42` from `generate/knobs.py`. Same seed → byte-identical CSVs → identical DB.
- **All Bedrock config is external** (`config.toml` / env): `region`, `orchestrator_model_id`, `query_model_id`, credentials source. Swapping work↔personal creds = one config edit, zero code change.
- **Bedrock via Converse API only** (`client.converse(...)`), never `invoke_model`. Reasoning calls set a `thinking` budget; `maxTokens` generous (>=4096).
- **Read-only at query time:** the query executor rejects any Cypher containing a mutating keyword. Agents can never alter the DB.
- **No bandaids/spaghetti:** one responsibility per file; agents are pure functions (state in → typed result out); `graph/schema_doc.py` is the single source of schema truth used by both DDL and every agent prompt.
- **Schema vocab (fixed strings):** LOBs = `CB`, `CM`, `Wealth`, `P&BB`. Industries of interest = `franchisee`, `auto_dealer`, `equipment`. US regions = `US Midwest`, `US Northeast`, `US South`, `US West`. CA regions = `Ontario`, `Quebec`, `Prairies`, `BC`, `Atlantic`.

---

## Phase 0 — Scaffold + Bedrock smoke test

### Task 0.1: Project scaffold, requirements, config

**Files:**
- Create: `requirements.txt`, `config.example.toml`, `.gitignore`, `oneclient/__init__.py` and package `__init__.py` files for `generate/ load/ llm/ graph/ agents/ agents/prompts/ viz/ app/ tests/`
- Create: `data/staged/.gitkeep`

**Interfaces:**
- Produces: directory layout; `config.example.toml` keys consumed by Task 2.2's `llm/config.py`.

- [ ] **Step 1: Write `requirements.txt`**

```
kuzu==0.7.1
boto3>=1.34
streamlit>=1.36
pyvis>=0.3.2
faker>=25
numpy>=1.26
pytest>=8
```

- [ ] **Step 2: Write `config.example.toml`**

```toml
[bedrock]
region = "us-east-1"
# Inference-profile / model ids (confirm Claude model access enabled in AWS console).
# Opus everywhere per decision; both keys kept separate so a future cost-tune is a one-line change.
orchestrator_model_id = "us.anthropic.claude-opus-4-1-20250805-v1:0"
query_model_id = "us.anthropic.claude-opus-4-1-20250805-v1:0"
# credentials: leave blank to use default boto3 chain (env / shared profile / role)
aws_profile = ""

[agent]
max_iters = 8        # orchestrator hard ceiling
min_queries = 2      # orchestrator floor before synthesis unlocks
thinking_budget = 2048

[paths]
db_path = "data/oneclient.kuzu"
staged_dir = "data/staged"
```

- [ ] **Step 3: Write `.gitignore`**

```
__pycache__/
*.pyc
config.toml
data/oneclient.kuzu/
data/staged/*.csv
.streamlit/
```

- [ ] **Step 4: Create empty `__init__.py` in each package dir and `data/staged/.gitkeep`.**

- [ ] **Step 5: Commit**

```bash
git init && git add -A && git commit -m "chore: project scaffold, requirements, example config"
```

### Task 0.2: Bedrock Converse smoke test (de-risk credentials first)

**Files:**
- Create: `llm/config.py`, `tests/smoke_bedrock.py`

**Interfaces:**
- Produces: `load_config(path="config.toml") -> dict` (used by all later LLM tasks).

- [ ] **Step 1: Write `llm/config.py`**

```python
import tomllib, os
from pathlib import Path

def load_config(path: str = "config.toml") -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"{path} missing — copy config.example.toml to config.toml")
    with p.open("rb") as f:
        return tomllib.load(f)
```

- [ ] **Step 2: Write `tests/smoke_bedrock.py` (manual script, not auto pytest — needs live creds)**

```python
"""Run manually: python tests/smoke_bedrock.py
Confirms Bedrock creds + model access via a tiny Converse call."""
import boto3
from llm.config import load_config

def main():
    cfg = load_config()
    sess = boto3.Session(profile_name=cfg["bedrock"]["aws_profile"] or None)
    client = sess.client("bedrock-runtime", region_name=cfg["bedrock"]["region"])
    resp = client.converse(
        modelId=cfg["bedrock"]["query_model_id"],
        messages=[{"role": "user", "content": [{"text": "Reply with the single word: OK"}]}],
        inferenceConfig={"maxTokens": 16, "temperature": 0},
    )
    text = resp["output"]["message"]["content"][0]["text"]
    print("MODEL REPLIED:", text)
    assert "OK" in text.upper()

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run it (requires `config.toml` with real creds)**

Run: `python tests/smoke_bedrock.py`
Expected: prints `MODEL REPLIED: OK`. If `AccessDenied` → model access not enabled / wrong region; if `Unauthorized` → creds. **Resolve before proceeding — this is the credential gate.**

- [ ] **Step 4: Commit**

```bash
git add llm/config.py tests/smoke_bedrock.py && git commit -m "feat: bedrock converse smoke test + config loader"
```

---

## Phase 1 — Data + load + verification gate (NO LLM)

### Task 1.1: Schema single-source-of-truth

**Files:**
- Create: `graph/schema_doc.py`, `tests/test_schema_doc.py`

**Interfaces:**
- Produces: `SCHEMA_TEXT: str` (human/agent-readable schema), `NODE_TABLES: dict`, `REL_TABLES: dict`, `LOBS`, `US_REGIONS`, `CA_REGIONS`, `INDUSTRIES_OF_INTEREST`.

- [ ] **Step 1: Write the failing test `tests/test_schema_doc.py`**

```python
from graph import schema_doc as s

def test_vocab_present():
    assert s.LOBS == ["CB", "CM", "Wealth", "P&BB"]
    assert "US Midwest" in s.US_REGIONS
    assert set(s.INDUSTRIES_OF_INTEREST) == {"franchisee", "auto_dealer", "equipment"}

def test_schema_text_mentions_core_tables():
    for tbl in ["Company", "Person", "Region", "LineOfBusiness",
                "HAS_RELATIONSHIP", "EXECUTIVE_OF", "EMPLOYED_BY", "LOCATED_IN"]:
        assert tbl in s.SCHEMA_TEXT
```

- [ ] **Step 2: Run → FAIL** (`pytest tests/test_schema_doc.py -v`, ModuleNotFound).

- [ ] **Step 3: Write `graph/schema_doc.py`**

```python
LOBS = ["CB", "CM", "Wealth", "P&BB"]
US_REGIONS = ["US Midwest", "US Northeast", "US South", "US West"]
CA_REGIONS = ["Ontario", "Quebec", "Prairies", "BC", "Atlantic"]
ALL_REGIONS = US_REGIONS + CA_REGIONS
INDUSTRIES_OF_INTEREST = ["franchisee", "auto_dealer", "equipment"]
OTHER_INDUSTRIES = ["manufacturing", "retail", "healthcare", "tech", "logistics", "real_estate"]

SCHEMA_TEXT = """
GRAPH SCHEMA (kuzu)

NODES
  Company(ecif_id STRING PK, name STRING, country STRING, region STRING,
          industry STRING, employee_count INT64, revenue DOUBLE, net_income DOUBLE,
          rwa DOUBLE, roe DOUBLE, lending_balance DOUBLE, deposit_balance DOUBLE)
  Person(ecif_id STRING PK, name STRING, country STRING, region STRING, customer_type STRING)
  Region(name STRING PK, country STRING)
  LineOfBusiness(name STRING PK)        // one of: CB, CM, Wealth, P&BB

RELATIONSHIPS
  HAS_RELATIONSHIP (Company->LineOfBusiness) and (Person->LineOfBusiness)
        {revenue DOUBLE, lending DOUBLE, deposit DOUBLE}
  EXECUTIVE_OF (Person->Company) {title STRING}
  EMPLOYED_BY  (Person->Company)            // bank-at-work signal
  LOCATED_IN   (Company->Region) and (Person->Region)

NOTES
  - A client "has a CB/CM/Wealth/P&BB relationship" == an outgoing HAS_RELATIONSHIP edge to that LineOfBusiness.
  - Company.industry interesting values: franchisee, auto_dealer, equipment.
  - Regions: US Midwest/Northeast/South/West; Ontario, Quebec, Prairies, BC, Atlantic.
"""
```

- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `git add graph/schema_doc.py tests/test_schema_doc.py && git commit -m "feat: schema single source of truth"`

### Task 1.2: kuzu DDL + connection + read-only guard

**Files:**
- Create: `schema/schema.cypher`, `graph/db.py`, `tests/test_db_guard.py`

**Interfaces:**
- Produces: `connect(db_path) -> kuzu.Connection`; `run_read(conn, cypher, params=None) -> list[dict]` (raises `ValueError` on mutating Cypher); `MUTATING = {"CREATE","DELETE","SET","MERGE","DROP","COPY","ALTER"}`.

- [ ] **Step 1: Write `schema/schema.cypher`** (one statement per line; loader splits on `;`)

```sql
CREATE NODE TABLE Company(ecif_id STRING, name STRING, country STRING, region STRING, industry STRING, employee_count INT64, revenue DOUBLE, net_income DOUBLE, rwa DOUBLE, roe DOUBLE, lending_balance DOUBLE, deposit_balance DOUBLE, PRIMARY KEY(ecif_id));
CREATE NODE TABLE Person(ecif_id STRING, name STRING, country STRING, region STRING, customer_type STRING, PRIMARY KEY(ecif_id));
CREATE NODE TABLE Region(name STRING, country STRING, PRIMARY KEY(name));
CREATE NODE TABLE LineOfBusiness(name STRING, PRIMARY KEY(name));
CREATE REL TABLE HAS_RELATIONSHIP(FROM Company TO LineOfBusiness, FROM Person TO LineOfBusiness, revenue DOUBLE, lending DOUBLE, deposit DOUBLE);
CREATE REL TABLE EXECUTIVE_OF(FROM Person TO Company, title STRING);
CREATE REL TABLE EMPLOYED_BY(FROM Person TO Company);
CREATE REL TABLE LOCATED_IN(FROM Company TO Region, FROM Person TO Region);
```

- [ ] **Step 2: Write failing test `tests/test_db_guard.py`**

```python
import pytest
from graph.db import run_read, connect

def test_mutating_cypher_rejected(tmp_path):
    conn = connect(str(tmp_path / "t.kuzu"))
    with pytest.raises(ValueError):
        run_read(conn, "CREATE NODE TABLE X(id STRING, PRIMARY KEY(id))")
    with pytest.raises(ValueError):
        run_read(conn, "MATCH (c:Company) DELETE c")
```

- [ ] **Step 3: Run → FAIL** (ModuleNotFound).

- [ ] **Step 4: Write `graph/db.py`**

```python
import re
import kuzu

MUTATING = {"CREATE", "DELETE", "SET", "MERGE", "DROP", "COPY", "ALTER", "DETACH"}

def connect(db_path: str) -> kuzu.Connection:
    return kuzu.Connection(kuzu.Database(db_path))

def _is_mutating(cypher: str) -> bool:
    tokens = set(re.findall(r"[A-Za-z]+", cypher.upper()))
    return bool(tokens & MUTATING)

def run_read(conn: kuzu.Connection, cypher: str, params: dict | None = None) -> list[dict]:
    if _is_mutating(cypher):
        raise ValueError(f"Refusing mutating Cypher: {cypher[:80]}")
    res = conn.execute(cypher, parameters=params or {})
    cols = res.get_column_names()
    return [dict(zip(cols, row)) for row in res] if res.has_next.__self__ else \
           [dict(zip(cols, res.get_next())) for _ in range(res.get_num_tuples())]
```
> Note Step 4 uses kuzu's QueryResult API; the test in Step 5 verifies the row-dict shape on a real query, so adjust the iteration to whatever the installed kuzu version exposes (`while res.has_next(): res.get_next()`).

- [ ] **Step 5: Replace the fragile iteration with the canonical form and add a positive test**

```python
def run_read(conn, cypher, params=None):
    if _is_mutating(cypher):
        raise ValueError(f"Refusing mutating Cypher: {cypher[:80]}")
    res = conn.execute(cypher, parameters=params or {})
    cols = res.get_column_names()
    out = []
    while res.has_next():
        out.append(dict(zip(cols, res.get_next())))
    return out
```
Add to test file:
```python
def test_read_returns_dicts(tmp_path):
    import kuzu
    db = kuzu.Database(str(tmp_path / "r.kuzu")); c = kuzu.Connection(db)
    c.execute("CREATE NODE TABLE N(id STRING, PRIMARY KEY(id))")
    c.execute("CREATE (:N {id: 'a'})")
    rows = run_read(c, "MATCH (n:N) RETURN n.id AS id")
    assert rows == [{"id": "a"}]
```

- [ ] **Step 6: Run → PASS.** `pytest tests/test_db_guard.py -v`
- [ ] **Step 7: Commit** `git commit -am "feat: kuzu DDL + read-only query executor"`

### Task 1.3: Generation knobs + shared constants

**Files:**
- Create: `generate/knobs.py`

**Interfaces:**
- Produces: `SEED`, `N_COMPANIES`, `N_PERSONS`, `PENETRATION` (per-region CB→Wealth rate dict driving Q3), helper `rng()`.

- [ ] **Step 1: Write `generate/knobs.py`**

```python
import numpy as np
SEED = 42
N_COMPANIES = 100      # background companies (fixtures add a handful more)
N_PERSONS = 500

# Per-region P(company with CB also has Wealth). Quebec deliberately highest -> Q3 winner.
PENETRATION = {
    "Quebec": 0.70, "Ontario": 0.45, "US Northeast": 0.40, "US West": 0.35,
    "US South": 0.30, "Prairies": 0.28, "BC": 0.25, "Atlantic": 0.20, "US Midwest": 0.18,
}

def rng() -> np.random.Generator:
    return np.random.default_rng(SEED)
```

- [ ] **Step 2: Commit** `git add generate/knobs.py && git commit -m "feat: generation knobs"`

### Task 1.4: Per-question fixtures (backwards-designed cohorts)

**Files:**
- Create: `generate/fixtures.py`, `tests/test_fixtures.py`

**Interfaces:**
- Produces: `build_fixtures() -> Fixtures` dataclass with `.companies, .persons, .rel_company_lob, .rel_person_lob, .executive_of, .employed_by` (lists of dataclass rows), plus `EXPECTED` dict mapping question id → expected answer entities/counts (consumed by `verify_demo.py`).
- Consumes: vocab from `graph.schema_doc`.

- [ ] **Step 1: Write failing test `tests/test_fixtures.py`**

```python
from generate.fixtures import build_fixtures, EXPECTED

def test_q1_cm_only_cohort_exists():
    fx = build_fixtures()
    # EXPECTED[1] = {"region": "US West", "names": [10 company names]}
    assert len(EXPECTED[1]["names"]) == 10
    cm_only = {c.name for c in fx.companies if c.name in EXPECTED[1]["names"]}
    assert cm_only == set(EXPECTED[1]["names"])

def test_q3_winner_is_quebec():
    assert EXPECTED[3]["winner"] == "Quebec"

def test_q4_midwest_industry_cohort():
    fx = build_fixtures()
    assert all(n for n in EXPECTED[4]["names"])
    assert EXPECTED[4]["region"] == "US Midwest"
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Write `generate/fixtures.py`** — dataclasses + one builder function per question. Each builder creates named companies/persons and the exact edges so the question's Cypher returns the designed set. Records the expected answer in `EXPECTED`.

```python
from dataclasses import dataclass, field

@dataclass
class Company:
    ecif_id: str; name: str; country: str; region: str; industry: str
    employee_count: int; revenue: float; net_income: float = 0.0; rwa: float = 0.0
    roe: float = 0.0; lending_balance: float = 0.0; deposit_balance: float = 0.0
@dataclass
class Person:
    ecif_id: str; name: str; country: str; region: str; customer_type: str
@dataclass
class RelLob:
    src: str; lob: str; revenue: float = 0.0; lending: float = 0.0; deposit: float = 0.0
@dataclass
class Edge:
    src: str; dst: str; title: str = ""
@dataclass
class Fixtures:
    companies: list = field(default_factory=list)
    persons: list = field(default_factory=list)
    rel_company_lob: list = field(default_factory=list)
    rel_person_lob: list = field(default_factory=list)
    executive_of: list = field(default_factory=list)
    employed_by: list = field(default_factory=list)

EXPECTED: dict = {}

def build_fixtures() -> Fixtures:
    fx = Fixtures()
    _q1_cm_only(fx)       # 10 CM-only companies in US West
    _q2_cb_no_wealth(fx)  # 20 CB-no-Wealth companies in US Northeast
    _q3_penetration(fx)   # Quebec dominant CB∩Wealth (also driven by knobs.PENETRATION)
    _q4_midwest(fx)       # franchisee/auto_dealer/equipment CB-no-Wealth in US Midwest
    _q5_bank_at_work(fx)  # large-employee CB/CM cos + many P&BB employees
    _q6_underpenetrated(fx)  # one standout cross-BMO-rich, missing one LOB
    return fx
# ... each _qN_* helper appends rows and sets EXPECTED[N]; full bodies written during impl.
```
> The helper bodies are the deliverable of this task — each must append concrete rows and set `EXPECTED[N]`. Implement them so the asserts in `verify_demo.py` (Task 1.8) pass. Keep ids namespaced `FX1-001` etc.

- [ ] **Step 4: Implement all six `_qN_*` helpers so Step-1 tests pass; run → PASS.**
- [ ] **Step 5: Commit** `git commit -am "feat: backwards-designed per-question fixtures"`

### Task 1.5: Background noise population

**Files:**
- Create: `generate/population.py`, `tests/test_population.py`

**Interfaces:**
- Produces: `build_population(fx) -> None` (mutates the same `Fixtures` container, appending noise rows). Consumes `knobs.PENETRATION`, `knobs.rng`, vocab.

- [ ] **Step 1: Failing test** — assert `build_population` adds ~`N_COMPANIES` companies, every company has ≥1 LOB edge, person count ≈ `N_PERSONS`, and regional CB∩Wealth rates roughly track `PENETRATION` (±0.1).
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** seeded faker/numpy generation; assign each company a region, industry, employee_count, financials; attach LOB edges using `PENETRATION[region]` for Wealth-given-CB; create persons with P&BB/Wealth edges and `EMPLOYED_BY`/`EXECUTIVE_OF` links into companies.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `git commit -am "feat: seeded background population"`

### Task 1.6: Generator entrypoint → staged CSVs

**Files:**
- Create: `generate/generate_data.py`, `tests/test_generate_csv.py`

**Interfaces:**
- Produces 9 CSVs in `data/staged/`: `companies.csv, persons.csv, regions.csv, lob.csv, rel_company_lob.csv, rel_person_lob.csv, rel_executive_of.csv, rel_employed_by.csv, rel_located_in.csv`. Each rel CSV: first two columns are the FROM/TO primary keys, then properties. `rel_located_in.csv` has a `src_kind` column (`Company`|`Person`) so the loader knows which pair to COPY.

- [ ] **Step 1: Failing test** — run `generate_data.main()`, assert all 9 files exist, headers correct, company rows = fixtures+population count, no null primary keys, every company ecif_id unique.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** `main()`: `fx = build_fixtures(); build_population(fx)`; derive `regions.csv` from vocab, `lob.csv` from `LOBS`; write CSVs with `csv.writer`. Split `LOCATED_IN` into company-rows and person-rows but emit one file with `src_kind`.
- [ ] **Step 4: Run → PASS;** eyeball `data/staged/companies.csv`.
- [ ] **Step 5: Commit** `git commit -am "feat: generate staged CSVs"`

### Task 1.7: kuzu loader (bulk COPY)

**Files:**
- Create: `load/load_kuzu.py`, `tests/test_load_kuzu.py`

**Interfaces:**
- Produces: `build_db(db_path, staged_dir, schema_path) -> None`. Drops/recreates the db dir, executes DDL, then `COPY` each node table, then `COPY` each rel pair. For multi-pair rel tables (`HAS_RELATIONSHIP`, `LOCATED_IN`) load each source file separately; if kuzu needs pair disambiguation, filter `rel_located_in.csv` by `src_kind` into two temp CSVs and COPY each.

- [ ] **Step 1: Failing test** — `build_db` then open conn, assert `MATCH (c:Company) RETURN count(*)` > 100, `MATCH (:Company)-[:HAS_RELATIONSHIP]->(l:LineOfBusiness {name:'CB'}) RETURN count(*)` > 0, `MATCH (:Person)-[:EMPLOYED_BY]->(:Company) RETURN count(*)` > 0.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** `build_db`: `shutil.rmtree(db_path, ignore_errors=True)`, create db, split `schema.cypher` on `;`, execute each DDL stmt, `conn.execute(f"COPY Company FROM '{path}' (HEADER=true)")`, etc. **This step proves the multi-pair COPY approach — if it errors, switch to per-pair temp files here (the test is the proof).**
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `git commit -am "feat: kuzu bulk loader"`

### Task 1.8: Verification gate — the 6 questions in raw Cypher

**Files:**
- Create: `tests/verify_demo.py`, `graph/queries.py`

**Interfaces:**
- `graph/queries.py` produces one function per question returning `(cypher, params)`: `q1_cm_only(region)`, `q2_cb_no_wealth(region)`, `q3_penetration()`, `q4_midwest_industries()`, `q5_bank_at_work()`, `q6_underpenetrated()`. These canonical queries are reused as the query agent's few-shot gold answers in Task 2.3.
- `tests/verify_demo.py` builds the DB, runs each query, asserts against `fixtures.EXPECTED`.

- [ ] **Step 1: Write `graph/queries.py`** with the 6 canonical Cypher builders. Example:

```python
def q2_cb_no_wealth(region: str):
    cypher = """
    MATCH (c:Company)-[:HAS_RELATIONSHIP]->(:LineOfBusiness {name:'CB'})
    WHERE c.region = $region
      AND NOT EXISTS { MATCH (c)-[:HAS_RELATIONSHIP]->(:LineOfBusiness {name:'Wealth'}) }
    RETURN c.name AS name, c.revenue AS revenue
    ORDER BY c.revenue DESC LIMIT 20
    """
    return cypher, {"region": region}
```

- [ ] **Step 2: Write `tests/verify_demo.py`** — `build_db(...)`, then for each question run query via `run_read` and assert the returned names/counts equal `EXPECTED[N]` (e.g. Q1 returns exactly the 10 fixture names; Q3 top row is `Quebec`).

- [ ] **Step 3: Run the gate**

Run: `python -m pytest tests/verify_demo.py -v`
Expected: all 6 assertions PASS. **If any fail → adjust the fixture/knob (Tasks 1.4–1.5) and regenerate; do not weaken the assertion.** This is the demo-lands gate; everything downstream depends on it being green.

- [ ] **Step 4: Commit** `git commit -am "feat: 6-question verification gate (no LLM)"`

**CHECKPOINT 1:** `python generate/generate_data.py && python load/load_kuzu.py && pytest tests/ -v` all green before Phase 2.

---

## Phase 2 — Query agent

### Task 2.1: Typed agent dataclasses

**Files:** Create `agents/types.py`, `tests/test_types.py`

**Interfaces:** Produces `@dataclass QueryResult(cypher: str, rows: list[dict], error: str|None, attempts: int)`; `@dataclass Evidence(request: str, result: QueryResult)`; `@dataclass OrchestratorState(question: str, evidence: list[Evidence], iterations: int)` with `.query_count` property.

- [ ] **Step 1: Failing test** — construct each, assert defaults and `OrchestratorState.query_count == len(evidence)`.
- [ ] **Step 2–4: Implement, run → PASS.**
- [ ] **Step 5: Commit** `git commit -am "feat: typed agent contracts"`

### Task 2.2: Bedrock Converse wrapper (tool loop)

**Files:** Create `llm/bedrock.py`, `tests/test_bedrock_wrapper.py`

**Interfaces:**
- Produces `class BedrockClient(cfg)` with:
  - `converse(model_id, system, messages, tools=None, thinking=False, max_tokens=4096) -> dict` returning `{"text": str, "tool_uses": list[{"id","name","input"}], "stop_reason": str, "messages": updated}`.
  - `converse_stream(model_id, system, messages, tools=None, thinking=False, max_tokens=4096, on_event=None) -> dict` — same return shape, but consumes `client.converse_stream(...)` and invokes `on_event(kind, text)` for each delta (`kind` ∈ `"thinking" | "text" | "tool"`). This is what powers the live UI trace. `on_event=None` → behaves like buffered `converse`.
  - Builds boto3 session from cfg; sets `additionalModelRequestFields={"thinking":{"type":"enabled","budget_tokens":cfg.thinking_budget}}` when `thinking=True`; retries on `ThrottlingException` with backoff (deterministic, no `time`-based randomness in tests — inject sleeper).

- [ ] **Step 1: Failing test** — fake boto3 `bedrock-runtime` client; assert `converse` parses a tool_use response into `tool_uses` and a text response into `text`; assert `converse_stream` with a scripted event iterator calls `on_event` with the right `kind`/`text` deltas and returns the same aggregated shape.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** the wrapper; `converse` parses `resp["output"]["message"]["content"]` blocks (`text`, `toolUse`), maps `stopReason`; `converse_stream` parses the event stream (`contentBlockDelta` → `text`/`reasoningContent`; `contentBlockStart` toolUse; `messageStop`) and aggregates into the same dict.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `git commit -am "feat: bedrock converse wrapper (buffered + streaming) with tool-use + thinking"`

### Task 2.3: Query agent (Cypher writer + self-repair)

**Files:** Create `agents/query_agent.py`, `agents/prompts/query_agent.md`, `tests/test_query_agent.py`

**Interfaces:**
- Produces `run_query_agent(client, conn, request: str, max_repairs=3) -> QueryResult`. Loop: ask model (system = `query_agent.md` + `schema_doc.SCHEMA_TEXT`) to emit ONE Cypher in a fenced block; extract it; `run_read`; on kuzu exception feed the error back and retry (≤`max_repairs`); cap returned rows to 50.
- `query_agent.md` content: schema, "bulletproof Cypher" rules (always alias RETURN cols, use `EXISTS{}` for negation, parameterize regions, never mutate, LIMIT large results), and 2–3 few-shots drawn from `graph/queries.py`.

- [ ] **Step 1: Failing test** — with a fake `client` scripted to return a known-good Cypher for "CB clients without wealth in US Northeast", assert `run_query_agent` returns rows matching `q2_cb_no_wealth("US Northeast")` against the real test DB; and with a client scripted to first return broken Cypher then valid, assert `attempts == 2` and final rows non-empty.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** agent + write `query_agent.md`.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `git commit -am "feat: query agent with self-repair"`

---

## Phase 3 — Orchestrator + synthesizer

### Task 3.1: Orchestrator (anti-lazy reasoning loop)

**Files:** Create `agents/orchestrator.py`, `agents/prompts/orchestrator.md`, `tests/test_orchestrator.py`

**Interfaces:**
- Produces `run_orchestrator(client, conn, question: str, cfg, on_event=None) -> OrchestratorState`. The query agent is exposed to the model as a single tool `query_data(request: str)`. Uses `client.converse_stream(..., on_event=on_event)` so the UI can render reasoning + each Cypher live; `on_event=None` in tests. Loop until the model emits a final "ready to synthesize" signal AND `state.query_count >= cfg.min_queries`, bounded by `cfg.max_iters`. Each tool call appends an `Evidence` (and emits an `on_event("tool", request)`).
- `orchestrator.md`: biased toward investigation; explicit rule "before concluding, list negative-space checks and unfollowed threads; if any remain, call query_data again"; few-shots showing multi-query decomposition for Q5/Q6.

- [ ] **Step 1: Failing test** — fake client scripted to (a) try to finish after 1 query → assert orchestrator forces another because `min_queries=2`; (b) a script that issues 3 queries then finishes → assert `state.query_count==3` and loop exits cleanly; (c) runaway script → assert it stops at `max_iters`.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** loop enforcing the floor/ceiling + tool dispatch to `run_query_agent`; write `orchestrator.md`.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** `git commit -am "feat: anti-lazy orchestrator loop"`

### Task 3.2: Synthesizer (evidence-only answer)

**Files:** Create `agents/synthesizer.py`, `agents/prompts/synthesizer.md`, `tests/test_synthesizer.py`

**Interfaces:**
- Produces `synthesize(client, question, state) -> str` (markdown). System prompt forbids any number/entity not present in `state.evidence`; instructs structured output (headline answer, supporting bullets with counts, brief recommendation for Q6).

- [ ] **Step 1: Failing test** — fake client; assert the evidence (rows) is serialized into the user message and that `synthesize` returns the model text; add a guard test that `synthesize` raises if `state.evidence` is empty.
- [ ] **Step 2–4: Implement, run → PASS.**
- [ ] **Step 5: Commit** `git commit -am "feat: evidence-only synthesizer"`

### Task 3.3: End-to-end pipeline

**Files:** Create `agents/pipeline.py`, `tests/test_pipeline_live.py` (manual, live Bedrock)

**Interfaces:**
- Produces `answer_question(question: str, cfg, conn, client, on_event=None) -> {"answer": str, "state": OrchestratorState}`. Wires orchestrator (streaming via `on_event`) → synthesizer.

- [ ] **Step 1: Implement** `answer_question`.
- [ ] **Step 2: Manual live test** — `python tests/test_pipeline_live.py` runs all 6 demo questions against real Bedrock; print answer + the queries the orchestrator ran. **Confirm each answer matches the verified entities from Task 1.8 and the orchestrator ran ≥2 queries (anti-lazy).**
- [ ] **Step 3: Commit** `git commit -am "feat: end-to-end answer pipeline"`

**CHECKPOINT 2:** all 6 questions answered correctly end-to-end, no hallucinated entities, multi-query reasoning visible.

---

## Phase 4 — pyvis subgraph

### Task 4.1: Relevant-subgraph builder

**Files:** Create `viz/subgraph.py`, `tests/test_subgraph.py`

**Interfaces:**
- Produces `build_subgraph(conn, entity_ids: list[str], cap=15) -> str` (HTML). Given the entities the answer references (company/person/region/LOB ids from evidence rows), fetch their 1-hop neighborhood, cap to ≤`cap` nodes prioritizing answer entities + their LOB/region nodes. **Offline rendering only** — no Font-Awesome/CDN: each node gets `shape` + per-type `color` + an emoji prefix in its label (Company 🏢, Person 👤, Region 📍, LOB 🏷️). Tuned physics; `Network(..., cdn_resources='in_line')` so the vis-network JS is inlined into the HTML (works on the locked network). Return embeddable HTML string.

- [ ] **Step 1: Failing test** — build_subgraph on a known fixture company returns HTML containing its name, ≤15 node entries (`assert html.count('"id":') <= 15`), and no `http`-scheme asset URLs (`assert 'cdnjs' not in html and 'http://' not in html and 'https://' not in html`).
- [ ] **Step 2–4: Implement, run → PASS.**
- [ ] **Step 5: Commit** `git commit -am "feat: capped relevant subgraph viz"`

---

## Phase 5 — Streamlit BMO UI

### Task 5.1: BMO-branded app

**Files:** Create `app/streamlit_app.py`, `app/assets/bmo.css`, `app/assets/` icons

**Interfaces:**
- Consumes `agents.pipeline.answer_question` (extended to accept `on_event`), `viz.subgraph.build_subgraph`. **Single-shot** (no chat memory): each chip/typed question is answered independently. Layout: BMO header (blue `#0079C1`, navy, white, red accent), 6 question chips that prefill the input, free-text box, a **live-streaming** "Reasoning" panel, the synthesized answer (markdown), and the embedded subgraph (`streamlit.components.v1.html`).
- Streaming: pass an `on_event(kind, text)` callback into the pipeline that appends to a `st.empty()` placeholder (and a `st.status` spinner) so reasoning tokens + each Cypher appear live as Opus thinks; the final answer + subgraph render when the stream completes.

- [ ] **Step 1: Implement** app reading `config.toml`, caching the kuzu connection + BedrockClient with `@st.cache_resource`; wire the `on_event` streaming callback into the reasoning placeholder.
- [ ] **Step 2: Manual run** — `streamlit run app/streamlit_app.py`; click each of the 6 chips; confirm reasoning streams live, shows multiple queries, answer matches verified entities, subgraph shows a clean handful of nodes.
- [ ] **Step 3: Commit** `git commit -am "feat: BMO-branded streamlit UI"`

---

## Phase 6 — Polish + transfer

### Task 6.1: README + transfer dry-run

**Files:** Create `README.md`

- [ ] **Step 1: Write `README.md`:** setup (`pip install -r requirements.txt`, `cp config.example.toml config.toml`, fill creds), build (`python generate/generate_data.py && python load/load_kuzu.py`), gate (`pytest tests/verify_demo.py`), run (`streamlit run app/streamlit_app.py`), and the **work-machine swap** (edit `[bedrock]` creds/region/model only).
- [ ] **Step 2: Transfer dry-run** — fresh clone in a temp dir, follow README verbatim, confirm gate green + app launches.
- [ ] **Step 3: Commit** `git commit -am "docs: README + transfer instructions"`

---

## Verification (end-to-end)

1. `python tests/smoke_bedrock.py` → `OK` (creds + model access).
2. `python generate/generate_data.py && python load/load_kuzu.py` → builds DB.
3. `pytest tests/ -v` → unit + the 6-question gate green.
4. `python tests/test_pipeline_live.py` → all 6 answered correctly via Bedrock, ≥2 queries each, no invented entities.
5. `streamlit run app/streamlit_app.py` → click 6 chips; trace + correct answer + clean ≤15-node subgraph each.
6. Swap dry-run: change `[bedrock]` creds/region/model in `config.toml`, re-run one question, identical flow.

## Decisions locked
- **Models:** Opus on every call (orchestrator + query + synthesizer). Both model-id keys kept in config for a one-line future cost-tune.
- **Reasoning trace:** live-streamed to the UI via `converse_stream` + `on_event`.
- **Viz:** embedded shape+color+emoji, `cdn_resources='in_line'`, zero external assets (locked-network safe).
- **Interaction:** single-shot questions, no chat memory.

## Open items (sensible defaults set; tune during build)
- Confirm exact Bedrock model id string + region (Task 0.2 proves access; adjust `config.toml` to whatever profile your console exposes).
- `min_queries=2`, `max_iters=8`, `thinking_budget=2048` (tune in Phase 3 if orchestrator under/over-investigates).
- BMO palette pinned to `#0079C1` + navy/white/red until brand assets provided.
- kuzu multi-pair COPY: Task 1.7 Step 3 proves it; falls back to per-pair temp CSVs if needed.
