"""LLM response confidence scoring."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ConfidenceScore:
    value: float        # 0.0–1.0
    label: str          # low | medium | high
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "label": self.label, "reasons": self.reasons}


_LABEL_THRESHOLDS = (
    (0.8, "high"),
    (0.5, "medium"),
    (0.0, "low"),
)


def _label(value: float) -> str:
    for threshold, label in _LABEL_THRESHOLDS:
        if value >= threshold:
            return label
    return "low"


def score_proposal_confidence(parsed: dict | None, issues: list[str]) -> ConfidenceScore:
    """Heuristic confidence score for a parsed LLM proposal."""
    if parsed is None:
        return ConfidenceScore(value=0.0, label="low",
                               reasons=["no parsed JSON"] + issues[:3])

    reasons: list[str] = []
    score = 1.0

    if issues:
        score -= min(0.4, 0.1 * len(issues))
        reasons.extend(f"issue: {i}" for i in issues[:3])

    # Reward presence of expected top-level keys
    expected_keys = {"schema_version", "title", "description"}
    present = expected_keys & set(parsed.keys())
    missing = expected_keys - present
    if missing:
        score -= 0.1 * len(missing)
        reasons.append(f"missing keys: {', '.join(sorted(missing))}")

    # Penalise empty strings in critical text fields
    for key in ("title", "description"):
        val = parsed.get(key, "")
        if isinstance(val, str) and len(val.strip()) < 5:
            score -= 0.1
            reasons.append(f"very short {key!r}")

    score = max(0.0, min(1.0, round(score, 2)))
    return ConfidenceScore(value=score, label=_label(score), reasons=reasons)
