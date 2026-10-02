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

Run this loop only when testing/live verification is explicitly requested.
Historical PIDs, successful doctor runs, and June deployment results do not
establish current runtime readiness.

Reusable item-use scope is separate from bridge/director mutation scope.
Enchanting Stone (910015), vellums (910007/910008), Bone Lure (910009), and
Energy Surge Potion (910014) were made usable by all characters and unbound.
Do not restore the bridge player allowlist check in their item-use handlers.
For an inactive-item report, inspect both use and follow-up handlers (including
summoned AI), item_template bonding, and existing item_instance soulbound bit 1.
The global item behavior does not authorize widening the director action bus.

1. Confirm BridgeLab runtime is the target: MySQL `127.0.0.1:33307`, SOAP `7879`, world port `8095`.
2. Confirm the player allowlist/scope before mutating game state.
3. Run a native `debug_ping` or focused status check after native rebuild/restart.
4. Use dry-run before apply unless the command is a proven release lane.
5. Capture proof through audit/event rows, native request status, DB state, and in-client observation when required.
6. Label the result `WORKING`, `PARTIAL`, `BROKEN`, or `UNKNOWN`.

## In-Game Oracle

Adapted from Universal Modder's [game-automation](https://github.com/rehan-remade/universal-modder/blob/main/skills/game-automation/SKILL.md) and [oracle field note](https://github.com/rehan-remade/universal-modder/blob/main/knowledge/techniques/oracles-how-agents-know-a-mod-works.md). Use WM's existing BridgeLab and proof tooling; `um` is not a WM dependency.

- Set up one repeatable action on the scoped test player using existing typed controls. Record the character GUID, build/version, server DBC and client patch identity when relevant, request/quest IDs, and action time.
- Check two independent oracles: server receipt plus DB/audit/event state, and the actual client result. For a player-facing change, inspect a screenshot or direct in-game observation of the relevant quest text, icon, aura, movement, damage, or message. Open and inspect captured images; merely saving one proves nothing.
- Keep server-applied and player-visible proof separate. `wm.proofs` can report `passed` from backend evidence alone; that is not permission to label player-facing gameplay `WORKING` without client evidence tied to the same player and runtime window. Record what was not observed.
- Prefer the existing native action bus and game client over a new in-game command socket. Do not add GM, raw SQL, or direct LLM mutation paths to make a test easier.
- Do not drive the user's game window while they are active without asking. If input automation is approved, confine it to the intended game window, use a stable viewport, inspect after each consequential action, and stop/clean up by exact PID. If capture or input tools are unavailable, ask for manual client proof instead of inferring it from server logs.
- Put versioned symptom -> cause -> fix findings in the existing WM status/postmortem docs. Extend a relevant note rather than creating a parallel modding journal.

## Summon And Pet Tests

Before summon or pet testing, clean the lab:

- `character_pet` rows for the test player are clean.
- `character_spell` has no stale carrier grants.
- The worldserver log is known-clean or the dirty state is noted.
- The lab worldserver has restarted after native code or config changes.
- The test character has logged in fresh after restart.

Do not touch stock Summon Voidwalker `697`, do not bind WM scripts onto stock carriers, and do not reuse retired prototype carriers as permanent release paths.
