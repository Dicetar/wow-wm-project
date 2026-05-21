---
name: wm-auto-bounty
description: Run the reactive watcher / auto-bounty lane so the WM generates bounty quests from a player's live kill activity. Use this WHENEVER you want dynamic reactive content (the Watcher) actually running against BridgeLab, or to validate the auto-bounty loop. Triggers: "run the watcher", "start auto-bounty", "generate bounties from kills", "turn on the reactive lane", "the watcher isn't running". This is the reactive half of the slice (point #3); the arc half is wm-grant-quest + the panel approval gate.
---

# Run the watcher / auto-bounty lane

The reactive content loop watches the event spine for patterns (e.g. repeated
kills) and proposes bounty quests. On BridgeLab it runs as a detached watcher via
the repo-owned script — **do not hand-roll the launch** (per wm-live-bridge-lab).

## Start it
```powershell
powershell -File scripts/bridge_lab/Start-BridgeLabAutoBounty.ps1 `
  -PlayerGuid 5408 -Mode apply -LabMySqlPort 33307 -SoapPort 7879
```
Key params: `-PlayerGuid` (scope — default 5406, Broug 5405), `-Mode dry-run|apply`,
`-IntervalSeconds`, `-BatchSize`, `-ReactiveAutoBountyMaxEventAgeSeconds`,
`-ReactiveAutoBountySingleOpenPerPlayer`. The full lab launcher
(`start-bridge-lab-all.bat`) runs this by default unless you pass `-Watcher native`
or `-Watcher none` (I disabled it earlier with `-Watcher none`, which is why no
bounty fired).

## wm-live-bridge-lab rules that apply
- Start live proof from a clean window with `-ArmFromEnd` /
  `-MarkExistingEvaluatedOnArm` so stale events don't explain new behavior.
- Prefer explicit bounty templates for normal proof; only use the auto-bounty
  lane when intentionally testing dynamic generation.
- A watcher isn't "started" until its PID exists and survives the startup delay.
- Logs/metadata under `artifacts/bridge_lab_native_watch/`.

## Verify
- Watcher PID alive; then have the scoped player kill the trigger creatures.
- A `reactive_bounty:*` proposal/quest appears (DB rows / panel). Approve via the
  panel **Slice**/approval gate, complete in-game.

## Relationship to LIVE LLM (point #3)
The watcher's *proposals* still flow through the proposal adapter. In the slice
runtime that adapter defaults to **FIXTURE** — so even with the watcher running,
generated text is canned until the slice is wired to **LIVE** (LM Studio). That
LIVE wiring is a code task, not covered by this skill.

## Gotchas
- No bounty ever fires → watcher not running (you ran `-Watcher none`), player not
  in scope, or events older than the max-age window.
- Stale `reactive_bounty:*` rows → clear them; don't let them masquerade as new.
