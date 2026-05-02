# Broug Empty Court V2

Status: `PARTIAL`
Last verified: 2026-05-02
Verified by: Codex
Doc type: status

Broug `5405` keeps the guard/parry kit as `WORKING` foundation. This slice adds the next lightness-assassin identity only: room pressure, active cleanse, and sustain. It does not add parry behavior and does not mutate Vulnerable stacks.

## Scope

- Arc: `broug_empty_court_v2`
- Stage: `first_peak_empty_court`
- Required foundation: quest `910183` complete and shells `946202` / `946803` learned.
- Content style: stock Westfall anchors plus custom mentor Wei Jin `915500`.

## Quest Chain

| Quest | Name | Starter | Objective | Reward |
| --- | --- | --- | --- | --- |
| `910184` | Broug: The Weight Before the Blade | Gryan Stoutmantle `234` | Inspect Ash-Worn Track Circle `195500`, then speak to Wei Jin | Mentor chain unlock |
| `910185` | Broug: Stilling the Water | Wei Jin `915500` | Earn `920107` three times from ash-hushed trial actors `915510-915512` | `946621` Qi Reversal |
| `910186` | Broug: Ninety-Eight | Wei Jin `915500` | Kill `6x` Defias Knuckleduster `449`, `6x` Defias Trapper `504`, and Hal Morrow `915520` | `946805` Predator's Strike |
| `910187` | Broug: The Room That Silenced | Wei Jin `915500` | Clear Silent Hall actors `915530-915539` for credit `920109` | `946804` Killing Intent: Domain |
| `910188` | Broug: Domain Unsealed | Wei Jin `915500` | Defeat Court Remnant `915540` for credit `920110` | `946806` Vitality Drain |

## Ability Inventory

- `946804` Killing Intent: Domain, passive, behavior `broug_killing_intent_domain_v1`
- `946204` Suppressed, visible target debuff, behavior `broug_suppressed_v1`
- `946621` Qi Reversal, active self-cast cleanse, behavior `broug_qi_reversal_v1`
- `946622` Purged State, visible self state, behavior `broug_purged_state_v1`
- `946805` Predator's Strike, passive sustain, behavior `broug_predators_strike_v1`
- `946806` Vitality Drain, passive kill sustain, behavior `broug_vitality_drain_v1`

## Runtime Rules

- Domain upgrades Cloud Step's `946620` Killing Intent to at least `15s`.
- Domain pulses `946204` Suppressed every `2s` to hostile enemies within `8 yd`.
- Suppressed enemy deaths extend active Killing Intent by `+5s`. There is no player-facing hard cap, but runtime state is pruned on logout, death, and aura loss.
- Qi Reversal removes up to `3` Magic, `2` Poison, and `1` Disease harmful auras, then applies two native-tracked Purged State charges for `30s`.
- Predator's Strike heals from actual damage dealt when Marked Meridian is consumed.
- Vitality Drain heals on killing blows and gives a larger heal plus extra energy inside Silent Meridian's Cloud Step kill window.

## Proof Counters

`wm_broug_empty_court_counter` records:

- `domain_pulse`
- `suppressed_death_extend`
- `qi_reversal_cleanse`
- `predator_heal`
- `vitality_kill`

## Safety Notes

- Does not touch item `910014`.
- Does not reuse spell `946606`.
- Does not reuse hidden credit `920106`.
- Does not touch retired shells `946604` / `946801`.
- Does not touch `playercreateinfo` or `mod_learnspells`.
- Does not mutate Vulnerable stack behavior.

## Deployment Proof

On 2026-05-02, BridgeLab world SQL applied after correcting the spawn-row schema to this core's `creature.id1` / `wander_distance` layout. Server `Spell.dbc` staged all 26 named WM shells with the castable profile, including `946204`, `946621`, `946622`, `946804`, `946805`, and `946806`. Client `patch-z.mpq` was rebuilt and installed. Native worldserver build passed cleanly with `0 Warning(s), 0 Error(s)` using `Build-BridgeLabIncremental.ps1 -NoStageRuntime`; the earlier broad runtime copy hit a locked running `authserver.exe`, then the worldserver-only deploy path succeeded and restarted BridgeLab worldserver to pid `32352`. Native bridge ping request `622` returned `pong`.

Follow-up live DB check found Ash-Worn Track Circle `195500` was spawned at `map 0, -10752, 990, 48`, but the initial template used `displayId=0`, making it effectively invisible in-game. The source SQL and live DB were corrected to use visible track display `8298`, size `0.75`, and GOOBER quest data `Data1=910184`, `Data3=3000`. Bolted Cellar Hatch `195501` was also corrected from invisible `displayId=0` to visible trapdoor display `8413`, size `0.75`, with `Data1=910187`, `Data3=3000`. Worldserver template cache may require reload/restart before an already-running world shows these display/template changes.

Second follow-up live test found Wei Jin `915500` and the other V2 custom actors were rejected by worldserver because this core requires `creature_template_model` rows and the initial V2 SQL only inserted `creature_template`. Source SQL and live DB now add model rows for `915500`, `915510-915512`, `915520`, `915530-915539`, `915540`, and V2 hidden credits `920107-920110`. BridgeLab worldserver was restarted again; fresh `Errors.log` no longer reports missing display/model rows for V2 custom actors.

Quest `LogDescription` text for `910184-910188` was revised after live test feedback so the upper quest log gives concrete directions and coordinates. Lore remains in `QuestDescription`; instructions now point Broug to the exact objects, camps, targets, and kill requirements. BridgeLab worldserver was restarted after the live DB update so quest template cache can pick up the new text.

Qi Reversal `946621` live review found the self-cast cleanse inherited the self-aura seed's ranged presentation. Shell-bank and client manifest now set `range_index=1`, and focused client/server DBC tests assert the self range so the tooltip/cast shape does not show a target range.

Latest tuning after live review changes Qi Reversal and Purged State to the Cloak of Shadows icon (`SpellIcon.dbc` id `1933`), extends Purged State to `30s`, upgrades Domain's Killing Intent floor to `15s`, refreshes Suppressed for `12s`, and changes Suppressed death extension to `+5s`. Focused repo tests passed (`72 passed`), world SQL was reapplied, server `Spell.dbc` was staged, client `patch-z.mpq` was rebuilt/installed, native worldserver build passed with `0 Error(s)`, BridgeLab restarted to pid `8932`, and Broug native bridge debug ping `625` returned `pong`.

Final status remains `PARTIAL` until live proof confirms the full quest chain, spellbook visibility, Domain pulses, Qi Reversal cleanse, Predator heal, Vitality Drain, and no guard/Vulnerable regression.
