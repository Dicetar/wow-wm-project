from __future__ import annotations
import re
from pathlib import Path

_FORBIDDEN = ("5405", "5406", "5408")
_ALLOWLIST = {
    "src/wm/spells/broug_empty_court.py",
    "src/wm/spells/broug_lightness.py",
    "src/wm/live/proof_packet.py",
    "src/wm/bridge_lab/release_gate.py",
    "src/wm/content/preflight.py",
}


def _violations() -> list[str]:
    root = Path("src/wm")
    pattern = re.compile(r"\b(" + "|".join(_FORBIDDEN) + r")\b")
    out: list[str] = []
    for path in root.rglob("*.py"):
        rel = path.as_posix()
        if rel in _ALLOWLIST:
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                out.append(f"{rel}:{i}: {line.strip()}")
    return out


def test_no_hardcoded_test_subject_guids_in_generic_code_paths():
    violations = _violations()
    assert not violations, "Hardcoded test-subject GUIDs in generic code paths:\n" + "\n".join(violations)
