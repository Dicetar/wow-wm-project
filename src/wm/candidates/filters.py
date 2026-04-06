from __future__ import annotations

import re

_BAD_LABEL_PATTERNS_BY_KIND: dict[str, list[re.Pattern[str]]] = {
    "quest": [
        re.compile(r"\[unused\]", re.IGNORECASE),
        re.compile(r"deprecated", re.IGNORECASE),
        re.compile(r"^zzold", re.IGNORECASE),
    ],
    "item": [
        re.compile(r"\[unused\]", re.IGNORECASE),
        re.compile(r"deprecated", re.IGNORECASE),
        re.compile(r"\btest\b", re.IGNORECASE),
        re.compile(r"\bdummy\b", re.IGNORECASE),
        re.compile(r"^zzold", re.IGNORECASE),
    ],
    "spell": [
        re.compile(r"\[unused\]", re.IGNORECASE),
        re.compile(r"deprecated", re.IGNORECASE),
        re.compile(r"^zzold", re.IGNORECASE),
    ],
}


def is_candidate_label_allowed(kind: str, label: str) -> bool:
    normalized = label.strip()
    if not normalized:
        return False
    for pattern in _BAD_LABEL_PATTERNS_BY_KIND.get(kind, []):
        if pattern.search(normalized):
            return False
    return True
