# Summon and Spell Platform Status

State snapshot for the WM summon / custom spell lane after the stock-carrier recovery work.

This document is the truth source for:

- what worked
- what failed
- what is now the supported path
- what is still blocked on client-patch work

## Scope

This covers the WM-owned summon and new-ability lane built around:

- shell-bank contract
- `mod-wm-spells`
- workbench shell publish / grant flows
- lab-only behavior invocation
- retirement of `mod-wm-prototypes` as the main summon lane

It does not try to restate the whole WM project.

## Current supported path

The supported path is now:

1. define a WM-only shell in `control/runtime/spell_shell_bank.json`
2. build a matching client patch entry under `client_patches/wm_spell_shell_bank/`
3. bind shell spell ID -> native behavior in `mod-wm-spells`
4. publish shell metadata into:
   - `wm_spell_shell`
   - `wm_spell_behavior`
   - `wm_spell_grant`
5. grant or revoke the shell through the workbench, preferring native bridge spell learn / unlearn
6. use the lab-only debug invoke lane only for tuning behavior before the client shell is installed

Anything based on stock spell carrier reuse is no longer a supported implementation path.

## Successful paths

### 1. Shell-bank contract and patch workspace

Status: working

What succeeded:

- reserved WM shell IDs are now explicit and repo-owned
- `940000` is reserved for `bonebound_servant_v1`
- `940500` is reserved for a future pet-active shell and kept disabled
- the client patch workspace now records:
  - default package name
  - default install path
  - shell-row requirements
  - no-stock-reuse rule

Relevant files:

- [spell_shell_bank.json](D:/WOW/wm-project/control/runtime/spell_shell_bank.json)
- [client patch README](D:/WOW/wm-project/client_patches/wm_spell_shell_bank/README.md)
- [client patch manifest](D:/WOW/wm-project/client_patches/wm_spell_shell_bank/manifest.json)
- [bonebound shell definition](D:/WOW/wm-project/client_patches/wm_spell_shell_bank/shells/bonebound_servant_v1.json)

### 2. Stable native spell runtime module

Status: working

What succeeded:

- `mod-wm-spells` exists as the stable runtime for WM-owned spell behavior
- native world tables exist for shell, behavior, grant, and debug invocation state
- the module builds successfully in `WM_BridgeLab`
- the module is now the intended summon runtime instead of `mod-wm-prototypes`

Relevant files:

- [mod-wm-spells README](D:/WOW/wm-project/native_modules/mod-wm-spells/README.md)
- [wm_spell_runtime.cpp](D:/WOW/wm-project/native_modules/mod-wm-spells/src/wm_spell_runtime.cpp)
- [wm spell platform SQL](D:/WOW/wm-project/native_modules/mod-wm-spells/data/sql/world/updates/2026_04_12_10_wm_spell_platform.sql)

### 3. Workbench shell/operator lane

Status: working

What succeeded:

- workbench commands now exist for:
  - `new-summon-shell`
  - `publish-shell`
  - `grant-shell`
  - `ungrant-shell`
  - `invoke-shell-behavior`
- spell learn / unlearn prefers native bridge transport and falls back to SOAP only when needed
- direct `python -m wm.content.workbench --help` now works from repo root

Relevant files:

- [workbench.py](D:/WOW/wm-project/src/wm/content/workbench.py)
- [spell platform helpers](D:/WOW/wm-project/src/wm/spells/platform.py)
- [shell bank loader](D:/WOW/wm-project/src/wm/spells/shell_bank.py)
- [repo-root wm shim](D:/WOW/wm-project/wm/__init__.py)
- [pytest.ini](D:/WOW/wm-project/pytest.ini)

### 4. Native bridge spell learn / unlearn

Status: working

What succeeded:

- `player_learn_spell` and `player_unlearn_spell` now exist in the native action bus
- Python action metadata marks them implemented
- workbench grant/ungrant can target native bridge transport first

Relevant files:

- [wm_bridge_action_queue.cpp](D:/WOW/wm-project/native_modules/mod-wm-bridge/src/wm_bridge_action_queue.cpp)
- [spell grant actions SQL](D:/WOW/wm-project/native_modules/mod-wm-bridge/data/sql/world/updates/2026_04_12_11_wm_bridge_spell_grant_actions.sql)
- [action kinds](D:/WOW/wm-project/src/wm/sources/native_bridge/action_kinds.py)

### 5. Jecia-only poison cleanup

Status: working

What succeeded:

- the legacy carrier spell rows for Jecia were removed from `character_spell`
- Jecia-owned stale prototype pet state was removed from:
  - `character_pet`
  - `pet_spell`
  - `pet_aura`
  - `pet_spell_cooldown`
- legacy `spell_script_names` mappings for stock carrier IDs were removed from the lab world DB
- cleanup is scoped to Jecia and the lab only

Relevant files:

- [cleanup wrapper](D:/WOW/wm-project/scripts/bridge_lab/Clear-LegacyPrototypeState.ps1)
- [character cleanup SQL](D:/WOW/wm-project/sql/dev/clear_jecia_legacy_summon_state_characters.sql)
- [world cleanup SQL](D:/WOW/wm-project/sql/dev/clear_jecia_legacy_summon_state_world.sql)

Observed cleanup result:

- `legacy_pet_rows_remaining = 0`
- `legacy_spell_rows_remaining = 0`
- `legacy_spell_script_rows_remaining = 0`

### 6. Lab runtime default direction

Status: working

What succeeded:

- lab runtime configuration now enables `mod-wm-spells`
- lab runtime configuration disables `mod-wm-prototypes` by default
- deploy helper now writes `WmSpells.BoneboundServant.ShellSpellIds = "940000"` instead of reintroducing prototype shell IDs

Relevant files:

- [Configure-BridgeLabRuntime.ps1](D:/WOW/wm-project/scripts/bridge_lab/Configure-BridgeLabRuntime.ps1)
- [Deploy-BridgeLabWorldServer.ps1](D:/WOW/wm-project/scripts/bridge_lab/Deploy-BridgeLabWorldServer.ps1)

## Unsuccessful paths

### 1. Stock warlock summon carrier hijack

Status: failed and retired

Carrier IDs involved:

- `697`

What happened:

- normal warlock summon behavior was hijacked
- expected class summons were replaced by WM prototype behavior
- summon identity was never truly isolated because the client and core both still recognized the stock spell

Decision:

- do not reuse stock warlock summon shells for WM abilities again

### 2. Other stock carrier reuse experiments

Status: failed and retired

Carrier IDs involved:

- `8853`
- `57913`
- `49126`

Observed failure modes across those attempts:

- spell visible but click produced no reaction
- summon path leaked stock behavior instead of staying inside the WM prototype logic
- spellbook visibility was inconsistent by carrier
- recast while active produced stuck or uncontrollable summons
- dismiss/replacement behavior was unstable

Decision:

- do not continue carrier-cancellation hacks as the implementation strategy

### 3. Prototype pet behavior mixed onto the wrong chassis

Status: failed and retired

What happened:

- ghoul-style and other stock summon behaviors were mixed with a custom skeleton overlay
- the pet bar, resource model, and control behavior were inconsistent
- at one point only `Thrash` appeared and was unusable because the chassis assumptions were wrong for the desired summon behavior

Decision:

- the first stable summon milestone uses one clean pet chassis and only base controls
- no custom pet active button until the core lifecycle is stable

### 4. Hostile or incorrect summoned unit leakage

Status: failed and retired

What happened:

- one live path spawned a hostile `Scourge Corpserender`
- this proved the stock carrier path was not safely isolated and could fall back into default-game behavior

Decision:

- WM summon work must use a WM-owned shell ID with explicit `createdBySpellId`
- no stock carrier is trusted for this feature

### 5. Saved-pet state poisoning retests

Status: failed until cleanup was added

What happened:

- stale rows in `character_pet` and related pet tables polluted later tests
- retests appeared to be exercising new code but were sometimes loading old servant state instead

Decision:

- keep Jecia-only cleanup tooling in repo
- use it before assuming a retest is clean

### 6. Visible shell end-to-end proof

Status: not complete yet

What is still blocked:

- the repo now contains the shell-bank contract and local patch workspace
- the built client patch artifact is not committed and has not been finalized/installed from this repo yet
- until that patch exists in the local client, `940000` cannot be treated as a proven visible spellbook ability

Current workaround:

- use `invoke-shell-behavior` in the lab-only path for behavior tuning

## What is validated right now

Validated from repo root:

- `python -m wm.content.workbench --help`
- `python -m pytest tests/test_spell_shell_bank.py tests/test_spell_platform.py tests/test_content_workbench.py -q`

Validated in lab:

- Jecia-only legacy cleanup executed successfully
- legacy carrier script rows and saved prototype pet rows are gone

Validated by build:

- `mod-wm-spells` built successfully through the incremental bridge-lab build path

## What is still not validated

- `940000` visible in the spellbook through a real installed client shell patch
- cast-failure UX when no corpse is selected
- clean friendly summon through the final visible shell
- relog persistence on the final shell path
- dismiss / recast lifecycle on the final shell path

## Practical next step

The next engineering step is not more summon hacking. It is:

1. build/install the first local WM shell patch for `940000`
2. teach or grant `940000` to Jecia through the stable shell lane
3. prove:
   - visible shell
   - no-corpse cast failure
   - friendly summon
   - recast / dismiss / relog lifecycle

Do not resume work from the retired stock-carrier paths.
