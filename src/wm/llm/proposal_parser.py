"""LLM proposal parser: validates LLM output against WM safety constraints."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from wm.llm.results import parse_json_object

FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    (r"(?i)\bDROP\b\s+\bTABLE\b", "SQL DROP TABLE"),
    (r"(?i)\bTRUNCATE\b\s+\bTABLE\b", "SQL TRUNCATE TABLE"),
    (r"(?i)\bDELETE\b\s+\bFROM\b", "SQL DELETE FROM"),
    (r"(?i)\bUPDATE\b\s+\w+\s+\bSET\b", "SQL UPDATE ... SET"),
    (r"(?i)\bINSERT\b\s+\bINTO\b", "SQL INSERT INTO"),
    (r"(?i)\.announce\b", "GM .announce command"),
    (r"(?i)\.go\b", "GM .go teleport command"),
    (r"(?i)\bos\.system\b", "os.system shell call"),
    (r"(?i)\bsubprocess\.", "subprocess shell call"),
    (r"(?i)\beval\s*\(", "eval() call"),
    (r"(?i)\bexec\s*\(", "exec() call"),
]

_REQUIRED_SCHEMA_VERSION_PREFIX = "wm."
_MAX_RAW_LENGTH = 32_000


@dataclass(slots=True)
class ParseResult:
    ok: bool
    schema_version: str | None
    parsed: dict | None
    issues: list[str] = field(default_factory=list)
    raw_length: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "schema_version": self.schema_version,
            "issues": self.issues,
            "raw_length": self.raw_length,
        }


class ProposalParser:
    """Parse and validate an LLM text response as a WM proposal."""

    def __init__(self, extra_forbidden: list[tuple[str, str]] | None = None):
        self._patterns = FORBIDDEN_PATTERNS + (extra_forbidden or [])

    def parse(self, raw: str) -> ParseResult:
        issues: list[str] = []
        raw_length = len(raw)

        if raw_length > _MAX_RAW_LENGTH:
            issues.append(f"Response too long: {raw_length} chars (max {_MAX_RAW_LENGTH})")

        for pattern, label in self._patterns:
            if re.search(pattern, raw):
                issues.append(f"Forbidden pattern detected: {label}")

        if issues:
            return ParseResult(ok=False, schema_version=None, parsed=None,
                               issues=issues, raw_length=raw_length)

        try:
            parsed = parse_json_object(raw)
        except Exception as exc:
            return ParseResult(ok=False, schema_version=None, parsed=None,
                               issues=[str(exc)], raw_length=raw_length)

        schema_version = str(parsed.get("schema_version") or "")
        if not schema_version.startswith(_REQUIRED_SCHEMA_VERSION_PREFIX):
            issues.append(
                f"schema_version must start with '{_REQUIRED_SCHEMA_VERSION_PREFIX}', "
                f"got {schema_version!r}"
            )

        if issues:
            return ParseResult(ok=False, schema_version=schema_version or None,
                               parsed=parsed, issues=issues, raw_length=raw_length)

        return ParseResult(ok=True, schema_version=schema_version, parsed=parsed,
                           raw_length=raw_length)
