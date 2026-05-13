from __future__ import annotations

from dataclasses import dataclass
import json
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
        raw = self._request_json("POST", "/chat/completions", payload=request_payload)
        content = _extract_message_content(raw)
        parsed = parse_json_object(content)
        return {"request": request_payload, "raw": raw, "content": content, "parsed": parsed}

    def build_chat_payload(
        self,
        *,
        schema_version: str,
        schema: dict[str, Any],
        instruction: str,
        context_pack: Any | None = None,
        candidate_pack: Any | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_tokens,
            "messages": build_messages(
                schema_version=schema_version,
                instruction=instruction,
                context_pack=context_pack,
                candidate_pack=candidate_pack,
            ),
        }
        if self.settings.schema_mode == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_version,
                    "strict": True,
                    "schema": schema,
                },
            }
        elif self.settings.schema_mode == "json_object":
            payload["response_format"] = {"type": "json_object"}
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
