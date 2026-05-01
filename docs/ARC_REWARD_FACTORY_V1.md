Status: PARTIAL
Last verified: 2026-04-29
Verified by: Codex
Doc type: reference

# Arc + Reward Factory V1

Arc + Reward Factory V1 is the first product-facing arc lane. It turns the live-proven Personal Journey Spine into a content publisher for one short personal arc, one fresh managed quest slot, and one visible managed reward.

## Architecture

The factory composes existing systems:

- `wm.character.eligibility.JourneyEligibilitySnapshot` gates whether a character can receive arc content
- `wm.items.publish` publishes or refreshes a managed item reward
- `wm.reserved.db_allocator` allocates a fresh reserved quest slot
- `wm.quests.publish` publishes the visible quest into that slot
- `wm.character.journey` records the active arc state, reward instance, conversation steering, and prompt queue
- `wm.runtime_sync` reports reload/restart requirements

It does not add freeform SQL, GM command generation, addon/log transport, combat-log scraping, or direct LLM mutation.

## CLI

```powershell
$env:PYTHONPATH='src'
$env:WM_WORLD_DB_PORT='33307'
$env:WM_CHAR_DB_PORT='33307'
$env:WM_SOAP_PORT='7879'
python -m wm.arcs.factory --scenario-json control/examples/arcs/jecia_shadowmoon_lens_arc_v9.json --mode dry-run --summary --write-artifact
python -m wm.arcs.factory --scenario-json control/examples/arcs/jecia_shadowmoon_lens_arc_v9.json --mode verify --summary --write-artifact
```

## Current Live Scenario

`control/examples/arcs/jecia_shadowmoon_lens_arc_v9.json` describes the three-beat Jecia arc fitted to the current live character context. The live proof quest itself is published by cloning known-working quest `910151` and changing identity, current-zone objective, Earthmender Wilda starter/ender, all visible quest text fields, and fresh reward item:

- setup: the lens reacts to Shadowmoon Valley's unstable spirits
- objective: Jecia slays six Enraged Earth Spirits near her current Shadowmoon position
- reward: `910013` Shadowmoon Watcher's Lens is recorded as a character reward instance tied to the new quest slot

The scenario uses player `5406`, target creature `21059`, turn-in NPC `21027` (`Earthmender Wilda`), managed item draft `control/examples/items/shadowmoon_watchers_lens_v9.json`, reward item `910013`, and the known-working quest row shape from `910151`.

`control/examples/arcs/jecia_lens_arc_v1.json` remains as a regression fixture and historical proof of the factory. It is not the live gameplay target for level-70 Jecia because it sends the character back to Elwynn with a low-level reward.

The reward item now also has a no-grant item-effect playcycle at `control/examples/content_playcycles/shadowmoon_watchers_lens_arc_reward.json`. It verifies the managed item publish/slot/snapshot evidence for `910013` without bypassing quest `910171`.

## Status

`WORKING` at repo-test level:

- strict scenario parsing
- rejection of freeform mutation fields
- two-to-three beat validation
- dry-run with no slot or journey mutation
- fresh quest-slot allocation in apply mode
- managed item reward publish path
- quest publish path
- journey arc/reward recording path
- apply-time stop when journey eligibility is not ready
- slot release when quest publish fails
- verify path for arc state, reward instance, quest row, slot row, publish log, and reward item row

`WORKING` in BridgeLab DB proof:

- Elwynn proof quest `910151` (`jecia_lens_turns_v1`) exposed and fixed a journey-plan raw/normalized mismatch; the repaired state remains verified but is superseded as the live target
- Shadowmoon v1/v2 proofs (`910152` / `910010` and `910154` / `910011`) were retired after the live quest reward panel resolved the item as a wrong/stale identity; those IDs are `BROKEN` in the custom ID ledger and their reserved slots are retired
- Shadowmoon v3 (`910155` / `919001`) was retired after live proof showed the quest details panel resolving `RewardMoney=19600` as `Pebble of Kajaro`
- Shadowmoon v4 (`910160` / `919002`) was retired after live proof showed a DB-correct fixed reward did not render any reward in the quest details panel
- Shadowmoon v5 (`910167` / `919003`) was retired after live proof showed one-option choice reward presentation still did not render a reward; the structural issue was inherited generated quest `Flags=128`
- Shadowmoon v6 (`910168` / `919004`) was retired in favor of cloning the known-working quest `910151` row shape directly
- Shadowmoon v7 (`910169` / `919005`) was retired after live proof showed `RewardMoney=1296` rendering as item `1296` (`Blackrock Mace`) in the quest details reward slot
- Shadowmoon v8 (`910170` / `910012`) was retired after live proof still showed stale source objective text and no visible reward on Oronok Torn-heart
- Shadowmoon v9 uses fresh item ID `910013`, fresh quest slot `910171`, Earthmender Wilda as starter/ender, target `21059`, and a direct clone of quest `910151` with all visible quest text fields overwritten; its visible money reward remains cleared so copper cannot be interpreted as an item entry
- BridgeLab DB publish succeeded for v9 on `127.0.0.1:33307`; `python -m wm.arcs.factory --scenario-json control/examples/arcs/jecia_shadowmoon_lens_arc_v9.json --mode verify --summary --write-artifact` returned `WORKING` on 2026-04-29. Quest `910171` is active on Earthmender Wilda with `Flags=8`, `LogDescription`/`QuestCompletionLog` rewritten, `RewardItem1=910013`, `RewardAmount1=1`, choice reward columns cleared, `RewardMoney=0`, and item `910013` active in `item_template`
- standard quest reload commands and full `.reload item_template` succeeded through BridgeLab SOAP on port `7879`
- `python -m wm.content.playcycle item-effect --scenario-json control/examples/content_playcycles/shadowmoon_watchers_lens_arc_reward.json --mode verify --summary` returned `WORKING` on 2026-04-29. The scenario keeps `direct_grant.enabled=false`, so quest reward-panel proof is not bypassed.
- Current BridgeLab character DB has no `character_queststatus`, `character_queststatus_rewarded`, or inventory row for Jecia / `910171` / `910013`; the live proof is still clean to run from Earthmender Wilda.

`PARTIAL` gameplay:

- Jecia still needs to accept/complete quest `910171` at Earthmender Wilda and confirm the level-70 reward is visible in-game
- after reward, Jecia needs to equip `910013` and confirm the visible wearer aura `132`, target debuff `770`, Lens Focus damage bonus, and Lens Command marked-target Echo preference; the native item-entry gate is rebuilt/restarted in BridgeLab worldserver pid `30124`, but live effect proof for the new item remains pending

## Test Command

```powershell
python -m pytest -q tests/test_arc_reward_factory.py
python -m pytest -q tests/test_content_playcycle.py
python -m pytest -q
```
