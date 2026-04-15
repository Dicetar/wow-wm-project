# On-The-Fly Spells V1

This note defines what "on-the-fly spells" should mean for WM on a 3.3.5 client.

## Short truth

WM can support on-the-fly **spell behavior**.
WM cannot support truly arbitrary **new client-visible spell definitions** on a stock running client without prepared client assets.

So the stable WM lane is:

1. claim a prepared visible shell spell from a WM shell bank
2. bind that shell to a native server behavior kind
3. teach or grant the shell to a scoped player
4. retune behavior through WM-owned data, not by hijacking stock gameplay spells

## What changed

The older `mod-wm-prototypes` summon experiments proved useful engine facts, but they are not the right foundation for the final system.

What they taught:

- player-facing spell identity must be isolated from stock spell IDs
- saved pet state can pollute retests
- stock spell carriers leak unwanted behavior
- one real pet first is the correct target
- a proper shell bank plus native behavior registry is the clean path

What they do **not** prove:

- that reused stock carriers are safe for live WM abilities
- that WM should keep extending `mod-wm-prototypes`

## Current architecture target

### 1. Client shell bank

Repo contract:

- [D:/WOW/wm-project/control/runtime/spell_shell_bank.json](D:/WOW/wm-project/control/runtime/spell_shell_bank.json)
- [D:/WOW/wm-project/client_patches/wm_spell_shell_bank/README.md](D:/WOW/wm-project/client_patches/wm_spell_shell_bank/README.md)

Shell families currently defined:

- `summon_pet`
- `summon_companion`
- `self_buff`
- `offensive_bolt`
- `passive_aura`
- `pet_active`

These shells are WM-owned spell identities. They are the player-facing layer.

### 2. Native behavior registry

The core should own a fixed set of behavior kinds, not arbitrary scripts.

Current first target:

- `summon_bonebound_servant_v1`

Near-term follow-up kinds:

- `grant_shell_spell`
- `summon_bonebound_alpha_v3`

WM fills structured data. C++ executes registered behavior.

### 3. WM-owned spell tables

Current stable tables in `acore_world`:

- `wm_spell_shell`
- `wm_spell_behavior`
- `wm_spell_grant`
- `wm_spell_debug_request`

This lets WM:

- allocate or reference a shell
- publish behavior
- grant or revoke it
- audit provenance
- invoke behavior directly in the lab without teaching a live shell

## Native module split

- `mod-wm-bridge`
  - perception
  - native action queue
  - player-scoped spell learn/unlearn actions
- `mod-wm-spells`
  - shell-bound ability behavior runtime
  - lab-only debug behavior invocation
- `mod-wm-prototypes`
  - legacy scratch/postmortem only

## Bonebound Servant v1

The first real target is:

- one stable controllable skeleton pet
- generic demon-style pet backend
- skeleton visuals layered on top
- corpse-required cast gate
- no stock spell collision

This is the right first vertical slice because it proves:

- shell bank -> behavior binding
- native spell grant
- summon lifecycle
- future quest reward -> learn shell flow

## Fast operator path

The workbench is now the operator surface for this lane:

- create shell draft
- publish shell
- grant shell
- invoke behavior in lab

Reference:

- [D:/WOW/wm-project/docs/CONTENT_WORKBENCH_V1.md](D:/WOW/wm-project/docs/CONTENT_WORKBENCH_V1.md)

## What "on the fly" should mean

It should mean:

- no stock spell hijacking for final features
- no full rebuild for tuning-only changes
- no freeform generated C++ or SQL from the LLM
- yes to shell allocation
- yes to native behavior selection
- yes to audited teach/grant/apply flows

It should not mean:

- inventing arbitrary client visuals live on a stock client
- treating prototype carrier hacks as the final design
- letting the LLM mutate random server internals directly
