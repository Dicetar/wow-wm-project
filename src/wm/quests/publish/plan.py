from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class PublishResult:
    mode: Literal["dry_run", "apply"]
    quest_id: int
    executed: bool
    verify_passed: bool = False
    error: str | None = None
    snapshot_taken: bool = False
