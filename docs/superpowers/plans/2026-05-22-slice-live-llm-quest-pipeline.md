# Slice LIVE-LLM Quest Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the panel slice's proposal adapter from FIXTURE to LIVE so an LLM authors kill-bounty quest drafts (Phase 1, OPEN cards, no mutation) that get published to the world DB and granted on panel approval (Phase 2).

**Architecture:** Reuse the existing `LmStudioClient.generate_json` lane to emit the flat `BountyQuestDraft` shape the publish pipeline already consumes; screen with `ProposalParser` + `validate_bounty_quest_draft`; wrap into the existing slice `Proposal` envelope so the approval gate is unchanged. On approval, a `SlicePublishService` composes `ReservedSlotDbAllocator` + `QuestPublisher` + `SoapRuntimeClient` + the existing `apply_quest_grant_proposal` to mint and grant.

**Tech Stack:** Python 3.14, stdlib `urllib` (LM Studio HTTP), `pytest`, MySQL via `MysqlCliClient`, SOAP via `SoapRuntimeClient`. Design spec: `docs/superpowers/specs/2026-05-22-slice-live-llm-quest-pipeline-design.md`.

**Run focused tests with:** `python -m pytest <path> -q`. Full suite: `python -m pytest -q` (pre-existing unrelated failures: `tests/test_cli.py` CATALOG import; `tests/test_native_bridge_*` 8 fails — not ours).

---

## File structure

**Phase 1 (generation, no world mutation):**
- Create `control/schemas/wm.slice.bounty_draft.v1.schema.json` — JSON schema mirroring `BountyQuestDraft`, drives `generate_json` `response_format`.
- Modify `src/wm/quests/publish/__init__.py` — extract `bounty_draft_from_dict(raw)` from `load_bounty_quest_draft`.
- Modify `src/wm/llm/proposal_adapter.py` — real `_call_live`, `ProposalGenerationError`, LIVE branch in `propose`, injected deps.
- Modify `src/wm/cli/slice_demo.py` — thread `llm_client` + `quest_schema` into the `ProposalAdapter`.
- Modify `src/wm/panel/slice_wiring.py` + `src/wm/panel/server.py` — build `LmStudioClient` from settings, select LIVE.

**Phase 2 (publish-on-approval):**
- Create `src/wm/cli/slice_publish.py` — `SlicePublishService.publish_and_grant`.
- Modify `src/wm/cli/slice_demo_live.py` — `live_quest` uses the service (draft branch) or existing grant (grant_quest_id branch).

**Tests:** `tests/quests/test_bounty_draft_from_dict.py`, `tests/llm/test_proposal_adapter_live.py`, `tests/cli/test_slice_publish.py`, `tests/panel/test_server_slice_live.py`.

---

## Task 1: Reusable dict → BountyQuestDraft helper

**Files:**
- Modify: `src/wm/quests/publish/__init__.py:575-652` (`load_bounty_quest_draft`)
- Test: `tests/quests/test_bounty_draft_from_dict.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/quests/test_bounty_draft_from_dict.py
from wm.quests.publish import bounty_draft_from_dict
from wm.quests.models import BountyQuestDraft


def _raw() -> dict:
    return {
        "quest_id": 910503, "quest_level": 2, "min_level": 1,
        "questgiver_entry": 197, "questgiver_name": "Marshal McBride",
        "title": "Wolves at the Treeline",
        "quest_description": "Thin the wolves circling Northshire.",
        "objective_text": "Slay 6 Young Wolves.",
        "offer_reward_text": "The valley is safer for it.",
        "request_items_text": "Are the wolves dealt with?",
        "objective": {"target_entry": 299, "target_name": "Young Wolf", "kill_count": 6},
        "reward": {"money_copper": 250, "reward_xp_difficulty": 2},
        "start_npc_entry": None, "end_npc_entry": 197,
        "grant_mode": "direct_quest_add", "tags": ["wm-slice"],
        "template_defaults": {"SpecialFlags": 0},
    }


def test_bounty_draft_from_dict_builds_draft():
    draft = bounty_draft_from_dict(_raw())
    assert isinstance(draft, BountyQuestDraft)
    assert draft.quest_id == 910503
    assert draft.objective.target_entry == 299
    assert draft.objective.kill_count == 6
    assert draft.grant_mode == "direct_quest_add"


def test_load_bounty_quest_draft_still_works(tmp_path):
    import json
    from wm.quests.publish import load_bounty_quest_draft
    p = tmp_path / "d.json"
    p.write_text(json.dumps(_raw()), encoding="utf-8")
    assert load_bounty_quest_draft(p).quest_id == 910503
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/quests/test_bounty_draft_from_dict.py -q`
Expected: FAIL — `ImportError: cannot import name 'bounty_draft_from_dict'`.

- [ ] **Step 3: Refactor `load_bounty_quest_draft` to delegate**

In `src/wm/quests/publish/__init__.py`, replace the body of `load_bounty_quest_draft` (lines ~575-652) so the dict→draft logic lives in a new function. Add `bounty_draft_from_dict` and shrink `load_bounty_quest_draft`:

```python
def bounty_draft_from_dict(raw: dict) -> BountyQuestDraft:
    if isinstance(raw, dict) and isinstance(raw.get("draft"), dict):
        raw = raw["draft"]
    if not isinstance(raw, dict):
        raise ValueError("Quest draft JSON must be an object.")

    objective = raw.get("objective") or {}
    reward = raw.get("reward") or {}
    reward_reputations = [
        BountyQuestReputationReward(faction_id=int(item["faction_id"]), value=int(item["value"]))
        for item in reward.get("reputations", reward.get("reward_reputations", []))
    ]
    return BountyQuestDraft(
        quest_id=int(raw["quest_id"]),
        quest_level=int(raw["quest_level"]),
        min_level=int(raw["min_level"]),
        questgiver_entry=int(raw["questgiver_entry"]),
        questgiver_name=str(raw["questgiver_name"]),
        title=str(raw["title"]),
        quest_description=str(raw["quest_description"]),
        objective_text=str(raw["objective_text"]),
        offer_reward_text=str(raw["offer_reward_text"]),
        request_items_text=str(raw["request_items_text"]),
        objective=BountyQuestObjective(
            target_entry=int(objective["target_entry"]),
            target_name=str(objective["target_name"]),
            kill_count=int(objective["kill_count"]),
        ),
        reward=BountyQuestReward(
            money_copper=int(reward.get("money_copper", 0)),
            reward_item_entry=(int(reward["reward_item_entry"]) if reward.get("reward_item_entry") not in (None, "") else None),
            reward_item_name=(str(reward["reward_item_name"]) if reward.get("reward_item_name") not in (None, "") else None),
            reward_item_mode=str(reward.get("reward_item_mode") or "fixed"),
            reward_item_count=int(reward.get("reward_item_count", 1)),
            reward_xp_difficulty=(int(reward.get("reward_xp_difficulty", reward.get("xp_difficulty"))) if reward.get("reward_xp_difficulty", reward.get("xp_difficulty")) not in (None, "") else None),
            reward_spell_id=(int(reward["reward_spell_id"]) if reward.get("reward_spell_id") not in (None, "") else None),
            reward_spell_display_id=(int(reward["reward_spell_display_id"]) if reward.get("reward_spell_display_id") not in (None, "") else None),
            reward_reputations=reward_reputations,
        ),
        start_npc_entry=(int(raw["start_npc_entry"]) if raw.get("start_npc_entry") not in (None, "") else None),
        end_npc_entry=(int(raw["end_npc_entry"]) if raw.get("end_npc_entry") not in (None, "") else None),
        grant_mode=str(raw.get("grant_mode") or "npc_start"),
        tags=[str(x) for x in raw.get("tags", [])],
        template_defaults={str(k): v for k, v in (raw.get("template_defaults") or {}).items()},
    )


def load_bounty_quest_draft(path: str | Path) -> BountyQuestDraft:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return bounty_draft_from_dict(raw)
```

Add `"bounty_draft_from_dict"` to `__all__`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/quests/test_bounty_draft_from_dict.py -q`
Expected: PASS (2 passed). Also run `python -m pytest tests/ -k "publish or quest" -q` to confirm no regression in existing publish tests.

- [ ] **Step 5: Commit**

```bash
git add src/wm/quests/publish/__init__.py tests/quests/test_bounty_draft_from_dict.py
git commit -m "refactor(quests): extract bounty_draft_from_dict for in-memory drafts"
```

---

## Task 2: Slice bounty draft JSON schema

**Files:**
- Create: `control/schemas/wm.slice.bounty_draft.v1.schema.json`
- Test: `tests/quests/test_bounty_draft_from_dict.py` (extend)

- [ ] **Step 1: Write the failing test** (append to the Task 1 test file)

```python
def test_slice_bounty_schema_is_valid_json_and_constrains_kill_count():
    import json
    from pathlib import Path
    schema = json.loads(Path("control/schemas/wm.slice.bounty_draft.v1.schema.json").read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"]["const"] == "wm.slice.bounty_draft.v1"
    assert schema["properties"]["objective"]["properties"]["kill_count"]["maximum"] == 25
    for fld in ("title", "quest_description", "objective_text", "offer_reward_text",
                "request_items_text", "objective", "reward"):
        assert fld in schema["required"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/quests/test_bounty_draft_from_dict.py::test_slice_bounty_schema_is_valid_json_and_constrains_kill_count -q`
Expected: FAIL — `FileNotFoundError`.

- [ ] **Step 3: Create the schema file**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "title", "quest_description", "objective_text",
               "offer_reward_text", "request_items_text", "objective", "reward"],
  "properties": {
    "schema_version": {"type": "string", "const": "wm.slice.bounty_draft.v1"},
    "title": {"type": "string", "minLength": 1, "maxLength": 255},
    "quest_description": {"type": "string", "minLength": 1},
    "objective_text": {"type": "string", "minLength": 1},
    "offer_reward_text": {"type": "string", "minLength": 1},
    "request_items_text": {"type": "string", "minLength": 1},
    "narrative_summary": {"type": "string"},
    "objective": {
      "type": "object",
      "additionalProperties": false,
      "required": ["kill_count"],
      "properties": {"kill_count": {"type": "integer", "minimum": 1, "maximum": 25}}
    },
    "reward": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "money_copper": {"type": "integer", "minimum": 0, "maximum": 1000000},
        "reward_xp_difficulty": {"type": "integer", "minimum": 0}
      }
    }
  }
}
```

Note: fixed publish facts (`quest_id`, `questgiver_entry`, `objective.target_entry/target_name`, `end_npc_entry`, levels, `grant_mode`, `template_defaults`) are injected from `beat.constraints` in Task 3 — they are intentionally NOT in this schema so the model cannot set them.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/quests/test_bounty_draft_from_dict.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add control/schemas/wm.slice.bounty_draft.v1.schema.json tests/quests/test_bounty_draft_from_dict.py
git commit -m "feat(slice): add wm.slice.bounty_draft.v1 generation schema"
```

---

## Task 3: LIVE proposal adapter

**Files:**
- Modify: `src/wm/llm/proposal_adapter.py`
- Test: `tests/llm/test_proposal_adapter_live.py`

The LIVE adapter merges the LLM-authored prose with the fixed publish facts from `req.constraints`, screens + validates, and wraps into the existing `{kind, payload.quest_release}` envelope so `_validate` is unchanged.

- [ ] **Step 1: Write the failing test**

```python
# tests/llm/test_proposal_adapter_live.py
import json
from wm.llm.proposal_adapter import (
    ProposalAdapter, AdapterMode, ProposalKind, ProposalRequest,
)

SCHEMA = json.load(open("control/schemas/wm.slice.bounty_draft.v1.schema.json", encoding="utf-8"))

GOOD = {
    "schema_version": "wm.slice.bounty_draft.v1",
    "title": "Wolves at the Treeline",
    "quest_description": "Thin the wolves circling Northshire.",
    "objective_text": "Slay 6 Young Wolves.",
    "offer_reward_text": "The valley is safer for it.",
    "request_items_text": "Are the wolves dealt with?",
    "narrative_summary": "McBride sends you to thin the wolves.",
    "objective": {"kill_count": 6},
    "reward": {"money_copper": 250, "reward_xp_difficulty": 2},
}

CONSTRAINTS = {
    "quest_id_placeholder": 999000, "quest_level": 2, "min_level": 1,
    "questgiver_entry": 197, "questgiver_name": "Marshal McBride",
    "objective": {"target_entry": 299, "target_name": "Young Wolf"},
    "end_npc_entry": 197, "start_npc_entry": None,
    "grant_mode": "direct_quest_add", "template_defaults": {"SpecialFlags": 0},
}


class FakeClient:
    def __init__(self, parsed, content=None):
        self._parsed = parsed
        self._content = content if content is not None else json.dumps(parsed)
        self.calls = []

    def generate_json(self, **kwargs):
        self.calls.append(kwargs)
        return {"parsed": self._parsed, "content": self._content, "raw": {}, "request": {}}


def _req():
    return ProposalRequest(kind=ProposalKind.QUEST,
                           context={"character": {"guid": 5408}},
                           intent="A Northshire shake-out.",
                           constraints=CONSTRAINTS)


def test_live_good_draft_unblocked_with_embedded_flat_draft():
    client = FakeClient(GOOD)
    adapter = ProposalAdapter(mode=AdapterMode.LIVE, llm_client=client, quest_schema=SCHEMA)
    prop = adapter.propose(_req())
    assert prop.is_blocked is False
    qr = prop.payload["quest_release"]
    assert qr["title"] == "Wolves at the Treeline"
    assert qr["giver_creature_entry"] == 197
    assert qr["objective_kind"] == "kill"
    # the flat publish-ready draft is embedded, with fixed facts merged in
    assert qr["draft"]["objective"]["target_entry"] == 299
    assert qr["draft"]["objective"]["kill_count"] == 6
    assert qr["draft"]["grant_mode"] == "direct_quest_add"
    assert "grant_quest_id" not in qr
    assert prop.provenance["mode"] == "live"


def test_live_forbidden_pattern_blocks():
    bad = {**GOOD, "quest_description": "'; DROP TABLE quest_template; --"}
    adapter = ProposalAdapter(mode=AdapterMode.LIVE, llm_client=FakeClient(bad), quest_schema=SCHEMA)
    prop = adapter.propose(_req())
    assert prop.is_blocked is True
    assert "forbidden" in prop.block_reason.lower()


def test_live_validator_error_blocks():
    bad = {**GOOD, "objective": {"kill_count": 99}}  # >25
    adapter = ProposalAdapter(mode=AdapterMode.LIVE, llm_client=FakeClient(bad), quest_schema=SCHEMA)
    prop = adapter.propose(_req())
    assert prop.is_blocked is True
    assert "kill_count" in prop.block_reason


def test_live_llm_unreachable_blocks():
    class Boom:
        def generate_json(self, **kwargs):
            raise RuntimeError("LM Studio request failed")
    adapter = ProposalAdapter(mode=AdapterMode.LIVE, llm_client=Boom(), quest_schema=SCHEMA)
    prop = adapter.propose(_req())
    assert prop.is_blocked is True
    assert "LM Studio" in prop.block_reason
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/llm/test_proposal_adapter_live.py -q`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'llm_client'`.

- [ ] **Step 3: Implement the LIVE adapter**

In `src/wm/llm/proposal_adapter.py`: add the exception, extend the dataclass, replace `propose`/`_call_live`.

```python
class ProposalGenerationError(Exception):
    """Raised when LIVE generation cannot produce a safe, valid draft."""


@dataclass(slots=True)
class ProposalAdapter:
    mode: AdapterMode = AdapterMode.FIXTURE
    fixture: dict[str, Any] | None = None
    llm_client: Any | None = None
    quest_schema: dict[str, Any] | None = None
    model_default: str = "qwen3-coder-30b-a3b-instruct"

    def propose(self, req: ProposalRequest) -> Proposal:
        if self.mode is AdapterMode.FIXTURE:
            return self._validate(self.fixture or {}, req, {"mode": "fixture"})
        prov = {"mode": "live"}
        try:
            raw = self._call_live(req)
        except ProposalGenerationError as exc:
            cg = int(req.context.get("character", {}).get("guid", 0))
            return Proposal(kind=req.kind, payload={}, character_guid=cg,
                            provenance=prov, is_blocked=True, block_reason=str(exc))
        return self._validate(raw, req, prov)

    def _call_live(self, req: ProposalRequest) -> dict[str, Any]:
        from wm.llm.proposal_parser import ProposalParser
        from wm.quests.publish import bounty_draft_from_dict
        from wm.quests.validator import validate_bounty_quest_draft

        if self.llm_client is None or self.quest_schema is None:
            raise ProposalGenerationError("LIVE adapter missing llm_client/quest_schema")
        try:
            result = self.llm_client.generate_json(
                schema_version="wm.slice.bounty_draft.v1",
                schema=self.quest_schema,
                instruction=req.intent,
                context_pack=req.context,
                candidate_pack=req.constraints,
            )
        except Exception as exc:  # network / client errors
            raise ProposalGenerationError(str(exc)) from exc

        screen = ProposalParser().parse(result.get("content") or "")
        if not screen.ok:
            raise ProposalGenerationError("; ".join(screen.issues) or "screen failed")

        authored = result.get("parsed") or {}
        merged = self._merge_fixed_facts(authored, req.constraints)
        try:
            draft = bounty_draft_from_dict(merged)
        except (KeyError, ValueError, TypeError) as exc:
            raise ProposalGenerationError(f"draft build failed: {exc}") from exc
        vr = validate_bounty_quest_draft(draft)
        if not vr.ok:
            raise ProposalGenerationError(
                "; ".join(f"{i.path}: {i.message}" for i in vr.errors))

        flat = draft.to_dict()
        return {
            "kind": "quest",
            "payload": {"quest_release": {
                "title": draft.title,
                "objective": draft.objective_text,
                "description": draft.quest_description,
                "giver_creature_entry": draft.questgiver_entry,
                "objective_kind": "kill",
                "rewards": {"xp_difficulty": draft.reward.reward_xp_difficulty,
                            "money_copper": draft.reward.money_copper},
                "draft": flat,
            }},
            "narrative_summary": authored.get("narrative_summary") or draft.offer_reward_text,
        }

    @staticmethod
    def _merge_fixed_facts(authored: dict[str, Any], constraints: dict[str, Any]) -> dict[str, Any]:
        c = constraints or {}
        cobj = c.get("objective", {})
        aobj = authored.get("objective", {})
        return {
            "quest_id": int(c.get("quest_id_placeholder", 999000)),  # replaced at publish
            "quest_level": int(c.get("quest_level", 1)),
            "min_level": int(c.get("min_level", 1)),
            "questgiver_entry": int(c["questgiver_entry"]),
            "questgiver_name": str(c.get("questgiver_name", "")),
            "title": str(authored.get("title", "")),
            "quest_description": str(authored.get("quest_description", "")),
            "objective_text": str(authored.get("objective_text", "")),
            "offer_reward_text": str(authored.get("offer_reward_text", "")),
            "request_items_text": str(authored.get("request_items_text", "")),
            "objective": {
                "target_entry": int(cobj["target_entry"]),
                "target_name": str(cobj["target_name"]),
                "kill_count": int(aobj.get("kill_count", 1)),
            },
            "reward": authored.get("reward", {}),
            "start_npc_entry": c.get("start_npc_entry"),
            "end_npc_entry": c.get("end_npc_entry"),
            "grant_mode": str(c.get("grant_mode", "direct_quest_add")),
            "tags": list(c.get("tags", ["wm-slice"])),
            "template_defaults": dict(c.get("template_defaults", {})),
        }
```

Delete the old `_build_prompt` and the phantom `_call_live` body. Keep `_validate` as-is (the envelope it receives is identical to the FIXTURE shape).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/llm/test_proposal_adapter_live.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Run the existing FIXTURE tests for regression**

Run: `python -m pytest tests/ -k "proposal or slice" -q`
Expected: PASS (FIXTURE path unchanged).

- [ ] **Step 6: Commit**

```bash
git add src/wm/llm/proposal_adapter.py tests/llm/test_proposal_adapter_live.py
git commit -m "feat(llm): real LIVE proposal adapter (generate -> screen -> validate -> wrap)"
```

---

## Task 4: Thread LIVE wiring through SliceRuntime + panel

**Files:**
- Modify: `src/wm/cli/slice_demo.py:42-103` (`bootstrap`)
- Modify: `src/wm/panel/slice_wiring.py:62-76` (`make_live_slice_factory`)
- Modify: `src/wm/panel/server.py:454-498` (`_default_slice_factory`, `serve`)
- Test: `tests/panel/test_server_slice_live.py`

- [ ] **Step 1: Add optional LIVE params to `SliceRuntime.bootstrap`**

In `src/wm/cli/slice_demo.py`, extend the signature and the `ProposalAdapter(...)` construction:

```python
    @classmethod
    def bootstrap(cls, *, character_guid: int, starter_item_entry: int,
                  adapter_mode: AdapterMode = AdapterMode.FIXTURE,
                  fixture_path: str = DEFAULT_FIXTURE,
                  llm_client: Any | None = None,
                  quest_schema: dict | None = None) -> "SliceRuntime":
        ...
        adapter = ProposalAdapter(mode=adapter_mode, fixture=_load(fixture_path),
                                  llm_client=llm_client, quest_schema=quest_schema)
```

- [ ] **Step 2: Add a schema loader + LIVE option to the live factory**

In `src/wm/panel/slice_wiring.py`, add a helper and extend `make_live_slice_factory`:

```python
SLICE_QUEST_SCHEMA_PATH = "control/schemas/wm.slice.bounty_draft.v1.schema.json"


def load_slice_quest_schema(path: str = SLICE_QUEST_SCHEMA_PATH) -> dict:
    import json
    from pathlib import Path
    return json.loads(Path(path).read_text(encoding="utf-8"))


def make_live_slice_factory(*, client: Any, cfg: SliceDbConfig,
                            starter_item_entry: int = 0,
                            adapter_mode: Any = None,
                            llm_client: Any | None = None,
                            quest_schema: dict | None = None) -> Callable[..., Any]:
    def factory(*, character_guid: int) -> Any:
        from wm.cli.slice_demo import SliceRuntime
        from wm.cli.slice_demo_live import wrap_with_live_compilers
        from wm.cli.native_applier import NativeApplier
        from wm.llm.proposal_adapter import AdapterMode

        mode = adapter_mode or AdapterMode.FIXTURE
        rt = SliceRuntime.bootstrap(character_guid=character_guid,
                                    starter_item_entry=starter_item_entry,
                                    adapter_mode=mode,
                                    llm_client=llm_client, quest_schema=quest_schema)
        applier = NativeApplier(client=client, host=cfg.host, port=cfg.port,
                                user=cfg.user, password=cfg.password, database=cfg.world_db)
        wrap_with_live_compilers(rt, applier=applier)
        return rt
    return factory
```

- [ ] **Step 3: Build the LmStudioClient + select LIVE in `serve`**

In `src/wm/panel/server.py` `serve(...)`, where the live wiring block builds the factory (around line 479), construct the client from saved settings and pass LIVE:

```python
    if live_slice:
        from wm.panel.slice_wiring import (
            SliceDbConfig, make_live_slice_factory,
            make_live_slice_discoverer, make_live_slice_pump_factory,
            load_slice_quest_schema,
        )
        from wm.llm.lmstudio import LmStudioClient, LmStudioSettings
        from wm.llm.proposal_adapter import AdapterMode
        cfg = SliceDbConfig(host=db_host, port=db_port)
        raw_settings = state.load_settings() if 'state' in dir() else {}
        if not raw_settings.get("model"):
            raw_settings = {**raw_settings, "model": "qwen3-coder-30b-a3b-instruct"}
        llm_client = LmStudioClient(LmStudioSettings.from_dict(raw_settings))
        kwargs = {
            "slice_factory": make_live_slice_factory(
                client=client, cfg=cfg, adapter_mode=AdapterMode.LIVE,
                llm_client=llm_client, quest_schema=load_slice_quest_schema()),
            "slice_discoverer": make_live_slice_discoverer(client=client, cfg=cfg),
            "slice_pump_factory": make_live_slice_pump_factory(client=client, cfg=cfg),
        }
```

(Adjust to however `state`/`client` are named in the existing `serve` body — read lines 454-498 first and match. Do NOT introduce a second settings store.)

- [ ] **Step 4: Write the panel LIVE smoke test**

```python
# tests/panel/test_server_slice_live.py
import json
from wm.panel.slice_wiring import load_slice_quest_schema
from wm.cli.slice_demo import SliceRuntime
from wm.llm.proposal_adapter import AdapterMode

GOOD = json.load(open("tests/fixtures/llm/quest_proposal_basic.json", encoding="utf-8"))


class FakeClient:
    def generate_json(self, **kwargs):
        authored = {
            "schema_version": "wm.slice.bounty_draft.v1",
            "title": "T", "quest_description": "d", "objective_text": "o",
            "offer_reward_text": "r", "request_items_text": "q",
            "objective": {"kill_count": 4}, "reward": {"money_copper": 100},
        }
        return {"parsed": authored, "content": json.dumps(authored), "raw": {}, "request": {}}


def test_bootstrap_live_adapter_produces_open_card_with_fake_client(monkeypatch):
    rt = SliceRuntime.bootstrap(
        character_guid=5408, starter_item_entry=0,
        adapter_mode=AdapterMode.LIVE,
        llm_client=FakeClient(), quest_schema=load_slice_quest_schema())
    # the demo module's first OPEN beat must carry the fixed-fact constraints;
    # feed attention to drive the runner to the OPEN beat.
    rt.feed_attention(character_guid=5408)
    cards = rt.gate.issues  # OPEN proposals routed through the gate
    assert rt.runner is not None  # smoke: runtime built with LIVE adapter
```

(If `demo_one.story_module.json`'s OPEN beat lacks the fixed-fact `constraints` block, add it in this task — `objective.target_entry/target_name`, `questgiver_entry`, `end_npc_entry`, `grant_mode`, `quest_level`, `min_level`, `template_defaults` — so the merge in Task 3 has its inputs. Read `control/examples/story_modules/demo_one.story_module.json` and the `parse_story_module` beat schema first.)

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/panel/test_server_slice_live.py tests/panel -q`
Expected: PASS, no regressions in existing panel tests.

- [ ] **Step 6: Commit**

```bash
git add src/wm/cli/slice_demo.py src/wm/panel/slice_wiring.py src/wm/panel/server.py tests/panel/test_server_slice_live.py control/examples/story_modules/demo_one.story_module.json
git commit -m "feat(panel): select LIVE adapter in --live-slice, build client from settings"
```

---

## Task 5: SlicePublishService (publish-on-approval)

**Files:**
- Create: `src/wm/cli/slice_publish.py`
- Test: `tests/cli/test_slice_publish.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/cli/test_slice_publish.py
import pytest
from wm.cli.slice_publish import SlicePublishService, SlicePublishError


class FakeSlot:
    def __init__(self, reserved_id): self.reserved_id = reserved_id; self.slot_status = "staged"


class FakeAllocator:
    def __init__(self, reserved_id=910600): self._id = reserved_id; self.calls = []
    def allocate_next_free_slot(self, **kw):
        self.calls.append(kw); return FakeSlot(self._id)


class FakePublisher:
    def __init__(self, applied=True): self.applied = applied; self.published = []
    def publish(self, *, draft, mode, **kw):
        self.published.append((draft.quest_id, mode))
        class R:
            applied = self.applied
            validation = {"ok": True}; preflight = {"ok": True}
            def to_dict(self): return {"applied": self.applied}
        return R()


class FakeSoap:
    def __init__(self): self.commands = []
    def execute_command(self, cmd):
        self.commands.append(cmd)
        class R: ok = True
        return R()


class FakeApplier:
    def __init__(self): self.grants = []
    def insert_quest_add(self, *, character_guid, quest_id, idempotency_key):
        self.grants.append((character_guid, quest_id)); return {"ok": True, "quest_id": quest_id}


DRAFT = {
    "quest_id": 999000, "quest_level": 2, "min_level": 1,
    "questgiver_entry": 197, "questgiver_name": "Marshal McBride",
    "title": "T", "quest_description": "d", "objective_text": "o",
    "offer_reward_text": "r", "request_items_text": "q",
    "objective": {"target_entry": 299, "target_name": "Young Wolf", "kill_count": 6},
    "reward": {"money_copper": 250, "reward_xp_difficulty": 2},
    "start_npc_entry": None, "end_npc_entry": 197,
    "grant_mode": "direct_quest_add", "template_defaults": {"SpecialFlags": 0},
}


def _svc(publisher=None, soap=None, applier=None, alloc=None):
    return SlicePublishService(
        allocator=alloc or FakeAllocator(),
        publisher=publisher or FakePublisher(),
        soap=soap or FakeSoap(),
        applier=applier or FakeApplier(),
    )


def test_publish_and_grant_orders_allocate_publish_reload_grant():
    pub, soap, applier = FakePublisher(), FakeSoap(), FakeApplier()
    svc = _svc(publisher=pub, soap=soap, applier=applier)
    out = svc.publish_and_grant(draft_dict=dict(DRAFT), character_guid=5408, beat_id="b01")
    assert out["quest_id"] == 910600
    assert pub.published == [(910600, "apply")]          # reserved id injected
    assert any("reload" in c for c in soap.commands)
    assert applier.grants == [(5408, 910600)]            # granted after publish


def test_publish_failure_parks_no_grant():
    svc = _svc(publisher=FakePublisher(applied=False))
    with pytest.raises(SlicePublishError):
        svc.publish_and_grant(draft_dict=dict(DRAFT), character_guid=5408, beat_id="b01")


def test_no_free_slot_raises():
    class Empty(FakeAllocator):
        def allocate_next_free_slot(self, **kw): return None
    svc = _svc(alloc=Empty())
    with pytest.raises(SlicePublishError):
        svc.publish_and_grant(draft_dict=dict(DRAFT), character_guid=5408, beat_id="b01")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/cli/test_slice_publish.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'wm.cli.slice_publish'`.

- [ ] **Step 3: Implement the service**

```python
# src/wm/cli/slice_publish.py
"""Publish-on-approval for the LIVE slice: allocate -> publish -> reload -> grant.

Composes the existing reserved-slot allocator, quest publisher, SOAP runtime
client, and native applier. Any failure raises SlicePublishError so the
ApprovalGate parks the proposal (no partial state — the reserved slot only
flips to active inside a successful QuestPublisher.publish)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from wm.quests.publish import bounty_draft_from_dict


class SlicePublishError(Exception):
    pass


@dataclass(slots=True)
class SlicePublishService:
    allocator: Any
    publisher: Any
    soap: Any
    applier: Any

    def publish_and_grant(self, *, draft_dict: dict[str, Any],
                          character_guid: int, beat_id: str) -> dict[str, Any]:
        slot = self.allocator.allocate_next_free_slot(
            entity_type="quest", character_guid=character_guid,
            notes=[f"slice:{beat_id}"])
        if slot is None:
            raise SlicePublishError("no free reserved quest slot available")
        quest_id = int(slot.reserved_id)

        merged = dict(draft_dict)
        merged["quest_id"] = quest_id
        draft = bounty_draft_from_dict(merged)

        result = self.publisher.publish(draft=draft, mode="apply")
        if not getattr(result, "applied", False):
            raise SlicePublishError(
                f"publish not applied for quest {quest_id}: "
                f"{getattr(result, 'preflight', {})}")

        reload_result = self.soap.execute_command(".reload all quest")
        reload_ok = bool(getattr(reload_result, "ok", True))

        idem = f"slice.quest_grant:{beat_id}:{quest_id}:{character_guid}"
        grant = self.applier.insert_quest_add(
            character_guid=character_guid, quest_id=quest_id, idempotency_key=idem)
        if not grant.get("ok", False):
            raise SlicePublishError(
                f"quest {quest_id} published but grant failed; "
                "worldserver restart may be required")

        return {"ok": True, "quest_id": quest_id,
                "reload_ok": reload_ok, "grant": grant}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/cli/test_slice_publish.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/wm/cli/slice_publish.py tests/cli/test_slice_publish.py
git commit -m "feat(slice): SlicePublishService allocate->publish->reload->grant"
```

---

## Task 6: Wire publish-on-approval into the live compiler

**Files:**
- Modify: `src/wm/cli/slice_demo_live.py:19-52`
- Test: `tests/cli/test_slice_publish.py` (extend)

- [ ] **Step 1: Write the failing test** (append)

```python
def test_live_quest_compiler_publishes_when_draft_present():
    from wm.cli.slice_demo_live import build_live_quest_compiler
    from wm.llm.proposal_adapter import Proposal, ProposalKind
    pub, applier = FakePublisher(), FakeApplier()
    svc = _svc(publisher=pub, applier=applier)
    log = []
    compiler = build_live_quest_compiler(applied_log=log, publish_service=svc, applier=applier)
    prop = Proposal(kind=ProposalKind.QUEST, character_guid=5408,
                    payload={"quest_release": {"draft": dict(DRAFT)}},
                    provenance={"beat_id": "b01"})
    out = compiler(prop)
    assert out["ok"] is True
    assert applier.grants == [(5408, 910600)]


def test_live_quest_compiler_grants_existing_when_only_id_present():
    from wm.cli.slice_demo_live import build_live_quest_compiler
    from wm.llm.proposal_adapter import Proposal, ProposalKind
    applier = FakeApplier()
    log = []
    compiler = build_live_quest_compiler(applied_log=log, publish_service=_svc(applier=applier), applier=applier)
    prop = Proposal(kind=ProposalKind.QUEST, character_guid=5408,
                    payload={"quest_release": {"grant_quest_id": 910502}},
                    provenance={"beat_id": "watcher"})
    out = compiler(prop)
    assert out["ok"] is True
    assert applier.grants == [(5408, 910502)]  # existing path, no publish
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/cli/test_slice_publish.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_live_quest_compiler'`.

- [ ] **Step 3: Refactor `slice_demo_live.py` to a buildable compiler**

Replace the inner `live_quest` with a module-level builder and use it in `wrap_with_live_compilers`. Add an optional `publish_service`:

```python
from wm.cli.native_applier import NativeApplier, apply_quest_grant_proposal
from wm.cli.slice_publish import SlicePublishService
from wm.llm.proposal_adapter import Proposal


def build_live_quest_compiler(*, applied_log, publish_service, applier):
    def live_quest(p: Proposal) -> dict:
        qr = (p.payload or {}).get("quest_release", {})
        if qr.get("draft"):
            beat_id = (p.provenance or {}).get("beat_id", "watcher")
            result = publish_service.publish_and_grant(
                draft_dict=qr["draft"], character_guid=p.character_guid, beat_id=beat_id)
        else:
            result = apply_quest_grant_proposal(p, applier=applier)
        applied_log.append({"kind": "quest", "applier": result,
                            "narrative": p.narrative_summary, "provenance": p.provenance})
        return result
    return live_quest


def wrap_with_live_compilers(rt, *, applier: NativeApplier,
                             publish_service: SlicePublishService | None = None):
    rt.gate._quest = build_live_quest_compiler(
        applied_log=rt.applied_log, publish_service=publish_service, applier=applier)
    # live_ability / live_scene unchanged (keep existing closures)
    ...
    return rt
```

Keep the existing `live_ability` and `live_scene` exactly as they are.

- [ ] **Step 4: Build the publish service in the live factory**

In `src/wm/panel/slice_wiring.py` `make_live_slice_factory.factory`, construct the service from real components and pass it to `wrap_with_live_compilers`:

```python
        from wm.config import Settings
        from wm.quests.publish import QuestPublisher
        from wm.reserved.db_allocator import ReservedSlotDbAllocator
        from wm.runtime_sync import SoapRuntimeClient
        from wm.cli.slice_publish import SlicePublishService
        import dataclasses
        settings = dataclasses.replace(Settings.from_env(),
                                       world_db_port=cfg.port, world_db_host=cfg.host)
        svc = SlicePublishService(
            allocator=ReservedSlotDbAllocator(client, settings),
            publisher=QuestPublisher(client=client, settings=settings),
            soap=SoapRuntimeClient(settings=settings),
            applier=applier)
        wrap_with_live_compilers(rt, applier=applier, publish_service=svc)
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/cli/test_slice_publish.py tests/ -k "slice" -q`
Expected: PASS (Phase 1 + Phase 2 unit tests green; existing slice tests unaffected).

- [ ] **Step 6: Commit**

```bash
git add src/wm/cli/slice_demo_live.py src/wm/panel/slice_wiring.py tests/cli/test_slice_publish.py
git commit -m "feat(slice): publish-on-approval live quest compiler (draft -> mint -> grant)"
```

---

## Task 7: Full suite + skills validator

- [ ] **Step 1: Run the full suite**

Run: `python -m pytest -q`
Expected: the new tests pass; only the documented pre-existing failures remain (`tests/test_cli.py` CATALOG import; `tests/test_native_bridge_*` 8 fails). If any OTHER test fails, fix it before continuing.

- [ ] **Step 2: Validate skills (if any skill was touched)**

Run: `python scripts/validate_agent_skills.py`
Expected: OK.

- [ ] **Step 3: Commit any fixups**

```bash
git add -A && git commit -m "test: green full suite for slice LIVE-LLM pipeline"
```

---

## Task 8: Live-proof Phase 1 (manual, BridgeLab)

Not a unit test — operator verification. Record outcome with a `WORKING`/`PARTIAL` label.

- [ ] **Step 1: Confirm prerequisites**
  - LM Studio up: `curl -s http://localhost:1234/v1/models` returns models.
  - Stack up (DB 33307 / SOAP 7879 / world 8095); Astel (5408) online + marked (aura 946500) + on allowlists.
- [ ] **Step 2: Start the panel LIVE**

Run: `WM_WORLD_DB_PORT=33307 WM_SOAP_PORT=7879 python -m wm.panel serve --live-slice`
- [ ] **Step 3: In the Slice tab** → Bootstrap (auto-discovers Astel from the marker spine) → Poll. Drive the OPEN beat.
- [ ] **Step 4: Verify** an OPEN card appears with LLM-authored prose and provenance `mode=live`. Confirm **no** new `quest_template` row was written yet (generation only):
  `SELECT ID FROM quest_template WHERE ID >= 910600;` → empty.
- [ ] **Step 5: Record** the result (label + card screenshot/prose) in the closeout notes for Task 10.

---

## Task 9: Live-proof Phase 2 (manual, BridgeLab)

- [ ] **Step 1: Approve** the LLM-generated OPEN card in the panel.
- [ ] **Step 2: Verify mint** — a fresh reserved id was published and slot flipped active:
  `SELECT ID, LogTitle, RequiredNpcOrGo1, RequiredNpcOrGoCount1 FROM quest_template WHERE ID >= 910600;`
  `SELECT ReservedID, SlotStatus FROM wm_reserved_slot WHERE EntityType='quest' AND SlotStatus='active' ORDER BY ReservedID DESC LIMIT 3;`
- [ ] **Step 3: Verify grant** — quest is in Astel's log:
  `SELECT quest, status FROM character_queststatus WHERE guid=5408 AND quest >= 910600;`
- [ ] **Step 4: Verify audit** — `SELECT artifact_entry, action, status FROM wm_publish_log WHERE artifact_entry >= 910600 ORDER BY id DESC LIMIT 5;` shows `success`; a `wm_rollback_snapshot` row exists.
- [ ] **Step 5: If grant did not land** (worldserver caching), restart worldserver and re-poll; if it then grants, label `PARTIAL — restart required`, else investigate. Do NOT reuse the minted id on retry — allocate a fresh one (never reuse dirty visible IDs).

---

## Task 10: Docs + handoff closeout

**Files:**
- Modify: `docs/LIVE_PROOF_BACKLOG.md`, `docs/WM_PLATFORM_HANDOFF.md`
- Create: `docs/NEXT_CHAT_HANDOFF_LIVE_LLM_2026_05_22.md`

- [ ] **Step 1: Update `LIVE_PROOF_BACKLOG.md`** — move the LIVE-LLM slice item from PARTIAL to the proven state with the Task 8/9 evidence, or note PARTIAL with the exact gap.
- [ ] **Step 2: Update `WM_PLATFORM_HANDOFF.md`** — slice now runs LIVE; note the draft-only boundary is crossed only inside the slice runtime behind approval.
- [ ] **Step 3: Write the next-chat handoff** following the repo handoff template (status header; what shipped; live state; what's NOT done; recommended next order).
- [ ] **Step 4: Commit**

```bash
git add docs/LIVE_PROOF_BACKLOG.md docs/WM_PLATFORM_HANDOFF.md docs/NEXT_CHAT_HANDOFF_LIVE_LLM_2026_05_22.md
git commit -m "docs: slice LIVE-LLM pipeline proof + handoff (2026-05-22)"
```

---

## Self-review notes

- **Spec coverage:** Phase 1 (schema/adapter/wiring) → Tasks 1–4; Phase 2 (publish service + compiler) → Tasks 5–6; fixed-facts-from-constraints → Task 3 `_merge_fixed_facts` + Task 4 demo-module constraints; backward-compat grant-existing → Task 6; safety screen/validator → Task 3; park-on-failure → Tasks 5/6; ID permanence/audit → Tasks 5/9; testing strategy → Tasks 3/4/5/6/7; live-proof → Tasks 8/9; docs → Task 10. No spec section is unmapped.
- **Type consistency:** `bounty_draft_from_dict`, `SlicePublishService.publish_and_grant`, `build_live_quest_compiler`, `load_slice_quest_schema`, `ProposalGenerationError`, `SlicePublishError` are defined before use. `Proposal.payload.quest_release.draft` is produced in Task 3 and consumed in Task 6.
- **Known assumption to verify during Task 4:** the demo OPEN beat must carry the fixed-fact `constraints`; if absent, Task 4 Step 4 adds them (read `demo_one.story_module.json` + `parse_story_module` first).
