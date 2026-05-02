Status: PARTIAL
Last verified: 2026-05-02
Verified by: Codex
Doc type: status

# Broug Lightness Assassin V1

This is Broug's next personal arc after the accepted guard kit. The guard/parry lane remains `WORKING` for the current Broug scope; this lane does not add new parry behavior.

## Current Scope

`PARTIAL`: repo implementation is in place for a murim-style lightness assassin pivot. BridgeLab world SQL, Broug journey state, server DBC staging, client patch package build, native rebuild, and worldserver restart have passed. The first live turn-in exposed a missing reward grant and stale client MPQ; Cloud Step was recovered for Broug and runtime diagnostics were added. A later live check confirmed Cloud Step movement, then exposed missing smoke presentation, an unwanted minimum range, broken Marked Meridian consumption, and a client patch regression for `946605`. Broug has now completed both lightness quests and learned `Silent Meridian Manual`; the remaining live proof is the manual's kill-window energy/cooldown behavior.

- Character: Broug `5405`, level `22`, human rogue.
- Arc key: `broug_lightness_assassin_v1`.
- Stage key: `footwork_trial`.
- Journey example: `control/examples/journey/broug_lightness_assassin_v1.json`.
- Helper: `python -m wm.spells.broug_lightness --player-guid 5405 --mode dry-run --summary --show-sql`.

## IDs

- Quest `910182`: `Broug: Steps Without Dust`.
- Quest `910183`: `Broug: No Footfall Twice`.
- Shell `946202`: `Cloud Step`.
- Shell `946203`: `Marked Meridian`.
- Shell `946620`: `Killing Intent`.
- Shell `946803`: `Silent Meridian Manual`.
- Hidden credit `920106`: Cloud Step empowered-hit credit.

The original draft slot `946606` is not used by this arc. It is claimed by the parallel Energy Surge Potion lane with item `910014`, so Broug's self-aura shell is `946620`.

## Mechanics

Quest `910182` starts and ends at Master Mathias Shaw `332`; objective is `8x Syndicate Watchman` `2261`.

The target was corrected from the first draft's Defias Profiteer. `Syndicate Watchman` is level `20-21`, uses faction template `87` with `FactionGroup 8` and `EnemyGroup 1`, and has `52` map `0` spawns in BridgeLab.

`Cloud Step` is a Broug-scoped hostile-target shell:

- range `0-25 yd`
- line of sight required
- `20` energy cost
- `12s` cooldown
- normal global cooldown
- movement landing behind target, with side fallback and clean failure if no reachable landing is found
- plays the stock `Vanish Visual` (`24222`) at departure and arrival as smoke/fog presentation
- applies `Killing Intent` to Broug for `10s`
- applies `Marked Meridian` to the target for `12s`

The next Broug direct melee hit, Skirmisher's Mark hit, or future Cloud Step direct-damage hook against that marked target consumes native `Marked Meridian` state for `+35%` damage, records `wm_broug_lightness_counter('cloud_step_strike')`, grants hidden credit `920106`, and clears the visible mark. V1 deliberately preserves existing `Vulnerable` stacks instead of consuming or modifying them.

Quest `910183` requires `20` empowered hits. Its reward is `Silent Meridian Manual`, a passive that restores `10` energy and reduces remaining `Cloud Step` cooldown by `6s` when Broug kills the Cloud Step target within `10s`. The native handler must update both WM's internal Cloud Step timer and AzerothCore's live spell cooldown table with `ModifySpellCooldown`, or the client button will still show the old cooldown.

## Implementation

- Shell-bank/client truth: `control/runtime/spell_shell_bank.json` and `client_patches/wm_spell_shell_bank/manifest.json`.
- Server SQL: `native_modules/mod-wm-spells/data/sql/world/updates/2026_05_02_00_wm_spell_broug_lightness_assassin.sql`.
- Native runtime: `native_modules/mod-wm-spells/src/wm_spell_runtime.cpp`, `wm_spell_player_scripts.cpp`, and `wm_spell_unit_scripts.cpp`.
- Python helper: `src/wm/spells/broug_lightness.py`.
- ID registry: `data/specs/custom_id_registry.json`.

## Verification Status

Repo tests cover ID freshness, grant scoping to `5405`, no use of the parallel `910014` / `946606` claims, no new parry SQL lane, shell-bank/client/server DBC presentation, mark consumption hooks, energy/cooldown behavior hooks, quest credit, and journey-plan validity.

Verified on 2026-05-02:

- Focused repo suite: `54 passed`.
- Full repo suite before deploy: `574 passed`.
- Native incremental build: `0 Error(s)`.
- BridgeLab world SQL applied for shells `946202`, `946203`, `946620`, `946803`, quests `910182`, `910183`, and hidden credit `920106`.
- Broug `5405` journey arc recorded as `broug_lightness_assassin_v1` / `footwork_trial`.
- Server `Spell.dbc` staged with `946202`, `946203`, `946620`, and `946803`.
- Client `patch-z.mpq` package built and verified for `946202`, `946203`, `946620`, and `946803`; install is deferred because `wow.exe` was running.
- BridgeLab worldserver restarted with the new build and responded to a scoped Broug native bridge `debug_ping`.
- Live repair after first proof failure: Broug `5405` now has `character_spell` `946202` and `wm_spell_grant` `broug_lightness_reward` from quest `910182`.
- Runtime repair after no-op cast report: generic shell checks no longer gate Broug shells behind `WmSpells.BoneboundServant.Enable`, and failed shell execution now prints `WM shell <id> failed: <reason>` in chat.
- Quest display rows now advertise `RewardDisplaySpell = 946202` for `910182` and `RewardDisplaySpell = 946803` for `910183`.
- Presentation/runtime repair after movement proof: Cloud Step has smoke visuals at both endpoints, no native minimum range gate, Marked Meridian is keyed by native target/expiry state, Cloud Step and Marked Meridian use fitting rogue icons, and Counterstrike Stance `946605` is included in the full named client patch with a non-Arcane visual/icon row.
- Quest completion proof after user report: Broug `5405` is level `22`, `character_spell` contains `946202` and `946803`, `wm_spell_grant` contains active rewards for quests `910182` and `910183`, and `wm_broug_lightness_counter('cloud_step_strike') = 20`.
- Bridge allowlist repair after Energy Surge Potion regression: `Deploy-BridgeLabWorldServer.ps1` and `Configure-BridgeLabRuntime.ps1` now keep `WmBridge.PlayerGuidAllowList = "5406,5405"` by default, matching the spells allowlist. BridgeLab restarted to pid `18036`; Broug native bridge debug ping `620` returned `pong`.
- Timing/cooldown correction after live Silent Meridian report: Cloud Step now applies `10s` Killing Intent and `12s` Marked Meridian, Silent Meridian now uses a `10s` kill window with a `6s` cooldown refund, and the native kill handler calls `ModifySpellCooldown` so the live Cloud Step button cooldown is reduced. Focused repo tests passed (`72 passed`), world SQL was reapplied, server `Spell.dbc` was staged, client `patch-z.mpq` was rebuilt/installed, native worldserver build passed with `0 Error(s)`, BridgeLab restarted to pid `8932`, and Broug native bridge debug ping `625` returned `pong`.

Live proof still required before marking gameplay `WORKING`:

- Confirm `946803` energy/cooldown behavior after a kill inside the Cloud Step window.
- Confirm Energy Surge Potion `910014` no longer reports inactive for Broug after the bridge allowlist restart.
