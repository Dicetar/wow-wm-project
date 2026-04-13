# WM Spell Shell Bank

Repo-owned workspace for the client patch that makes WM spell shells visible to the 3.3.5a client.

The shell bank solves one specific problem: stock 3.3.5 clients do not know about arbitrary new spell IDs, so a true WM ability needs a matching client-visible shell before it can appear cleanly in the spellbook or on hotbars.

## Source of truth

- contract: `control/runtime/spell_shell_bank.json`
- patch workspace manifest: `client_patches/wm_spell_shell_bank/manifest.json`

## Rules

- do not hook stock live spell IDs for WM abilities
- shell rows must be WM-only identities
- summon shells should be dummy/script-style shells that defer behavior to `mod-wm-spells`
- name/icon/tooltip live in the client patch
- summon logic, scaling, gating, and lifecycle live on the server
- built patch artifacts stay local and are not committed to git

## Workspace layout

- manifest: `client_patches/wm_spell_shell_bank/manifest.json`
- shell definitions: `client_patches/wm_spell_shell_bank/shells/*.json`
- source contract: `control/runtime/spell_shell_bank.json`
- family generation model: 6 families x 1000 slots each = 6000 pre-seeded WM shells

## First install target

- local patch package name: `patch-z.mpq`
- client install location: `D:\WOW\world of warcraft 3.3.5a hd\Data\patch-z.mpq`
- built artifact policy: generate locally, do not commit

If `patch-z.mpq` is already occupied on a specific client, pick the next free patch letter and update the local install note. Keep the repo manifest on `patch-z.mpq` as the default contract.

## First live shell

- shell key: `bonebound_servant_v1`
- spell ID: `940000`
- family: `summon_pet`
- behavior kind: `summon_bonebound_servant_v1`
- server config hook: `WmSpells.BoneboundServant.ShellSpellIds = "940000"`

Reserved future pet-active shell:

- shell key: `bonebound_servant_slash_v1`
- spell ID: `945000`
- family: `pet_active`

## Shell requirements for `940000`

- WM-only spell row, no copied stock summon row
- dummy/script-driven effect only
- no class restriction
- no reagent or soul shard requirement
- no talent requirement
- "always castable" style client flags so the button does not silently fail
- WM-owned:
  - name
  - icon
  - tooltip
  - cooldown identity

## Local build/install workflow

1. Export the generated patch plan:
   - `python -m wm.spells.export_patch_plan --summary`
   - default output: `.wm-bootstrap\state\client-patches\wm_spell_shell_bank\patch-plan.json`
2. Build or export the `940000` shell row into the local patch package defined by `manifest.json`.
   The intended patch workflow is range-driven: generate 1000 pre-seeded rows per family from the family ranges in the manifest, then override named shells like `940000` and `945000` with WM-specific metadata from the generated patch plan.
3. Install the generated package to `D:\WOW\world of warcraft 3.3.5a hd\Data\patch-z.mpq`.
4. If the shell requires matching server-side DBC data, stage that copy into the lab runtime DBC tree before boot:
   - `D:\WOW\WM_BridgeLab\run\data\dbc\`
5. Restart the client after installing the patch.

This repo does not commit the binary patch output. It commits the shell contract, install target, and build notes only.

## Current status

- shell IDs and metadata are committed in repo
- reproducible patch instructions are committed in repo
- no packaged patch artifact is committed yet
- until the patch is built and installed, summon behavior should be tested through the lab-only debug invocation lane
