from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VALID_CUSTOM_ID_STATUSES = {"WORKING", "PARTIAL", "BROKEN", "UNKNOWN"}


@dataclass(slots=True)
class CustomIdRange:
    namespace: str
    range_key: str
    start_id: int
    end_id: int
    purpose: str
    status: str
    allocation_rule: str


@dataclass(slots=True)
class CustomIdClaim:
    namespace: str
    id: int
    key: str
    kind: str
    purpose: str
    status: str
    owner_system: str
    source_paths: list[str]
    player_guid_scope: int | None = None
    notes: list[str] = field(default_factory=list)
    replaced_by: str | None = None


@dataclass(slots=True)
class CustomIdRegistry:
    schema_version: str
    description: str
    notes: list[str]
    ranges: list[CustomIdRange]
    claims: list[CustomIdClaim]

    def range_by_key(self, *, namespace: str, range_key: str) -> CustomIdRange | None:
        for entry in self.ranges:
            if entry.namespace == namespace and entry.range_key == range_key:
                return entry
        return None

    def claim_by_key(self, *, namespace: str, key: str) -> CustomIdClaim | None:
        for claim in self.claims:
            if claim.namespace == namespace and claim.key == key:
                return claim
        return None

    def claim_by_id(self, *, namespace: str, id: int) -> CustomIdClaim | None:
        for claim in self.claims:
            if claim.namespace == namespace and claim.id == int(id):
                return claim
        return None


@dataclass(slots=True)
class RegistryIssue:
    path: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(slots=True)
class RegistryValidationResult:
    issues: list[RegistryIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def default_custom_id_registry_path() -> Path:
    return Path(__file__).resolve().parents[3].joinpath("data", "specs", "custom_id_registry.json")


def load_custom_id_registry(path: str | Path | None = None) -> CustomIdRegistry:
    source = Path(path) if path is not None else default_custom_id_registry_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    return CustomIdRegistry(
        schema_version=str(raw["schema_version"]),
        description=str(raw["description"]),
        notes=[str(note) for note in raw.get("notes", [])],
        ranges=[
            CustomIdRange(
                namespace=str(entry["namespace"]),
                range_key=str(entry["range_key"]),
                start_id=int(entry["start_id"]),
                end_id=int(entry["end_id"]),
                purpose=str(entry["purpose"]),
                status=str(entry["status"]),
                allocation_rule=str(entry["allocation_rule"]),
            )
            for entry in raw.get("ranges", [])
        ],
        claims=[
            CustomIdClaim(
                namespace=str(entry["namespace"]),
                id=int(entry["id"]),
                key=str(entry["key"]),
                kind=str(entry["kind"]),
                purpose=str(entry["purpose"]),
                status=str(entry["status"]),
                owner_system=str(entry["owner_system"]),
                source_paths=[str(value) for value in entry.get("source_paths", [])],
                player_guid_scope=(
                    int(entry["player_guid_scope"]) if entry.get("player_guid_scope") not in (None, "") else None
                ),
                notes=[str(note) for note in entry.get("notes", [])],
                replaced_by=(str(entry["replaced_by"]) if entry.get("replaced_by") not in (None, "") else None),
            )
            for entry in raw.get("claims", [])
        ],
    )


def validate_custom_id_registry(path: str | Path | None = None) -> RegistryValidationResult:
    source = Path(path) if path is not None else default_custom_id_registry_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    result = RegistryValidationResult()

    if raw.get("schema_version") in (None, ""):
        result.issues.append(RegistryIssue(path="schema_version", message="schema_version is required."))
    if raw.get("description") in (None, ""):
        result.issues.append(RegistryIssue(path="description", message="description is required."))

    seen_claim_ids: set[tuple[str, int]] = set()
    for index, entry in enumerate(raw.get("claims", [])):
        path_prefix = f"claims[{index}]"
        for field_name in ["namespace", "id", "key", "kind", "purpose", "status", "owner_system", "source_paths"]:
            if field_name not in entry:
                result.issues.append(
                    RegistryIssue(path=f"{path_prefix}.{field_name}", message=f"{field_name} is required.")
                )
        namespace = str(entry.get("namespace") or "")
        try:
            claim_id = int(entry.get("id"))
        except (TypeError, ValueError):
            claim_id = 0
            result.issues.append(RegistryIssue(path=f"{path_prefix}.id", message="id must be an integer."))
        status = str(entry.get("status") or "")
        if status not in VALID_CUSTOM_ID_STATUSES:
            result.issues.append(
                RegistryIssue(
                    path=f"{path_prefix}.status",
                    message=f"Unknown status `{status}`. Expected one of {', '.join(sorted(VALID_CUSTOM_ID_STATUSES))}.",
                )
            )
        source_paths = entry.get("source_paths")
        if not isinstance(source_paths, list) or not source_paths:
            result.issues.append(
                RegistryIssue(path=f"{path_prefix}.source_paths", message="source_paths must be a non-empty list.")
            )
        claim_key = (namespace, claim_id)
        if namespace and claim_id and claim_key in seen_claim_ids:
            result.issues.append(
                RegistryIssue(
                    path=f"{path_prefix}.id",
                    message=f"Duplicate exact claim for namespace `{namespace}` and id `{claim_id}`.",
                )
            )
        seen_claim_ids.add(claim_key)

    ranges_by_namespace: dict[str, list[tuple[int, int, str, int]]] = {}
    for index, entry in enumerate(raw.get("ranges", [])):
        path_prefix = f"ranges[{index}]"
        for field_name in ["namespace", "range_key", "start_id", "end_id", "purpose", "status", "allocation_rule"]:
            if field_name not in entry:
                result.issues.append(
                    RegistryIssue(path=f"{path_prefix}.{field_name}", message=f"{field_name} is required.")
                )
        namespace = str(entry.get("namespace") or "")
        range_key = str(entry.get("range_key") or "")
        try:
            start_id = int(entry.get("start_id"))
            end_id = int(entry.get("end_id"))
        except (TypeError, ValueError):
            start_id = 0
            end_id = -1
            result.issues.append(
                RegistryIssue(path=path_prefix, message="start_id and end_id must be integers.")
            )
        status = str(entry.get("status") or "")
        if status not in VALID_CUSTOM_ID_STATUSES:
            result.issues.append(
                RegistryIssue(
                    path=f"{path_prefix}.status",
                    message=f"Unknown status `{status}`. Expected one of {', '.join(sorted(VALID_CUSTOM_ID_STATUSES))}.",
                )
            )
        if end_id < start_id:
            result.issues.append(
                RegistryIssue(path=path_prefix, message=f"Invalid range `{range_key}`: end_id must be >= start_id.")
            )
        ranges_by_namespace.setdefault(namespace, []).append((start_id, end_id, range_key, index))

    for namespace, ranges in ranges_by_namespace.items():
        ordered = sorted(ranges)
        previous_end: int | None = None
        previous_key: str | None = None
        for start_id, end_id, range_key, index in ordered:
            if previous_end is not None and start_id <= previous_end:
                result.issues.append(
                    RegistryIssue(
                        path=f"ranges[{index}]",
                        message=(
                            f"Range `{range_key}` overlaps `{previous_key}` in namespace `{namespace}`."
                        ),
                    )
                )
            previous_end = end_id
            previous_key = range_key

    return result
