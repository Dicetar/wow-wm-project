Status: DESIGN_ONLY
Last verified: 2026-05-20
Verified by: Claude
Doc type: runbook

# WM Vertical Slice — BridgeLab Runbook

## Preconditions

- BridgeLab stack up: `start-bridge-lab-all.bat` (MySQL 33307, authserver, worldserver, native watch).
- Demo character created (level-bracket appropriate, in zone 12). Note its `character_guid` (substitute for `5407` below).
- Slice tests green: `pytest tests/test_slice_demo.py tests/test_arc_runner.py tests/test_watcher.py -q`.

## Run

1. Grant the starter item to the demo character through the native bus (one `player_add_item` row):

   ```bash
   "/d/WOW/WM_BridgeLab/deps/mysql/bin/mysql.exe" --host=127.0.0.1 --port=33307 --user=acore --password=acore acore_world -e \
     "INSERT INTO wm_bridge_action_request (IdempotencyKey,PlayerGUID,ActionKind,PayloadJSON,Status,CreatedBy,RiskLevel) \
      VALUES ('onboarding.starter_item:910500:5407',5407,'player_add_item','{\"item_id\":910500,\"count\":1}','pending','wm-runbook','low');"
   ```

2. Boot the slice runtime against the live worldserver:

   ```bash
   python -m wm.cli.slice_demo --character 5407 --starter-item 910500
   ```

   The runtime opens the panel (or prints pending proposals to stdout); it
   subscribes to the bridge event spine for `quest.completed`, `kill`,
   `use_item`, `death`, `zone_change` rows tagged with `character_guid=5407`.

3. **In-client:** Log in as the demo character. Use the starter item.
   The native bridge emits `use_item` → onboarding → `wm.attention.granted` →
   b00 PINNED auto-applies → the b00 quest is published into your log via
   the existing content-release pipeline.

4. Complete the b00 quest in-game. The Arc Runner advances; the b01 OPEN
   proposal appears in the panel. **Approve it.** Complete b01.

5. At ≥ character level 2 + on completing b01, the **shadow_pulse_aura_v1**
   ability grant proposal appears. Approve it. The passive visible aura
   becomes active on the character (verify via DB row in
   `character_aura` / `acore_world.wm_bridge_event` or the visible buff).

6. Drive the Watcher: kill ~8 of one creature family in zone 12 within
   15 minutes. A `zone_kill_bounty` proposal appears at the panel.
   Approve it; complete the bounty quest in-game.

7. Continue: b02 OPEN → approve → complete → b03 PINNED auto-applies →
   defeat the finale creature → **echo_lash_v1** grant proposal →
   approve → active ability becomes available.

## Evidence to capture

- DB rows: `wm_bridge_action_request` (Status='done') for the starter
  item grant, each PINNED quest publish, each approved grant.
- `LIVE_PROOF_BACKLOG.md`: byte-identical-style log entry per Task 12 below.
- Optional: panel screenshot of the approval queue mid-run.

## Failure triage

The loop never crashes. Anything that goes wrong lands in the issues
queue (panel `/issues` view, or `rt.issues.list_open()` from a REPL).
Each entry carries `reason`, `kind`, `character_guid`, `payload`,
`provenance`. Triage between turns; rerun.
