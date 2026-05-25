from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from wm.llm.lmstudio import LmStudioClient
from wm.panel.schemas import SchemaCatalog


SCHEMA_BY_LANE: dict[str, str] = {
    "quest": "wm.quest.release.repeatable_bounty.v1",
    "item": "wm.item.release.managed_power.v1",
    "ability": "wm.ability.release.shell_power.v1",
    "scene": "wm.scene.release.native_sequence.v1",
    "action": "control.proposal.v1",
}

FORBIDDEN_TEXT = (
    "freeform_sql",
    "gm_command",
    "shell_command",
    "powershell",
    "cmd.exe",
    "mysql ",
    "insert into",
    "update ",
    "delete from",
    "drop table",
    ".additem",
    ".learn",
    ".modify",
)


@dataclass(slots=True)
class LlmDraftResult:
    ok: bool
    schema_version: str
    draft: dict[str, Any] | None = None
    request: dict[str, Any] | None = None
    issues: list[dict[str, str]] = field(default_factory=list)
    raw_content: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AutoplayLlmAdapter:
    client: LmStudioClient
    schemas: SchemaCatalog = field(default_factory=SchemaCatalog.load)

    def health(self) -> dict[str, Any]:
        try:
            models = self.client.list_models()
            configured = self.client.settings.model
            return {
                "ok": bool(configured and configured in models),
                "base_url": self.client.settings.base_url,
                "model": configured,
                "models": models,
                "error": None if configured else "LM Studio model is not configured.",
            }
        except Exception as exc:
            return {
                "ok": False,
                "base_url": self.client.settings.base_url,
                "model": self.client.settings.model,
                "models": [],
                "error": str(exc),
            }

    def generate(
        self,
        *,
        schema_version: str,
        instruction: str,
        context_pack: dict[str, Any] | None = None,
        candidate_pack: dict[str, Any] | None = None,
        deterministic_facts: dict[str, Any] | None = None,
    ) -> LlmDraftResult:
        try:
            entry = self.schemas.get(schema_version)
        except KeyError as exc:
            return LlmDraftResult(
                ok=False,
                schema_version=schema_version,
                issues=[{"path": "schema_version", "message": str(exc), "severity": "error"}],
            )
        try:
            result = self.client.generate_json(
                schema_version=schema_version,
                schema=entry.schema,
                instruction=instruction,
                context_pack=context_pack,
                candidate_pack=candidate_pack,
            )
        except Exception as exc:
            return LlmDraftResult(
                ok=False,
                schema_version=schema_version,
                issues=[{"path": "llm", "message": str(exc), "severity": "error"}],
            )
        draft = result.get("parsed") if isinstance(result.get("parsed"), dict) else None
        if draft is None:
            return LlmDraftResult(
                ok=False,
                schema_version=schema_version,
                request=result.get("request") if isinstance(result.get("request"), dict) else None,
                raw_content=str(result.get("content") or ""),
                issues=[{"path": "llm.content", "message": "LM Studio did not return a JSON object.", "severity": "error"}],
            )
        locked = lock_deterministic_facts(draft, deterministic_facts or {}, schema_version=schema_version)
        issues = screen_forbidden_content(locked)
        validation = self.schemas.validate(schema_version, locked)
        issues.extend(validation.get("issues") or [])
        ok = not any(str(issue.get("severity", "error")) == "error" for issue in issues)
        return LlmDraftResult(
            ok=ok,
            schema_version=schema_version,
            draft=locked,
            request=result.get("request") if isinstance(result.get("request"), dict) else None,
            raw_content=str(result.get("content") or ""),
            issues=issues,
        )


def schema_for_lane(lane: str) -> str:
    try:
        return SCHEMA_BY_LANE[str(lane)]
    except KeyError as exc:
        raise KeyError(f"Unsupported autoplay LLM lane: {lane}") from exc


def lock_deterministic_facts(draft: dict[str, Any], facts: dict[str, Any], *, schema_version: str) -> dict[str, Any]:
    locked = dict(draft)
    locked["schema_version"] = schema_version
    if facts.get("player_guid") not in (None, "") and "player_guid" in locked:
        locked["player_guid"] = int(facts["player_guid"])
    if schema_version == "control.proposal.v1":
        player = locked.get("player") if isinstance(locked.get("player"), dict) else {}
        if facts.get("player_guid") not in (None, ""):
            player["guid"] = int(facts["player_guid"])
        locked["player"] = player
        source_event = facts.get("source_event")
        if isinstance(source_event, dict):
            locked["source_event"] = source_event
        author = locked.get("author") if isinstance(locked.get("author"), dict) else {}
        author["kind"] = "llm"
        locked["author"] = author
    if schema_version == "wm.scene.release.native_sequence.v1":
        allowed = set(str(item) for item in facts.get("allowed_native_action_kinds") or [])
        if allowed:
            steps = locked.get("steps")
            if isinstance(steps, list):
                for step in steps:
                    if isinstance(step, dict) and step.get("native_action_kind") not in allowed:
                        step["native_action_kind"] = "world_announce_to_player"
                        step["payload"] = {"message": "WM sensed something nearby."}
    return locked


def screen_forbidden_content(value: Any, *, path: str = "") -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            lowered_key = str(key).lower()
            if lowered_key in {"sql", "freeform_sql", "gm_command", "shell_command", "config_edit"}:
                issues.append({"path": _join(path, str(key)), "message": "Forbidden mutation field.", "severity": "error"})
            issues.extend(screen_forbidden_content(nested, path=_join(path, str(key))))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            issues.extend(screen_forbidden_content(nested, path=f"{path}[{index}]" if path else f"[{index}]"))
    elif isinstance(value, str):
        lowered = value.lower()
        for token in FORBIDDEN_TEXT:
            if token in lowered:
                issues.append({"path": path, "message": f"Forbidden mutation text: {token}", "severity": "error"})
                break
    return issues


def _join(parent: str, child: str) -> str:
    return f"{parent}.{child}" if parent else child
