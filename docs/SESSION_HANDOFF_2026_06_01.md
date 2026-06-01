Status: CURRENT
Last verified: 2026-06-01
Verified by: Claude
Doc type: handoff (session snapshot)

# WM Session Handoff — 2026-06-01

Current-truth snapshot. Supersedes `NEXT_CHAT_HANDOFF.md` for chat / perception /
ambient / memory / spawn work. Everything below is in the working tree but
**uncommitted to git** (left for the user to review). Full test suite: **1096 passed**.

## Plan the user is following (their words)

```
PHASE 1  Conversational Action Loop      — talk -> typed proposal -> pipeline -> confirm in chat
PHASE 2  Live Reaction Layer (ambient GM) — WM narrates notable events on cooldown
PHASE 3  Verb Surface Expansion (native C++) — death/level-up sensors + flavor verbs
PHASE 4  Persistent Narrative Memory      — journal/subject memory into chat + facts back out
PHASE 5  Scene Director                   — multi-step orchestrated moments
ENABLER  Split autoplay/service.py        — ONLY after Phase 1 live-proven (now unlocked)
```

## DONE and live-proven in-game (2026-06-01)

- **Phase 1 — action loop:** "heal me" -> `player_restore_health_power` (auto). "give me
  10 gold" -> confirm -> "yes" -> `player_add_money` copper:100000. talk->act->confirm works.
- **Phase 2 — ambient narration:** unprompted lines on zone entry (Azshara, Goldshire).
- **Phase 4 — conversational memory (write):** "Remember I prefer fighting undead" persisted
  to `wm_character_conversation_steering` (source=conversation) and reused in later replies.

## DONE in code this session, NOT yet live (need deploy/restart + in-game proof)

- **Phase 3 sensors (C++):** `OnPlayerLevelChanged` -> `progress/level_up`;
  `OnPlayerJustDied` -> `combat/death`; config `WmBridge.Emit.LevelUp/Death`. Adapter maps
  to canonical `level_up`/`death`; ambient notability + descriptors added.
  **Worldserver REBUILT OK but NOT deployed** (running worldserver was elevated; the agent
  shell got "Access denied" stopping it).
- **Voice fixes:** stops refusing things it can do; stops over-claiming completion.
- **Latency fixes:** `/v1/models` health cached 30s; memory call gated behind keyword
  prefilter; voice prompt trimmed (no manifest -> `_voice_world_digest`).
- **Spawn-by-name (Python, fully unit-tested, suite green):**
  - `wm/targets/name_resolver.py` — `CreatureNameResolver` (offline, uses
    `data/lookup/creature_template_full.json`; "deer"->883). `get_default_creature_name_resolver()`
    lazily caches it.
  - `wm/autoplay/spawn_args.py` — `prepare_creature_spawn_args` resolves spoken name to
    `creature_entry` (the real required field) and passes through follow/distance hints.
    No position needed: the native verb spawns near the player automatically.
  - Wired into `service._handle_intent`: `creature_spawn` intents resolve the name -> entry
    before compile; unresolved names are rejected cleanly with an in-character line.

## ONE remaining step for spawn-by-name (then live-prove)

The `creature_spawn` contract (`control/actions/native/native_bridge_action.json`) is clean:
`required: ["creature_entry"]`, `optional: [arc_key, duration_ms, distance, angle_offset,
follow_player, follow_distance, follow_angle]`. The PIPELINE already works (resolution +
validation pass). The gap is only that the **intent extractor doesn't know it may send a
creature NAME**. Add `creature_name` to that verb's `optional` list and a note like:
"Provide creature_name (e.g. 'deer') instead of creature_entry; the system resolves it and
spawns it near the player." Then live-prove "spawn a deer". (No corruption in that file —
an earlier note about duplicated keys was a tool-render glitch, disregard it.)

## Live bring-up (the part the agent can't do — needs the user's elevated shell)

Everything is DOWN now (user killed worldserver+authserver; agent stopped the brain).

1. **Deploy the Phase 3 worldserver** (build already succeeded) from the USER's elevated shell:
   `D:\WOW\wm-project\scripts\bridge_lab\Deploy-BridgeLabWorldServer.ps1`
2. **Relaunch the brain** with lab env (SOAP port is REQUIRED or readiness=false silently
   disables chat+ambient):
   ```
   $env:PYTHONPATH="src"; $env:WM_WORLD_DB_HOST="127.0.0.1"; $env:WM_WORLD_DB_PORT="33307"
   $env:WM_CHAR_DB_HOST="127.0.0.1"; $env:WM_CHAR_DB_PORT="33307"; $env:WM_SOAP_PORT="7879"
   .venv\Scripts\python.exe -m wm.autoplay run --project-root D:\WOW\wm-project ^
     --lab-mysql-port 33307 --soap-port 7879 --player-guid 5408 --interval-seconds 2.0 ^
     --no-start-watcher --llm-lanes chat --llm-events-per-tick 1 --summary
   ```
3. **Live-prove Phase 3:** char 5408, level up / die -> expect an ambient WM line.
4. **Live-prove spawn** (after the contract note above): "spawn a deer".

## Gotchas learned this session

- Brain reads DB via `Settings.from_env()`; the launching shell MUST set the lab ports +
  `WM_SOAP_PORT=7879`. Missing SOAP -> doctor SOAP check fails -> readiness=false ->
  chat AND ambient silently skipped.
- LM Studio serves one model at a time, so chat latency = sum of serial LLM calls. Visible
  reply still = intent-extract + voice (2 calls). Levers if still slow: (a) speak voice
  first, run intent after; (b) point json-schema passes at a small text model via
  `llm_intent_model`/`llm_memory_model`. User planned to drop the vision model (qwen3-vl-8b).
- `player_add_money` takes COPPER; contract note now teaches gold/silver conversion.
- Run tests: `Set-Location D:\WOW\wm-project; $env:PYTHONPATH="src"; python -m pytest -q`.

## Suggested next offline/autonomous work

- Add the `creature_name` hint to the `creature_spawn` contract (above).
- Phase 3 flavor verbs: write C++ bodies for `player_play_sound`, `creature_whisper` (+
  Python contracts / `implemented=True` / tests); stage for the next worldserver build.
- Phase 5 scene-director design (uses action-bus sequence support).
- The ENABLER (split `service.py`, ~2.3k lines) is unlocked now Phase 1 is live-proven, but
  it is a big refactor — plan before executing.
