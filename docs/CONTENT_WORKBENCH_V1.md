# Content Workbench V1

This is the fast operator lane for managed WM content.

Goal:
- claim a managed item, spell slot, or WM shell
- write a draft JSON
- publish it
- immediately give, learn, or debug it on one test player

This remains lighter than the full control lane. It is for rapid iteration while the main WM platform stays deterministic and audited.

## What it supports now

- managed item draft creation
- managed passive spell-slot draft creation
- managed visible spell-slot draft creation
- managed item-trigger spell-slot draft creation
- WM shell-bank summon draft creation
- WM shell publish into `wm_spell_shell` / `wm_spell_behavior`
- WM shell grant / ungrant on one player
- lab-only WM spell behavior debug invocation
- fast release summon submitter for already-proven Bonebound Alpha behavior
- native-bridge-first spell learn / unlearn with SOAP fallback
- direct item delivery helpers:
  - `.additem`
  - `.send items`

## What it does not claim yet

- arbitrary new client-visible spell invention on a stock client
- automated DBC patch generation
- native-bridge execution for item add
- full control-lane policy/audit richness for every content action

The spell-slot side still follows [SPELL_SLOT_PIPELINE_V1.md](D:/WOW/wm-project/docs/SPELL_SLOT_PIPELINE_V1.md). The true new-ability lane now starts from the shell bank contract.

## Draft creation

Create a managed item draft:

```powershell
python -m wm.content.workbench new-item `
  --name "Jecia Test Token" `
  --base-item-entry 6948 `
  --player-guid 5406
```

Create a passive slot draft:

```powershell
python -m wm.content.workbench new-passive `
  --name "Jecia Passive Surge" `
  --player-guid 5406 `
  --helper-spell-id 48161 `
  --aura-description "Temporary passive test hook."
```

Create an item-trigger spell draft:

```powershell
python -m wm.content.workbench new-trigger-spell `
  --name "Jecia Trigger Burst" `
  --trigger-item-entry 910020 `
  --player-guid 5406 `
  --helper-spell-id 133
```

Create a visible spell slot draft:

```powershell
python -m wm.content.workbench new-visible-spell `
  --name "Jecia Visible Burst" `
  --base-visible-spell-id 133 `
  --player-guid 5406
```

Create a WM summon shell draft:

```powershell
python -m wm.content.workbench new-summon-shell `
  --shell-key bonebound_servant_v1 `
  --player-guid 5406
```

Drafts are written by default under:

```text
.wm-bootstrap/state/content-drafts/
```

## Publish and test

Dry-run an item publish:

```powershell
python -m wm.content.workbench publish-item `
  --draft-json .wm-bootstrap\state\content-drafts\item-910020-jecia-test-token.json `
  --mode dry-run
```

Publish it and give it to Jecia:

```powershell
python -m wm.content.workbench publish-item `
  --draft-json .wm-bootstrap\state\content-drafts\item-910020-jecia-test-token.json `
  --mode apply `
  --give-to-player-guid 5406 `
  --count 1
```

Item delivery defaults to `auto`, which tries `.additem` first and falls back to `.send items` mail if this branch rejects the direct give.

Publish a managed spell and learn it on Jecia:

```powershell
python -m wm.content.workbench publish-spell `
  --draft-json .wm-bootstrap\state\content-drafts\spell-940020-jecia-passive-surge.json `
  --mode apply `
  --learn-to-player-guid 5406
```

Publish a WM shell draft:

```powershell
python -m wm.content.workbench publish-shell `
  --draft-json .wm-bootstrap\state\content-drafts\shell-bonebound_servant_v1.json `
  --mode apply
```

## Direct test commands

Give an item without publishing:

```powershell
python -m wm.content.workbench give-item `
  --item-entry 910020 `
  --player-guid 5406 `
  --count 1 `
  --mode apply
```

Teach a spell directly:

```powershell
python -m wm.content.workbench learn-spell `
  --spell-entry 940020 `
  --player-guid 5406 `
  --mode apply
```

Remove a spell directly:

```powershell
python -m wm.content.workbench unlearn-spell `
  --spell-entry 940020 `
  --player-guid 5406 `
  --mode apply
```

Grant the WM Bonebound Servant shell:

```powershell
python -m wm.content.workbench grant-shell `
  --player-guid 5406 `
  --shell-key bonebound_servant_v1 `
  --reload-via-soap `
  --mode apply
```

What that does:

- scopes `mod-wm-spells` to player `5406`
- keeps shell spell `940000` in the WM spell runtime config
- reloads config if requested
- teaches the shell spell through the native bridge action queue when available
- falls back to SOAP learn if native spell grant is rejected or unavailable

Invoke the same summon behavior through the lab-only debug lane:

```powershell
python -m wm.content.workbench invoke-shell-behavior `
  --player-guid 5406 `
  --shell-key bonebound_servant_v1 `
  --mode apply
```

After that path is proven, use the fast release submitter for repeated summon execution:

```powershell
python -m wm.spells.summon_release `
  --player-guid 5406 `
  --summary
```

BridgeLab shortcut:

```powershell
.\summon-bridge-lab-bonebound-twins.bat -PlayerGuid 5406
```

Release submitter behavior:

- defaults to shell `940001` and behavior `summon_bonebound_alpha_v3`
- defaults to `apply`, not dry-run
- skips shell-bank lookup, player lookup, preflight, and default wait/poll verification
- returns the request id immediately; pass `--wait` only when you want post-submit confirmation

Do not use the release submitter while changing schema, behavior config, player scope, or native code. Use `invoke-shell-behavior` for proof and diagnostics first.

Current lab default:

- `mod-wm-spells` is the intended summon / ability runtime
- `mod-wm-prototypes` is legacy and disabled by default
- `bonebound_servant_v1` is the first stable summon shell target
- `bonebound_twins_v1` / shell `940001` is the current fast release summon target
- the client patch workspace lives under `client_patches\wm_spell_shell_bank\`

## Recommended workflow

1. create a draft with `new-item`, `new-passive`, or `new-summon-shell`
2. edit the JSON by hand if needed
3. dry-run publish
4. apply publish
5. grant or learn it on one scoped player
6. test in-game
7. iterate quickly

For brand-new item entries on some server builds, a worldserver restart may still be needed before direct `.additem` sees the new template. When that branch gets picky, `--delivery auto` or `--delivery mail` is the reliable operator fallback.

The 3.3.5 client can also keep stale item-entry visuals in `Cache\WDB\...\itemcache.wdb`. If a custom item is mechanically correct but still shows a `?` icon or old visuals in bags, close the client and clear the item cache:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\client\Clear-WoWItemCache.ps1
```

Managed item drafts now zero out inherited random-affix clone fields by default:
- `RandomProperty = 0`
- `RandomSuffix = 0`
- `ScalingStatDistribution = 0`
- `ScalingStatValue = 0`

That avoids accidental suffix junk when cloning from randomized base items.

See also:

- [ON_THE_FLY_SPELLS_V1.md](D:/WOW/wm-project/docs/ON_THE_FLY_SPELLS_V1.md)
- [SPELL_SHELL_BANK_V1.md](D:/WOW/wm-project/docs/SPELL_SHELL_BANK_V1.md)
