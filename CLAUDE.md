# CLAUDE.md

EVERY SINGLE CHANGE MADE SHOULD ASK THE QUESTION: "Is this the simplest solution executed in the most efficient manner, and is this the industry standard for clean scalable code?"

If the answer is no, the change is wrong. No spaghetti code EVER.

## Golden Rules
- Never assume. Read the code, don't guess.
- Simplest solution wins. If it's a bandaid, re-evaluate.
- The first solution is rarely the best, be critical and compare every option shrewdly
- Challenge your own biases, think several layers of abstraction deep
- The WHY matters as much as the WHAT. Include reasoning in decisions and documentation.
- Before implementing a plan, critique it. Does it make sense? What could go wrong? What does it interact with?
- My words are NOT gospel. They are a starting point. Push back.
- Every change must be verified with irrefutable proof before it is considered done.

## Verification
Verification with `/verify` is **optional** — only run it when I explicitly ask for it.

When I do request it:
- Run `/verify` against the workplan to generate tests in `__verify__/`
- After each change, run its corresponding test. If it fails, fix the implementation, not the test.
- At each breakpoint, run the checkpoint script. Fix before proceeding.

## Git & Attribution
- NEVER add "Co-Authored-By" lines, AI attribution, or any indication that code was AI-generated to commits, PRs, comments, or any other git artifacts. Write commits and PRs as a normal human developer would.

## Context Management
**40%+ context saturation is high — start conserving.** Prefer referencing earlier reads over re-reading files. `offset`/`limit` is only allowed on files already read in full (partial reads without full context lead to bad edits).

## Testing
- Run tests: `python -m pytest tests/ -v --tb=short` (from project root)
- Verification gate: `python -m pytest tests/verify_demo.py -v` (6 demo questions, no LLM)
- Bedrock smoke: `python tests/smoke_bedrock.py` (needs valid AWS keys in config.toml)

## Architecture (OneClient)
- **Bedrock API:** invoke_model (NOT Converse — permissions issue). Anthropic Messages API format.
- **kuzu rel tables:** Split names — `COMPANY_HAS_RELATIONSHIP` / `PERSON_HAS_RELATIONSHIP`, `COMPANY_LOCATED_IN` / `PERSON_LOCATED_IN`. kuzu v0.7.1 doesn't support multi-FROM. All Cypher must use split names.
- **AWS creds:** Temporary session keys (`ASIA...` prefix) in config.toml. Expire hourly. Refresh before demo.

## File Conventions
- `masterplan.md` — long-range architecture and goals
- `workplan.md` — current implementation steps
- `scratchpad.md` — context for session handoffs
- `notes.md` — raw backlog (bugs, issues, features)
- `__verify__/` — generated test scripts (do not modify)
- `changelog/` — archived masterplans
