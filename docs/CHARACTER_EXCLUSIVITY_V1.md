Status: WORKING
Last verified: 2026-04-26
Verified by: Codex
Doc type: reference

# Personal Journey Spine V1

This is the first product-facing state layer from the roadmap's Personal Journey Spine track.

It is character-scoped by `CharacterGUID`. Do not key WM journeys by account, bot group, or global player name.

## What It Owns

- character profile and WM persona
- active/completed/paused arc state
- exclusive unlock records
- reward-instance records
- conversation steering notes
- pending prompt/branch-choice queue entries

This layer records WM truth. Actual game mutation still goes through managed publishers, shell grants, control proposals, or typed native actions. Freeform SQL, freeform GM commands, and direct LLM mutation are not valid grant methods.

## Repo Interfaces

- `python -m wm.character.journey inspect --player-guid <guid> --summary`
- `python -m wm.character.journey apply --plan-json <path> --mode dry-run --summary`
- `python -m wm.character.journey apply --plan-json <path> --mode apply --summary`

Default BridgeLab seed plan:

```powershell
python -m wm.character.journey apply --plan-json control\examples\journey\jecia_personal_spine_v1.json --mode dry-run --summary
```

The plan schema is `wm.character_journey.seed.v1`.

Allowed plan sections:

- `profile`
- `arc_states`
- `unlocks`
- `reward_instances`
- `conversation_steering`
- `prompt_queue`
- `metadata`

Rejected plan fields include freeform mutation fields such as `sql`, `sql_text`, `gm_command`, `gm_commands`, `shell_command`, and `command`.

Allowed unlock `grant_method` values:

- `control`
- `native_bridge`
- `managed_publish`
- `shell_grant`
- `item_grant`
- `manual_record`

`gm_command` is explicitly rejected.

## Tables

Apply `sql/bootstrap/wm_character_state.sql` to `acore_characters`.

Tables:

- `wm_character_profile`
- `wm_character_arc_state`
- `wm_character_unlock`
- `wm_character_reward_instance`
- `wm_character_conversation_steering`
- `wm_character_prompt_queue`

The conversation steering table stores durable player/operator preferences that later arc/reward/scene proposal code can read without letting the model mutate state directly.

## Status

`WORKING` at repo-test level:

- strict journey plan parsing
- dry-run without DB connection
- apply path through structured repo-owned SQL
- reader fallback when character tables are absent
- inspect payload and summary rendering
- context pack generation input includes active arc keys, unlock refs, reward refs, and steering notes

`PARTIAL` for live gameplay:

- BridgeLab state apply for player `5406` still needs to be run when we want live DB proof
- future arc/reward factory code still needs to consume this spine as an eligibility source

## Test Commands

```powershell
python -m pytest -q tests/test_character_models.py tests/test_character_reader.py tests/test_character_journey.py tests/test_context_pack.py tests/test_prompt_package.py
python -m pytest -q
```
