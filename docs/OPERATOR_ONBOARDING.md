# WM Operator Onboarding

This document gets a new operator up and running with the World Master (WM) platform for AzerothCore 3.3.5a.

## Prerequisites

- Python 3.11+
- AzerothCore 3.3.5a server (running locally or via BridgeLab)
- MySQL access to `acore_world`, `acore_characters`, and `wm_brain` databases
- LM Studio (optional — for LLM-driven quest generation)

## First-Time Setup

### 1. Clone and install

```bash
git clone <repo>
cd wm-project
python -m pip install -e .
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in your database credentials:

```
WM_WORLD_DB_HOST=127.0.0.1
WM_WORLD_DB_PORT=3306
WM_BRAIN_DB_HOST=127.0.0.1
WM_BRAIN_DB_PORT=3306   # BridgeLab uses 33307
```

Key settings:
- `WM_LLM_DIRECT_APPLY=0` — keeps LLM output blocked from live DB until you explicitly set to 1
- `WM_BRIDGELAB_PLAYER_GUID=5406` — your test player GUID (Jecia on BridgeLab)

### 3. Bootstrap WM brain tables

Apply all SQL bootstrap files to your `wm_brain` database:

```bash
mysql -h 127.0.0.1 -P 33307 -u root -p wm_brain < sql/bootstrap/wm_bootstrap.sql
mysql -h 127.0.0.1 -P 33307 -u root -p wm_brain < sql/bootstrap/wm_journal_v2.sql
mysql -h 127.0.0.1 -P 33307 -u root -p wm_brain < sql/bootstrap/wm_subject_tables.sql
mysql -h 127.0.0.1 -P 33307 -u root -p wm_brain < sql/bootstrap/wm_living_tables.sql
mysql -h 127.0.0.1 -P 33307 -u root -p wm_brain < sql/bootstrap/wm_artifact_tables.sql
mysql -h 127.0.0.1 -P 33307 -u root -p wm_brain < sql/bootstrap/wm_llm_proposal_log.sql
mysql -h 127.0.0.1 -P 33307 -u root -p wm_brain < sql/bootstrap/wm_context_pack_log.sql
```

### 4. Run tests

```bash
python -m pytest -q
```

All tests should pass without a live DB (offline mode).

### 5. Start the panel

```bash
python -m wm.panel --port 8765
```

Then open `http://127.0.0.1:8765` in your browser.

## Key API Routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Liveness check |
| GET | `/api/status` | Full panel status |
| GET | `/api/feature_status` | Living world feature readiness |
| GET | `/api/living_readiness` | Dry-run all living evaluators |
| GET | `/api/living` | Wild Feature Catalog |
| GET | `/api/proposals` | LLM draft proposals list |
| POST | `/api/llm/generate` | Generate quest/recipe draft |
| POST | `/api/llm/adopt` | Log an LLM proposal adoption |

## Architecture Principles

- **Python owns** decisions, validation, audit, publishing, arcs, state
- **Native (C++) owns** sensing, typed actions, runtime effects
- **No freeform SQL/GM-command/shell mutations** from LLM output
- **BridgeLab** (`player_guid=5406`, MySQL `127.0.0.1:33307`) for integration testing
- Never claim `WORKING` without proof: DB row, native ping, or in-game observation

## Living World Features

| Feature | Status | C++ Batch |
|---------|--------|-----------|
| Nemesis | Contract-valid, lab-gated | Batch 1 |
| Rumor | Live-ready | None |
| Legend | Lab-gated | Batch 2 |
| Patron | Lab-gated | Batch 3 |
| Oath | Lab-gated | Batch 3 |

See `src/wm/living/catalog.py` and run `python -m wm.living.catalog` for current readiness.
