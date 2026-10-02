Status: PARTIAL
Last reviewed: 2026-10-01
Review basis: local source and documentation inspection; no tests or runtime checks performed
Doc type: reference / feature backlog

# WM Tool Capability Map

## Product Direction

WM should notice what a player is doing, understand the surrounding world, and offer or stage an appropriate playable response. Hunting and skinning in Duskwood is one case, not a special-purpose architecture. The same tools should support mining, exploration, repeated defeats, helping strangers, dungeon preparation, player requests, and ongoing personal stories.

The execution foundation is substantial. The larger remaining gap is turning observations into an experience with real interaction, progress, consequences, and follow-up. More native verbs alone will not close that gap. Conversely, a smarter prompt cannot supply missing quest objectives or NPC interactions.

Build playable features on the existing integration. Do not replace AzerothCore modules, the native action bus, publishers, shell bank, panel, or director ledger. Do not add another harness service or make a new safety framework the next deliverable.

## How To Read This Inventory

- **Existing:** implementation was found in source; deployment and end-to-end usability are separate questions.
- **Partial:** some machinery exists, but the stated general experience is incomplete.
- **Missing:** no complete reusable path was found in the inspected owners. This does not deny isolated scripted examples.
- Current gameplay remains `PARTIAL` where the handoff records outstanding proof. This review does not upgrade any feature to gameplay `WORKING`.

An action registry declaration, schema field, operator command, and model-accessible capability are different things. In particular, new world-editing code is pending native build/deploy, and its operator tools are not automatically selected-director capabilities.

## General Tool Families

| Family | Questions or operations WM needs |
| --- | --- |
| Observe | Who is here? What did the player kill, gather, craft, use, discover, say, accept, or decline? Which actor or resource caused it? |
| Inspect | Read live location, inventory, equipment, professions, active obligations, nearby actors, spawn availability, loot sources, terrain and interaction points. |
| Interpret | Summarize an activity over time; distinguish observed facts, tentative intent, explicit requests, and Author's Notes. |
| Discover possibilities | Find appropriate enemies, materials, NPCs, objects, rewards, and already-supported mechanics instead of inventing IDs or capabilities. |
| Plan an experience | Choose no intervention, a small acknowledgement, trade, a challenge, an encounter, a quest, or a story continuation. |
| Author content | Create clear quest objectives, rewards, items, supported abilities, NPC interactions, and event recipes. |
| Stage the world | Place and control actors and objects precisely; change populations and respawn timing; connect staged content to interaction and credit. |
| Run and follow up | Respond to triggers, choices, completion, failure, departure, and expiry; remember consequences and continue accepted stories. |
| Extend mechanics | Produce a linked development task when the desired experience needs a mechanic WM cannot currently execute. |

These are tool families, not instructions to create nine new services. Extend their existing owners below.

## What Is Already Here

| Area | Existing source and owners | Actual boundary / remaining gap |
| --- | --- | --- |
| Native sensing | [Player hooks](../native_modules/mod-wm-bridge/src/wm_bridge_player_script.cpp), [event vocabulary](../src/wm/events/models.py), native context snapshots | Kill, loot, quest and other player events exist. Loot carries item/count/source information, but a dedicated skinning observation or loot-type attribution was not found in this native path. Declared event types are not proof of deployed sensing. |
| Event patterns | [Rules](../src/wm/events/rules.py), [auto bounty](../src/wm/reactive/auto_bounty.py) | Repeated hunts, bursts and area pressure already have deterministic foundations. Auto bounty uses a kill window; it is not a general interpreter of gathering, travel or player motivation. |
| World/player context | [World context](../src/wm/autoplay/world_context.py), [context builder](../src/wm/context/builder.py) | Bounded character, online presence, quests, event/chat history and native snapshots exist. A coherent inventory/equipment/profession view was not found in these decision-context builders. Saved DB position must not be confused with fresh live position. |
| Subject knowledge | [Clusters](../src/wm/subjects/clusters.py), [enrichment](../src/wm/subjects/enrichment.py) | Entry, archetype, family and local-population grouping exist. Connect them to activities; do not rebuild grouping from scratch or infer a complete activity from one entry counter. |
| Memory and progression | `src/wm/journal/`, [journey](../src/wm/character/journey.py), [memory](../src/wm/character/memory.py), `src/wm/autoplay/memory_extract.py` | Durable events, summaries, arcs, unlocks, steering and conversational memory exist. First-visit history, activity episodes, and dedicated Author's Notes need a complete integrated path. |
| Natural-language actions | [Tool manifest](../src/wm/autoplay/tools.py), `src/wm/autoplay/intent.py`, `src/wm/autoplay/service.py` | Conversation can propose enabled native intents; the May claim that chat can only talk is stale. Legacy intent execution and the narrower selected-scope director path still coexist. |
| Durable director work | [Intake](../src/wm/autoplay/director_intake.py), [work](../src/wm/autoplay/director_work.py), request/work/intake bootstrap tables | Decisions, artifacts, authorizations, effects, receipts and linked capability tasks exist. Selected-scope cutover currently centers on kill quests and `world_announce_to_player`, not the full authoring surface. Live milestone remains incomplete. |
| Quest authoring | [Quest model](../src/wm/quests/models.py), [compiler](../src/wm/quests/compiler.py), `src/wm/quests/live_publish.py`, [feasibility](../src/wm/autoplay/quest_feasibility.py) | Kill quests and host-owned kill feasibility exist. Single-material delivery now has loader/compiler/publisher and operator-generation source, untested and undeployed; see [Material Delivery Quests](MATERIAL_DELIVERY_QUESTS.md). Automatic delivery feasibility and other collect/explore/escort recipes remain incomplete. `item_entry` in a release schema alone is not objective compilation. |
| Arcs and scenes | `src/wm/arcs/`, [release](../src/wm/content/release.py), `src/wm/control/` | Arc/journey artifacts, branches and scene sequences exist. They do not yet form a general autonomous experience lifecycle driven by player choices and world triggers. |
| Managed items | `src/wm/items/`, native inventory actions | Draft, compile, publish, grant, remove and rollback foundations exist. Reusable item-use mechanics, loot distribution, vendors and crafting connections are separate capabilities. |
| Abilities and client presentation | `src/wm/abilities/`, `src/wm/spells/`, `native_modules/mod-wm-spells/` | Shells, DBC/client patch tooling, grants and native behavior implementations exist. An ability spec is not a generator of arbitrary C++ mechanics. Generic ability runtime publication still has staging limits; client-ready and server-known are distinct. |
| Actor and object control | [Native registry](../src/wm/sources/native_bridge/action_kinds.py), native creature/gameobject handlers | Spawn, speech, movement, combat and object primitives exist in varying readiness. Audit actual handler and deployment per action, not only a named contract. |
| Persistent world editing | [World tools](../src/wm/world/tools.py), native `wm_bridge_spawn_actions.cpp`, [operations](WORLD_EDITING_TOOLS.md) | New source supports exact persistent spawn creation/edit/deletion and respawn delay. Pending build/deploy. Editing loaded spawns is not a general offline world editor, density controller or NPC template creator. |
| Event bundles | [Bundle runner](../src/wm/world/bundle.py) | Ordered publications/native actions/waits with references to earlier results exist. This is a synchronous sequence, not a persistent scheduler with triggers, branches and automatic restoration. Earlier completed steps remain after a later failure. |
| NPC interaction | Native `wm_bridge_gossip_actions.cpp` | The inspected gossip handler registers close-gossip, not a complete dynamic offer/choice/menu system. Announcing a quest or spawning a friendly actor is not equivalent to an interactive buyer or mentor. |
| Operator surface | `src/wm/panel/`, `control/` | Universal session, command catalog, jobs, drafts, pending work and approvals exist. Operator availability does not imply model availability. Keep one panel flow rather than creating character-specific consoles. |
| Pacing | `src/wm/autonomy/governor.py`, runtime cooldowns/budgets | Operational throttles exist. On Demand / Moderate / Active story initiative and integrated Author's Notes are agreed product semantics, not a complete feature found in this review. |

## Needed Feature List

Stable IDs below are backlog references, not a claim that GitHub tickets were created. Implement one playable slice at a time. Each slice includes the smallest integration needed for the experience, not an advance platform-hardening project.

### Next Playable Slice: Recognize An Activity And Offer Something Useful

| ID | Needed feature | Extend existing owners | Playable completion |
| --- | --- | --- | --- |
| WM-T01 | Activate the pending world-editing tools | World tools, native spawn handlers, panel catalog | An operator places/moves a creature or object precisely and changes a spawn's respawn delay on a running server. No claim that source alone finished this. |
| WM-T02 | Profession-aware evidence and usable character inventory | Native sensing, context snapshots/builders | WM can distinguish skinning from ordinary corpse loot and see current relevant materials and profession/skill. Reuse source attribution for mining/herbalism and add other profession hooks as needed, rather than guessing from item names. |
| WM-T03 | Activity episodes and visit memory | Event rules/projector, subject clusters, journal | Summarize a hunting/gathering/travel episode across events, targets and location. Report first recorded visit versus confirmed first-ever visit honestly. Preserve facts separately from inferred purpose. |
| WM-T04 | Collection and delivery quests: single-material authoring source added, `PARTIAL` | Quest model/compiler/publisher, feasibility | Publish a quest requesting existing materials; items already in bags count under declared rules, turn-in consumes the correct amount and delivers the reward. Clear directions and native item-objective fields are implemented; testing/live proof and automatic director feasibility remain. |
| WM-T05 | Visible offers and real NPC choices | Native gossip, queststarter/ender publishing, panel | A relevant nearby NPC offers an opportunity; player can accept, decline or leave it alone. Acceptance and completion have actual interaction/credit, not just a system message. Initially reuse a suitable stock NPC before requiring arbitrary custom templates. |
| WM-T06 | Activity-to-opportunity selection | Director intake/work, context, native/content adapters | Moderate WM notices the activity and chooses one useful response, including doing nothing. Complete a material delivery or specimen hunt rather than automatically issuing another generic kill counter. |

T02-T06 now have a connected initial **PARTIAL source slice**: loot attribution, carried inventory/professions, bounded gathering episodes, single-material delivery, optional stock-NPC offers and selected-scope typed decisions. This is not deployed or live-proven. Visit memory, offer expiry, navigation-sensitive discovery and richer dialogue remain missing. T07's three initiative presets are implemented in panel/runtime source; its dedicated Author's Notes surface remains separate. See [Material Delivery Quests](MATERIAL_DELIVERY_QUESTS.md) for exact limits and rollout requirements. T01 can be delivered independently; it should not turn into a prerequisite to every stock-NPC quest.

### Broaden Playable Content

WM-T07 now also has a **PARTIAL source implementation** of Author's Notes: World/Character
editing in both panel modes, explicit Character commands in game, expiry/archive and separate
decision/draft context. It is not tested or deployed. Natural-language firmness remains
model-interpreted, not a replacement for apply policy. See [Author's Notes](AUTHORS_NOTES.md).

WM-T09 now has an initial **PARTIAL source implementation**: fresh-position scouting, template identity search/detail, direct/reference loot-source lookup, panel read commands and typed `inspect_world` natural-language reads. No concrete quests were added. Navigation, conditions, object lock requirements and live proof remain separate; see [World Ingredient Tools](WORLD_INGREDIENT_TOOLS.md).

| ID | Needed feature | Extend existing owners | Playable completion |
| --- | --- | --- | --- |
| WM-T07 | Initiative presets and Author's Notes | Panel/session, chat intake, journey/steering, governor | Set On Demand, Moderate (default), or Active. Add World/Character notes from panel and in-game, with preference/firmness. Notes affect decisions without becoming machine-inferred facts. |
| WM-T08 | More objective recipes | Quest compiler, native interaction/credit hooks, scenes | Add inspect/use/explore/talk first, then defend/survive/escort/craft and combined objectives as complete slices. Each objective has a real completion mechanism; a new enum alone is not delivery. |
| WM-T09 | Searchable world/content ingredients | Existing context, DB readers, feasibility and shell/behavior inventories | Resolve appropriate templates, loot sources, rewards, questgivers, faction hostility, population and available interaction points from current data. Query on demand rather than flooding every model call with the DB. |
| WM-T10 | Reusable NPC/object authoring | Managed content publishers, native actor/object handlers | Publish an appropriate custom questgiver or event object with model, faction, interaction and bindings. Later add vendors and targeted loot changes. Stock-template spawning remains the initial cheap path. |
| WM-T11 | Triggered, resumable event lifecycle | Bundle/scene runner, director ledger, event pump | Start an encounter on approach or interaction, react to victory/choice/failure, and finish or expire it across ticks and restart. Departure or actor death leads to a meaningful outcome. Avoid a second independent event authority. |
| WM-T12 | Local population and world transformations | Persistent spawn tools, event lifecycle | Run an infestation, migration or temporary occupation with controllable population/respawn, a reason, affected quests, and replacement or restoration. Destructive changes are allowed when the experience accounts for consequences. |
| WM-T13 | Supported item/ability recipes | Item publisher, shell bank, native spell behaviors, client patch workflow | WM can select and parameterize a known playable mechanic and grant/publish it with the correct client identity. Add missing behavior families individually; do not pretend a DBC name or generic JSON creates their logic. |
| WM-T14 | Outcomes that influence future experiences | Journal, journey, director records | Remember offered/accepted/declined/completed/failed/expired experiences and player choices; continue obligations and avoid repeating ignored offers. A kill log is not the same as narrative outcome memory. |
| WM-T15 | Capability task completion and resumption | Existing `awaiting_capability` intake and development task linkage | A coding agent receives the desired mechanic, current owners, required runtime/client changes and playable completion criteria. Once developed and available, the waiting experience can resume or be reconsidered. |

## Initiative And Memory Semantics

Use the definitions in [CONTEXT.md](../CONTEXT.md), not a new competing policy vocabulary:

- **On Demand:** observe and remember; start new unsolicited experiences only on request. Continue accepted stories, obligations and cleanup.
- **Moderate:** occasional grounded opportunities at natural breaks; silence is a legitimate result.
- **Active:** initiate more often and develop longer sequences, while still allowing refusal and avoiding repeated interruption.
- **Author's Notes:** explicit author requests, separate from event history and WM deductions. Support both input surfaces and World/Character scope.

Repeated hunting could mean gathering, leveling, practicing or simply enjoying combat. WM should use available evidence, offer a reversible choice, or ask when the distinction matters. It should not decide that one episode permanently defines the character.

## Experience Examples Using The Same Tools

| Situation | Possible response | Tools exercised |
| --- | --- | --- |
| Hunting and skinning | Nearby hide buyer, specimen request, or a hunting rival; use existing materials where appropriate | Gathering attribution, inventory, episode, delivery objective, NPC offer, outcome memory |
| Mining along a mountain route | Survey commission or a discovered blocked seam, not an unrelated kill bounty | Gathering/route episode, resource knowledge, inspect/use objective, object placement |
| Repeated defeat at one camp | Optional scouting clue, preparation request or a temporary ally | Failure history, target context, conversation, NPC/companion control, follow-up |
| Exploration without questing | Rumor, landmark encounter or no intervention | Visit memory, location trigger, low-pressure offer, initiative preset |
| Explicit request for an ambush | Stage a supported hostile encounter at an appropriate reachable location | NL intent, content discovery, placement/faction/combat, event outcome and cleanup |
| Request for a new power | Grant a suitable existing recipe, or create a mechanic development task | Capability inventory, ability/client publication, task linkage and resumption |
| Player clears a local threat | Population changes and a replacement opportunity that acknowledges the result | Shared-world editing, accepted obligations, event lifecycle, restoration/replacement |

## Delivery Order And Limits

1. Make the pending world-editing feature playable; in parallel planning, define the smallest gathering -> material delivery -> NPC offer slice.
2. Implement T02-T06 as that experience, reusing stock materials and a stock questgiver initially. Evaluate presets/notes in the same director wiring instead of introducing another decision framework.
3. Expand one objective and one event recipe at a time through T07-T12. Prefer repeated usefulness over a huge declared verb count.
4. Add reusable powers and capability resumption through T13-T15 as actual stories require them.

Do not run an LLM call on every kill or loot event. Existing deterministic event rules can maintain short activity summaries and surface meaningful changes. Feed the model bounded evidence and a small relevant set of available ingredients; host tools resolve IDs and publish through existing paths.

The next acceptance demonstration is not "a proposal was generated." It is: WM recognizes a nontrivial activity, offers a relevant optional opportunity, the player can do it, and the game delivers and remembers the outcome. Testing and live deployment are separate requested work; neither was performed for this inventory.
