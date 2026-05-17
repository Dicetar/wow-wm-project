Status: PROPOSED
Last verified: 2026-05-17
Verified by: Claude
Doc type: adr

# ADR 0004: The Compiler Output Is the Shipped Quest Artifact

## Context

WM has a real, schema-adaptive quest compiler (`wm.quests.compiler.compile_bounty_quest_sql_plan`).
The Arc + Reward Factory already wires it: it harvests structural defaults
(`QuestType`, `QuestInfoID`, `QuestSortID`, `ZoneOrSort`, `SuggestedPlayers`) from the
turn-in NPC's existing working quests, forces WM flags and repeatable `SpecialFlags`,
then emits a fresh-ID `quest_template` INSERT with WM-owned text, objectives, and rewards.

However, the only documented *live* arc proof (Jecia Shadowmoon Lens v9) deliberately did
**not** ship compiler output. The operator hand-cloned known-working quest `910151` in the
DB and mutated visible fields, because compiler/harvested-defaults output was not trusted
to render a correct reward panel and survive client quest-cache reality. Eight Shadowmoon
quest IDs were burned and retired during that iteration.

This is a **trust/proof gap, not an absence gap**. The generative path exists and is
tested at repo level; it has never been proven as the shipped artifact in a client.
Track 2 (Arc + Reward Factory) and Track 5 (LLM on locked contracts) both rest on the
assumption that deterministic compiler output is shippable. That assumption is currently
unvalidated, and the ambiguity compounds the moment LLM-authored proposals feed the same
compiler.

## Options Considered

### Option A: Prove the compiler path; compiler output is the only shipped artifact

| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium — one focused in-client proof, then fix whatever columns are missing |
| Cost | One clean BridgeLab window + bounded ID burn |
| Scalability | High — every future arc/LLM proposal ships through one proven path |
| Team familiarity | High — compiler already exists and is tested |

**Pros:** Tracks 2/5 get a real foundation; no per-arc manual cloning; LLM-safe.
**Cons:** Requires spending a proof window on infra rather than features; may surface more missing columns.

### Option B: Formalize harvest-and-clone; compiler is dev-only

| Dimension | Assessment |
|-----------|------------|
| Complexity | Low short-term, High long-term |
| Cost | Recurring manual cloning + ID burn per arc |
| Scalability | Low — does not generalize to LLM proposals or volume |
| Team familiarity | High — it is the current de facto practice |

**Pros:** Matches what actually worked once; lowest immediate effort.
**Cons:** Track 5 (LLM) becomes infeasible — a model cannot "hand-clone a golden row";
per-arc manual work; the deterministic-content north star is abandoned in practice while
still claimed in docs.

## Decision

**Adopt Option A with a falsifiable gate.** Compiler output is the shipped quest artifact.
Hand-cloning a golden row is retired as a shipping path and demoted to an emergency-only
recovery step that must be recorded as a `PARTIAL` with a follow-up proof task.

The Track 2 gameplay-`WORKING` exit gate becomes specifically:

> One arc quest, generated *by the factory/compiler* (not hand-cloned), published to a
> fresh reserved ID, accepted and turned in by the test character in-client, with the
> correct reward panel and reward delivery, on a clean BridgeLab window.

If that proof fails, the **failure mode is the specification**: each missing/wrong column
that breaks the reward panel or cache gets added to the compiler's harvested-defaults set
or default map, and the proof is rerun. No more than a bounded number of fresh IDs
(recommend ≤3) may be burned per proof cycle before stopping to write the structural root
cause, per the existing three-failure rule.

## Consequences

- Tracks 2 and 5 get a single proven content path; LLM proposal mode stays feasible.
- The next live window must spend on this proof before more arc features (aligns with
  the roadmap's Medium-Term Execution Order, which already lists this kind of gate first).
- `docs/ROADMAP.md`, `WM_PLATFORM_HANDOFF.md`, and `ARC_REWARD_FACTORY_V1.md` must stop
  describing hand-clone as the live path and reference this ADR instead.
- The compiler's harvested-defaults column set becomes a maintained contract, not an
  incidental list; widening it is the sanctioned fix when a proof fails.
- Short-term cost: one infra-focused proof window instead of a feature.

## Action Items

1. [ ] Run the bounty/arc full-loop runbook (see `docs/FULL_LOOP_PROOF_RUNBOOK.md`,
       Part B) on a clean BridgeLab window using factory/compiler output, not a hand-clone.
2. [ ] For each reward-panel/cache failure, extend the compiler harvested-defaults or
       default-column map; rerun; cap fresh-ID burn per cycle.
3. [ ] On success, relabel Arc + Reward Factory V1 gameplay `WORKING` and update the
       three docs above to cite this ADR.
4. [x] Add a repo test asserting the factory plan for a sample scenario contains the
       columns the proof identified as reward-panel-critical.
       Done: `tests/test_arc_compiler_contract.py` locks ID/LogTitle/ObjectiveText1/
       RewardItem1/RewardAmount1/RewardMoney=0/choice-routing/repeatable-flag/
       fresh-id-delete. Widen this test as the live proof surfaces more columns.
