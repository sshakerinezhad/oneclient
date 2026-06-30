# OneClient Intelligence

OneClient Intelligence is a BMO Wealth Management demo that uses AI to answer business questions about client relationships by reasoning over a graph database.

## Setup

Install dependencies and configure credentials:

```bash
pip install -r requirements.txt
cp config.example.toml config.toml
# Edit config.toml: set your AWS Bedrock credentials and region
```

## Build the Database

Generate deterministic test data and load into kuzu:

```bash
python -m generate.generate_data
python -m load.load_kuzu
```

Uses fixed seed (42) for reproducible data generation across machines.

## Verify (Optional)

Run 6 canonical business questions against the graph to verify data integrity:

```bash
python -m pytest tests/verify_demo.py -v
```

## Run

Start the Streamlit application:

```bash
streamlit run app/streamlit_app.py
```

## The 6 Demo Questions

1. Top 10 CM clients with no other relationships (US West)
2. Top 20 CB clients without Wealth (US Northeast)
3. Regions with strongest CB∩Wealth penetration
4. Franchisee/auto dealer/equipment CB clients without Wealth (US Midwest)
5. Large CB/CM clients — bank-at-work candidates
6. Best underpenetrated opportunity with strong cross-BMO relationships

## Work Machine Transfer

Copy the project to your work machine and set up in 5 steps:

```bash
# 1. Copy entire project folder
# 2. Install dependencies via proxy
pip install -r requirements.txt

# 3. Update config.toml with work AWS credentials/region
# Edit [bedrock] section

# 4. Generate and load database
python -m generate.generate_data && python -m load.load_kuzu

# 5. Run the app
streamlit run app/streamlit_app.py
```

The database regenerates identically (fixed seed=42) — no data file transfer needed.

## Architecture

```
Mock ECIF Data
    ↓
Kuzu Graph Database
    ↓
Orchestrator (Claude Opus via Bedrock)
    ↓
Query Agent (Cypher)
    ↓
Synthesizer
    ↓
Streamlit UI + Pyvis Graph Visualization
```

The system generates deterministic test data representing BMO clients across business segments (CM, CB, Wealth), then uses an agentic orchestrator to reason over the graph and synthesize answers to business questions.

## Smoke Test (Bedrock Credentials)

Verify AWS Bedrock access before running the full app:

```bash
python tests/smoke_bedrock.py
```

This test confirms your credentials and region are correctly configured.
