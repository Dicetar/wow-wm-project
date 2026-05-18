"""Read-only operator dashboard summary.

Assembles a PanelReport from live WM subsystems. Tolerates partial
availability — any subsystem that fails to import or probe contributes an
UNKNOWN HealthCheck rather than propagating an exception.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

WORKING = "WORKING"
PARTIAL = "PARTIAL"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"

_FEATURE_STATUS_PATH = Path(__file__).parent.parent.parent.parent / "data" / "specs" / "feature_status.json"


@dataclass
class HealthCheck:
    name: str
    status: str  # WORKING | PARTIAL | FAIL | UNKNOWN
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


@dataclass
class PanelReport:
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    health: list[HealthCheck] = field(default_factory=list)
    living_readiness: dict[str, bool] = field(default_factory=dict)
    feature_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "wm.panel_report.v1",
            "generated_at": self.generated_at.strftime("%Y-%m-%dT%H:%M:%S") + "Z",
            "health": [h.to_dict() for h in self.health],
            "living_readiness": self.living_readiness,
            "feature_counts": self.feature_counts,
        }


def build_panel() -> PanelReport:
    """Assemble a PanelReport from live WM subsystems. Tolerates partial availability."""
    report = PanelReport()

    # --- Living World catalog probe ---
    try:
        from wm.living.catalog import build_wild_feature_catalog
        cat = build_wild_feature_catalog()
        total = cat["count"]
        live = cat["live_ready_count"]
        report.living_readiness = {
            e["key"]: e["live_ready"] for e in cat["entries"]
        }
        status = WORKING if live == total else PARTIAL
        report.health.append(HealthCheck(
            name="living.catalog",
            status=status,
            detail=f"{live}/{total} features live-ready",
        ))
    except Exception as exc:
        report.health.append(HealthCheck(name="living.catalog", status=UNKNOWN, detail=str(exc)))

    # --- Journal projector probe ---
    try:
        from wm.journal.projector import JournalProjector  # noqa: F401
        report.health.append(HealthCheck(name="journal.projector", status=WORKING))
    except Exception as exc:
        report.health.append(HealthCheck(name="journal.projector", status=UNKNOWN, detail=str(exc)))

    # --- Native payload contracts probe ---
    try:
        from wm.sources.native_bridge.payload_contract import audit_contract_coverage
        cov = audit_contract_coverage()
        contracted = len(cov.contracted)
        total_kinds = cov.total_kinds
        report.health.append(HealthCheck(
            name="native.contracts",
            status=WORKING,
            detail=f"{contracted}/{total_kinds} action kinds contracted",
        ))
    except Exception as exc:
        report.health.append(HealthCheck(name="native.contracts", status=UNKNOWN, detail=str(exc)))

    # --- Feature status counts ---
    try:
        path = _FEATURE_STATUS_PATH
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            counts: dict[str, int] = {}
            for entry in data.get("entries", []):
                layer = str(entry.get("layer", "unknown"))
                counts[layer] = counts.get(layer, 0) + 1
            report.feature_counts = counts
            report.health.append(HealthCheck(
                name="feature_status.json",
                status=WORKING,
                detail=f"{sum(counts.values())} features tracked",
            ))
        else:
            report.health.append(HealthCheck(name="feature_status.json", status=UNKNOWN, detail="file not found"))
    except Exception as exc:
        report.health.append(HealthCheck(name="feature_status.json", status=UNKNOWN, detail=str(exc)))

    return report
