Status: PARTIAL
Last updated: 2026-10-01
Doc type: howto / implementation status

# Material Delivery Quests

WM now has source implementation for gathering observation -> activity summary -> typed decision -> optional NPC material-delivery offer -> core turn-in/payment. This is universal, not a Duskwood-specific quest or character feature. Implementation has not been tested, built or deployed in this slice.

## Reactive Gathering Slice

- Native loot events attribute skinning, mining, herbalism and fishing using the actual loot source, loot type and object lock, not item-name guesses.
- Existing native perception snapshots include carried/equipped inventory, profession values and phase. Bank contents are not scanned.
- `python -m wm.autoplay.activities --player-guid <guid>` and panel **Inspect Gathering Activity** read recent evidence without mutation. Episodes group material, gathering kind and current map/zone, keep observed facts separate from tentative purpose, and count distinct source GUIDs rather than item stacks.
- The selected-scope durable director can propose `material_delivery`. Host discovery resolves an ordinary gathered material currently carried, a nearby same-map faction-friendly questgiver with a matching phase, quantity up to ten, and money-only payment. DB proximity is not navigation-mesh proof or reputation-sensitive runtime interaction proof.
- Publication uses managed fresh quest IDs, existing publisher, runtime reload and ledger effects. A separate scoped announcement gives the NPC name, location, count and consumption rule. The quest is offered through stock NPC quest dialogue, not forced into the player's log. Accepting and rewarding use existing core behavior and bridge interaction events.
- Exact artifact preview and current policy still govern application. Unconstrained model output is draft-only. Publication followed by a failed reload is reported as an already-published failure requiring reconciliation, not a successful playable offer.
- Accepted delivery quests in recent director work suppress another proactive delivery. Unresolved work also suppresses new offers. Applied receipts alone are not player-visible proof.

### Initiative And Pacing

Panel autoplay configuration persists `initiative_preset` and `activity_proposals_enabled`:

| Preset | Gathering response |
| --- | --- |
| On Demand | No unsolicited gathering offers; explicit requests and started-quest reactions remain available |
| Moderate (default) | At least three distinct sources; fifteen-minute proactive pacing |
| Active | At least two distinct sources; five-minute proactive pacing |

Activity scans are at most once per fifteen seconds per selected character. Evidence is bounded to 300 recent events and fifteen minutes; an episode must have gathering in the last two minutes. Model context keeps only relevant materials and compact summaries. Repeated harvests of the same source GUID do not count as different nodes in this initial slice. A model may choose `no_action`; harvesting does not establish an obligation to sell the materials.

### Runtime Prerequisites

Rebuild/deploy the native module before expecting attribution or inventory fields. The new perception interval default and distributed config are twenty seconds; an existing installed configuration with `WmBridge.Perception.IntervalMS = 150000` must be updated through the normal operator configuration workflow. Delivery discovery requires a snapshot no older than thirty seconds and fresh character presence. No installed configuration was changed here.

Enable the existing selected-scope durable director and its DB schemas, LLM generation with the **quest** lane, gathering opportunities, and an appropriate saved apply policy. The general runtime lane defaults are not silently widened. Existing native announcement scope/policy and SOAP quest reload connectivity are required. No live IDs, rewards or quest rows have been created by this implementation.

NPC queststarter/ender relations are global world content, not private visibility for the selected GUID. The selected character receives the notice, but other eligible players may see the NPC quest. Ignored offers currently do not auto-expire or restore NPC relations; resumable event/offer lifecycle remains separate work. Author's Notes do not gain a new world/character editor in this slice.

## What Was Added

- `DeliveryQuestObjective`: `kind=deliver`, `item_entry`, `item_name`, `item_count`.
- The existing draft loader accepts this objective; old kill drafts still default to `kind=kill` without changing their JSON shape.
- The existing quest compiler writes `RequiredItemId1` / `RequiredItemCount1` and clears the first creature objective for delivery quests.
- Publisher preflight resolves the item in `item_template` and requires the item-objective columns. It rejects quest-bound items and counts exceeding an item's unique ownership limit.
- `python -m wm.quests.generate_delivery` reads existing item/NPC identities, checks the questgiver flag and persistent spawn candidates, and writes a draft artifact. It does not reserve a slot, publish, grant or change the world.
- Panel command `quests.draft_delivery` exposes generation; `workbench.publish_quest` accepts the resulting draft envelope or its inner `draft` object.
- Existing `publish_quest` event-bundle steps use the same loader and publisher, so they accept delivery drafts too.

The delivery objective itself needs no new client patch or native mechanic: core item objectives handle it. Reactive attribution and inventory sensing do require the native source changes above. A new quest still needs managed ID allocation and quest runtime synchronization.

## Generate And Publish

Choose and stage a fresh managed quest slot through the existing allocation workflow. Resolve an ordinary material and an accessible stock questgiver for the intended player. The generator checks DB identity and a spawn's existence; it does not establish faction friendliness, phase visibility or reachability for a selected player.

With `$QuestId`, `$QuestgiverEntry`, `$ItemEntry`, `$ItemCount`, `$QuestLevel` and `$TurnInDirections` set to those reviewed values:

```powershell
python -m wm.quests.generate_delivery --quest-id $QuestId --questgiver-entry $QuestgiverEntry --item-entry $ItemEntry --item-count $ItemCount --quest-level $QuestLevel --location $TurnInDirections --reward-money-copper 1000 --output-json artifacts/material-delivery.json --summary
python -m wm.quests.live_publish --draft-json artifacts/material-delivery.json --mode dry-run --summary
```

Review the draft and SQL preview. In the panel, use **Draft Material Delivery Quest**, then supply the resulting JSON to **Publish Managed Quest** and use its existing preview/confirmation flow. The CLI equivalent for an approved publication is:

```powershell
python -m wm.quests.live_publish --draft-json artifacts/material-delivery.json --mode apply --summary
```

These are operational instructions, not commands executed for this implementation. No IDs have been claimed or live rows published here.

## Objective And Turn-In Semantics

| Field | Meaning |
| --- | --- |
| `objective.kind` | `deliver`; kill and delivery fields cannot be mixed in one objective |
| `objective.item_entry` | Existing ordinary material entry |
| `objective.item_name` | Player-facing material name, resolved by the generator |
| `objective.item_count` | 1-255 units for the single supported item objective |
| `start_npc_entry`, `end_npc_entry` | Generator uses the same existing questgiver for both |
| `request_items_text` | Concrete count, item, turn-in NPC and location; includes existing-inventory and consumption information |
| `quest_description` | Narrative, separate from upper quest-log directions |

This is **delivery**, not proof of newly gathered items: already-owned materials qualify under core inventory rules. Turn-in consumes the requested quantity and uses the existing reward fields. Do not manually remove items or issue a second scripted payment on top of the quest reward.

Local core source inspected for this design:

- `ObjectMgr.cpp`: nonzero item objectives receive the delivery special flag during quest loading.
- `PlayerQuest.cpp`: item inventory checks, acceptance progress and reward-time item destruction already exist.
- Quest-bound item destruction can remove all copies; this slice deliberately excludes that category.

These are source findings, not fresh in-game proof. Bank/equipment edge cases follow core behavior and remain unproven here; the initial demonstration should use ordinary materials in bags.

## Still To Do

- Requested focused tests and a live accept -> existing-item progress -> turn-in -> quantity consumption -> reward demonstration, including the old kill-quest path.
- Native build/deployment and end-to-end reactive proof: gathering -> decision -> publication -> NPC offer -> acceptance -> turn-in -> payment, plus unchanged ordinary kill quests.
- Navigation/reputation-aware NPC accessibility, offer expiry and cleanup, longer-lived episode/visit memory and dedicated custom NPC dialogue.
- Additional item objectives, source restrictions, crafting objectives or requirements to gather after acceptance.

Track those separately in [WM Tool Capability Map](WM_TOOL_CAPABILITY_MAP.md). Do not label the general reactive gathering experience finished because this compiler primitive exists.
