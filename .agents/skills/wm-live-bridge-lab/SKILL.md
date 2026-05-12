---
name: wm-live-bridge-lab
description: Use for BridgeLab runtime work, native bridge watcher setup, watcher status or stop/start tasks, live proof, player scoping, auto-bounty validation, summon or pet lab cleanup, native action smoke tests, and Windows detached watcher operations in the WM project.
---

# WM Live BridgeLab

## Default Path

Use the repo-owned BridgeLab scripts. Do not hand-roll detached watcher launch code.

- One-shot lab start: `.\start-bridge-lab-all.bat`
- Native watcher only: `.\start-bridge-lab-watch.bat`
- Watcher status: `.\status-bridge-lab-watch.bat`
- Stop watcher: `.\stop-bridge-lab-watch.bat`

`start-bridge-lab-all.bat` starts lab MySQL, applies BridgeLab compatibility SQL, syncs realmlist, starts auth/world if needed, and starts a scoped watcher. Its default watcher is `auto-bounty`; pass `-Watcher native` for plain native bridge watching or `-Watcher none` for no watcher.

## Watcher Rules

- Default player is `5406`; Broug is `5405`. Keep player scope explicit.
- Start live proof from a clean window with `-ArmFromEnd` and `-MarkExistingEvaluatedOnArm`.
- Use `scripts/bridge_lab/Start-BridgeLabAutoBounty.ps1` only when intentionally testing the dynamic auto-bounty lane.
- Prefer explicit bounty templates for normal proof; do not let stale `reactive_bounty:*` rows explain new behavior.
- Logs and metadata live under `artifacts/bridge_lab_native_watch/`.
- A watcher is not started until the PID exists and the process is still alive after startup delay.

## Live-Proof Loop

1. Confirm BridgeLab runtime is the target: MySQL `127.0.0.1:33307`, SOAP `7879`, world port `8095`.
2. Confirm the player allowlist/scope before mutating game state.
3. Run a native `debug_ping` or focused status check after native rebuild/restart.
4. Use dry-run before apply unless the command is a proven release lane.
5. Capture proof through audit/event rows, native request status, DB state, and in-client observation when required.
6. Label the result `WORKING`, `PARTIAL`, `BROKEN`, or `UNKNOWN`.

## Summon And Pet Tests

Before summon or pet testing, clean the lab:

- `character_pet` rows for the test player are clean.
- `character_spell` has no stale carrier grants.
- The worldserver log is known-clean or the dirty state is noted.
- The lab worldserver has restarted after native code or config changes.
- The test character has logged in fresh after restart.

Do not touch stock Summon Voidwalker `697`, do not bind WM scripts onto stock carriers, and do not reuse retired prototype carriers as permanent release paths.
