from __future__ import annotations

from pathlib import Path
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)  # type: ignore[name-defined]

_SRC_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "wm"
if _SRC_PACKAGE.is_dir():
    src_text = str(_SRC_PACKAGE)
    if src_text not in __path__:
        __path__.append(src_text)
