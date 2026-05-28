# Conversational Action Loop — Design Spec

Status: `APPROVED_DESIGN`
Created: 2026-05-29
Repository: `wm-project`
Roadmap phase: Phase 1 keystone (see `docs/WM_CAPABILITY_ROADMAP.md`)
Architecture reference: `docs/WM_MAIN_DESIGN_DOCUMENT.md`

## 1. Problem

The autoplay LLM and the native action bus are disconnected at the conversational layer.
In chat, the WM can only *talk* — `service.py::_chat_reply` constrains the model to one short
sentence and `_send_chat_reply` hardcodes the result as a single `player_chat_message`. Real,
validated, applyable actions only happen on the *event-driven* generation lanes, never from
conversation. A player who says "send something to hunt me" gets flavor text, not a spawned
creature, even though `creature_spawn` is implemented and a full validate -> dry-run -> apply
-> audit pipeline already exists.

## 2. Goal

Let the WM optionally *act* from a conversation: emit a typed action proposal, run it through
the existing control pipeline, then confirm the outcome in chat. Talk -> act -> tell you.

### Non-goals (this phase)
- Multi-step orchestrated scenes (Phase 5).
- Proactive/ambient reactions to live events (Phase 2).
- Writing conversation content back as narrative memory (Phase 4). Each *applied deed* is still
  journaled for audit.
- New multi-turn dialogue memory; `build_chat_world_context` already carries recent WM chat.
- Any change that weakens, duplicates, or bypasses an existing safeguard.

## 3. Basis: this generalizes a proven path

`_send_chat_reply` already performs: build `ControlProposal` -> `coordinator.execute(mode="dry-run")`
-> `coordinator.execute(mode="apply", confirm_live_apply=True)` -> journal/audit
(`service.py:557-583`). It is proven for the low-risk `player_chat_message` verb. The keystone
makes the **verb a model choice from an operator-allowed set** instead of a hardcode, reusing
the same coordinator, dry-run, apply, and audit. The LLM never applies; Python compiles,
clamps, dry-runs, applies; C++ executes only the contracted verb.

## 4. Architecture

```
player message
  -> world_context (build_chat_world_context) + allowed-verb manifest (modes != "off")
  -> LLM (text mode): { reply: str, intent: {verb,args,reason} | null }
  -> ALWAYS deliver `reply` as player_chat_message  (today's behavior preserved)
  -> if intent present and valid:
        compile intent -> ControlProposal  (deterministic; args clamped; scope/guid locked)
        coordinator.execute(mode="dry-run")
          dry-run fails        -> park issue; WM says it could not
          verb mode = "auto"   -> execute(mode="apply") -> WM confirms result in chat -> journal
          verb mode = "confirm"-> store pending intent (TTL)
                                  WM: "I can <X> - say yes to confirm"
                                  ALSO surfaced in panel approval inbox
                                  resolve via in-chat yes/no OR panel approve/reject
                                    approve -> execute(mode="apply") -> WM confirms; clear both
                                    reject/timeout/other -> drop; WM acknowledges
```

## 5. Components

### 5.1 Chat response schema (modify `_chat_reply`)
- Model is asked for a single JSON object `{reply, intent}` (text mode; `schema_mode="text"`
  retained because LM Studio's json_schema channel is backend-sensitive).
- `intent` is `null` or `{verb: str, args: object, reason: str}`.
- Parsing reuses `parse_json_object` + `_sanitize_chat_reply` + `_guard_chat_reply` for `reply`.
- If the object is unparseable, or `reply` is empty, fall back to today's plain-sentence handling
  (`reply` only, `intent = null`). The chat can never be silenced by intent parsing.

### 5.2 Intent compiler — new module `src/wm/autoplay/intent.py`
- `compile_intent(*, player_guid, intent, allowed) -> ControlProposal | IntentRejection`.
- Steps: verb must be in `allowed` (mode != "off"); args validated/clamped against the existing
  native payload contract used by `platform.native_payload_contracts`; `player`/scope/guid set by
  code (never taken from the model); `author = {kind: manual_admin, name: wm.autoplay.intent,
  manual_reason: <reason>}`; `selected_recipe = manual_admin_action`;
  `action.kind = native_bridge_action` with `native_action_kind = <verb>`; risk from the verb's
  `default_risk`; deterministic `idempotency_key`.
- On any validation failure: return `IntentRejection(reason)` — caller drops the intent, still
  delivers the reply, and logs an issue. Never raises into the chat path.

### 5.3 Allowed-verb manifest + per-verb mode
- Extend `autoplay_tool_manifest()` to filter by per-verb mode: only verbs with mode `confirm`
  or `auto` are shown to the model; `off` verbs are omitted entirely.
- Verb mode source of truth: autoplay config (`AutoplayStateStore` config + panel sync), new key
  e.g. `conversational_verb_modes: { <verb>: "off"|"confirm"|"auto" }`.
- Default modes (operator-overridable): `low -> auto`, `medium -> confirm`, `high -> confirm`.
  Only `implemented=True` verbs are eligible.

### 5.4 Pending-intent store (extend `AutoplayStateStore`)
- One pending record per `player_guid`: `{intent, proposal_summary, dry_run, created_at,
  expires_at, source}` with TTL = 120s.
- API: `set_pending_intent`, `load_pending_intent`, `clear_pending_intent(reason)`.
- Surfaced in panel inbox as a job/approval item referencing the same record (id-linked), so the
  two surfaces resolve one object. Resolving in chat clears the inbox item and vice versa.

### 5.5 Confirmation parsing (deterministic)
- `_is_affirmation(message)` / `_is_negation(message)` — small word lists ("yes","do it","confirm",
  "go ahead" / "no","cancel","stop","forget it"), mirroring `_is_forget_context_command`.
- In `_reply_to_chat_event` / `chat_once`: if a fresh pending intent exists and message is an
  affirmation -> apply; negation -> clear; anything else -> expire pending and process normally.

### 5.6 Panel surfaces (`panel/server.py`, `panel/static`)
- Auto-apply checklist: per implemented verb, a checkbox (checked = `auto`), with a disable
  control (= `off`); unchecked-and-enabled = `confirm`. Persists via the existing settings sync
  into autoplay config. Lives in the Advanced panel; Simple panel can show a compact summary.
- Pending approvals: reuse the existing approval inbox to list pending conversational intents
  with approve/reject wired to the shared pending-intent record.

### 5.7 Apply + confirm + audit (extend `_send_chat_reply` path)
- Generalize the existing proposal/dry-run/apply/journal flow to accept any compiled proposal,
  not only the chat-message proposal.
- After a successful apply of an action verb, the WM speaks a short confirmation
  (`player_chat_message`) describing the result; on block/failure it speaks the reason.
- Every applied deed is journaled (`append_journal("deed", ...)`) carrying the originating LLM
  intent for traceability (Phase 4 will consume this).

## 6. Safety framing (why this keeps every safeguard)
- The LLM only *selects* a verb from an operator-pre-authorized manifest and proposes args.
- Deterministic Python compiles the proposal, clamps args via the native payload contract, and
  locks scope/guid — the model cannot author raw SQL, GM commands, or arbitrary mutations.
- "Auto-apply" is an explicit operator pre-authorization per verb, recorded in audit; it is the
  human consent the existing policy requires, not an unattended LLM apply.
- Dry-run, idempotency, native C++ re-validation, scope allow-list, and rollback all still run.
- High-risk verbs default to `confirm` and require a human yes (chat or panel) each time.

## 7. Error handling / weak-model degradation
Every failure path degrades to "just reply":
- Unparseable JSON or empty reply -> plain sentence, no intent.
- Unknown/`off` verb -> drop intent, reply, log issue.
- Arg validation/clamp failure -> drop intent, reply, log issue.
- Dry-run failure -> park issue, WM says it could not do it.
- LM Studio error -> existing fallback sentence.
The player always receives a sentence; actions are best-effort on top of reliable chat.

## 8. Acceptance criteria (live proof, not tests)
- In `/join WM`, "heal me" (low/auto) restores the scoped player and the WM confirms in chat.
- "spawn something to hunt me" (medium/confirm) prompts "say yes to confirm"; replying "yes"
  spawns a WM-owned creature and the WM confirms; the same pending item is approvable in the panel.
- Toggling a verb to `auto` in the panel checklist makes it apply without confirmation next time;
  toggling to `off` makes the WM stop proposing it.
- Unparseable model output still yields a normal chat reply.
- Every applied deed appears in the autoplay journal and control audit with the originating intent.
- Existing chat-only behavior is unchanged when the model emits no intent.

## 9. Defaults chosen (no open TBDs)
- Pending-intent TTL: 120s.
- Default verb modes: low=auto, medium=confirm, high=confirm; non-implemented=unavailable.
- Confirmation requires an explicit affirmation token; ambiguous replies expire the pending intent.
- Manifest exposes only `implemented=True`, non-`off` verbs.
