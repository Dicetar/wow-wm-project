Status: PARTIAL
Last verified: 2026-05-22
Verified by: Claude
Doc type: status

# Live Proof Backlog

Repo/build/API proof and gameplay proof are separate. A lane can be repo `WORKING` while gameplay remains `PARTIAL`.

This sprint does not require in-game proof. It defines the proof packets that must be run later before the project claims player-facing `WORKING` status.

## 1. Panel-Driven Content Dry-Run And Packet Flow

Status: `WORKING` for explicit-GUID API/control-plane proof; marker-selection UI remains `PARTIAL`

Prerequisite state:

- Panel starts with `python -m wm.panel --host 127.0.0.1 --port 8765`.
- LM Studio is optional for this proof; a human form payload is enough.
- `.wm-bootstrap/state/control-panel/settings.json` is preserved.

Command sequence:

```powershell
python -m wm.panel --host 127.0.0.1 --port 8765
```

Use the panel API or GUI to:

```text
validate managed item or repeatable bounty payload
run content.release.plan dry-run
run content.release.packet dry-run
write or inspect packet artifacts
do not apply
```

In-client observation needed:

- None for this gate.

Audit/event/DB evidence required:

- Panel job reaches `AWAITING_CONFIRM` or `DRY_RUN_PASSED`.
- Packet output exists under panel job state or the requested artifact directory.
- No direct LLM apply path is used.

Rollback/cleanup command:

```powershell
python scripts/cleanup_workspace.py
```

Use `--apply` only after reviewing the dry-run target list.

## 1A. Universal WM Session Panel Loop

Status: `PARTIAL`

Prerequisite state:

- BridgeLab is running.
- `python -m wm.doctor --summary` reports DB/SOAP reachable and either a
  scoped native bridge config or an actionable `UNKNOWN` config detail.
- A target character is online.
- Marker aura `946602` (`WM Watcher Beacon`) is available, or the operator has
  an explicit player GUID.

Command sequence:

```powershell
start-bridge-lab-all.bat
$env:WM_WORLD_DB_PORT="33307"; $env:WM_CHAR_DB_PORT="33307"; $env:WM_SOAP_PORT="7879"
python -m wm.doctor --summary
python -m wm.panel --host 127.0.0.1 --port 8765 --live-slice
```

Use the panel to:

```text
scan marker candidates with spell 946602 or enter explicit GUID
bootstrap WM Session
dry-run marker.scope_latest, then apply with job-id confirmation
run native.queue.inspect for the selected GUID
dry-run and apply a low-risk debug_ping control proposal
```

In-client observation needed:

- None beyond confirming the selected character is the intended online
  character; `debug_ping` is a control-plane proof, not gameplay content.

Audit/event/DB evidence required:

- Panel session shows `source=marker` or `source=explicit_guid`.
- Native bridge player scope includes the selected GUID with a TTL.
- Native queue inspect uses the selected GUID, not a hardcoded fixture.
- `debug_ping` action request reaches `done` with a `pong` result.

Rollback/cleanup command:

```powershell
python -m wm.sources.native_bridge.configure --clear --reload-via-soap --summary
```

Proof note 2026-05-23 (Codex):

- BridgeLab doctor with DB `33307` and SOAP `7879` was all `WORKING`.
- Recent marker scan for `946602` found no candidates, so proof used explicit
  GUID `5406`.
- Panel API bootstrapped `/api/wm/session/bootstrap` for `5406`.
- Panel job `job-20260522221357-59927577` dry-ran `control.apply`, reached
  `AWAITING_CONFIRM`, then approved apply with type-job-id confirmation.
- Native request `702` completed `debug_ping` with `status=done`,
  `player_guid=5406`, `error=None`.
- Browser visual smoke is still `PARTIAL`: Codex in-app browser refused local
  navigation to `127.0.0.1:8766` under its security policy.

## 2. Auto-Bounty Loop

Status: `PARTIAL`

Prerequisite state:

- BridgeLab is running.
- Validation player is online and scoped.
- Old bounty rules for the player are intentionally cleared or an explicit template is installed.

Command sequence:

```powershell
start-bridge-lab-all.bat
python -m wm.reactive.auto_bounty --player-guid 5406 --deactivate-existing-bounty-rules --summary
scripts/bridge_lab/Start-BridgeLabAutoBounty.ps1
```

In-client observation needed:

- Kill the same eligible creature entry enough times to trigger the configured bounty lane.
- Accept or receive the generated bounty.
- Complete, turn in, observe reward, wait cooldown, and prove regrant or suppression behavior.

Audit/event/DB evidence required:

- Native bridge kill events.
- WM dynamic rule/proposal records.
- Native `quest_add` request reaches `done`.
- `wm.control.audit` shows the grant path.
- Quest active/complete/rewarded state is visible through GM status, DB rows, or native quest events.

Rollback/cleanup command:

```powershell
python -m wm.reactive.auto_bounty --player-guid 5406 --deactivate-existing-bounty-rules --summary
```

## 3. Generic Release Packets

Status: `PARTIAL`

Prerequisite state:

- Release spec validates with `wm.content.release`.
- Fresh visible IDs are reserved where the schema requires them.

Command sequence:

```powershell
python -m wm.content.release <spec.json> --plan --summary
python -m wm.content.release <spec.json> --packet --summary
python -m wm.content.release <spec.json> --write-packet-dir <packet-dir> --summary
```

In-client observation needed:

- Lane-specific. Quest packets need quest log/reward-panel proof. Item packets need tooltip/equip/use proof. Spell packets need client/server DBC and spellbook/action proof. Scene packets need visible action proof.

Audit/event/DB evidence required:

- Packet manifest and proof checklist.
- Generated artifacts are reviewed.
- Apply uses an owned publisher/control/workbench/journey/rollback CLI, not the release validator directly.

Rollback/cleanup command:

```text
Use the rollback command printed in the packet proof checklist.
```

## 4. Spell Lifecycle

Status: `PARTIAL`

Prerequisite state:

- Client patch is installed.
- Server `Spell.dbc` is staged.
- Worldserver restarted after DBC/native changes.
- Player has no stale carrier grants.

Command sequence:

```powershell
python -m wm.spells.publish <spell-spec.json> --mode dry-run --summary
python -m wm.spells.live_publish <spell-spec.json> --mode dry-run --summary
python -m wm.spells.rollback --spell-id <spell-id> --mode dry-run --summary
```

In-client observation needed:

- Spellbook visibility when expected.
- Tooltip/icon/cast UX.
- Action bar and relog persistence if the spell is player-facing.
- Native behavior and visible state match the contract.

Audit/event/DB evidence required:

- `wm_spell_shell`, `wm_spell_behavior`, and `wm_spell_grant` rows as applicable.
- `character_spell` row appears or is absent according to the grant contract.
- Native debug/audit events show behavior execution.

Rollback/cleanup command:

```powershell
python -m wm.spells.rollback --spell-id <spell-id> --mode apply --summary
```

## 5. Bonebound And Broug Remaining Checks

Status: `PARTIAL`

Prerequisite state:

- Lab pet/summon state is cleaned before tests.
- Broug/Jecia player scopes and allowlists are current.
- Client is restarted after patch changes.

Command sequence:

```powershell
start-bridge-lab-all.bat
python -m wm.spells.shell_audit --spell-id <spell-id> --summary
python -m wm.live.proof_packet --arc <arc-key> --summary
```

In-client observation needed:

- Bonebound: stock Voidwalker `697` stays stock, Alpha shell summons Alpha, echo restore survives mount/dismount, Demonology assumptions are checked explicitly.
- Broug: Silent Meridian kill-window refund, Empty Court quest chain, Qi Reversal cleanse/anti-reapply, Domain pulses, Predator heal, Vitality kill sustain, and no guard/Vulnerable regression.

Audit/event/DB evidence required:

- Relevant `wm_broug_*` counters.
- Native bridge pings/actions.
- Spell grant rows and quest completion rows.

Rollback/cleanup command:

```text
Use the lane-specific rollback, ungrant, or lab cleanup command printed by the proof packet.
```

## 6. AoE Loot

Status: `PARTIAL`

Prerequisite state:

- BridgeLab module is built and enabled.
- Worldserver is running the build that includes `mod-aoe-loot`.

Command sequence:

```powershell
start-bridge-lab-all.bat
```

In-client observation needed:

- `.aoeloot on/off` works if the module exposes the command.
- Nearby corpse loot merges at the configured range.
- Normal loot remains unaffected when disabled.

Audit/event/DB evidence required:

- Module config is loaded.
- `module_string` contains `mod-aoe-loot` rows.
- Native ping proves the expected worldserver is running.

Rollback/cleanup command:

```text
Disable the module config or revert the BridgeLab module link, then rebuild/restart BridgeLab.
```

## 7. Solo Dungeon Tuning

Status: `PARTIAL`

Prerequisite state:

- BridgeLab runtime config contains the solo dungeon AutoBalance/SoloLFG/DynamicLootRates values.
- A solo test character can enter the selected dungeon.

Command sequence:

```powershell
start-bridge-lab-all.bat
```

In-client observation needed:

- Solo dungeon enemy health, damage, XP, and loot feel match the intended tuning.
- No broad outdoor/world tuning regression appears.

Audit/event/DB evidence required:

- Active config values recorded.
- Worldserver pid/build noted.
- Loot/XP observations captured.

Rollback/cleanup command:

```text
Restore previous BridgeLab runtime config and restart worldserver.
```

## Phase 0 — Native Consolidation Refactor Proofs

### 0B. Unified JSON Layer — IN-ENGINE PROOF: `WORKING`

Verified: 2026-05-19 (Claude). BridgeLab worldserver pid 36488,
MySQL 8.4.7 :33307, modules relinked with `wm_bridge_json`.

Method: enqueued two `wm_bridge_action_request` rows for player 5406.

- `debug_ping` → ResultJSON
  `{"ok":true,"action_kind":"debug_ping","message":"pong"}`
  (baseline result shape unchanged).
- `debug_echo` payload `{"note":"café-Ωμ-ÆØ"}` → ResultJSON
  `{"ok":true,"action_kind":"debug_echo","payload_json":"{\"note\":\"café-Ωμ-ÆØ\"}"}`.
  HEX of payload bytes: `...636166 C3A9 2D CEA9 CEBC 2D C386 C398 ...`
  — every multi-byte UTF-8 sequence (é Ω μ Æ Ø) intact.

Pre-refactor, `action_queue.cpp` `EscapeForJson` iterated signed
`char`; every byte >=0x80 hit `ch < 0x20` and became `0x20` (space),
corrupting all non-ASCII in result JSON. The unified canonical escaper
(common.cpp-derived, unsigned-char) preserves them. Documented bugfix
confirmed in the live engine; normal result JSON otherwise identical.

Standalone harness: 20/20 (`build_standalone.ps1`). Real-engine
`modules` build: 0 errors.

### 0C. Table-Driven Action Dispatch — IN-ENGINE PROOF: `WORKING`

Verified: 2026-05-19 (Claude). BridgeLab worldserver pid 4388
(relinked, timestamp-verified deploy). 309-line if-chain replaced by
O(1) ActionRegistry; 8 inline bodies extracted to uniform handlers.

Matrix (player 5406):
- `debug_ping` -> `{"ok":true,"action_kind":"debug_ping","message":"pong"}`
  (extracted handler, registry-dispatched; byte-identical).
- `debug_echo` `{"u":"café-Ωμ"}` -> payload_json round-trips intact
  (extraction + JSON fix both hold through new path).
- `totally_unknown_kind` -> rejected `missing_action_policy` — policy
  pre-check still gates before dispatch (ordering preserved).
- `player_apply_aura` (Jecia offline) -> failed `player_not_online`
  (delegated handler dispatches identically to pre-refactor).

Standalone: 26/26 (incl. 6 ActionRegistry cases). Real-engine
modules build: 0 errors. not_implemented fallback line unchanged;
Find()->nullptr path unit-tested.

### 0D. action_queue Decomposition — IN-ENGINE PROOF: `WORKING`

Verified: 2026-05-19 (Claude). BridgeLab worldserver pid 30152
(relinked, timestamp-verified deploy). 26 handlers + 43 defs moved out
of the monolith into 6 domain TUs + wm_bridge_action_support
(WmBridge::detail); `wm_bridge_action_queue.cpp` 2587 -> 190 lines
(poll/claim/dispatch + registry bootstrap only).

Matrix (player 5406, CreatedBy non-llm so handler bodies execute),
9 actions across all 6 domains, diffed byte-for-byte against the
pre-0D baseline captured from the 0C binary:
- debug: debug_ping -> pong; debug_fail -> debug_fail_requested;
  debug_echo with UTF-8 (snowman + accents) -> payload round-trips
  intact (0B JSON fix holds through the new debug TU path).
- player: player_add_money -> failed player_not_online (scoped).
- inventory: player_add_item -> failed player_not_online.
- quest: quest_add -> failed player_not_online.
- creature: creature_despawn -> failed player_not_online (scoped JSON).
- environment: context_snapshot_request, world_announce_to_player ->
  failed player_not_online.
Result: IDENTICAL across all 9 (artifacts/phase0d/pre0d.txt vs
post0d_all.txt). modules + worldserver build: 0 errors. diff -rq
BridgeLab <-> native_modules: clean.

Note: 0D.2-0D.4 were verified and committed as one bundled,
fully-proven commit (single build + comprehensive 6-domain live-proof
as the gate) rather than six per-domain cycles — the user
deprioritized strict per-domain cadence; all plan deliverables
(queue <400 ln, handlers in domain files, byte-identical behavior,
tree parity) are met and proven.

#### 0D deep-proof addendum (2026-05-19, Jecia 5406 online)

Closes the "seam-only" gap in the 0D matrix. With Jecia in-world,
real SUCCESSFUL mutations driven through the post-0D split + include-trim
binary (pid 22412):
- `player_add_money {amount:1234}` -> done; `characters.money` delta
  exactly +1234 (33672334 -> 33673568).
- `player_add_item {item_id:2589,count:3}` -> done; linen cloth 0 -> 3
  in character_inventory/item_instance.
Both via wm_bridge_player_actions.cpp / wm_bridge_inventory_actions.cpp
+ WmBridge::detail, exercising the rich ActionResultJson field path
(item_id/count/copper/player_guid). Proof script:
scripts/phase0/deepproof_0d.sh.

Environment TU success path (same session): context_snapshot_request
{context_kind:nearby,radius:25} -> done "context_snapshot_written";
wm_bridge_context_snapshot row written (schema wm.bridge_context_
snapshot.v1, player_name Jecia, live zone 41) — proves
BuildNearbyContextSnapshotJson + WriteContextSnapshot + cell/grid
search in wm_bridge_environment_actions.cpp. Net 0D coverage: player +
inventory + environment SUCCESS paths (real deltas) + 6-domain
seam/rejection matrix + debug success. Decomposition fully verified.

### 0E.3 + 0E.1 — wm_spell_internal extract + characterization: `WORKING`

Verified 2026-05-19 (Claude). The 5 SHARED JSON config extractors
(ExtractJsonString/UInt/Float/Bool/UIntArray — the only cross-family
logic, used by Bonebound/Broug/Core/Lanathel/Proficiency builders)
moved verbatim from wm_spell_runtime.cpp's anon namespace into
wm_spell_internal.{h,cpp} (WmSpells::detail). Monolith 8381 -> 8324 ln;
includes the header + `using namespace WmSpells::detail;` so all
callers resolve unchanged. modules + worldserver build: 0 errors;
binary deployed (pid 23652).

0E.1 characterization: new standalone wm_spell_unit_tests (0A harness
pattern, scripts/phase0 cl.exe build) — 17/17 PASS over a fixed
input matrix (present/absent, whitespace, negative-clamps-to-0,
decimal-vs-int, arrays). This is the regression net for the 0E.4
family moves and proves the extraction byte-behaviour. In-game shell-
cast live-proof deferred (no char online at extract time); the move is
verbatim pure regex with the standalone net + the existing Python
suite as cover, and will be exercised by the 0E.4 per-family casts.

### WM Vertical Slice — IN-ENGINE PROOF: `PARTIAL` (awaiting live run)

Planned 2026-05-20 (Claude). Slice runtime, 3 new schemas, demo content,
2 ability specs, 10 reactive templates, all landed in commits per the
[2026-05-20-wm-vertical-slice plan](superpowers/plans/2026-05-20-wm-vertical-slice.md);
41/41 unit + integration tests green
(`pytest tests/test_{story_module_schema,reactive_template_schema,ability_schema,demo_data_loads,ability_grant_compiler,proposal_adapter,approval_gate,arc_runner,watcher,onboarding_starter_item,slice_demo}.py`).
Awaiting live BridgeLab run per
[WM_VERTICAL_SLICE_RUNBOOK.md](WM_VERTICAL_SLICE_RUNBOOK.md): one new
character → b00 PINNED auto-apply → b01 OPEN approve → grant 1 →
zone_kill_bounty Watcher fire + approve → b02 OPEN approve → b03 PINNED
auto-apply → grant 2. Evidence: action-request rows + visible buffs +
in-client quest log.

## Phase — Slice LIVE-LLM Quest Pipeline (2026-05-22)

Status: repo/unit `WORKING`, gameplay `PARTIAL` (UNPROVEN this session)

The panel `--live-slice` arc OPEN beat now generates a kill-bounty quest draft
via LM Studio, screens + validates it, and on **panel approval** publishes it
through `QuestPublisher` (fresh reserved id) + reloads + grants. Full suite
green; LM Studio reachable with the default model. Watcher (reactive) LIVE
generation is intentionally NOT wired (parks with an actionable reason).

Awaiting live BridgeLab run (DB `33307` / SOAP `7879`, marked character online).
Proof packet:

```text
1. python -m wm.panel serve --live-slice   (LM Studio up; stack up)
2. Slice tab -> Bootstrap -> Poll -> drive the b01 OPEN beat
3. Phase 1: OPEN card shows LLM-authored prose, provenance mode=live;
   SELECT ID FROM quest_template WHERE ID >= 910600  -> still empty (no mint)
4. Phase 2: approve the card; verify quest_template row (>=910600), reserved
   slot flipped active, character_queststatus row for the player, and
   wm_publish_log 'success' + wm_rollback_snapshot rows.
```

Design + plan:
[slice LIVE-LLM design](superpowers/specs/2026-05-22-slice-live-llm-quest-pipeline-design.md),
[implementation plan](superpowers/plans/2026-05-22-slice-live-llm-quest-pipeline.md).

## Next live-proof pass — one ordered BridgeLab session (2026-05-22)

Several lanes are repo/unit `WORKING` but gameplay `UNPROVEN` because BridgeLab
was down. This is the single ordered pass that converts the stack to proven (or
surfaces regressions). Do NOT move any lane to gameplay `WORKING` until its step
passes. Operator action gates everything.

**Step 0 — bring the stack up (operator):**
```powershell
start-bridge-lab-all.bat
$env:WM_WORLD_DB_PORT="33307"; $env:WM_CHAR_DB_PORT="33307"; $env:WM_SOAP_PORT="7879"
python -m wm.doctor --summary   # must be green on 33307/7879 before continuing
```
Gate: world_db + char_db + soap all `WORKING`. If not, stop and fix readiness first.

**Step 1 — Universal Panel marker selection + character view (V1 + V2.1):**
- In-game, mark the target character with marker aura `946602`.
- `python -m wm.panel serve --live-slice` → WM Session tab → Bootstrap (must discover the marked GUID, not a hardcoded one) → confirm the **Character** card shows that GUID's status/counts/readiness.
- Pass: `/api/wm/markers` lists the `946602` bearer; bootstrap selects it; `/api/wm/session/overview` returns real journey/state for the **discovered** GUID. Moves V1 marker-selection + V2.1 view from `PARTIAL` → `WORKING`.

**Step 2 — Slice LIVE-LLM arc loop (Phase 1 + 2):** run the "Slice LIVE-LLM Quest Pipeline" packet above (LM Studio up; b01 OPEN → generate → approve → mint ≥910600 → grant). Watcher LIVE stays parked.

**Step 3 — Energy Surge buff timer (DBC truth):** use item `910014`; confirm aura `946606` shows a **countdown timer** on the buff icon in-client. If no timer, that confirms the repo-side `shell_audit` warning (no `duration_index`) is a real client gap → add `duration_index` to `946606` in client + server DBC, refresh, re-prove.

**Step 4 — Broug regression canary:** log in Broug (`5405`); confirm Lightness + Empty Court abilities cast with correct icons/tooltips/cooldowns/auras (spell-shell/DBC/scoped-grant canary).

Record outcomes here with hard labels. Only after a step passes does its lane earn gameplay `WORKING`.

### Outcomes — 2026-05-22 pass (BridgeLab up, 33307/7879)

- **Step 0 readiness:** `WORKING`. `wm.doctor --summary` → 8/8, 0 FAIL (world/char DB + SOAP on 33307/7879; native bridge scoped to 5405,5406,5408).
- **Step 1 character view + selection:** `WORKING` (read-side + bootstrap selection).
  - Live `build_character_overview` against the real char DB: guid 5406 `status=WORKING has_profile=True` (11 arc_states / 2 unlocks / 3 rewards / 5 steering / 3 prompt_queue); guid 5405 `WORKING` (2/2/2/3/1); guid 5408 `PARTIAL` (no profile/journey). Real per-character state for any scoped GUID — V2.1 read-side is gameplay-`WORKING`.
  - Bootstrap discoverer selected GUID **5405 from the marker spine** (discovered, not hardcoded).
  - Marker *candidate list* (`/api/wm/markers` source): `PARTIAL` — 0 recent/online candidates (historical 946602 marks are for an offline/stale Broug). Needs a freshly-marked **online** character to prove the candidate UI.
- **Step 2 slice LIVE-LLM loop:** run 2026-05-22 (LM Studio up, Astel 5408 marked + online).
  - **Phase 1 (LLM generation): `WORKING`.** LIVE adapter + `qwen3-coder-30b-a3b-instruct` generated a screened, validated quest ("The Watcher's Mark", kill 1× Young Wolf 299) for guid 5408; fixed facts (target/giver/grant_mode) from constraints, LLM authored prose + kill_count; `is_blocked=False`, `mode=live`.
  - **Model finding:** the loaded `qwen3.5-9b-uncensored-hauhaucs-aggressive` returns **empty content** under strict `json_schema` (RP/thinking model) → blocked. An instruct/coder model is required. Recommend pinning an instruct model for the slice (panel LM Studio setting / default).
  - **Phase 2 mint/publish: `WORKING`.** `SlicePublishService.publish_and_grant` minted `quest_template` 910213 (`"The Watcher's Mark"`, RequiredNpcOrGo1=299 count 1), flipped reserved slot 910213 `active` (CharacterGUID 5408, notes `slice:b01_zone_intro`), `wm_publish_log` `success`, `.reload all quest` ok.
  - **Phase 2 grant persistence: `PARTIAL`.** Bridge `quest_add` (RequestID 703) ran with `{"ok":true,"message":"quest_added"}`, Astel online — but no `character_queststatus` row after `.saveall`. Matches the documented caveat (`wm-create-quest`): a freshly published quest needs a **worldserver restart** to be fully grantable (reload alone isn't enough). Next: restart BridgeLab worldserver, re-grant 910213 to 5408, re-verify the quest-log row + in-client.
- **Step 3 Energy Surge timer:** not run — in-client visual (operator).
- **Step 4 Broug canary:** not run — in-client visual (operator).

**Operator actions to finish the pass:** (1) start LM Studio (unblocks Step 2); (2) cast `946602` on an **online** character (proves the marker candidate UI). In-client visuals (Steps 3-4) need eyes on the game client.
