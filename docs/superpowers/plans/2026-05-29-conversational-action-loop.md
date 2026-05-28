# Conversational Action Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the WM act from a conversation — the chat model may emit a typed action proposal that runs through the existing dry-run/apply pipeline, then the WM confirms the outcome in chat.

**Architecture:** Generalize the already-proven chat path in `service.py::_send_chat_reply` (build `ControlProposal` -> `coordinator.execute(dry-run)` -> `execute(apply)` -> journal) so the native verb is chosen by the model from an operator-allowed manifest instead of hardcoded to `player_chat_message`. A deterministic compiler turns a model intent into a typed proposal; per-verb operator modes (`off`/`confirm`/`auto`) gate apply; confirmation is resolvable in-chat or via the panel inbox.

**Tech Stack:** Python 3.11, pydantic v2 (`wm.control.models.ControlProposal`), stdlib JSON state store (`AutoplayStateStore`), existing `ControlCoordinator`, `validate_native_action_payload`, LM Studio text-mode client.

**Testing approach (per project doctrine + owner directive "features, not wheelchairs"):** Tasks 1-5 are pure deterministic logic and get focused unit tests in the existing `tests/test_autoplay.py`. Tasks 6-8 are integration/gameplay and are validated by **live in-client proof** (see each task's Live Proof block), matching `WM_MAIN_DESIGN_DOCUMENT.md` §4.8. Do not add tests for the integration glue for its own sake; keep the existing suite green.

**Spec:** `docs/superpowers/specs/2026-05-29-conversational-action-loop-design.md`

---

## File Structure

- **Create** `src/wm/autoplay/intent.py` — verb-mode defaults/resolution, intent compiler (`compile_intent`), `IntentRejection`, affirmation/negation parsing. Pure, no I/O.
- **Modify** `src/wm/autoplay/tools.py` — `autoplay_tool_manifest(modes=...)` filters verbs by mode.
- **Modify** `src/wm/autoplay/state.py` — add `conversational_verb_modes` + `pending_intents` to status; add pending-intent methods.
- **Modify** `src/wm/autoplay/service.py` — structured chat output (`reply` + `intent`); wire the loop into `chat_once` / `_reply_to_chat_event`; generalize the apply helper; confirmation messages.
- **Modify** `src/wm/panel/server.py` + `src/wm/panel/static/{app.js,index.html,style.css}` — verb-mode checklist + pending approvals inbox.
- **Test** `tests/test_autoplay.py` — unit tests for tasks 1-5.

---

## Task 1: Verb-mode model + resolution

**Files:**
- Create: `src/wm/autoplay/intent.py`
- Test: `tests/test_autoplay.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autoplay.py
from wm.autoplay.intent import default_verb_modes, resolve_verb_modes

def test_default_verb_modes_low_auto_medium_high_confirm():
    modes = default_verb_modes()
    assert modes["player_restore_health_power"] == "auto"   # low + implemented
    assert modes["player_apply_aura"] == "confirm"          # medium + implemented
    assert "player_teleport" not in modes                   # not implemented -> excluded

def test_resolve_verb_modes_applies_overrides_and_ignores_unimplemented():
    resolved = resolve_verb_modes({"player_apply_aura": "auto", "player_teleport": "auto"})
    assert resolved["player_apply_aura"] == "auto"          # override wins
    assert "player_teleport" not in resolved                # unimplemented dropped
    assert resolved["player_restore_health_power"] == "auto"  # default preserved
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autoplay.py -k verb_modes -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'wm.autoplay.intent'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/wm/autoplay/intent.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID
from wm.sources.native_bridge.payload_contract import validate_native_action_payload

VERB_MODES = ("off", "confirm", "auto")
_RISK_DEFAULT_MODE = {"low": "auto", "medium": "confirm", "high": "confirm"}


def default_verb_modes() -> dict[str, str]:
    return {
        kind.kind: _RISK_DEFAULT_MODE.get(kind.default_risk, "confirm")
        for kind in NATIVE_ACTION_KIND_BY_ID.values()
        if kind.implemented and not kind.admin_only
    }


def resolve_verb_modes(config: dict[str, Any] | None) -> dict[str, str]:
    modes = default_verb_modes()
    for verb, mode in (config or {}).items():
        if verb in modes and str(mode) in VERB_MODES:
            modes[verb] = str(mode)
    return modes
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autoplay.py -k verb_modes -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/wm/autoplay/intent.py tests/test_autoplay.py
git commit -m "feat(autoplay): verb-mode model for conversational actions"
```

---

## Task 2: Filter the tool manifest by verb mode

**Files:**
- Modify: `src/wm/autoplay/tools.py`
- Test: `tests/test_autoplay.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autoplay.py
from wm.autoplay.tools import autoplay_tool_manifest

def test_manifest_excludes_off_verbs_and_lists_modes():
    modes = {"player_restore_health_power": "auto", "player_apply_aura": "off"}
    manifest = autoplay_tool_manifest(modes=modes)
    verbs = {item["kind"]: item for item in manifest["native_actions"]}
    assert "player_apply_aura" not in verbs            # off -> hidden from model
    assert verbs["player_restore_health_power"]["mode"] == "auto"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autoplay.py -k manifest_excludes -v`
Expected: FAIL (`autoplay_tool_manifest()` takes no `modes` kwarg / no `mode` key)

- [ ] **Step 3: Implement**

Replace the body of `autoplay_tool_manifest` in `src/wm/autoplay/tools.py` so it accepts modes and filters/annotates. Use `resolve_verb_modes` so a `None` argument yields defaults:

```python
# src/wm/autoplay/tools.py  (full replacement of the function)
from __future__ import annotations

from typing import Any

from wm.autoplay.intent import resolve_verb_modes
from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KINDS


def autoplay_tool_manifest(*, modes: dict[str, str] | None = None) -> dict[str, Any]:
    resolved = resolve_verb_modes(modes)
    native_actions = [
        {
            "kind": item.kind,
            "category": item.category,
            "risk": item.default_risk,
            "mode": resolved[item.kind],
            "description": item.description,
        }
        for item in NATIVE_ACTION_KINDS
        if item.implemented and resolved.get(item.kind, "off") != "off"
    ]
    return {
        "schema_version": "wm.autoplay.tools.v2",
        "model_contract": (
            "Reply in plain words. You MAY include one `intent` choosing exactly one verb from "
            "native_actions with its args; WM validates, dry-runs, and applies it. Never write SQL, "
            "GM commands, shell commands, config edits, or raw mutations."
        ),
        "player_input": {
            "preferred": "custom chat channel named WM",
            "also_supported": ["chat prefix: towm <message>", "addon mirror events"],
        },
        "player_output": {
            "preferred_action": "player_chat_message",
            "styles": ["channel", "whisper", "system"],
            "default_payload": {"style": "channel", "channel_name": "WM", "sender_name": "WorldMaster"},
        },
        "native_actions": native_actions,
        "content_lanes": ["quest", "item", "spell", "ability", "scene", "action", "chat"],
        "autoplay_gates": [
            "BridgeLab doctor green",
            "active session character",
            "LM Studio model available",
            "verb enabled in operator manifest",
            "dry-run successful",
            "auto-apply pre-authorized OR operator confirmed",
        ],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autoplay.py -k "manifest_excludes or verb_modes" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/wm/autoplay/tools.py tests/test_autoplay.py
git commit -m "feat(autoplay): mode-filtered tool manifest for chat intents"
```

---

## Task 3: Intent compiler

**Files:**
- Modify: `src/wm/autoplay/intent.py`
- Test: `tests/test_autoplay.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autoplay.py
from wm.autoplay.intent import IntentRejection, compile_intent

def test_compile_intent_rejects_off_verb():
    out = compile_intent(player_guid=5408, verb="player_teleport", args={}, modes={})
    assert isinstance(out, IntentRejection)

def test_compile_intent_rejects_missing_required_args():
    # player_apply_aura requires a spell id per the payload contract
    out = compile_intent(player_guid=5408, verb="player_apply_aura", args={}, modes={"player_apply_aura": "confirm"})
    assert isinstance(out, IntentRejection)

def test_compile_intent_builds_proposal_with_locked_guid():
    out = compile_intent(
        player_guid=5408,
        verb="player_restore_health_power",
        args={},
        modes={"player_restore_health_power": "auto"},
    )
    assert not isinstance(out, IntentRejection)
    assert out.proposal.player.guid == 5408
    assert out.mode == "auto"
    assert out.risk == "low"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autoplay.py -k compile_intent -v`
Expected: FAIL (`compile_intent` / `IntentRejection` not defined)

- [ ] **Step 3: Implement (append to `src/wm/autoplay/intent.py`)**

```python
# src/wm/autoplay/intent.py  (append)
import hashlib
from datetime import datetime, timezone


@dataclass(slots=True)
class IntentRejection:
    reason: str


@dataclass(slots=True)
class CompiledIntent:
    proposal: Any          # wm.control.models.ControlProposal
    verb: str
    mode: str
    risk: str


def _stable(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def compile_intent(
    *,
    player_guid: int,
    verb: str,
    args: dict[str, Any] | None,
    modes: dict[str, str] | None,
    reason: str = "",
) -> CompiledIntent | IntentRejection:
    from wm.control.models import ControlProposal

    resolved = resolve_verb_modes(modes)
    mode = resolved.get(verb, "off")
    if mode == "off":
        return IntentRejection(f"verb not enabled: {verb!r}")
    kind = NATIVE_ACTION_KIND_BY_ID.get(verb)
    if kind is None or not kind.implemented:
        return IntentRejection(f"verb not implemented: {verb!r}")
    payload_args = dict(args or {})
    issues = validate_native_action_payload(action_kind=verb, payload=payload_args)
    if issues:
        return IntentRejection("; ".join(issues)[:300])
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    idem = f"autoplay:intent:{_stable(f'{player_guid}:{verb}:{payload_args}:{now}')}"
    proposal = ControlProposal.model_validate(
        {
            "schema_version": "control.proposal.v1",
            "source_event": None,
            "player": {"guid": int(player_guid)},          # guid locked by code, never from model
            "selected_recipe": "manual_admin_action",
            "action": {
                "kind": "native_bridge_action",
                "payload": {
                    "native_action_kind": verb,
                    "payload": payload_args,
                    "created_by": "wm.autoplay.intent",
                    "risk_level": kind.default_risk,
                    "expires_seconds": 120,
                },
            },
            "rationale": (reason or f"Conversational WM action: {verb}")[:300],
            "risk": {"level": kind.default_risk, "irreversible": False, "notes": []},
            "idempotency_key": idem,
            "author": {
                "kind": "manual_admin",
                "name": "wm.autoplay.intent",
                "manual_reason": (reason or f"operator-authorized conversational verb {verb}")[:300],
            },
            "metadata": {"lane": "intent", "intent_reason": reason[:300]},
        }
    )
    return CompiledIntent(proposal=proposal, verb=verb, mode=mode, risk=kind.default_risk)
```

> Note: `validate_native_action_payload` checks *required* fields only; it does not clamp numeric ranges. Per-verb numeric sanity (e.g. capping `player_add_money`) is intentionally out of scope for v1 — native C++ re-validates and high-risk verbs default to `confirm`. Add range clamps later only if a live test shows a real footgun.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autoplay.py -k compile_intent -v`
Expected: PASS (if `player_apply_aura` has no contract yet, the missing-args test may pass trivially because no required fields exist — in that case change that test's verb to one with a `required` contract entry, e.g. `player_add_item`)

- [ ] **Step 5: Commit**

```bash
git add src/wm/autoplay/intent.py tests/test_autoplay.py
git commit -m "feat(autoplay): deterministic intent->proposal compiler"
```

---

## Task 4: Affirmation / negation parsing

**Files:**
- Modify: `src/wm/autoplay/intent.py`
- Test: `tests/test_autoplay.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autoplay.py
from wm.autoplay.intent import is_affirmation, is_negation

def test_affirmation_and_negation():
    assert is_affirmation("yes") and is_affirmation("Do it!") and is_affirmation("go ahead")
    assert is_negation("no") and is_negation("cancel") and is_negation("forget it")
    assert not is_affirmation("what can you do?")
    assert not is_negation("spawn a wolf")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autoplay.py -k affirmation -v`
Expected: FAIL (names not defined)

- [ ] **Step 3: Implement (append to `src/wm/autoplay/intent.py`)**

```python
# src/wm/autoplay/intent.py  (append)
_AFFIRM = {"yes", "y", "yeah", "yep", "do it", "go ahead", "confirm", "ok", "okay", "sure", "go for it"}
_NEGATE = {"no", "n", "nope", "cancel", "stop", "nevermind", "never mind", "forget it", "no thanks"}


def _norm(message: str) -> str:
    return " ".join(str(message).strip().lower().split()).rstrip("!.")


def is_affirmation(message: str) -> bool:
    return _norm(message) in _AFFIRM


def is_negation(message: str) -> bool:
    return _norm(message) in _NEGATE
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autoplay.py -k affirmation -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/wm/autoplay/intent.py tests/test_autoplay.py
git commit -m "feat(autoplay): deterministic yes/no parsing for action confirms"
```

---

## Task 5: Pending-intent store

**Files:**
- Modify: `src/wm/autoplay/state.py`
- Test: `tests/test_autoplay.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_autoplay.py
from wm.autoplay.state import AutoplayStateStore

def test_pending_intent_roundtrip_and_expiry(tmp_path):
    store = AutoplayStateStore(root=tmp_path)
    store.set_pending_intent(5408, {"verb": "creature_spawn", "summary": "spawn a wolf"}, ttl_seconds=120)
    loaded = store.load_pending_intent(5408)
    assert loaded and loaded["verb"] == "creature_spawn"
    store.set_pending_intent(5408, {"verb": "x"}, ttl_seconds=0)   # already expired
    assert store.load_pending_intent(5408) is None
    store.set_pending_intent(5408, {"verb": "y"}, ttl_seconds=120)
    store.clear_pending_intent(5408, reason="rejected")
    assert store.load_pending_intent(5408) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_autoplay.py -k pending_intent -v`
Expected: FAIL (methods not defined)

- [ ] **Step 3: Implement**

In `src/wm/autoplay/state.py`, add `"pending_intents": {}` to the dict returned by `default_status()` (next to `"issues": []`). Then add these methods to `AutoplayStateStore` (e.g. after `add_issue`):

```python
# src/wm/autoplay/state.py  (new methods on AutoplayStateStore)
    def set_pending_intent(self, player_guid: int, record: dict[str, Any], *, ttl_seconds: int = 120) -> dict[str, Any]:
        from datetime import timedelta
        status = self.load_status()
        pending = dict(status.get("pending_intents") or {})
        created = datetime.now(timezone.utc).replace(microsecond=0)
        payload = {
            **record,
            "player_guid": int(player_guid),
            "created_at": created.isoformat().replace("+00:00", "Z"),
            "expires_at": (created + timedelta(seconds=int(ttl_seconds))).isoformat().replace("+00:00", "Z"),
        }
        pending[str(int(player_guid))] = payload
        status["pending_intents"] = pending
        self.save_status(status)
        self.append_journal("pending_intent_set", payload)
        return payload

    def load_pending_intent(self, player_guid: int) -> dict[str, Any] | None:
        status = self.load_status()
        pending = dict(status.get("pending_intents") or {})
        record = pending.get(str(int(player_guid)))
        if not isinstance(record, dict):
            return None
        expires = _parse_iso(record.get("expires_at"))
        if expires is None or datetime.now(timezone.utc) > expires:
            pending.pop(str(int(player_guid)), None)
            status["pending_intents"] = pending
            self.save_status(status)
            return None
        return record

    def clear_pending_intent(self, player_guid: int, *, reason: str = "cleared") -> None:
        status = self.load_status()
        pending = dict(status.get("pending_intents") or {})
        if pending.pop(str(int(player_guid)), None) is not None:
            status["pending_intents"] = pending
            self.save_status(status)
            self.append_journal("pending_intent_cleared", {"player_guid": int(player_guid), "reason": reason})
```

Add this module-level helper near `_safe_name`:

```python
# src/wm/autoplay/state.py  (module-level)
def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_autoplay.py -k pending_intent -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/wm/autoplay/state.py tests/test_autoplay.py
git commit -m "feat(autoplay): per-player pending-intent store with TTL"
```

---

## Task 6: Structured chat output (reply + optional intent)

**Files:**
- Modify: `src/wm/autoplay/service.py` (`_chat_reply`, ~lines 220-325)

This task changes `_chat_reply` to return an optional `intent` alongside `message`, parsed from the model's JSON. It must degrade to today's behavior on any parse failure.

- [ ] **Step 1: Update the system prompt + user payload in `_chat_reply`**

In the first attempt's system message (currently "You are World Master, speaking inside the game. Reply in one plain in-game chat sentence..."), append:

```
You may also include one optional action. Respond ONLY as a JSON object:
{"reply": "<one short in-game sentence under 160 chars>", "intent": null}
or, to act, set "intent": {"verb": "<one kind from wm_tools.native_actions>", "args": {...}, "reason": "<why>"}.
Choose a verb only if the player clearly wants it. If unsure, set intent to null.
```

Keep the second (fallback) attempt exactly as-is — it remains the plain-sentence rescue path.

- [ ] **Step 2: Pass mode-filtered tools**

Where the user payload sets `"wm_tools": autoplay_tool_manifest()`, change to:

```python
"wm_tools": autoplay_tool_manifest(modes=control_config.get("conversational_verb_modes")),
```

- [ ] **Step 3: Parse intent out of the model reply**

After the existing `parsed = parse_json_object(content)` block resolves `reply`, extract an intent dict when present. Replace the success `return` inside the loop with:

```python
            reply = _sanitize_chat_reply(reply)
            reply = _guard_chat_reply(reply)
            intent = None
            if isinstance(parsed, dict) and isinstance(parsed.get("intent"), dict):
                raw = parsed["intent"]
                verb = str(raw.get("verb") or "").strip()
                if verb:
                    intent = {
                        "verb": verb,
                        "args": raw.get("args") if isinstance(raw.get("args"), dict) else {},
                        "reason": str(raw.get("reason") or "")[:300],
                    }
            if reply:
                return {"message": reply, "raw_content": content, "source": "llm",
                        "model": settings.model, "intent": intent}
```

(The second attempt and all fallbacks return without an `intent` key — callers must treat a missing key as "no intent".)

- [ ] **Step 4: Live proof (no unit test — integration glue)**

Run the chat CLI against a running LM Studio; confirm structured output is parsed and plain replies still work:

```powershell
python -m wm.autoplay chat --player-guid 5408 --message "just say hello" --summary
python -m wm.autoplay chat --player-guid 5408 --message "heal me" --summary
```

Expected: first returns a normal sentence (no action yet — wiring is Task 7); second's raw model output should contain an `intent` (visible in the autoplay journal `drafts`/`chat` records). If the model emits prose instead of JSON, the reply must still be delivered.

- [ ] **Step 5: Commit**

```bash
git add src/wm/autoplay/service.py
git commit -m "feat(autoplay): chat model may emit an optional typed intent"
```

---

## Task 7: Wire the action loop (compile -> gate -> apply/confirm)

**Files:**
- Modify: `src/wm/autoplay/service.py` (`chat_once` ~399, `_reply_to_chat_event` ~465, and a new `_handle_intent` + generalized apply helper)

This is the keystone. The chat handlers gain three responsibilities, in order: (1) resolve a pending intent if the message is yes/no; (2) deliver the model reply; (3) if the reply carried an intent, compile -> dry-run -> auto-apply or park-for-confirm.

- [ ] **Step 1: Add a pending-resolution + intent-handling block**

Add these methods to `AutoplayService`:

```python
# src/wm/autoplay/service.py  (new methods on AutoplayService)
    def _resolve_pending_if_yes_no(self, *, settings, control_config, player_guid, message):
        from wm.autoplay.intent import is_affirmation, is_negation
        pending = self.store.load_pending_intent(player_guid)
        if not pending:
            return None
        if is_negation(message):
            self.store.clear_pending_intent(player_guid, reason="player_declined")
            return self._speak(settings=settings, player_guid=player_guid,
                               text="Understood, I will hold off.", source_message=message)
        if is_affirmation(message):
            return self._apply_pending(settings=settings, player_guid=player_guid,
                                       pending=pending, source_message=message)
        # ambiguous -> drop the stale pending and let normal handling proceed
        self.store.clear_pending_intent(player_guid, reason="superseded")
        return None

    def _handle_intent(self, *, settings, control_config, player_guid, intent, source_message):
        from wm.autoplay.intent import IntentRejection, compile_intent
        compiled = compile_intent(
            player_guid=player_guid,
            verb=str(intent.get("verb") or ""),
            args=intent.get("args") if isinstance(intent.get("args"), dict) else {},
            modes=control_config.get("conversational_verb_modes"),
            reason=str(intent.get("reason") or ""),
        )
        if isinstance(compiled, IntentRejection):
            self.store.add_issue({"reason": "intent_rejected", "kind": "intent",
                                  "detail": compiled.reason, "payload": {"intent": intent, "player_guid": player_guid}})
            return {"intent": "rejected", "reason": compiled.reason}
        coordinator = self._control_coordinator(settings)
        dry = coordinator.execute(proposal=compiled.proposal, mode="dry-run", confirm_live_apply=False)
        if dry.status != "dry-run":
            self.store.add_issue({"reason": "intent_dry_run_failed", "kind": "intent",
                                  "detail": _result_to_dict(dry), "payload": {"verb": compiled.verb}})
            self._speak(settings=settings, player_guid=player_guid,
                        text=f"I cannot do that right now ({compiled.verb}).", source_message=source_message)
            return {"intent": "dry_run_failed"}
        if compiled.mode == "auto":
            return self._apply_compiled(settings=settings, player_guid=player_guid,
                                        compiled=compiled, source_message=source_message)
        # confirm mode -> park pending, surfaced in chat + panel inbox (same record)
        self.store.set_pending_intent(player_guid, {
            "verb": compiled.verb, "risk": compiled.risk,
            "summary": intent.get("reason") or compiled.verb,
            "proposal": compiled.proposal.model_dump(mode="json"),
        }, ttl_seconds=120)
        self._speak(settings=settings, player_guid=player_guid,
                    text=f"I can {compiled.verb.replace('_', ' ')} - say yes to confirm.",
                    source_message=source_message)
        return {"intent": "pending", "verb": compiled.verb}
```

- [ ] **Step 2: Add the generalized apply + speak helpers**

`_speak` is the generalized version of today's chat send; `_apply_compiled` / `_apply_pending` apply any compiled proposal and confirm in chat. Reuse the existing dry-run/apply/journal shape from `_send_chat_reply` (lines 557-583):

```python
# src/wm/autoplay/service.py  (new methods on AutoplayService)
    def _speak(self, *, settings, player_guid, text, source_message):
        proposal = _chat_action_proposal(player_guid=player_guid, message=text, source_message=source_message)
        coordinator = self._control_coordinator(settings)
        dry = coordinator.execute(proposal=proposal, mode="dry-run", confirm_live_apply=False)
        if dry.status != "dry-run":
            return {"ok": False, "error": "speak_dry_run_failed"}
        applied = coordinator.execute(proposal=proposal, mode="apply", confirm_live_apply=True)
        return {"ok": applied.status == "applied", "apply": _result_to_dict(applied)}

    def _apply_compiled(self, *, settings, player_guid, compiled, source_message):
        coordinator = self._control_coordinator(settings)
        applied = coordinator.execute(proposal=compiled.proposal, mode="apply", confirm_live_apply=True)
        record = {"at": utc_now_iso(), "player_guid": int(player_guid), "verb": compiled.verb,
                  "risk": compiled.risk, "source_message": source_message, "apply": _result_to_dict(applied)}
        self.store.append_journal("deed", record)
        ok = applied.status == "applied"
        counters_status = self.store.load_status()
        counters = dict(counters_status.get("counters") or {})
        counters["auto_applied"] = int(counters.get("auto_applied") or 0) + (1 if ok else 0)
        self.store.update_status(counters=counters)
        msg = (f"Done - {compiled.verb.replace('_', ' ')}." if ok
               else f"That did not take ({compiled.verb}).")
        self._speak(settings=settings, player_guid=player_guid, text=msg, source_message=source_message)
        if not ok:
            self.store.add_issue({"reason": "intent_apply_failed", "kind": "intent", "detail": record})
        return {"intent": "applied" if ok else "apply_failed", "verb": compiled.verb}

    def _apply_pending(self, *, settings, player_guid, pending, source_message):
        from wm.control.models import ControlProposal
        from wm.autoplay.intent import CompiledIntent
        proposal = ControlProposal.model_validate(pending["proposal"])
        compiled = CompiledIntent(proposal=proposal, verb=pending.get("verb", "action"),
                                  mode="confirm", risk=pending.get("risk", "medium"))
        self.store.clear_pending_intent(player_guid, reason="player_confirmed")
        return self._apply_compiled(settings=settings, player_guid=player_guid,
                                    compiled=compiled, source_message=source_message)
```

- [ ] **Step 3: Call the new blocks from `chat_once` and `_reply_to_chat_event`**

In `chat_once`, after computing `player_guid` and before the `_is_forget_context_command` check, add:

```python
        resolved = self._resolve_pending_if_yes_no(
            settings=settings, control_config=control_config, player_guid=player_guid, message=message)
        if resolved is not None:
            return {"ok": True, "pending_resolution": resolved}
```

After the existing `_send_chat_reply(...)` call returns (the normal reply), if the reply carried an intent, handle it. Change the trailing `return self._send_chat_reply(...)` to capture the result and then dispatch the intent:

```python
        send_result = self._send_chat_reply(
            settings=settings, player_guid=player_guid, source_message=message,
            reply=reply, source_event=None, world_context=world_context)
        if reply.get("intent"):
            send_result["intent_result"] = self._handle_intent(
                settings=settings, control_config=control_config, player_guid=player_guid,
                intent=reply["intent"], source_message=message)
        return send_result
```

Apply the **same two additions** in `_reply_to_chat_event` (the in-game path): add the `_resolve_pending_if_yes_no` guard right after `player_guid = int(player_guid_value)` and the message non-empty check; and after its `_send_chat_reply(...)` add the identical `if reply.get("intent"):` dispatch.

- [ ] **Step 4: Live proof**

With the full stack up (launcher), in-game `/join WM`:

```
heal me
spawn a wolf to hunt me
yes
no
```

Expected: "heal me" (low/auto) restores you and WM confirms "Done - ...". "spawn..." (medium/confirm) replies "I can creature spawn - say yes to confirm"; "yes" spawns the WM-owned creature and WM confirms; a later "no" to a fresh prompt holds off. Verify via `python -m wm.autoplay status --summary` (counters `auto_applied` rising) and the `wm_bridge_action_request` rows showing the chosen verb, not `world_announce_to_player`.

- [ ] **Step 5: Commit**

```bash
git add src/wm/autoplay/service.py
git commit -m "feat(autoplay): conversational action loop - compile, gate, apply, confirm"
```

---

## Task 8: Panel — verb-mode checklist + pending approvals

**Files:**
- Modify: `src/wm/panel/server.py`, `src/wm/panel/static/{app.js,index.html,style.css}`

> Before editing, read the existing settings-sync handler and the approval inbox handlers in `server.py` (search for `conversational` is fruitless — search the existing `/api/settings` and inbox routes) and follow their exact request/response shape. The two sub-features below must reuse those patterns, not invent new routing.

- [ ] **Step 1: Expose verb modes via settings**

Extend the existing settings GET to include `conversational_verb_modes` (defaulting via `resolve_verb_modes(None)`), and the settings POST to accept a `conversational_verb_modes` object, normalize it through `resolve_verb_modes`, and persist it into autoplay config via the same `AutoplayStateStore.configure(...)` sync the panel already uses for `llm_model`/lanes.

```python
# server.py settings GET payload addition
from wm.autoplay.intent import resolve_verb_modes
settings_payload["conversational_verb_modes"] = resolve_verb_modes(
    autoplay_config.get("conversational_verb_modes"))
```

```python
# server.py settings POST handling addition
if isinstance(body.get("conversational_verb_modes"), dict):
    store.configure({"conversational_verb_modes": resolve_verb_modes(body["conversational_verb_modes"])})
```

- [ ] **Step 2: Render the checklist (Advanced panel)**

In `index.html` add a "Conversational actions" section; in `app.js` fetch settings, render one row per verb from `conversational_verb_modes` with a checkbox (checked = `auto`) and a disable control (unchecked+disabled = `off`; unchecked+enabled = `confirm`); on change POST the full `conversational_verb_modes` map. Style minimally in `style.css`. The Simple panel shows only a count summary ("N verbs auto, M confirm").

- [ ] **Step 3: Pending approvals in the inbox**

Add the current `pending_intents` (from autoplay status) to the existing approval inbox list. Wire its approve button to a new `POST /api/wm/autoplay/intent/approve` (body `{player_guid}`) that calls a thin service entrypoint applying the stored pending proposal (reuse `_apply_pending` via a public `AutoplayService.approve_pending(player_guid)` wrapper), and reject to `.../intent/reject` calling `store.clear_pending_intent`. Approving/rejecting here clears the same record the in-chat path uses (single source of truth).

- [ ] **Step 4: Live proof**

Open the panel app. Toggle `creature_spawn` to auto; in-game it now spawns without a confirm. Toggle it back to confirm; trigger a spawn intent in chat, see it appear in the panel inbox, approve it there, and confirm the creature spawns and the in-chat pending clears. Toggle a verb to off; confirm the WM stops proposing it.

- [ ] **Step 5: Commit**

```bash
git add src/wm/panel/server.py src/wm/panel/static/app.js src/wm/panel/static/index.html src/wm/panel/static/style.css
git commit -m "feat(panel): verb-mode auto-apply checklist + conversational approvals inbox"
```

---

## Final verification

- [ ] Run the full suite, confirm green (acceptance gate, not the deliverable):

```powershell
python -m pytest -q
python -m wm.status --validate
```

- [ ] Walk the spec §8 acceptance criteria in-client end to end.
- [ ] Update `data/specs/feature_status.json`: add `autoplay.conversational_action_loop` with `repo_status=WORKING`, `gameplay_status` set honestly from the live walk (`PARTIAL` until every §8 line is proven).

---

## Self-Review

**Spec coverage:** §4 flow -> Tasks 6+7. §5.1 schema -> Task 6. §5.2 compiler -> Task 3. §5.3 manifest/modes -> Tasks 1,2. §5.4 pending store -> Task 5. §5.5 affirmation -> Task 4. §5.6 panel -> Task 8. §5.7 apply/confirm/journal -> Task 7. §6 safety -> compiler locks guid (T3) + operator modes (T1) + existing coordinator (T7). §7 degradation -> Task 6 step 3 + Task 7 rejection paths. §8 acceptance -> Final verification. No gaps.

**Placeholder scan:** No TBD/TODO. Task 8 intentionally instructs reading existing panel routes first because the stdlib router conventions must be matched exactly; the handler logic to add is shown.

**Type consistency:** `compile_intent` returns `CompiledIntent | IntentRejection` (T3) consumed in T7 with `isinstance(..., IntentRejection)`; `CompiledIntent` fields `.proposal/.verb/.mode/.risk` used consistently. `resolve_verb_modes` signature `(config)` used in T1/T2/T3/T8. Pending record keys (`verb`,`risk`,`proposal`) written in T7 step 1 match reads in T7 step 2 `_apply_pending`. `autoplay_tool_manifest(modes=...)` keyword consistent T2/T6.
