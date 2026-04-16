from __future__ import annotations

import json
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ReactiveBountyTemplateSummary:
    key: str
    path: str
    rule_key: str
    quest_title: str | None
    player_guid: int | None
    subject_entry: int | None
    turn_in_npc_entry: int | None
    kill_threshold: int | None
    window_seconds: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_reactive_bounty_template_dir() -> Path:
    return Path(__file__).resolve().parents[3].joinpath("control", "examples", "reactive_bounties")


def list_reactive_bounty_templates(
    *,
    template_dir: Path | None = None,
) -> list[ReactiveBountyTemplateSummary]:
    root = template_dir or default_reactive_bounty_template_dir()
    if not root.exists():
        return []

    templates: list[ReactiveBountyTemplateSummary] = []
    for path in sorted(root.glob("*.json")):
        raw = _load_template_object(path)
        templates.append(
            ReactiveBountyTemplateSummary(
                key=path.stem,
                path=str(path),
                rule_key=str(raw.get("rule_key") or ""),
                quest_title=_str_or_none(raw.get("quest_title")),
                player_guid=_int_or_none(raw.get("player_guid")),
                subject_entry=_int_or_none(raw.get("subject_entry")),
                turn_in_npc_entry=_int_or_none(raw.get("turn_in_npc_entry")),
                kill_threshold=_int_or_none(raw.get("kill_threshold")),
                window_seconds=_int_or_none(raw.get("window_seconds")),
            )
        )
    return templates


def resolve_reactive_bounty_template_path(
    key: str,
    *,
    template_dir: Path | None = None,
) -> Path:
    wanted = key.strip()
    if not wanted:
        raise ValueError("Reactive bounty template key is required.")

    root = template_dir or default_reactive_bounty_template_dir()
    if not root.exists():
        raise ValueError(f"Reactive bounty template directory was not found: {root}")

    matches: list[Path] = []
    for path in sorted(root.glob("*.json")):
        raw = _load_template_object(path)
        aliases = {
            path.stem,
            str(raw.get("rule_key") or ""),
        }
        rule_key = str(raw.get("rule_key") or "")
        if ":" in rule_key:
            aliases.add(rule_key.rsplit(":", 1)[-1])
        if wanted in aliases:
            matches.append(path)

    if not matches:
        available = ", ".join(template.key for template in list_reactive_bounty_templates(template_dir=root))
        raise ValueError(f"Unknown reactive bounty template key `{wanted}`. Available templates: {available}")
    if len(matches) > 1:
        options = ", ".join(str(path) for path in matches)
        raise ValueError(f"Reactive bounty template key `{wanted}` is ambiguous: {options}")
    return matches[0]


def render_reactive_bounty_template_list(templates: list[ReactiveBountyTemplateSummary]) -> str:
    if not templates:
        return "No reactive bounty templates found."

    lines = ["reactive bounty templates:"]
    for template in templates:
        details = [
            f"key={template.key}",
            f"rule_key={template.rule_key}",
        ]
        if template.quest_title:
            details.append(f"title={template.quest_title}")
        if template.subject_entry is not None:
            details.append(f"subject={template.subject_entry}")
        if template.turn_in_npc_entry is not None:
            details.append(f"turn_in={template.turn_in_npc_entry}")
        if template.kill_threshold is not None and template.window_seconds is not None:
            details.append(f"trigger={template.kill_threshold}/{template.window_seconds}s")
        lines.append("- " + " ".join(details))
    return "\n".join(lines)


def _load_template_object(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Reactive bounty template JSON must be an object: {path}")
    return raw


def _str_or_none(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _int_or_none(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
