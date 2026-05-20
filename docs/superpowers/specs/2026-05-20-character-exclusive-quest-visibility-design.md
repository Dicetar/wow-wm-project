Status: DESIGN_ONLY
Last verified: 2026-05-20
Verified by: Claude
Doc type: design

# Character-Exclusive Quest Visibility — Design

## Problem (observed 2026-05-20)

Astel (level 1, fresh char, NOT the Broug-arc owner) talked to Marshal
McBride in Northshire and was offered quest **910180 "Broug: One
Thousand Impossible Guards"** and **910181 "Broug: One Thousand
Deflections"** — quests authored as personal Broug-arc content.

Root cause: AzerothCore's `creature_queststarter` is a *global* "this
NPC offers this quest" registry. It has no per-character column. The
existing Broug arc publish step wrote rows `(creature=197, quest=910180)`
and `(creature=197, quest=910181)` into it. AC's standard gates
(`quest_template_addon.AllowableRaces/Classes`, `MinLevel`, `PrevQuestId`)
don't include "owner character", so McBride offers the quest to anyone
who meets those standard criteria. The "Broug:" title prefix is
cosmetic.

**Architectural mismatch** with Roadmap Track 1 (Personal Journey
Spine) exit criterion:
> *"player isolation so broadcasts, drops, rewards, and unlocks never
> leak from the active WM character to others"*

This is a leak.

## What the project already has (and doesn't)

Has:
- `wm_bridge_player_scope` (PlayerGUID + Profile + Enabled) — used by
  the post-0D `WmBridge::IsPlayerGuidAllowed` to gate **action execution**.
- `WmBridge.PlayerGuidAllowList` config + native `IsPlayerAllowed` check
  inside bridge action handlers.
- `mod-wm-bridge` script registrations for various scripts, but **none**
  intercepting quest offer / accept (verified by grep:
  `OnGossipHello | OnCanTakeQuest | OnQuestAccept | CanTakeQuest |
  quest_filter` returns zero matches in `native_modules/mod-wm-bridge/src`).

Does not have:
- A native hook that filters McBride's rendered offer list, or rejects
  `OnCanTakeQuest` for non-owners.
- A per-quest ownership table.

## Two clean fixes (this design picks #2; #1 is a complementary content rule)

### Fix #1 — Don't write managed quests to `creature_queststarter`

Managed personal quests are direct-grant content, not world content.
The bridge's `quest_add` action (post-0D, in `wm_bridge_quest_actions.cpp`)
calls `Player::AddQuestAndCheckCompletion` directly — the player gets
the quest in their log regardless of any NPC offer list. The vertical
slice I just built uses this path and **cannot leak by construction**.

The Broug arc's existing publish step writes those NPC rows; that's the
generator that needs to stop doing so for personal content. Until it
does, the leak persists.

**Rule (new):** the content-release pipeline MUST NOT write
`creature_queststarter` or `creature_questender` rows for managed
personal quests (those in the 91xxxx / personal-arc id range). Direct
grant + (if needed) a one-shot turn-in via the bridge's quest_remove
or a managed scene.

**Cleanup task:** drop the existing leaky rows:
```sql
DELETE FROM creature_queststarter WHERE quest IN (910180, 910181);
DELETE FROM creature_questender   WHERE quest IN (910180, 910181);
-- and any other personal arc quests where the same was done
```

### Fix #2 — Defense-in-depth: native filter hook

Even with Fix #1, operator mistakes happen. Add a native hook that gates
at the engine level so personal quests can never leak even if the
content table has a stray row.

**New script** in `mod-wm-bridge`:
`wm_bridge_quest_visibility.cpp` — a `PlayerScript` with:
- `bool OnPlayerCanTakeQuest(Player* player, Quest const* quest)` →
  return false (suppresses offer/accept) when:
  - `quest->GetQuestId()` is in the managed range (91xxxx OR explicitly
    listed in a new `wm_managed_quest_owner` table), AND
  - the quest is **not** owned by this player (per
    `wm_managed_quest_owner.player_guid` OR `wm_bridge_player_scope`
    profile lookup).

Optionally also override `OnCreatureGossipHello` for managed-quest-giver
NPCs to omit the "!" icon entirely — but a simple `OnCanTakeQuest`
suffices for correctness; the gossip cosmetics are polish.

**New table** `wm_managed_quest_owner`:
```sql
CREATE TABLE wm_managed_quest_owner (
    quest_id   INT UNSIGNED NOT NULL,
    player_guid INT UNSIGNED NOT NULL,
    arc_id     VARCHAR(128) NULL,
    granted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (quest_id, player_guid),
    KEY idx_player (player_guid)
);
```
The bridge's `quest_add` action writes this row when the grant succeeds;
the visibility hook reads it.

## Slice impact

The WM vertical slice (this branch) already uses direct-grant via the
bridge's `quest_add` action. It is **not affected** by the leak. It
inserts no `creature_queststarter` rows; quests appear in the active
character's log only.

## Scope

In:
- Drop the leaky Broug arc rows from `creature_queststarter` /
  `creature_questender` (one-time SQL).
- Create `wm_managed_quest_owner` table.
- Add `wm_bridge_quest_visibility.cpp` PlayerScript with
  `OnPlayerCanTakeQuest` hook reading the new table.
- Wire `quest_add` action to write `wm_managed_quest_owner` after
  successful grant.
- Authoring rule: managed personal quests are direct-grant only;
  publish path MUST NOT write `creature_queststarter`. Add a check to
  `wm.content.release` / publish path to reject specs that try.
- One live-proof on BridgeLab: Astel logs in, talks to McBride, does
  NOT see 910180/910181. Jecia (or whichever char is in
  `wm_managed_quest_owner` for these quests) logs in, talks to McBride
  if a row remains, OR receives the quest via direct grant.

Out:
- Refactoring the existing Broug arc publish path itself (separate
  follow-up; this design ships the defense-in-depth so further leaks
  can't ship).
- Per-account (vs. per-character) ownership semantics (defer until a
  real ask appears).

## Test plan

1. Unit (Python): `wm_managed_quest_owner` table schema migration test.
2. Native standalone (post-0A pattern): the `OnPlayerCanTakeQuest`
   filter logic with a fake quest+player+table-lookup stub.
3. Live BridgeLab:
   - Insert one `wm_managed_quest_owner` row for (quest=910180,
     player_guid=5407).
   - Astel (5408 or new char): McBride does NOT offer 910180.
   - Astel attempts to accept 910180 via `gossip_select` if the icon
     somehow shows: rejected.
   - Jecia (5407, owner): McBride DOES offer 910180.

## Open follow-ups (post-fix)

- A migration helper that scans all existing `creature_queststarter` /
  `creature_questender` rows for quests in the managed range and either
  (a) deletes them, or (b) flips them to direct-grant via the bridge.
- A panel view showing managed quests + their owners.
- Audit the existing Broug arc publish to use the slice's direct-grant
  pattern.
