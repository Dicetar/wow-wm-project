from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any
from urllib import error
from urllib import request

from wm.llm.prompts import build_messages
from wm.llm.results import parse_json_object


@dataclass(slots=True)
class LmStudioSettings:
    base_url: str = "http://localhost:1234/v1"
    model: str | None = None
    temperature: float = 0.2
    top_p: float | None = None
    max_tokens: int = 2048
    timeout_seconds: int = 60
    schema_mode: str = "json_schema"
    api_key: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "LmStudioSettings":
        return cls(
            base_url=str(raw.get("base_url") or "http://localhost:1234/v1"),
            model=(str(raw["model"]) if raw.get("model") not in (None, "") else None),
            temperature=float(raw.get("temperature", 0.2)),
            top_p=(float(raw["top_p"]) if raw.get("top_p") not in (None, "") else None),
            max_tokens=int(raw.get("max_tokens", 2048)),
            timeout_seconds=int(raw.get("timeout_seconds", 60)),
            schema_mode=str(raw.get("schema_mode") or "json_schema"),
            api_key=(str(raw["api_key"]) if raw.get("api_key") not in (None, "") else None),
        )

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
            "timeout_seconds": self.timeout_seconds,
            "schema_mode": self.schema_mode,
        }


class LmStudioClient:
    def __init__(self, settings: LmStudioSettings) -> None:
        self.settings = settings

    def list_models(self) -> list[str]:
        payload = self._request_json("GET", "/models")
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            return []
        models: list[str] = []
        for item in data:
            if isinstance(item, dict) and item.get("id") not in (None, ""):
                models.append(str(item["id"]))
        return models

    def generate_json(
        self,
        *,
        schema_version: str,
        schema: dict[str, Any],
        instruction: str,
        context_pack: Any | None = None,
        candidate_pack: Any | None = None,
    ) -> dict[str, Any]:
        if not self.settings.model:
            raise ValueError("LM Studio model is not configured.")
        request_payload = self.build_chat_payload(
            schema_version=schema_version,
            schema=schema,
            instruction=instruction,
            context_pack=context_pack,
            candidate_pack=candidate_pack,
        )
        try:
            raw = self._request_json("POST", "/chat/completions", payload=request_payload)
        except RuntimeError as exc:
            if self.settings.schema_mode != "json_schema" or "HTTP Error 400" not in str(exc):
                raise
            request_payload = self.build_chat_payload(
                schema_version=schema_version,
                schema=schema,
                instruction=instruction,
                context_pack=context_pack,
                candidate_pack=candidate_pack,
                schema_mode="text",
            )
            raw = self._request_json("POST", "/chat/completions", payload=request_payload)
        content = _extract_message_content(raw)
        parsed = parse_json_object(content)
        return {"request": request_payload, "raw": raw, "content": content, "parsed": parsed}

    def generate_text(self, *, messages: list[dict[str, str]]) -> dict[str, Any]:
        if not self.settings.model:
            raise ValueError("LM Studio model is not configured.")
        request_payload: dict[str, Any] = {
            "model": self.settings.model,
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_tokens,
            "messages": messages,
        }
        if self.settings.top_p is not None:
            request_payload["top_p"] = self.settings.top_p
        if self.settings.schema_mode == "text":
            request_payload["response_format"] = {"type": "text"}
        raw = self._request_json("POST", "/chat/completions", payload=request_payload)
        try:
            content = _extract_message_content(raw)
            reasoning_fallback = False
        except RuntimeError as exc:
            content = _extract_reasoning_text_fallback(raw)
            if not content:
                raise
            reasoning_fallback = "message content was empty" in str(exc)
        return {"request": request_payload, "raw": raw, "content": content, "reasoning_fallback": reasoning_fallback}

    def build_chat_payload(
        self,
        *,
        schema_version: str,
        schema: dict[str, Any],
        instruction: str,
        context_pack: Any | None = None,
        candidate_pack: Any | None = None,
        schema_mode: str | None = None,
    ) -> dict[str, Any]:
        response_mode = schema_mode or self.settings.schema_mode
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_tokens,
            "messages": build_messages(
                schema_version=schema_version,
                instruction=instruction,
                context_pack=context_pack,
                candidate_pack=candidate_pack,
                output_schema=schema if response_mode in {"json_object", "text"} else None,
            ),
        }
        if self.settings.top_p is not None:
            payload["top_p"] = self.settings.top_p
        if response_mode == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": _schema_response_name(schema_version),
                    "strict": True,
                    "schema": schema,
                },
            }
        elif response_mode == "json_object":
            payload["response_format"] = {"type": "json_object"}
        elif response_mode == "text":
            payload["response_format"] = {"type": "text"}
        return payload

    def _request_json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = self.settings.base_url.rstrip("/") + path
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"
        req = request.Request(url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=self.settings.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                detail = ""
            suffix = f": {detail[:500]}" if detail else ""
            raise RuntimeError(f"LM Studio request failed: HTTP Error {exc.code}: {exc.reason}{suffix}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"LM Studio request failed: {exc}") from exc
        parsed = json.loads(body or "{}")
        if not isinstance(parsed, dict):
            raise RuntimeError("LM Studio response must be a JSON object.")
        return parsed


def _extract_message_content(raw: dict[str, Any]) -> str:
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("LM Studio response did not include choices.")
    first = choices[0]
    if not isinstance(first, dict):
        raise RuntimeError("LM Studio response choice must be an object.")
    message = first.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("LM Studio response choice did not include a message object.")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LM Studio response message content was empty.")
    return content


def _extract_reasoning_text_fallback(raw: dict[str, Any]) -> str:
    reasoning = _extract_message_field(raw, "reasoning_content")
    if not reasoning:
        return ""
    for marker in (
        "Final Output Generation:",
        "Final Response:",
        "Construct Final Response:",
        "Final choice:",
        "Decision:",
        "Response:",
        "Output:",
    ):
        candidate = _short_candidate_after_marker(reasoning, marker)
        if candidate:
            return candidate
    candidates = []
    for match in re.finditer(r"`([^`\r\n]{1,220})`|\"([^\"\r\n]{1,220})\"", reasoning):
        candidate = match.group(1) or match.group(2) or ""
        candidate = _clean_reasoning_candidate(candidate)
        if _looks_like_final_chat_candidate(candidate):
            candidates.append(candidate)
    return candidates[-1] if candidates else ""


def _extract_message_field(raw: dict[str, Any], field: str) -> str:
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    value = message.get(field)
    return value if isinstance(value, str) else ""


def _short_candidate_after_marker(text: str, marker: str) -> str:
    index = text.rfind(marker)
    if index < 0:
        return ""
    tail = text[index + len(marker):].strip()
    if not tail:
        return ""
    first_lines = [line.strip(" \t*-") for line in tail.splitlines() if line.strip()]
    if not first_lines:
        return ""
    for line in first_lines[:4]:
        line = _clean_reasoning_candidate(line)
        if _looks_like_final_chat_candidate(line):
            return line
    return ""


def _clean_reasoning_candidate(candidate: str) -> str:
    line = " ".join(str(candidate).replace("\r", " ").replace("\n", " ").split())
    line = line.strip(" \t`*_")
    if len(line) >= 2 and line[0] == line[-1] and line[0] in {"'", '"'}:
        line = line[1:-1].strip()
    return line


def _looks_like_final_chat_candidate(candidate: str) -> bool:
    if not candidate or len(candidate) > 220:
        return False
    lowered = candidate.lower()
    blocked = (
        "analyze the request",
        "input:",
        "instruction:",
        "constraint",
        "draft ",
        "final verification",
        "character count",
        "thinking process",
    )
    return not any(token in lowered for token in blocked)


def _schema_response_name(schema_version: str) -> str:
    name = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(schema_version))
    return name[:64] or "wm_schema"
