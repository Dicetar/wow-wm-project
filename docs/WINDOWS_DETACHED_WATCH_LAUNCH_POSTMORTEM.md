Status: BROKEN
Last verified: 2026-04-14
Verified by: Codex
Doc type: postmortem

# Windows Detached Watch Launch Postmortem

## Objective

Start a detached experimental WM watcher on Windows for live bridge-lab testing, with stdout and stderr redirected to repo log files and a PID written for later status/stop control.

## What happened

An ad-hoc PowerShell launcher used `Start-Process` for the detached watch process and hit a Windows environment-handling failure:

```text
Start-Process : Item has already been added. Key in dictionary: 'Path'  Key being added: 'PATH'
```

The launch wrapper then falsely reported success before proving that a real process with a usable PID existed. That left behind empty PID / metadata artifacts and forced manual cleanup before the next launch attempt.

A follow-up experimental launcher used `System.Diagnostics.ProcessStartInfo` with `UseShellExecute = $false`. That did start the watcher, but Codex shell execution still treated the long-running child as attached to the launch command. The watcher kept running correctly while the UI kept the original shell command open for hours.

## Evidence

- failure string from the detached launcher:
  - `Item has already been added. Key in dictionary: 'Path' Key being added: 'PATH'`
- the broken launcher wrote:
  - empty `template_watch.pid`
  - metadata claiming the watcher started
  - no actual child Python watcher process
- the repo already had a working detached-launch pattern in:
  - [Start-BridgeLabNativeWatch.ps1](/D:/WOW/wm-project/scripts/bridge_lab/Start-BridgeLabNativeWatch.ps1)
  - it uses `System.Diagnostics.ProcessStartInfo`, not `Start-Process`

## Root causes

- this Windows host exposes both `Path` and `PATH` in the inherited environment; `Start-Process` is not robust against that collision for this use case
- the failed approach ignored the existing repo-owned detached-launch pattern and rebuilt a launcher ad hoc
- the wrapper treated "launch command returned" as success instead of requiring:
  - non-null process object
  - non-empty PID
  - process still alive after a short startup delay
- `UseShellExecute = $false` is not detached enough for long-running watchers launched through Codex shell commands; it can preserve the child process lifetime under the shell execution wrapper even with stdout and stderr redirected to files

## What is retired

- do not use PowerShell `Start-Process` for detached WM watcher launches on this host when log redirection or reliable PID capture matters
- do not write PID / metadata files until the child process is confirmed alive
- do not report `started=true` when PID is missing or the process object is null

## What remains useful

- the repo-owned detached launcher pattern in [Start-BridgeLabNativeWatch.ps1](/D:/WOW/wm-project/scripts/bridge_lab/Start-BridgeLabNativeWatch.ps1)
- the paired status and stop scripts:
  - [Get-BridgeLabNativeWatchStatus.ps1](/D:/WOW/wm-project/scripts/bridge_lab/Get-BridgeLabNativeWatchStatus.ps1)
  - [Stop-BridgeLabNativeWatch.ps1](/D:/WOW/wm-project/scripts/bridge_lab/Stop-BridgeLabNativeWatch.ps1)
- the PID + metadata + stdout/stderr artifact layout under `artifacts/`

## Next safe path

- use `System.Diagnostics.ProcessStartInfo` with:
  - `UseShellExecute = $true`
  - `WindowStyle = Hidden`
  - explicit working directory
- only persist PID / metadata after a startup delay confirms the process is still alive
- reuse repo-owned detached-launch helpers before writing a custom watcher launcher
- before live compare runs:
  - stop any old watcher for the same player
  - deactivate conflicting live reactive rules
  - then start the new watcher
