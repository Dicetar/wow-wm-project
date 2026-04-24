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
- name/icon/tooltip, cast presentation, resource display, and spellbook placement live in the client patch
- summon logic, scaling, gating, and lifecycle live on the server
- built patch artifacts stay local and are not committed to git

## Workspace layout

- manifest: `client_patches/wm_spell_shell_bank/manifest.json`
- shell definitions: `client_patches/wm_spell_shell_bank/shells/*.json`
- source contract: `control/runtime/spell_shell_bank.json`
- family generation model:
  - pinned compatibility shells stay on `940000`, `940001`, `944000`, and `945000`
  - generic V2 families pre-seed five cast-shape families in `946000-946999`
  - each generic family gets 100 usable slots plus a 100-id reserve gap

## First install target

- local patch package name: `patch-z.mpq`
- client install location: `D:\WOW\world of warcraft 3.3.5a hd\Data\patch-z.mpq`
- built artifact policy: generate locally, do not commit

If `patch-z.mpq` is already occupied on a specific client, pick the next free patch letter and update the local install note. Keep the repo manifest on `patch-z.mpq` as the default contract.

## First live shell

- shell key: `bonebound_servant_v1`
- spell ID: `940000`
- family: `summon_pet_compat`
- behavior kind: `summon_bonebound_servant_v1`
- server config hook: `WmSpells.BoneboundServant.ShellSpellIds = "940000"`

Reserved future pet-active shell:

- shell key: `bonebound_servant_slash_v1`
- spell ID: `945000`
- family: `pet_active_compat`

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
2. Build the local MPQ package:
   - `python -m wm.spells.client_patch build --source-dbc D:\WOW\Azerothcore_WoTLK_Rebuild\run\data\dbc\Spell.dbc --include all --summary`
   - default output: `.wm-bootstrap\state\client-patches\wm_spell_shell_bank\patch-z.mpq`
   - this uses repo-local Ladik MPQ Editor at `.wm-bootstrap\tools\mpqeditor\x64\MPQEditor.exe`
   - the payload includes full replacement `DBFilesClient\Spell.dbc` and `DBFilesClient\SkillLineAbility.dbc`
3. Install the generated package:
   - `python -m wm.spells.client_patch build --source-dbc D:\WOW\Azerothcore_WoTLK_Rebuild\run\data\dbc\Spell.dbc --include all --install --summary`
   - install target: `D:\WOW\world of warcraft 3.3.5a hd\Data\patch-z.mpq`
   - close the WoW client first; a running client locks MPQs and install will fail
4. If the shell needs visible cast proof, stage the matching server cast-shape DBC row before boot:
   - `.\scripts\bridge_lab\Stage-BridgeLabServerSpellDbc.ps1 -SeedProfile castable -SpellId 940001`
5. Restart worldserver after server DBC staging.
6. Restart the WoW client after installing the MPQ patch.

This repo does not commit the binary patch output. It commits the shell contract, install target, and build notes only.

## Current status

- shell IDs and metadata are committed in repo
- exact shell claims are tracked in `data/specs/custom_id_registry.json`
- `WORKING`: repo-owned patch builder exists at `python -m wm.spells.client_patch`
- `WORKING`: on 2026-04-17, Codex downloaded official Ladik MPQ Editor into `.wm-bootstrap\tools\mpqeditor`, built `.wm-bootstrap\state\client-patches\wm_spell_shell_bank\patch-z.mpq`, and verified extraction of both `DBFilesClient\Spell.dbc` and `DBFilesClient\SkillLineAbility.dbc`
- `WORKING`: the generated client payload includes named shell text for `940000`, `940001`, `944000`, and `945000`, plus the generic V2 cast-shape families in `946000-946999`
- `WORKING`: `940001` presentation now has icon `221`, 3 second cast time through index `14`, 180 mana cost, Summon Voidwalker visual `4054`, and a Warlock/Demonology `SkillLineAbility.dbc` mapping cloned from Summon Voidwalker
- `WORKING`: server `940001` can be staged with `-SeedProfile castable`, which keeps the WM-owned shell id but now has explicit presentation fields for icon/cast/cost/visual instead of relying only on the Raise-Ghoul seed defaults
- `PARTIAL`: the refreshed package is installed and BridgeLab worldserver restarted on pid `8580`; in-game client spellbook, action-bar, cast, recast, dismiss, and relog proof is pending after fresh client restart
