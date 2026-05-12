---
name: wm-content-release
description: Use for WM content work involving quests, items, spells, shell-bank abilities, arcs, scenes, context packs, release candidate packs, LLM proposal mode, or any change that can publish or mutate game state. Enforces fresh IDs, client/server truth separation, strict schemas, release gates, and rollback/proof discipline.
---

# WM Content Release

## Core Contract

Treat content as a strict release pipeline, not a freeform generation surface.

- LLM output may propose only structured context/candidate/release/control payloads.
- Deterministic code validates, compiles, applies, audits, and rolls back.
- No proposal schema may include arbitrary SQL, GM commands, shell commands, config edits, file mutation, or stock spell carrier reuse.
- Manual and future LLM proposals must use the same validators and apply paths.

## Truth Split

Before spell, item, UI, or shell work, state both sides:

- Client truth: spellbook entry, action bar, tooltip, icon, item display, visible aura, object model, or client DBC/MPQ requirement.
- Server truth: DB rows, native hook, action bus verb, shell behavior, grant state, cooldown, rollback, and audit.

Use the feasibility labels:

- `T1`: server only, still visible through game state.
- `T2`: server plus existing client assets.
- `T3`: client patch required.
- `T4`: client asset or UI work.
- `NOT FEASIBLE`: unreliable on stock 3.3.5a with WM contracts.

Hidden mechanics need a matching visible aura, buff, debuff, item, quest, creature, message, or tooltip, and server behavior must be gated by that visible state/duration.

## Required Gates

Use the repo-owned gates before live mutation:

```powershell
python -m wm.content.release <spec> --plan --summary
python -m wm.content.release <spec> --packet --summary
python -m wm.content.preflight --arc <arc_key> --summary
python -m wm.spells.shell_audit --spell-id <shell_id> --summary
python -m wm.bridge_lab.release_gate --arc <arc_key> --summary
python -m wm.live.proof_packet --arc <arc_key> --summary
python -m wm.candidates.release_pack --context-pack-json <context-pack.json> --summary
```

Read `docs/CONTENT_REQUIRED_FIELDS.md` before handing player-facing quests, items, abilities, scenes, or shells to the player.

## ID And Rollback Rules

- Use fresh reserved visible IDs for player-facing revisions after cache/proof failure.
- Retire dirty visible IDs in `data/specs/custom_id_registry.json`; do not recycle them as `free`.
- Never mutate rewards on a quest ID already accepted or rewarded by the live player; publish a fresh quest slot.
- Define rollback before apply, including DB rollback, runtime reload, player-copy cleanup limits, and docs/status updates.
- Mark generated content `WORKING` only after repo tests plus the required BridgeLab/live proof have passed.
