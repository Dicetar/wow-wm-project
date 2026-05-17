"""Native action payload-contract validation.

`control/actions/native/native_bridge_action.json` carries a `payload_contracts`
map (required / required_any / optional / notes per action kind). Until now it
was documentation only: `actions.py` checked the kind existed but never the
payload, so a malformed manual (or future LLM) proposal only failed deep in C++.

This module makes the contract enforceable in Python, pre-flight, before the
request is ever enqueued. It is the safety spine that lets the action
vocabulary go wide early: every contracted verb is validated the same way
whether or not its C++ body is implemented yet.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID


def _default_contract_path() -> Path:
    return Path(__file__).resolve().parents[4] / "control" / "actions" / "native" / "native_bridge_action.json"


def load_payload_contracts(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    contract_path = Path(path) if path else _default_contract_path()
    data = json.loads(contract_path.read_text(encoding="utf-8"))
    contracts = data.get("payload_contracts") or {}
    if not isinstance(contracts, dict):
        raise ValueError("payload_contracts must be a JSON object")
    return contracts


def validate_native_action_payload(
    *,
    action_kind: str,
    payload: dict[str, Any] | None,
    contracts: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """Return a list of human-readable issues; empty list == ok.

    - Unknown action kind -> hard issue.
    - Kind with no contract -> no payload issues (cannot validate yet), but the
      kind must still be registered.
    - `required`: every listed key must be present and non-empty.
    - `required_any`: at least one listed key must be present and non-empty.
    Unknown extra keys are allowed (forward-compatible); contracts stay additive.
    """
    issues: list[str] = []
    if action_kind not in NATIVE_ACTION_KIND_BY_ID:
        return [f"unknown native action kind: {action_kind!r}"]
    contracts = load_payload_contracts() if contracts is None else contracts
    contract = contracts.get(action_kind)
    if not contract:
        return issues
    data = payload or {}

    def _present(key: str) -> bool:
        return key in data and data[key] not in (None, "", [], {})

    for key in contract.get("required", []) or []:
        if not _present(str(key)):
            issues.append(f"{action_kind}: missing required payload field {key!r}")
    any_keys = [str(k) for k in (contract.get("required_any", []) or [])]
    if any_keys and not any(_present(k) for k in any_keys):
        issues.append(f"{action_kind}: requires at least one of {any_keys}")
    return issues


@dataclass(slots=True)
class ContractCoverage:
    total_kinds: int
    contracted: list[str]
    uncontracted: list[str]
    orphan_contracts: list[str]
    implemented_without_contract: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_kinds": self.total_kinds,
            "contracted_count": len(self.contracted),
            "uncontracted_count": len(self.uncontracted),
            "uncontracted": self.uncontracted,
            "orphan_contracts": self.orphan_contracts,
            "implemented_without_contract": self.implemented_without_contract,
        }


def audit_contract_coverage(contracts: dict[str, dict[str, Any]] | None = None) -> ContractCoverage:
    contracts = load_payload_contracts() if contracts is None else contracts
    kinds = NATIVE_ACTION_KIND_BY_ID
    contracted = sorted(k for k in kinds if k in contracts)
    uncontracted = sorted(k for k in kinds if k not in contracts)
    orphans = sorted(c for c in contracts if c not in kinds)
    impl_no_contract = sorted(
        k for k, v in kinds.items() if v.implemented and k not in contracts
    )
    return ContractCoverage(
        total_kinds=len(kinds),
        contracted=contracted,
        uncontracted=uncontracted,
        orphan_contracts=orphans,
        implemented_without_contract=impl_no_contract,
    )
