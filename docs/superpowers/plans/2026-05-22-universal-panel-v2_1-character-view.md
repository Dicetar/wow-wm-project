# Universal Panel V2.1 — Character-Scoped Operator View + GUID De-hardcode

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the WM panel show the *active scoped character's* state (journey, unlocks, rewards, prompt queue, readiness, open-proposal counts) for **any** GUID, and enforce that no test-subject GUID (`5405/5406/5408`) is hardcoded in a generic code path.

**Architecture:** Add a pure read-side aggregator (`wm.character.overview`) that composes the existing `CharacterStateReader`/`CharacterJourneyStore` bundle into a JSON-able summary; expose it via a new `/api/wm/session/overview` endpoint scoped to the persisted active session GUID (built on Codex's V1 `/api/wm/*` + `state.load_session()`); and lock the universality invariant with a guard test that fixes the remaining hardcoded GUIDs. No new mutation lanes — approval/publish stay on the existing contracts.

**Tech Stack:** Python 3.14, stdlib HTTP panel, `pytest`, vanilla JS UI. Builds on `src/wm/panel/{server,state,catalog}.py`, `src/wm/character/{reader,journey}.py`.

**Out of scope (separate V2.2 plan):** unifying generic quest/item/spell/action proposal *approval* into one inbox. That overlaps the `/api/jobs/*` + control-proposal systems and needs its own spec. This plan is the read-side view + de-hardcode only.

**Run focused tests:** `python -m pytest <path> -q`. Full suite: `python -m pytest -q` (must stay green; baseline `922 passed`).

---

## File structure

- Create `src/wm/character/overview.py` — pure `build_character_overview(...)` aggregator (no I/O).
- Create `tests/test_character_overview.py` — unit tests for the aggregator.
- Create `tests/test_no_hardcoded_test_guids.py` — the universality guard test.
- Modify `src/wm/living/catalog.py` — replace Jecia/`5406` demo sample data with a labeled synthetic constant.
- Modify `src/wm/arcs/factory.py` + `src/wm/content/playcycle.py` — de-Jecia the BridgeLab advisory note (key off ports, not GUID).
- Modify `src/wm/candidates/release_pack.py` + `src/wm/reactive/install_bounty.py` — remove `5406` fallback defaults.
- Modify `src/wm/panel/server.py` — injectable `character_reader` + `/api/wm/session/overview` endpoint.
- Modify `tests/panel/test_server_slice.py` — endpoint test with an injected fake reader.
- Modify `src/wm/panel/static/{index.html,app.js}` — a "Character" subsection in the WM Session tab.

---

## Task 1: Universality guard test + de-hardcode remaining GUIDs (Lane C)

**Files:**
- Create: `tests/test_no_hardcoded_test_guids.py`
- Modify: `src/wm/living/catalog.py:30-55`, `src/wm/arcs/factory.py:1025-1028`, `src/wm/content/playcycle.py:1234-1238`, `src/wm/candidates/release_pack.py:327,698`, `src/wm/reactive/install_bounty.py:586`

- [ ] **Step 1: Write the failing guard test**

```python
# tests/test_no_hardcoded_test_guids.py
from __future__ import annotations
import re
from pathlib import Path

# Test-subject GUIDs are canaries, not architecture. They may appear ONLY in
# Broug-specific content modules and arc-proof tooling (whose defaults are
# overridable), plus tests/examples. Generic code paths must stay GUID-agnostic.
_FORBIDDEN = ("5405", "5406", "5408")
_ALLOWLIST = {
    "src/wm/spells/broug_empty_court.py",
    "src/wm/spells/broug_lightness.py",
    "src/wm/live/proof_packet.py",
    "src/wm/bridge_lab/release_gate.py",
    "src/wm/content/preflight.py",
}


def _violations() -> list[str]:
    root = Path("src/wm")
    pattern = re.compile(r"\b(5405|5406|5408)\b")
    out: list[str] = []
    for path in root.rglob("*.py"):
        rel = path.as_posix()
        if rel in _ALLOWLIST:
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                out.append(f"{rel}:{i}: {line.strip()}")
    return out


def test_no_hardcoded_test_subject_guids_in_generic_code_paths():
    violations = _violations()
    assert not violations, "Hardcoded test-subject GUIDs in generic code paths:\n" + "\n".join(violations)
```

- [ ] **Step 2: Run it to see the violations**

Run: `python -m pytest tests/test_no_hardcoded_test_guids.py -q`
Expected: FAIL, listing the `living/catalog.py`, `arcs/factory.py`, `content/playcycle.py`, `candidates/release_pack.py`, `reactive/install_bounty.py` lines.

- [ ] **Step 3: Neutralize `living/catalog.py` demo data**

The `_*_demo()` builders feed `dry_run_all()`'s self-test; the player is sample data, not a real target. Add a labeled constant and use it. Replace lines 30-55:

```python
# Synthetic sample identity for the dry-run self-test only. NOT a real
# scoped player; the live catalog operates on whatever GUID the operator
# selects. Kept distinct from any real test-subject GUID on purpose.
SAMPLE_PLAYER_GUID = 9_999_001
SAMPLE_PLAYER_NAME = "SampleHero"


def _nemesis_demo():
    return nemesis.evaluate_nemesis(
        nemesis.NemesisTrigger(player_guid=SAMPLE_PLAYER_GUID, subject_entry=46, subject_name="Murloc Forager", kill_count=12, player_name=SAMPLE_PLAYER_NAME)
    )


def _rumor_demo():
    return rumor.evaluate_rumor(
        rumor.RumorTrigger(player_guid=SAMPLE_PLAYER_GUID, player_name=SAMPLE_PLAYER_NAME, subject_name="Defias", deed_count=12, zone_name="Westfall")
    )


def _legend_demo():
    return legend.evaluate_legend(
        legend.LegendTrigger(player_guid=SAMPLE_PLAYER_GUID, player_name=SAMPLE_PLAYER_NAME, zone_name="Westfall", deed_count=80)
    )


def _patron_demo():
    return patron.evaluate_patron(patron.PatronTrigger(player_guid=SAMPLE_PLAYER_GUID, player_name=SAMPLE_PLAYER_NAME, completed_wm_count=10))


def _oath_demo():
    return oath.evaluate_oath(
        oath.OathTrigger(player_guid=SAMPLE_PLAYER_GUID, player_name=SAMPLE_PLAYER_NAME, oath_key="no_death", constraint_label="no deaths for 20 kills", target_count=20, current_count=20, phase="resolve")
    )
```

- [ ] **Step 4: De-Jecia the BridgeLab advisory note in `arcs/factory.py`**

Replace `_bridge_lab_notes` body (lines ~1025-1028):

```python
def _bridge_lab_notes(*, settings: Settings, player_guid: int) -> list[str]:
    del player_guid  # advisory is about ports, not a specific character
    if int(settings.world_db_port) != 33307 or int(settings.char_db_port) != 33307:
        return ["BridgeLab proof expects WM_WORLD_DB_PORT=33307 and WM_CHAR_DB_PORT=33307."]
    return []
```

- [ ] **Step 5: Same fix in `content/playcycle.py`**

Find the matching block near line 1234-1238 (`if int(player_guid) == 5406 and (...ports...)`) and replace its condition the same way — drop the `int(player_guid) == 5406 and` clause so the note triggers purely on non-BridgeLab ports, and remove "Jecia" from the message text. Read the surrounding function first to preserve its exact signature/return type.

- [ ] **Step 6: Remove `5406` fallbacks in `candidates/release_pack.py`**

Line 327 (a note string): change `"Use BridgeLab player 5406 unless the context pack explicitly names another scoped player."` to `"Provide the scoped player GUID explicitly (e.g. via the context pack)."`.
Line 698: change the trailing `or 5406` so a missing GUID is explicit rather than defaulted to a canary:

```python
    return _positive_int(player.get("guid") or generation.get("player_guid") or context_pack.get("player_guid"))
```

(Read the call site; if a `None` return needs handling, add a clear `ValueError("scoped player_guid is required")` where the value is consumed rather than silently defaulting.)

- [ ] **Step 7: Remove `5406` fallback in `reactive/install_bounty.py`**

Line 586: replace the `5406` final fallback with an explicit error:

```python
    player_guid = _coalesce(args.player_guid, template.get("player_guid"))
    if player_guid is None:
        parser.error("--player-guid is required (no scoped player in the template)")
    player_guid = int(player_guid)
```

(Confirm `_coalesce` tolerates being called without the trailing default; if its signature requires ≥1 fallback, pass `None`.)

- [ ] **Step 8: Run the guard + affected tests**

Run: `python -m pytest tests/test_no_hardcoded_test_guids.py tests/ -k "living or release_pack or install_bounty or playcycle or arc_factory or factory" -q`
Expected: guard test PASSES; no regressions. If a `living`/`candidates` test asserted `5406`/`Jecia`, update it to the new sample constant / explicit-GUID behavior (those are content/test assertions, allowed to change).

- [ ] **Step 9: Commit**

```bash
git add tests/test_no_hardcoded_test_guids.py src/wm/living/catalog.py src/wm/arcs/factory.py src/wm/content/playcycle.py src/wm/candidates/release_pack.py src/wm/reactive/install_bounty.py
git commit -m "refactor(wm): de-hardcode test-subject GUIDs in generic code paths + guard test"
```

---

## Task 2: Character overview aggregator (pure read-side)

**Files:**
- Create: `src/wm/character/overview.py`
- Test: `tests/test_character_overview.py`

The aggregator turns a `CharacterStateBundle` (from `wm.character.reader`/`journey`) plus optional readiness + proposal-count inputs into a JSON-able summary. Pure function, no DB/HTTP — so it unit-tests without a live stack.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_character_overview.py
from wm.character.reader import CharacterStateBundle
from wm.character.overview import build_character_overview


def test_overview_summarizes_bundle_counts_and_status():
    bundle = CharacterStateBundle(
        profile=None,
        arc_states=[object(), object()],
        unlocks=[object()],
        rewards=[],
        conversation_steering=[object()],
        prompt_queue=[object(), object(), object()],
        status="WORKING",
        notes=["seeded"],
    )
    ov = build_character_overview(
        player_guid=5408, bundle=bundle,
        readiness={"ok": True}, proposal_counts={"pending": 2, "issues": 1},
    )
    assert ov["player_guid"] == 5408
    assert ov["status"] == "WORKING"
    assert ov["has_profile"] is False
    assert ov["counts"] == {
        "arc_states": 2, "unlocks": 1, "rewards": 0,
        "conversation_steering": 1, "prompt_queue": 3,
    }
    assert ov["readiness"] == {"ok": True}
    assert ov["proposals"] == {"pending": 2, "issues": 1}
    assert ov["notes"] == ["seeded"]


def test_overview_handles_missing_optionals():
    bundle = CharacterStateBundle(status="UNKNOWN")
    ov = build_character_overview(player_guid=1, bundle=bundle)
    assert ov["player_guid"] == 1
    assert ov["status"] == "UNKNOWN"
    assert ov["has_profile"] is False
    assert ov["counts"]["arc_states"] == 0
    assert ov["readiness"] is None
    assert ov["proposals"] is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_character_overview.py -q`
Expected: FAIL — `ModuleNotFoundError: wm.character.overview`.

- [ ] **Step 3: Implement the aggregator**

```python
# src/wm/character/overview.py
"""Read-side character overview for the operator panel.

Pure aggregation over a CharacterStateBundle (wm.character.reader) plus optional
readiness + proposal-count inputs. No DB or HTTP here so it is unit-testable and
reusable; the panel endpoint supplies the bundle/readiness from live readers.
"""
from __future__ import annotations
from typing import Any

from wm.character.reader import CharacterStateBundle


def build_character_overview(
    *,
    player_guid: int,
    bundle: CharacterStateBundle,
    readiness: dict[str, Any] | None = None,
    proposal_counts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "player_guid": int(player_guid),
        "status": bundle.status,
        "has_profile": bundle.profile is not None,
        "counts": {
            "arc_states": len(bundle.arc_states),
            "unlocks": len(bundle.unlocks),
            "rewards": len(bundle.rewards),
            "conversation_steering": len(bundle.conversation_steering),
            "prompt_queue": len(bundle.prompt_queue),
        },
        "notes": list(bundle.notes),
        "readiness": readiness,
        "proposals": proposal_counts,
    }
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_character_overview.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/wm/character/overview.py tests/test_character_overview.py
git commit -m "feat(character): pure read-side character overview aggregator"
```

---

## Task 3: `/api/wm/session/overview` endpoint (active-GUID scoped)

**Files:**
- Modify: `src/wm/panel/server.py` (PanelApp `__init__` injection + GET route + handler)
- Test: `tests/panel/test_server_slice.py`

- [ ] **Step 1: Write the failing endpoint test** (append to `tests/panel/test_server_slice.py`)

```python
def test_wm_session_overview_uses_active_session_guid():
    from wm.panel.server import PanelApp
    from wm.panel.state import PanelState
    from wm.character.reader import CharacterStateBundle
    import tempfile, json
    from pathlib import Path

    captured = {}

    def fake_reader(player_guid: int) -> CharacterStateBundle:
        captured["guid"] = player_guid
        return CharacterStateBundle(status="WORKING", arc_states=[object()])

    with tempfile.TemporaryDirectory() as d:
        state = PanelState(Path(d))
        state.ensure()
        state.save_session({"character_guid": 5408, "marker_spell_id": 946602})
        app = PanelApp(state=state, character_reader=fake_reader)
        status, payload = app.get("/api/wm/session/overview")

    assert status == 200
    assert payload["ok"] is True
    assert captured["guid"] == 5408
    assert payload["overview"]["player_guid"] == 5408
    assert payload["overview"]["status"] == "WORKING"
    assert payload["overview"]["counts"]["arc_states"] == 1


def test_wm_session_overview_400_without_active_session():
    from wm.panel.server import PanelApp
    from wm.panel.state import PanelState
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        state = PanelState(Path(d))
        state.ensure()
        app = PanelApp(state=state, character_reader=lambda player_guid: None)
        status, payload = app.get("/api/wm/session/overview")
    assert status == 400
    assert payload["ok"] is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/panel/test_server_slice.py -k overview -q`
Expected: FAIL — `PanelApp` has no `character_reader` kwarg / route 404.

- [ ] **Step 3: Add the injection + route + handler in `server.py`**

In `PanelApp.__init__`, add a keyword param mirroring the existing injection style (read the current `__init__` signature first and place it alongside `slice_factory`/`marker_discoverer`):

```python
        character_reader: Callable[[int], Any] | None = None,
        ...
        self._character_reader = character_reader  # default built lazily from MysqlCliClient+Settings
```

In the GET dispatch (next to the other `/api/wm/...` routes near line 117-123):

```python
        if path == "/api/wm/session/overview":
            return self._wm_session_overview()
```

Add the handler:

```python
    def _wm_session_overview(self) -> tuple[int, Any]:
        session = self.state.load_session()
        guid = (session or {}).get("character_guid")
        if guid in (None, ""):
            return 400, {"ok": False, "error": "no active session; bootstrap a character first"}
        guid = int(guid)
        reader = self._character_reader or _default_character_reader
        try:
            bundle = reader(guid)
        except Exception as exc:  # live DB unreachable, etc.
            return 200, {"ok": True, "overview": None, "error": f"character read failed: {exc}"}
        from wm.character.overview import build_character_overview
        readiness = self._wm_readiness().get("doctor")
        proposal_counts = None
        if self._slice is not None:
            try:
                proposal_counts = {
                    "pending": len(self._slice.gate.pending()),
                    "issues": len(self._slice.issues.list_open()),
                }
            except Exception:
                proposal_counts = None
        overview = build_character_overview(
            player_guid=guid, bundle=bundle,
            readiness=readiness, proposal_counts=proposal_counts,
        )
        return 200, {"ok": True, "overview": overview}
```

Add the default reader near the other module-level helpers (e.g. by `_session_from_marker_candidate`):

```python
def _default_character_reader(player_guid: int):
    from wm.character.reader import load_character_state
    from wm.config import Settings
    from wm.db.mysql_cli import MysqlCliClient
    return load_character_state(client=MysqlCliClient(), settings=Settings.from_env(), character_guid=int(player_guid))
```

(Confirm `load_character_state` is exported from `wm.character.reader` — it is defined there at module scope. Confirm `Callable`/`Any` are imported in `server.py`; add `from typing import Any, Callable` if missing.)

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/panel/test_server_slice.py -k overview -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Full panel suite (no regression)**

Run: `python -m pytest tests/panel -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/wm/panel/server.py tests/panel/test_server_slice.py
git commit -m "feat(panel): /api/wm/session/overview scoped to active session GUID"
```

---

## Task 4: "Character" UI section in the WM Session tab

**Files:**
- Modify: `src/wm/panel/static/index.html`, `src/wm/panel/static/app.js`

This is browser UI; there is no JS unit harness in-repo, so verification is a manual smoke (documented) plus confirming the endpoint it calls is covered by Task 3.

- [ ] **Step 1: Add the markup** — in `index.html`, inside the WM Session tab/section, add a container (read the existing WM Session markup first and match its class/structure):

```html
<section id="wm-character" class="card">
  <h3>Character</h3>
  <div id="wm-character-empty">No active session. Bootstrap a character to see state.</div>
  <dl id="wm-character-body" hidden>
    <dt>GUID</dt><dd id="wm-char-guid"></dd>
    <dt>Status</dt><dd id="wm-char-status"></dd>
    <dt>Arc states</dt><dd id="wm-char-arcs"></dd>
    <dt>Unlocks</dt><dd id="wm-char-unlocks"></dd>
    <dt>Rewards</dt><dd id="wm-char-rewards"></dd>
    <dt>Prompt queue</dt><dd id="wm-char-prompts"></dd>
    <dt>Open proposals</dt><dd id="wm-char-proposals"></dd>
    <dt>Live readiness</dt><dd id="wm-char-readiness"></dd>
  </dl>
</section>
```

- [ ] **Step 2: Add the fetch/render in `app.js`** — match the file's existing fetch/render style (read it first):

```javascript
async function refreshCharacterOverview() {
  const empty = document.getElementById('wm-character-empty');
  const body = document.getElementById('wm-character-body');
  let data;
  try {
    data = await (await fetch('/api/wm/session/overview')).json();
  } catch (e) { return; }
  if (!data.ok || !data.overview) {
    empty.hidden = false; body.hidden = true;
    empty.textContent = data.error || 'No active session. Bootstrap a character to see state.';
    return;
  }
  const o = data.overview;
  document.getElementById('wm-char-guid').textContent = o.player_guid;
  document.getElementById('wm-char-status').textContent = o.status;
  document.getElementById('wm-char-arcs').textContent = o.counts.arc_states;
  document.getElementById('wm-char-unlocks').textContent = o.counts.unlocks;
  document.getElementById('wm-char-rewards').textContent = o.counts.rewards;
  document.getElementById('wm-char-prompts').textContent = o.counts.prompt_queue;
  document.getElementById('wm-char-proposals').textContent = o.proposals
    ? `${o.proposals.pending} pending / ${o.proposals.issues} issues` : 'n/a';
  document.getElementById('wm-char-readiness').textContent = o.readiness
    ? (o.readiness.ok ? 'ready' : 'not ready') : 'n/a';
  empty.hidden = true; body.hidden = false;
}
```

Call `refreshCharacterOverview()` wherever the WM Session tab refreshes (after bootstrap and after poll — find the existing refresh hook and add the call alongside the status refresh).

- [ ] **Step 3: Manual smoke (documented, not blocking CI)**

Run: `python -m wm.panel serve` (no live DB needed to load the page). Open the panel, WM Session tab. With no session: the Character card shows the empty message. (Full data requires BridgeLab + a bootstrapped GUID — that is the V2 live-proof, gated separately.)

- [ ] **Step 4: Commit**

```bash
git add src/wm/panel/static/index.html src/wm/panel/static/app.js
git commit -m "feat(panel-ui): Character overview section in the WM Session tab"
```

---

## Task 5: Full suite + invariant confirmation

- [ ] **Step 1: Full suite twice (floor rule)**

Run: `python -m pytest -q` then `python -m pytest -q`
Expected: both green (≥ `924 passed` — baseline `922` + new tests), no `--ignore`.

- [ ] **Step 2: Guard + skills + status**

Run: `python -m pytest tests/test_no_hardcoded_test_guids.py -q && python scripts/validate_agent_skills.py && python -m wm.status --validate`
Expected: guard PASS, skills OK, status OK.

- [ ] **Step 3: Commit any fixups**

```bash
git add -u && git commit -m "test: green full suite for universal panel v2.1"
```

---

## Live-proof (deferred, BridgeLab-gated — not part of this plan's green bar)

Once the operator brings BridgeLab up (`start-bridge-lab-all.bat`; `WM_WORLD_DB_PORT=33307 WM_CHAR_DB_PORT=33307 WM_SOAP_PORT=7879`): mark a character with `946602`, bootstrap via the panel, and confirm `/api/wm/session/overview` returns real journey/state for the **discovered** GUID (not a hardcoded one). Record in `docs/LIVE_PROOF_BACKLOG.md`. No gameplay/live label moves to `WORKING` until this passes.

---

## Self-review notes

- **Spec coverage:** step 3 "panel shows character state/journey/journal/context/readiness/open proposals" → Tasks 2-4 (journey/state/unlocks/rewards/prompt-queue + readiness + proposal counts; journal/context summaries deferred — YAGNI, can extend the aggregator later). "no hardcoded 5405 except canaries" → Task 1 guard test + fixes. Active-GUID scoping (not hardcoded) → Task 3 reads `state.load_session()`. Generic cross-lane *approval* → explicitly deferred to V2.2.
- **Placeholder scan:** every code step has complete code; the few "read the surrounding function first" notes are integration-matching instructions (real function bodies shown for the load-bearing edits), not deferred work.
- **Type consistency:** `build_character_overview(*, player_guid, bundle, readiness=None, proposal_counts=None)` is defined in Task 2 and called identically in Task 3; `character_reader: Callable[[int], CharacterStateBundle]` injection name is consistent across Task 3 and its tests; `_default_character_reader` uses `load_character_state` (confirmed exported from `wm.character.reader`).
- **Assumption to verify during Task 3:** `PanelApp.get(path)` is the method the existing panel tests call — confirm the harness uses `app.get(...)`/`app.post(...)` (the file imports `PanelApp` directly); if the dispatch method differs, match it.
