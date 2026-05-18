"""LLM proposal critique: rule-based checks before adoption."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

CritiqueSeverity = Literal["error", "warning", "info"]


@dataclass(slots=True)
class CritiqueIssue:
    path: str
    message: str
    severity: CritiqueSeverity = "warning"

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "message": self.message, "severity": self.severity}


@dataclass(slots=True)
class CritiqueResult:
    ok: bool
    issues: list[CritiqueIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[CritiqueIssue]:
        return [i for i in self.issues if i.severity == "error"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "issues": [i.to_dict() for i in self.issues],
            "error_count": len(self.errors),
        }


def critique_quest_proposal(parsed: dict) -> CritiqueResult:
    """Apply WM domain rules to a parsed quest proposal."""
    issues: list[CritiqueIssue] = []

    # schema_version gate
    sv = str(parsed.get("schema_version") or "")
    if not sv.startswith("wm."):
        issues.append(CritiqueIssue("schema_version", f"Expected wm.* prefix, got {sv!r}", "error"))

    # level sanity: min_level <= quest_level
    quest_level = parsed.get("quest_level") or parsed.get("QuestLevel")
    min_level = parsed.get("min_level") or parsed.get("MinLevel")
    if quest_level is not None and min_level is not None:
        try:
            if int(min_level) > int(quest_level):
                issues.append(CritiqueIssue(
                    "min_level",
                    f"min_level ({min_level}) exceeds quest_level ({quest_level})",
                    "error",
                ))
        except (TypeError, ValueError):
            pass

    # title must be non-empty
    title = parsed.get("title") or parsed.get("LogTitle") or ""
    if not str(title).strip():
        issues.append(CritiqueIssue("title", "Quest title is empty", "error"))

    # reward money sanity
    money = parsed.get("reward_money") or parsed.get("RewardMoney") or 0
    try:
        if int(money) < 0:
            issues.append(CritiqueIssue("reward_money", "Negative reward money", "warning"))
    except (TypeError, ValueError):
        pass

    # check for forbidden flat SQL keys
    for key in ("sql", "raw_sql", "execute_sql"):
        if key in parsed:
            issues.append(CritiqueIssue(key, f"Forbidden key {key!r} in proposal", "error"))

    ok = not any(i.severity == "error" for i in issues)
    return CritiqueResult(ok=ok, issues=issues)
