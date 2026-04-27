# Spell Shell Bank V1

This note fixes the exact gap between:

- "custom behavior on a reused stock spell"
- and "a truly new player-facing WM ability"

## Short truth

For a **truly new** WM ability on a 3.3.5 client, we need both:

1. a **client-visible shell bank**
2. a **native server behavior registry**

Without the shell bank, WM can only hijack an existing client-known spell.

That is why the first twin-skeleton prototype missed the mark:

- it reused `Summon Voidwalker`
- it changed behavior, but it was not a new visible spell

That path is retired. The current Bonebound Alpha debug/native lane binds behavior to WM-owned shell `940001` and explicitly removes WM script bindings from stock carriers such as `697` and `49126`.

## Hard pet constraint

Stock AzerothCore exposes a **single real pet slot** for the player.

You can see the singular pet model in core code:

- [Player.h](D:/WOW/WM_BridgeLab/src/azerothcore/src/server/game/Entities/Player/Player.h)
- [Player.cpp](D:/WOW/WM_BridgeLab/src/azerothcore/src/server/game/Entities/Player/Player.cpp)

Important signals:

- `GetPetGUID()`
- `m_temporaryUnsummonedPetNumber`
- resummon logic built around one stored pet

So WM should target one of these two designs:

### Recommended

- **one true permanent skeleton pet**
- plus **one linked guardian / companion skeleton** if we still want a pair fantasy

This preserves the actual pet bar and normal warlock summon behavior.

### Expensive alternate

- deep multi-pet core rewrite

This is not a small spell feature. It changes engine assumptions and pet control behavior.

## Final WM spell architecture

### 1. Client shell bank

Repo contract:

- [spell_shell_bank.json](D:/WOW/wm-project/control/runtime/spell_shell_bank.json)

This now defines two shell layers:

- pinned compatibility shells for current live WM spell lanes
- generic V2 cast-shape families for future prepatched shells

Current generic V2 sizing default:

- 100 usable slots per family
- 100 reserve-gap ids after each generic family
- 5 generic families in `946000-946999`

Current pinned compatibility shells stay where they already work:

- `940000`
- `940001`
- `944000`
- `945000`

That means we do not patch the client once per spell. We patch the client with a generic cast-shape bank once, keep current pinned shells stable, and spend managed spell slots separately from shell ids.

These are now buildable client assets. The committed JSON is the repo-owned contract; the binary MPQ remains local-only and is generated from that contract.

The repo now also provides a range-driven patch-plan export:

- `python -m wm.spells.export_patch_plan --summary`

That export now expands the compatibility rows plus the five generic V2 families, then overlays named shells like `940000`, `940001`, `944000`, and `945000` with their WM-specific metadata.

The repo-owned local package builder is:

- `python -m wm.spells.client_patch build --source-dbc D:\WOW\Azerothcore_WoTLK_Rebuild\run\data\dbc\Spell.dbc --include all --summary`
- `python -m wm.spells.client_patch build --source-dbc D:\WOW\Azerothcore_WoTLK_Rebuild\run\data\dbc\Spell.dbc --include all --install --summary`

The builder emits both `DBFilesClient\Spell.dbc` and `DBFilesClient\SkillLineAbility.dbc`. The second command installs `patch-z.mpq` into `D:\WOW\world of warcraft 3.3.5a hd\Data\`. The WoW client locks MPQs while running, so close the client before installing and restart it after installing.

Named shell presentation must be client truth, not runtime guesswork. For `940001`, the contract currently sets icon `221` (`Spell_Shadow_AnimateDead`), cast time index `14` (3 seconds), mana cost `180`, Summon Voidwalker visual `4054`, and a `SkillLineAbility.dbc` row cloned from Summon Voidwalker (`697`) so the shell appears in the Warlock spellbook instead of the common/general tab.

### 2. Native behavior kinds

The native side should own fixed behavior kinds, for example:

- `warlock_pet_skeleton`
- `guardian_skeleton_pair`
- `scaled_aura`
- `scaled_projectile`

WM fills typed parameters.
C++ executes.

### 3. WM publish / grant path

For a real new WM ability:

1. claim a shell from the shell bank
2. bind that shell to a native behavior kind
3. teach the shell directly or grant it after a quest reward
4. audit and retire it later through WM control

## What "do it right" means for the requested summon

Your requested summon is best modeled as:

- visible shell family: `summon_pet_compat`
- behavior kind: `warlock_pet_skeleton`
- runtime shape:
  - one true permanent skeleton pet
  - optional second skeleton as guardian/companion if we keep the pair idea
  - stats scale from intellect + spell power

That is the correct next implementation lane.

Current status:

- `WORKING`: shell `940001` is bound to `summon_bonebound_alpha_v3` in the bridge-lab DB
- `WORKING`: Alpha is the one true persisted pet; Omega is retired from the release lane
- `WORKING`: total intellect is added to Alpha stats and shadow spell power is added to Alpha attack power
- `WORKING`: exact shell claims now live in `data/specs/custom_id_registry.json` and `docs/CUSTOM_ID_LEDGER.md`
- `WORKING`: generic shell-bank V2 is cast-shape based with 100-slot families and 100-id reserve gaps
- `WORKING`: server-side named-shell materialization exists through `python -m wm.spells.server_dbc materialize` and `scripts/bridge_lab/Stage-BridgeLabServerSpellDbc.ps1`; on 2026-04-17 BridgeLab staged `940000`, `940001`, `944000`, and `945000` into `Spell.dbc`, `grant-shell` created `character_spell(5406, 940001)`, and `ungrant-shell` removed it and revoked `wm_spell_grant`
- `WORKING`: client patch build is repeatable. On 2026-04-17, Codex downloaded official Ladik MPQ Editor into `.wm-bootstrap\tools\mpqeditor`, generated `DBFilesClient\Spell.dbc` plus `DBFilesClient\SkillLineAbility.dbc`, packed and verified `.wm-bootstrap\state\client-patches\wm_spell_shell_bank\patch-z.mpq`, and verified named shell text/presentation data for `940001`
- `WORKING`: server DBC staging now has a `castable` profile for visible-shell tests. `.\scripts\bridge_lab\Stage-BridgeLabServerSpellDbc.ps1 -SeedProfile castable -SpellId 940001` stages `940001` with WM-owned summon effect/targeting plus explicit icon `221`, cast time index `14`, mana cost `180`, and Summon Voidwalker visual `4054`
- `PARTIAL`: the neutral `learnable` server DBC lane remains proof of server-known shell ids only. Use `castable` plus the client MPQ for visible spellbook/action-bar testing
- `WORKING`: Alpha/Echo visible physical bleed and echo proc are BridgeLab-proven after the 2026-04-25 retune; bleed ticks scale primarily from caster melee attack power, use visible target aura `772`, and Echo bleed stacks independently by caster GUID plus target GUID
- `PARTIAL`: the visible player-facing spell remains pending until the freshly installed client patch and restarted worldserver are validated in-game after client restart

Do not replace or reuse `Summon Voidwalker`, `Raise Ghoul`, or any other stock spell as the permanent WM carrier for this behavior.
