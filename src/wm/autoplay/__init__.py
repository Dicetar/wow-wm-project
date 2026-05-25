"""Local WM autoplay service.

Autoplay is the no-Codex runtime loop: it records readiness/session/LLM state,
validates schema-locked drafts, and can drive the existing approval gate when a
live WM session runtime is available.
"""

from wm.autoplay.policy import AutoplayPolicy
from wm.autoplay.state import AutoplayStateStore

__all__ = ["AutoplayPolicy", "AutoplayStateStore"]
