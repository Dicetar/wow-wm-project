Status: DESIGN_ONLY
Last verified: 2026-05-22
Verified by: Claude
Doc type: design

# Slice LIVE-LLM quest pipeline (generate → publish → grant)

Design for wiring the panel slice's LLM proposal lane from FIXTURE to LIVE, in
two independently live-provable phases. Phase 1 makes the LLM author quest
drafts that surface as OPEN approval cards (no world mutation). Phase 2 mints
those drafts into real in-engine quests on human approval.

This is the highest-value remaining slice work flagged in
`NEXT_CHAT_HANDOFF_SKILLS_AND_SLICE_2026_05_21.md` (bucket D): until now the
slice has only ever shown canned FIXTURE proposals — "the LLM has never
generated anything."

## Goal / non-goals

**Goal:** an **arc OPEN beat** produces an LLM-generated kill-bounty quest draft,
screened and validated; on panel approval the draft is published to the world DB
and granted to the active character — proven live against BridgeLab.

**Non-goals:**
- Non-kill objective types (gather/escort/talk). The publish pipeline is
  documented kill-bounty-only (`wm-create-quest` skill); other kinds stay a
  flagged pipeline gap, not faked here.
- **Watcher (reactive) LIVE generation.** The watcher builds proposals from a
  different constraint shape (recipe/`compiler`/`slots`/`idempotency_key`), not
  the arc's fixed publish facts (`questgiver_entry`, `objective.target_*`,
  `end_npc_entry`). This adapter's `_merge_fixed_facts` is arc-beat-shaped, so a
  LIVE watcher quest proposal **parks with an actionable block reason** rather
  than generating. Wiring the watcher (resolving a concrete target/giver from
  recipe slots via `wm.targets.resolver`) is a follow-up — see "Out of scope".
- Changing the panel's `/api/llm/*` workbench lane. It stays **draft-only**.
- Scene compiler → bus wiring (separate bucket-D item; out of scope).
- Live watcher launcher work.

## Current state (verified 2026-05-22)

- `ProposalAdapter` (`src/wm/llm/proposal_adapter.py`) has a LIVE mode that is a
  **dead stub**: `_call_live` calls `lmstudio.chat_completion()` and
  `proposal_parser.parse_structured()`, **neither of which exists**.
- Both slice factories (`slice_wiring.make_live_slice_factory`,
  `server._default_slice_factory`) call `SliceRuntime.bootstrap(...)` without
  `adapter_mode`, so it defaults to `AdapterMode.FIXTURE`.
- A real, working LLM client exists: `LmStudioClient.generate_json(...)`
  (`src/wm/llm/lmstudio.py`) — JSON-schema `response_format`,
  `prompts.build_messages`, `results.parse_json_object`. The panel
  `/api/llm/generate` lane uses it but is **draft-only** (`_adopt_draft` only
  records the decision; it does not publish).
- Publish engine `QuestPublisher.publish(draft: BountyQuestDraft, mode)`
  (`src/wm/quests/publish/__init__.py`) is self-contained: validate → preflight →
  snapshot → compile SQL → apply → flip reserved slot staged→active → publish log.
  It consumes the **flat** `BountyQuestDraft` shape (same as
  `control/examples/quest_drafts/*.quest.json`), validated by
  `validate_bounty_quest_draft` (`src/wm/quests/validator.py`).
- `ReservedSlotDbAllocator` (`src/wm/reserved/db_allocator.py`) exposes
  `allocate_next_free_slot(entity_type="quest")`, `ensure_slot_prepared`,
  `transition_slot`, `get_slot`.
- `apply_quest_grant_proposal` (`src/wm/cli/native_applier.py`) fires a
  `quest_add` for `quest_release.grant_quest_id`; it explicitly refuses to publish
  templates. The live quest compiler is installed by
  `wrap_with_live_compilers` (`src/wm/cli/slice_demo_live.py`).
- LM Studio is UP at `:1234` (~17 models incl. `qwen3-coder-30b-a3b-instruct`).
- BridgeLab: DB `33307`, SOAP `7879`, world `8095`; Astel guid `5408`,
  marker aura `946500`; managed quests `910500/910502` published+granted last
  session, `910501` reserved/not granted.

## Locked decisions

1. **Schema home — slice-owned flat-bounty JSON schema.** The LLM emits the flat
   `BountyQuestDraft` shape that `QuestPublisher` already consumes and
   `validate_bounty_quest_draft` already validates. We do **not** adopt the nested
   catalog `wm.quest.release.repeatable_bounty.v1`, which would force a nested→flat
   mapper. New file: `control/schemas/wm.slice.bounty_draft.v1.schema.json`.
2. **Model — panel settings, with default `qwen3-coder-30b-a3b-instruct`.** The
   slice builds `LmStudioClient` from `state.load_settings()`; if no model is set,
   default to `qwen3-coder-30b-a3b-instruct` (structured-output friendly).
3. **Reload — `.reload all quest` via SOAP, then verify grant; park on failure.**
   Matches `wm.quests.live_publish`. New quests may occasionally need a worldserver
   restart to become grantable; if the post-publish `quest_add` does not land, the
   proposal parks to the issues queue with a "restart may be required" note rather
   than silently succeeding.

## The three quest shapes (and how they thread)

| Shape | Owner | Role |
|---|---|---|
| Flat `BountyQuestDraft` | `QuestPublisher`, `validate_bounty_quest_draft` | **LLM output + publish input.** One contract generation→publish. |
| Slice `Proposal.payload.quest_release` | OPEN card, `apply_quest_grant_proposal` | Carries `draft` (Phase 1), then `grant_quest_id` (Phase 2). |
| Catalog `wm.quest.release.*` (nested) | Panel content workbench | **Unused by the slice.** |

`Proposal.payload` shape after Phase 1:
```json
{ "quest_release": {
    "title": "...", "objective": "...", "description": "...",
    "reward": { "...": "..." },
    "draft": { "<flat BountyQuestDraft fields>": "..." }
} }
```
No `grant_quest_id` yet — the quest is not real until approved+published.

## Data flow

```
arc OPEN beat   (the watcher path parks — see "Fixed facts" below)
  → ProposalRequest(intent=beat.intent, constraints=FIXED publish facts)
  → ProposalAdapter._call_live
       → LmStudioClient.generate_json(schema = wm.slice.bounty_draft.v1)
       → ProposalParser safety screen (SQL/GM/shell forbidden patterns)
       → validate_bounty_quest_draft
  → Proposal{ payload.quest_release{ display fields, draft } }   (no grant_quest_id)
  → OPEN card in panel
  ───────────────── PHASE 1 boundary (no world mutation) ─────────────────
  → human approves in panel
  → live_quest compiler (Phase 2):
       → allocate_next_free_slot(entity_type="quest")  → reserved_id (staged)
       → draft.quest_id = reserved_id
       → QuestPublisher.publish(draft, mode="apply")   → slot staged→active
       → SoapRuntimeClient.execute_command(".reload all quest")
       → quest_release.grant_quest_id = reserved_id
       → apply_quest_grant_proposal(...)               → wm_bridge_action_request quest_add
       → verify grant landed; else park with restart-note
  ───────────────── PHASE 2 (mint + grant, approval-gated) ─────────────────
```

## Fixed facts vs. LLM-authored

The **arc** `beat.constraints` supply the facts the LLM must NOT invent, because
they gate publish preflight. (The **watcher** does NOT supply these — its
constraints are recipe/`slots`-shaped, so a LIVE watcher quest proposal parks
with an actionable block reason. Wiring it requires resolving a concrete
target/giver from recipe slots; out of scope here.)

- Fixed (from constraints): `objective.target_entry`, `objective.target_name`
  (must exist in `creature_template`), `end_npc_entry` (turn-in NPC, e.g. 197),
  `questgiver_entry`, `quest_level`/`min_level` band, `grant_mode =
  direct_quest_add`, `start_npc_entry = null`, repeatability via
  `template_defaults.SpecialFlags` (1 repeatable bounty / 0 one-shot story).
- LLM-authored: `title`, `quest_description`, `objective_text`,
  `offer_reward_text`, `request_items_text`, `narrative_summary`, and
  `objective.kill_count` (bounded 1–25 by the validator).

This keeps every generated draft publishable and prevents the LLM from minting an
unresolvable target or leaking a `!` quest offer.

## Components & changes

### Phase 1 — LIVE generation
- **`src/wm/llm/proposal_adapter.py`**
  - `ProposalAdapter` gains injected deps: `llm_client: LmStudioClient | None`,
    `quest_schema: dict | None`, `model_default: str`.
  - Rewrite `_call_live`: call `llm_client.generate_json(
    schema_version="wm.slice.bounty_draft.v1", schema=quest_schema,
    instruction=req.intent, context_pack=req.context,
    candidate_pack=req.constraints)` (it builds messages internally via
    `prompts.build_messages`), run `ProposalParser().parse(result["content"])` for
    the safety screen, then build a `BountyQuestDraft` from `result["parsed"]` and
    run `validate_bounty_quest_draft`.
  - Rework `_validate`: in LIVE mode validate the flat draft (block on validator
    errors with the validator's messages); build `Proposal` with embedded `draft`.
    FIXTURE path unchanged (keeps the existing fixture + tests green).
  - Delete the phantom references; no `chat_completion`/`parse_structured`.
- **New `control/schemas/wm.slice.bounty_draft.v1.schema.json`** — JSON schema
  mirroring `BountyQuestDraft` (required prose fields, `objective`, `reward`,
  bounded `kill_count`). Drives `generate_json` `response_format`.
- **`src/wm/quests/publish/__init__.py`** — small refactor: extract the
  dict→`BountyQuestDraft` body of `load_bounty_quest_draft` into a reusable
  `bounty_draft_from_dict(raw: dict)` so the adapter can build a draft from the
  parsed LLM JSON in-memory (no temp file). `load_bounty_quest_draft` keeps its
  file signature and calls the new helper.
- **`src/wm/cli/slice_demo.py`** — `bootstrap` already accepts `adapter_mode`;
  thread `llm_client` + `quest_schema` into the `ProposalAdapter(...)` it builds.
- **`src/wm/panel/slice_wiring.py`** + **`src/wm/panel/server.py`** — factories
  accept `adapter_mode` and build an `LmStudioClient` from `state.load_settings()`
  (default model per decision 2); `_default_slice_factory` and
  `make_live_slice_factory` pass `adapter_mode=LIVE` when selected.

### Phase 2 — publish-on-approval
- **`src/wm/cli/slice_demo_live.py`** (or a new `src/wm/cli/slice_publish.py`
  composed in) — replace `live_quest` with a publishing compiler:
  1. If `quest_release.draft` present → publish path; elif `grant_quest_id`
     present → existing grant-existing path (backward compatible; fixture safe).
  2. `allocate_next_free_slot(entity_type="quest")` → `reserved_id`.
  3. Inject `quest_id=reserved_id` into the flat draft; `QuestPublisher.publish(
     draft, mode="apply")`.
  4. `SoapRuntimeClient.execute_command(".reload all quest")`.
  5. Set `grant_quest_id=reserved_id`; call `apply_quest_grant_proposal`.
  6. Verify the `quest_add` row; on any failure raise so `ApprovalGate` parks the
     proposal to the issues queue (no partial state — slot only flips active inside
     a successful `publish`).
- **`custom_id_registry`** — record the minted id (status active, source = slice
  beat). Rollback/publish-log handled by `QuestPublisher` already.

## Error handling

- LLM unreachable / invalid JSON / forbidden pattern / validator error → Phase 1
  returns a **blocked** `Proposal` (`is_blocked=True`, reason) → routed to issues
  queue; never shown as an approvable OPEN card.
- Publish preflight/validation failure on approval → compiler raises → gate parks
  to issues queue; reserved slot left staged (not active), no quest rows written.
- Grant verification failure after publish → park with explicit
  "worldserver restart may be required" note (decision 3).

## Testing strategy

- **Phase 1 unit** (`tests/llm/test_proposal_adapter_live.py`): fake
  `LmStudioClient` returning canned JSON. Assert: valid draft → unblocked Proposal
  with embedded draft; malformed/forbidden/invalid draft → blocked Proposal. No
  network.
- **Phase 1 panel** (`tests/panel/test_server_slice_live.py`): factory builds LIVE
  adapter with the fake client; poll → OPEN card present.
- **Phase 2 unit** (`tests/cli/test_slice_publish.py`): fake DB client + fake SOAP
  + fake allocator. Assert allocate→publish→reload→grant ordering, slot flip on
  success, park-on-failure, and the backward-compatible grant-existing branch.
- **Full suite**: `python -m pytest -q`. Pre-existing unrelated failures
  (`test_cli.py` CATALOG import; `test_native_bridge_*` 8 fails) are not ours.
- **Skills validator**: `python scripts/validate_agent_skills.py` if any skill is
  touched (a `wm-slice-live` how-to may be added at ship time).

## Live-proof plan (BridgeLab, DB 33307 / SOAP 7879)

- **Phase 1 proof:** with LM Studio up, bootstrap the slice LIVE, fire the OPEN
  beat, and show an LLM-authored OPEN card in the panel (provenance `mode=live`).
  No DB writes.
- **Phase 2 proof:** approve that card; verify a fresh reserved quest id was
  minted (`quest_template` row), reloaded, and granted to Astel
  (`character_queststatus`), with `wm_publish_log`/`wm_rollback_snapshot` rows.
  Record in `docs/LIVE_PROOF_BACKLOG.md`.
- **Reactive (watcher) proof:** NOT achievable as built — the watcher's
  recipe/slots constraints don't carry fixed publish facts, so a LIVE watcher
  quest proposal parks. Deferred to the watcher-LIVE follow-up.

## Risks

- **ID permanence.** Phase 2 mints permanent visible IDs from LLM output. Mitigated
  by approval-before-mint, fixed-facts-from-constraints, `validate_bounty_quest_draft`,
  fresh reserved slot per publish, and rollback snapshots. Never reuse a dirty id
  (retire via registry + rollback if a proof fails).
- **Draft-only boundary crossing.** Phase 2 is the first LLM→world mutation path.
  It is confined to the slice runtime behind panel approval; the `/api/llm/*`
  workbench lane is unchanged.
- **Model output quality.** Small/instruct models may produce weak prose or
  out-of-band values; the schema + validator + constraints bound the blast radius
  (bad drafts block, they do not publish).

## Out of scope / follow-ups

- **Watcher LIVE generation.** Map reactive recipe/`slots` (creature family,
  zone) → concrete fixed publish facts (`target_entry/target_name` via
  `wm.targets.resolver`, a `questgiver_entry`/`end_npc_entry` policy) so the
  watcher can drive the same `_call_live` path. Until then, LIVE watcher quest
  proposals park with an actionable reason.
- Non-kill objective publish support (pipeline gap).
- Scene compiler → bus.
- Published-but-not-granted retry residue (re-approval allocates a new slot and
  orphans the first published quest — needs rollback or retry-into-same-slot).
- Watcher launcher hardening (`-Watcher none` was used last session).
- Bucket C native-bridge stub actions.
