# WM Platform — Setup Completion Checklist

Use this checklist to verify a fresh WM installation is fully operational.

## Offline / No-DB Checks

- [ ] `python -m pytest -q` — all tests pass
- [ ] `python -m wm.living.catalog --validate` — no issues
- [ ] `python -m wm.living.catalog --dry-run-all` — `ok=true`
- [ ] `python -m wm.living.nemesis --player-guid 5406 --subject-entry 46 --subject-name Murloc --kill-count 12` — shows plan
- [ ] `python -m wm.living.rumor --player-guid 5406 --player-name Jecia --subject-name Wolves --deed-count 10` — live_ready=True

## DB / Live Checks (requires wm_brain DB)

- [ ] Bootstrap SQL applied — all wm_* tables present
- [ ] `python -m wm.journal.writer` (or equivalent smoke test) — counter upsert succeeds
- [ ] `SELECT COUNT(*) FROM wm_journal_counter` — returns 0 (empty but accessible)
- [ ] `SELECT COUNT(*) FROM wm_llm_proposal_log` — returns 0
- [ ] `SELECT COUNT(*) FROM wm_artifact` — returns 0

## Panel Checks

- [ ] `python -m wm.panel` starts without error
- [ ] `GET /api/health` returns `{"ok": true}`
- [ ] `GET /api/feature_status` returns feature list
- [ ] `GET /api/living_readiness` returns `{"ok": true}`
- [ ] `GET /api/living` returns Wild Feature Catalog with 5 entries

## BridgeLab Checks (requires running AzerothCore + mod_wm_bridge)

- [ ] Player Jecia (guid=5406) online
- [ ] `player_chat_message` action delivers a WM-channel chat line in-game
- [ ] `wm_journal_counter` row inserted when player kills a creature
- [ ] Nemesis plan executes at least the spawn step (creature_spawn)

## Security Gates

- [ ] `WM_LLM_DIRECT_APPLY=0` in `.env` (default — blocks LLM live mutations)
- [ ] No `.env` committed to git (verify with `git status`)
- [ ] `python -m wm.sources.native_bridge.payload_contract --self-test` — all contracts valid

## Status: PARTIAL

This platform is operational at the Python layer. C++ Batch 1/2/3 actions are
contract-valid but lab-gated until `mod_wm_bridge` C++ hooks are proven in BridgeLab.
