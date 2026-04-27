Status: WORKING
Last verified: 2026-04-25
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
- `946000-946999`: generic shell-bank V2 cast-shape families
- `947000-947999`: managed spell publish/rollback slots

Current pinned spell claims:

- `940000`: `bonebound_servant_v1` - `PARTIAL`
- `940001`: `bonebound_twins_v1` / current Bonebound Alpha lane - `WORKING`
- `944000`: `jecia_intellect_block_v1` - `WORKING`
- `945000`: `bonebound_servant_slash_v1` - `PARTIAL`
- `946600`: `bonebound_echo_stasis_v1` - `PARTIAL`
- `947000`: `defias_pursuit_instinct` bundled managed spell example - `PARTIAL`

## Current non-spell examples

Repo-backed current claims include:

- quest `910000`: reactive bounty parity benchmark - `PARTIAL`
- quest `910020`: control-native grant proof - `WORKING`
- quest `910024`: `Bounty: Nightbane Dark Runner - Lens` - `WORKING`
- item `910006`: `Night Watcher's Lens` - `WORKING`
- item `910007`: `Unstable Enchanting Vellum` random-enchant consumable - `PARTIAL` for retuned live proof
- item `910008`: `Enchanting Vellum` focused single-slot random-enchant consumable - `PARTIAL`
- item `910009`: `Bone Lure Charm` throwable taunt-obelisk consumable - `PARTIAL`
- creature `920100`: Bonebound Alpha template - `PARTIAL`
- creature `920101`: Echo Destroyer melee template - `WORKING`
- creature `920102`: Bone Lure Obelisk deployed by item `910009` - `PARTIAL`
- creature `920103`: Echo Restorer support-role template - `PARTIAL`
- DBC override rows `100118`, `100414`, `100433`, `100434`: combat proficiency support - `WORKING`

Check the JSON ledger for the complete current list and source paths.

## Do

- Claim an ID in `custom_id_registry.json` before using it in a repo-owned WM lane.
- Treat `(namespace, id)` as the uniqueness key.
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
