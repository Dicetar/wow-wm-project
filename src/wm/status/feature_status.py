from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

VALID_STATUSES = {"WORKING", "PARTIAL", "BROKEN", "UNKNOWN"}
_REQUIRED = ("feature_key", "layer", "repo_status", "gameplay_status", "scope", "last_verified")


def _default_path() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "specs" / "feature_status.json"


@dataclass(slots=True)
class FeatureStatus:
    feature_key: str
    layer: str
    repo_status: str
    gameplay_status: str
    scope: str
    last_verified: str
    runtime_status: str = "UNKNOWN"
    requires_live_proof: bool = False
    last_live_proof: str | None = None
    evidence_ref: str | None = None
    evidence_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_key": self.feature_key,
            "layer": self.layer,
            "repo_status": self.repo_status,
            "runtime_status": self.runtime_status,
            "gameplay_status": self.gameplay_status,
            "requires_live_proof": self.requires_live_proof,
            "scope": self.scope,
            "last_verified": self.last_verified,
            "last_live_proof": self.last_live_proof,
            "evidence_ref": self.evidence_ref,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(slots=True)
class FeatureStatusDoc:
    schema_version: str
    entries: list[FeatureStatus] = field(default_factory=list)


@dataclass(slots=True)
class StatusValidationResult:
    ok: bool
    issues: list[str] = field(default_factory=list)


def load_feature_status(path: str | Path | None = None) -> FeatureStatusDoc:
    data = json.loads((Path(path) if path else _default_path()).read_text(encoding="utf-8"))
    entries = [
        FeatureStatus(
            feature_key=str(e["feature_key"]),
            layer=str(e["layer"]),
            repo_status=str(e["repo_status"]),
            runtime_status=str(e.get("runtime_status") or "UNKNOWN"),
            gameplay_status=str(e["gameplay_status"]),
            requires_live_proof=bool(e.get("requires_live_proof", False)),
            scope=str(e["scope"]),
            last_verified=str(e["last_verified"]),
            last_live_proof=e.get("last_live_proof"),
            evidence_ref=e.get("evidence_ref"),
            evidence_refs=[str(item) for item in e.get("evidence_refs", []) if item],
        )
        for e in data.get("entries", [])
    ]
    return FeatureStatusDoc(schema_version=str(data.get("schema_version", "")), entries=entries)


def validate_feature_status(path: str | Path | None = None) -> StatusValidationResult:
    issues: list[str] = []
    try:
        data = json.loads((Path(path) if path else _default_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return StatusValidationResult(ok=False, issues=[f"unreadable feature_status.json: {exc}"])
    if not data.get("schema_version"):
        issues.append("missing schema_version")
    seen: set[str] = set()
    for i, entry in enumerate(data.get("entries", [])):
        prefix = f"entries[{i}]"
        for fieldname in _REQUIRED:
            if not entry.get(fieldname):
                issues.append(f"{prefix}.{fieldname} missing")
        key = str(entry.get("feature_key") or "")
        if key in seen:
            issues.append(f"{prefix}.feature_key duplicate {key!r}")
        seen.add(key)
        for sfield in ("repo_status", "runtime_status", "gameplay_status"):
            val = str(entry.get(sfield) or "")
            if val and val not in VALID_STATUSES:
                issues.append(f"{prefix}.{sfield} invalid {val!r}; expected {sorted(VALID_STATUSES)}")
        if bool(entry.get("requires_live_proof")) and str(entry.get("gameplay_status") or "") == "WORKING":
            if not entry.get("last_live_proof") and not entry.get("evidence_refs"):
                issues.append(f"{prefix}.last_live_proof missing for live-proof-required WORKING gameplay feature")
    return StatusValidationResult(ok=not issues, issues=issues)


def summarize_by_status(doc: FeatureStatusDoc) -> dict[str, int]:
    return summarize_by_axis(doc, "gameplay_status")


def summarize_by_axis(doc: FeatureStatusDoc, axis: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for e in doc.entries:
        value = getattr(e, axis)
        counts[value] = counts.get(value, 0) + 1
    return counts
