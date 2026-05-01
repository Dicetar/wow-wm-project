Status: WORKING
Last verified: 2026-04-29
Verified by: Codex
Doc type: reference

# Custom ID Ledger

This is the exact-claim reference for WM custom IDs.

Use it with:

- `data/specs/custom_id_registry.json`
- `data/specs/reserved_id_ranges.json`
- `docs/SPELL_SHELL_BANK_V1.md`

## Source of truth

`WORKING`: `data/specs/custom_id_registry.json` is now the authoritative machine-readable ledger for:

- exact claimed custom IDs
- spell namespace subranges
- current owner system and source paths
- `WORKING` / `PARTIAL` / `BROKEN` / `UNKNOWN` status per claim

`WORKING`: `data/specs/reserved_id_ranges.json` is now coarse allocator policy only.

Do not use `reserved_id_ranges.json` as the exact claim ledger.

## Current spell layout

`WORKING`: broad WM spell namespace split.

- `940000-945999`: pinned shell-bank compatibility space for current named WM shells
- `946000-946999`: generic shell-bank V2 cast-shape families, fully allocated as ten 100-slot families
- `947000-947999`: managed spell publish/rollback slots

Current pinned spell claims:

- `940000`: `bonebound_servant_v1` - `PARTIAL`
- `940001`: `bonebound_twins_v1` / current Bonebound Alpha lane - `WORKING`
- `944000`: `jecia_intellect_block_v1` - `WORKING`
- `945000`: `bonebound_servant_slash_v1` - `PARTIAL`
- `946099`: `echo_restorer_mind_blast_x3_v1` - `PARTIAL`
- `946600`: `bonebound_echo_stasis_v1` - `PARTIAL`
- `946601`: `lanathel_blood_queen_stance_v1` - `PARTIAL`
- `946602`: `wm_watcher_beacon_v1` undispellable no-duration watcher discovery marker - `PARTIAL`
- `946098`: `broug_skirmisher_shot_v1` / targeted active `Skirmisher's Mark` ranged/thrown attack - `WORKING` for Broug current scope
- `946200`: `broug_vulnerable_v1` / `Vulnerable` Deflect target debuff, 60s stackable icon `558` - `WORKING` for Broug current scope
- `946201`: `broug_deflected_v1` / `Deflected` Deflect visible stun/status stack, runtime duration icon `558` - `WORKING` for Broug current scope
- `946603`: `broug_deflect_v1` / `Deflect` animation-timed active guard, aura-free, counter gated by `946605` - `WORKING` for Broug current scope
- `946604`: `broug_skirmisher_mark_v2` / retired self-aura toggle `Skirmisher's Mark` - `BROKEN`, replaced by `spell:946098`
- `946605`: `broug_deflect_counter_stance_v1` / `Counterstrike Stance` real stance aura gating Deflect auto-counter - `WORKING` for Broug current scope
- `946800`: `broug_universal_parry_v1` / `Impossible Guard` - `WORKING` for Broug current scope
- `946801`: `broug_mobile_marksman_v1` / retired passive `Skirmisher's Mark` - `BROKEN`, replaced by `spell:946098`
- `946802`: `broug_auto_retaliation_v1` / `Riposte Instinct` - `WORKING` for Broug current scope
- `947000`: `defias_pursuit_instinct` bundled managed spell example - `PARTIAL`

## Current non-spell examples

Repo-backed current claims include:

- quest `910000`: reactive bounty parity benchmark - `PARTIAL`
- quest `910020`: control-native grant proof - `WORKING`
- quest `910024`: `Bounty: Nightbane Dark Runner - Lens` - `WORKING`
- quest `910180`: `Broug: One Thousand Impossible Guards` linked progression step for `946603` - `WORKING` for Broug current scope
- quest `910181`: `Broug: One Thousand Deflections` linked progression step for `946802` - `WORKING` for Broug current scope
- quest `910152`: retired bad Shadowmoon Lens quest attempt - `BROKEN`, replaced by fresh quest `910171`
- quest `910154`: retired bad Shadowmoon Lens v2 quest attempt - `BROKEN`, replaced by fresh quest `910171`
- quest `910155`: retired Shadowmoon Lens v3 quest attempt - `BROKEN`, replaced by fresh quest `910171`
- quest `910160`: retired Shadowmoon Lens v4 quest attempt - `BROKEN`, replaced by fresh quest `910171`
- quest `910167`: retired Shadowmoon Lens v5 one-option choice reward attempt - `BROKEN`, replaced by fresh quest `910171`
- quest `910168`: retired Shadowmoon Lens v6 generated quest attempt - `BROKEN`, replaced by fresh quest `910171`
- quest `910169`: retired Shadowmoon Lens v7 money-as-item attempt - `BROKEN`, replaced by fresh quest `910171`
- quest `910170`: retired Shadowmoon Lens v8 stale Oronok text/no reward attempt - `BROKEN`, replaced by fresh quest `910171`
- quest `910171`: `Jecia: Shadowmoon Lens` fresh Earthmender Wilda quest - `PARTIAL`
- item `910006`: `Night Watcher's Lens` - `WORKING`
- item `910007`: `Unstable Enchanting Vellum` random-enchant consumable - `PARTIAL` for retuned live proof
- item `910008`: `Enchanting Vellum` focused single-slot random-enchant consumable - `PARTIAL`
- item `910009`: `Bone Lure Charm` throwable taunt-obelisk consumable - `PARTIAL`
- item `910010`: retired bad Shadowmoon Lens item attempt - `BROKEN`, replaced by fresh item `910013`
- item `910011`: retired bad Shadowmoon Lens v2 item attempt - `BROKEN`, replaced by fresh item `910013`
- item `919001`: retired Shadowmoon Lens v3 item attempt - `BROKEN`, replaced by fresh item `910013`
- item `919002`: retired Shadowmoon Lens v4 item attempt - `BROKEN`, replaced by fresh item `910013`
- item `919003`: retired Shadowmoon Lens v5 item attempt - `BROKEN`, replaced by fresh item `910013`
- item `919004`: retired Shadowmoon Lens v6 item attempt - `BROKEN`, replaced by fresh item `910013`
- item `919005`: retired Shadowmoon Lens v7 money-as-item attempt - `BROKEN`, replaced by fresh item `910013`
- item `910012`: retired Shadowmoon Lens v8 no reward attempt - `BROKEN`, replaced by fresh item `910013`
- item `910013`: `Shadowmoon Watcher's Lens` level-70 Earthmender Wilda Arc Factory reward cloned from the known-working Lens row - `PARTIAL`
- creature `920100`: Bonebound Alpha template - `PARTIAL`
- creature `920101`: Echo Destroyer melee template - `WORKING`
- creature `920102`: Bone Lure Obelisk deployed by item `910009` - `PARTIAL`
- creature `920103`: Echo Restorer support-role template - `PARTIAL`
- creature `920104`: hidden Broug parry quest credit marker - `WORKING` for Broug current scope
- creature `920105`: hidden Broug Deflect quest credit marker - `WORKING` for Broug current scope
- DBC override rows `100055`, `100118`, `100172`, `100229`, `100413`, `100414`, `100433`, `100434`: combat proficiency support - `WORKING` for Jecia and Broug current scope; Plate row `100293` remains level-gated and `PARTIAL` until a level-40 proof

Check the JSON ledger for the complete current list and source paths.

## Do

- Claim an ID in `custom_id_registry.json` before using it in a repo-owned WM lane.
- Treat `(namespace, id)` as the uniqueness key.
- Never reuse a visible ID after a failed, stale, wrong-tooltip, wrong-reward, or dirty live iteration. Mark it `BROKEN`, set `replaced_by`, clean up the live rows, retire the reserved slot, and publish the replacement on a fresh ID.
- Keep pinned shell IDs separate from managed spell slots.
- Update source paths when a claim moves or a new contract becomes authoritative.
- Keep statuses explicit: `WORKING`, `PARTIAL`, `BROKEN`, or `UNKNOWN`.

## Do Not Do

- Do not reuse one spell ID for two WM spell purposes.
- Do not allocate managed spell drafts from named shell IDs.
- Do not hide player-specific behavior behind a generic client shell family.
- Do not trust stale docs over the ledger.
- Do not use stock spell IDs as permanent WM carriers.

## Operator rule

If you are iterating on a spell, item, quest, or DBC override and cannot immediately answer "which exact ID owns this?" from the ledger, stop and add the claim first.
