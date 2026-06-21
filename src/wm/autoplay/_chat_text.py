from __future__ import annotations

from typing import Any

from wm.llm.lmstudio import LmStudioSettings


# The native bridge clamps each chat packet to 220 characters. Longer replies
# must be split rather than silently truncated.
_CHAT_PART_LIMIT = 220
_CHAT_REPLY_MAX_CHARS = 880


def _split_chat_message(text: str, *, limit: int = _CHAT_PART_LIMIT) -> list[str]:
    """Split a reply into in-order parts that each fit one chat packet."""
    text = str(text).strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            parts.append(remaining.strip())
            break
        window = remaining[:limit]
        cut = max(window.rfind(". "), window.rfind("! "), window.rfind("? "))
        if cut >= limit // 2:
            cut += 1
        else:
            cut = window.rfind(" ")
            if cut < limit // 2:
                cut = limit
        parts.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    return [part for part in parts if part]


def _sanitize_chat_reply(message: str) -> str:
    line = " ".join(str(message).replace("\r", " ").replace("\n", " ").split())
    for token in ("**", "__", "`", "#", "- "):
        line = line.replace(token, "")
    line = line.strip()
    if len(line) >= 2 and line[0] == line[-1] and line[0] in {"'", '"'}:
        line = line[1:-1].strip()
    if len(line) > _CHAT_REPLY_MAX_CHARS:
        line = line[:_CHAT_REPLY_MAX_CHARS - 3].rstrip() + "..."
    return line or "I am listening."


def _guard_chat_reply(message: str) -> str:
    lowered = str(message).lower()
    blocked = (
        "breast",
        "nipple",
        "grope",
        "lick",
        "suck",
        "erotic",
        "fetish",
        "sex",
        "sexual",
    )
    if any(token in lowered for token in blocked):
        return "I will keep this to the world at hand. What do you want to do next?"
    return message


def _fallback_chat_reply(reason: str) -> str:
    del reason
    return "I heard you, but the local model returned no words. Try once more in a moment."


def _chat_context_reset_payload(control_config: dict[str, Any]) -> dict[str, Any]:
    return {
        "epoch": int(control_config.get("llm_chat_context_epoch") or 0),
        "reset_at": control_config.get("llm_chat_context_reset_at"),
        "instruction": "Treat this as the current conversation boundary. Do not rely on any player chat before this reset.",
    }


def _is_forget_context_command(message: str) -> bool:
    normalized = " ".join(str(message).strip().lower().split())
    if normalized.startswith("towm "):
        normalized = normalized.removeprefix("towm ").strip()
    return normalized in {
        "forget context",
        "forget chat context",
        "reset context",
        "reset chat context",
    }


def _forget_context_ack(status: dict[str, Any]) -> str:
    config = status.get("config") if isinstance(status.get("config"), dict) else {}
    epoch = int(config.get("llm_chat_context_epoch") or 0)
    return f"Context forgotten. Fresh WM chat context epoch {epoch} is active."


def _chat_max_tokens(settings: LmStudioSettings) -> int:
    model = str(settings.model or "").lower()
    cap = 512 if "qwen" in model else 128
    return max(64, min(int(settings.max_tokens), cap))
