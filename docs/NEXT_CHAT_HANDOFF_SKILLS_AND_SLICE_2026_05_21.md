Status: HANDOFF
Last verified: 2026-05-21
Verified by: Claude
Doc type: handoff

# Handoff — WM panel slice + skills catalog (2026-05-21)

Read this in full before touching anything. Then read the repo's own
current-state chain (the `wm-workflow` skill mandates it, and ignoring it cost
this session repeatedly — see "Mistakes" below):

1. `AGENTS.md`
2. `docs/README_OPERATIONS_INDEX.md`
3. `docs/WM_PLATFORM_HANDOFF.md`
4. `docs/CODEX_WORKING_RULES.md`
5. `.agents/skills/wm-workflow`, `wm-content-release`, `wm-live-bridge-lab`

---

## TL;DR

Two things shipped and pushed this session:
1. **The vertical-slice panel loop is real and live-proven** — approval-gate UI,
   aura sentinel, and genuinely-new managed quests (Blocker #2 fixed). Astel
   (5408) was marked, b00→b01 fired through the panel, and the bus granted real
   quests `Status=done`.
2. **A 28-skill pipeline catalog** under `.agents/skills/` (25 added this
   session) covering **every `implemented=True` native action** + the
   author/publish/grant/rollback tooling, validator-green.

What's still hollow is the same thing flagged all session: **the slice runs on
FIXTURE proposals — the LLM has never generated anything, and the live watcher
isn't producing content.** That's code wiring (bucket D), not docs.

Branch `main`, pushed to `origin` (`Dicetar/wow-wm-project`), head **`4b4d0b9`**.
14 commits this session (`0976e3a..4b4d0b9`).

---

## What shipped (commits, all pushed)

| Commit | What |
|---|---|
| `56497a5` | Panel approval-gate UI for the slice (Blocker #1): `/api/slice/*` routes + Slice tab + injectable factory/discoverer/pump seams + `--live-slice` |
| `a9f0673` | Panel dark mode (OS-pref default + toggle) |
| `4ca2498` | **Aura sentinel** — `BridgeEventPump` recognizes the marker aura (spell 946500) `applied` event and fires `wm.attention.granted`; `make_mysql_fetch` broadened to `aura` family; `SliceRuntime.feed_attention` |
| `f137a52` | Blocker #2 first cut — fresh managed quests (raw-SQL clone; superseded) |
| `4605add` | Blocker #2 proper — **genuinely new managed quests via `wm.quests.publish`** (910500/910501/910502), drafts in `control/examples/quest_drafts/`, raw-SQL clone removed |
| `8056b03`→`4b4d0b9` | 25 pipeline skills under `.agents/skills/` + corrections (see Skills below) |

Tests: the slice + panel suites are green (`tests/panel/test_server_slice.py`,
`test_bridge_event_pump.py`, `test_slice_demo*.py`, etc.). Pre-existing failures
remain and are NOT ours: `tests/test_cli.py` (ImportError `CATALOG`),
`tests/test_native_bridge_actions.py` + `test_native_bridge_source.py` (8 fails —
confirmed failing on clean HEAD via `git stash`).

---

## Live BridgeLab state (as of this handoff — stack is UP)

- MySQL `33307`, authserver, worldserver all running (user booted the stack;
  worldserver was restarted during the session for the marker spell + allowlist).
- Ports: MySQL `33307`, SOAP `7879`, world `8095`. `.env` defaults DB to **3306**
  (the repack) — override `WM_WORLD_DB_PORT=33307 WM_SOAP_PORT=7879` for BridgeLab.
- **Astel (guid 5408)** — online, level 6, marked for attention (aura 946500),
  on `WmBridge`/`WmSpells` allowlists (`"5406,5405,5408"`), 946500 in
  `Emit.AuraSpellAllowList`.
- **Live-proven loop**: marker event 42929 → sentinel → b00 PINNED auto-apply →
  `quest_add 910500` **`Status=done`** → injected `quest_completed` → b01 OPEN
  proposal → **approved through the panel** → `quest_add 910502` **`Status=done`**.
  Both quests are in Astel's `character_queststatus` (status 3 / incomplete).
- **Finale b03 (910501) was NOT granted** — offered, user moved on. Granting it
  needs Astel online + a poll past b02 (or a synthetic `quest_completed` for b02).
- **Panel**: run with `python -m wm.panel serve --live-slice` (was launched via
  the preview tool on `:8765`; may need restarting). Slice tab → Bootstrap
  (auto-discovers the marked char from the spine) → Poll → approve cards.

### Managed quests published this session (rollback-tracked)
`910500` "An Unfamiliar Weight" (4× Kobold Vermin / entry 6), `910502` "Echo
Ridge Investigation" (6× Young Wolf / 299), `910501` "The Watcher's Lash" (8×
Stonetusk Boar / 113). Direct-grant (`grant_mode=direct_quest_add`,
`start_npc_entry=null` → no `creature_queststarter` leak), turn in at McBride
(197). Drafts: `control/examples/quest_drafts/*.quest.json`. Reserved slots
staged→active. To reproduce on a fresh DB: publish each draft via
`wm.quests.publish --mode apply` then `.reload all quest` (see
`.agents/skills/wm-create-quest`).

---

## The skills catalog (`.agents/skills/`, 28 total, validator-green)

Run after any skill edit: `python scripts/validate_agent_skills.py`.

- **Contract skills (pre-existing, authoritative — fine skills defer to these):**
  `wm-workflow`, `wm-content-release` (tiers T1–T4, gates, ID/rollback policy,
  `CONTENT_REQUIRED_FIELDS.md`), `wm-live-bridge-lab` (runtime/scope/ports).
- **Added this session (25):** create/grant for quest/item/ability;
  create-spell-shell; build-client-patch; edit-live-quest; remove-quest;
  remove-item; spawn-creature; mark-for-attention; grant-character-state;
  announce-to-player; random-enchant-item; native-smoke-test; auto-bounty;
  build-context-pack; write-journal; run-scene; reserve-slot; reload-worldserver;
  rollback; purge-quest-range. Index + close-out in `.agents/skills/README.md`.

**Coverage line:** every `implemented=True` native action (26 of 99 registered)
now has a skill. The other 73 are bridge stubs (bucket C below).

---

## What is NOT done — the two engineering buckets

### Bucket C — native-bridge implementation (73 registered, NOT `implemented=True`)
A bus row for these sits `pending` forever. No honest skill exists until the C++
bridge implements them: **all `gameobject_*`**; quest `complete`/`complete_objective`/
`reward`/`fail`; `player_send_mail[_with_items]`/`equip_item`/`create_bound_item`/
`add_xp`/`add_title`/`add_achievement_credit`/`teleport`/`set_phase`/`set_speed`/
`resurrect`/`summon_to_location`; most `creature_*` control (movement, faction,
yell/whisper, combat, waypoints). Check `implemented=True` in
`src/wm/sources/native_bridge/action_kinds.py` before assuming anything works.

### Bucket D — slice code wiring (point #3, the actual WM value)
- **LIVE LLM**: the proposal adapter has a LIVE mode, but BOTH slice factories
  (`wm.panel.server._default_slice_factory` and
  `wm.panel.slice_wiring.make_live_slice_factory`) call
  `SliceRuntime.bootstrap(...)` **without `adapter_mode`** → defaults to
  `AdapterMode.FIXTURE`. Every "OPEN" proposal so far is canned. Flip to LIVE +
  confirm **LM Studio** is running (:1234 was NOT answering this session).
- **Live watcher generation**: `wm-auto-bounty` / `Start-BridgeLabAutoBounty.ps1`
  runs the watcher, but its proposals also go through the FIXTURE adapter until
  the LIVE flip. (I started the stack with `-Watcher none` this session.)
- **Scene compiler → bus**: `slice_demo_live.live_scene` is record-only; real
  scene execution isn't wired.

---

## Mistakes made repeatedly this session (do NOT repeat)

The single root cause behind every correction: **producing from inference instead
of reading what the repo already encodes.** Three "ULTRATHINK rechecks" each found
errors of this kind:
1. **Hand-rolled SQL instead of the pipeline** — cloned stock quests as "managed"
   content. Fix: use `wm.quests.publish` / `wm.items.live_publish` /
   `wm.spells.*`; never hand-write `quest_template`/`item_template`/`spell_dbc`.
2. **Missed the `PlayerGuidAllowList` gate** — grants silently no-op for
   non-allow-listed GUIDs; the list is read at worldserver **startup** (restart to
   change). `WmSpells.PlayerGuidAllowList` too for auras/spells.
3. **Assumed actions work** — ~73 of 99 native actions are registered stubs.
   Always check `implemented=True`.
4. **Wrong skill location** — put skills in `.claude/skills/`; the repo standard is
   `.agents/skills/` with `scripts/validate_agent_skills.py`.
5. **Wrong reload forms** — it's `.reload all quest` / `.reload all item` /
   `.reload all spell`; **spells/`Spell.dbc` need a RESTART**, not reload.
6. **Ignored canonical wrappers** — `scripts/bridge_lab/*.ps1` set ports, back up
   files, handle `-WaitForPlayerOnline`. Prefer them over raw module calls.

The antidote is literally the `wm-workflow` skill's opening: read the current-state
chain FIRST.

---

## Recommended next-session order

1. Read this + the current-state chain + `.agents/skills/README.md`.
2. **Wire LIVE LLM (bucket D)** — the highest-value remaining work. Confirm LM
   Studio is up with a model; add an `adapter_mode` seam to the slice factories
   (panel `--live-slice` flag or panel LLM settings) so OPEN beats + watcher
   proposals actually call the model; TDD it; live-prove one LLM-generated
   proposal approved through the panel.
3. Run the **watcher live** (`wm-auto-bounty`, not `-Watcher none`) and prove one
   reactive bounty generated from real kills.
4. Optional: grant the **b03 finale (910501)** to Astel to complete the in-engine
   arc; record in `docs/LIVE_PROOF_BACKLOG.md` (currently PARTIAL).
5. Bucket C native-bridge actions only if a specific capability is needed.

---

## Cleanup / state notes

- Synthetic `wm_bridge_event` rows injected for proofs were deleted
  (`Source='wm-liveproof'`). Slice action rows tagged `CreatedBy='wm-slice'`
  remain as proof; clean with `DELETE FROM wm_bridge_action_request WHERE
  CreatedBy='wm-slice';` if needed.
- Preview/dev `.claude/launch.json` (and `D:\WOW\.claude/launch.json`) exist for
  the preview tool — untracked, not committed.
- Untracked pre-existing files (not ours, leave alone): `.superpowers/`,
  `docs/superpowers/plans/2026-05-18-*`, `sql/bootstrap/wm_ability_tables.sql`,
  `src/wm/abilities/{__init__,models,tracker}.py`, `tests/test_ability_effect_tracker.py`.

## Repo state at handoff
- Branch `main`; HEAD `4b4d0b9`; pushed (`origin/main` == `4b4d0b9`).
- `python scripts/validate_agent_skills.py` → OK.
- Working tree: clean except the pre-existing untracked files above.

End of handoff.
