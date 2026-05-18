Status: ACCEPTED
Last verified: 2026-05-18
Verified by: Claude
Doc type: adr

# ADR 0005: Wild Feature Catalog as a First-Class Surface

## Context

`docs/ROADMAP.md` defines the "Wild Feature Lanes" as the product center
(per-character arcs, exclusive rewards, item powers, shell powers, companions,
deployables/scenes, rune systems, conversation steering) and names reusable
archetypes (Night Watcher's Lens, Bonebound Alpha, Vellums, Bone Lure,
Area-pressure scene).

The repo already makes some lanes first-class and enumerable:
`wm.candidates.release_pack` (repeatable_bounty / story_arc / shell_ability /
native_scene / managed_item_power) and the ability/scene rosters in
`wm.content.release`.

This session added a new wild composite layer — Living World Memory
(`wm.living.{nemesis,rumor,legend,patron,oath}`) — but those features are
standalone CLIs. They are not enumerable as a set, not collectively
dry-run-provable, not CI-validated, and the web panel duplicates a hand-kept
verb map to describe them. That is exactly the "isolated feature silo" the
roadmap warns against (Risk: too many parallel feature spikes).

## Decision

Treat the wild-feature set as a first-class surface with one declarative
registry (`wm.living.catalog`), mirroring how `release_pack` / the rosters
make other lanes first-class.

The catalog:
- declares each wild feature: key, archetype, trigger dataclass, evaluator,
  native verbs, gating batch, docs;
- computes `live_ready` from the real `NATIVE_ACTION_KIND_BY_ID` (never a
  hand-kept copy) so the GUI/panel cannot drift or overclaim;
- exposes `dry_run_all()` that runs every evaluator on a representative
  trigger and asserts each plan is native-payload-contract valid — one call
  proves the entire wild surface composes;
- is validated in CI (`wm living.catalog --validate`): every verb is
  registered, every evaluator importable, every feature has tracked status.

The web panel and `wm panel` consume the catalog as the single source of
truth for Living World readiness.

## Options Considered

### Option A: Registry/catalog (chosen)
| Dimension | Assessment |
|-----------|------------|
| Complexity | Low — declarative wrapper over existing tested evaluators |
| Cost | One module + tests; no native/lab work |
| Scalability | High — new wild feature = one registry entry; CI guards it |
| Team familiarity | High — same pattern as release_pack/rosters |

**Pros:** wild ideas become enumerable, collectively provable, drift-proof,
LLM-enumerable later. **Cons:** one more registry to keep honest (CI does).

### Option B: Leave features as standalone CLIs
**Pros:** zero work. **Cons:** silos persist; GUI keeps a duplicated verb map
that will drift and overclaim; no single dry-run proof; not CI-guarded.

## Consequences

- Easier: discover/prove/extend wild features; GUI is single-sourced; a future
  LLM proposal mode can enumerate the wild surface from one contract.
- Harder: adding a wild feature now also requires a catalog entry + status row
  (intended — that is the anti-silo gate).
- Revisit: when live C++ batches land, `live_ready` flips automatically; no
  catalog change needed.

## Action Items

1. [x] `wm.living.catalog`: registry + `build_wild_feature_catalog` +
       `validate_wild_catalog` + `dry_run_all`.
2. [x] `wm living.catalog` CLI (list / --validate / --dry-run-all / --json).
3. [x] Web panel + `wm panel` consume the catalog (no duplicated verb map).
4. [x] CI runs `wm living.catalog --validate`; feature_status tracks it.
