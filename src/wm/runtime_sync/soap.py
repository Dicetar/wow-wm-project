from __future__ import annotations

from dataclasses import asdict, dataclass, field
from html import unescape
import base64
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from wm.config import Settings

SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
AC_NS = "urn:AC"


@dataclass(slots=True)
class RuntimeCommandResult:
    command: str
    ok: bool
    result: str = ""
    fault_code: str | None = None
    fault_string: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RuntimeSyncResult:
    protocol: str
    enabled: bool
    overall_ok: bool
    commands: list[RuntimeCommandResult] = field(default_factory=list)
    restart_recommended: bool = False
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "enabled": self.enabled,
            "overall_ok": self.overall_ok,
            "commands": [command.to_dict() for command in self.commands],
            "restart_recommended": self.restart_recommended,
            "note": self.note,
        }


class SoapRuntimeClient:
    def __init__(
        self,
        *,
        settings: Settings,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self.settings = settings
        self._opener = opener or urlopen

    @property
    def endpoint(self) -> str:
        path = self.settings.soap_path or "/"
        if not path.startswith("/"):
            path = "/" + path
        return f"http://{self.settings.soap_host}:{self.settings.soap_port}{path}"

    def execute_command(self, command: str) -> RuntimeCommandResult:
        payload = self._build_envelope(command).encode("utf-8")
        request = Request(
            self.endpoint,
            data=payload,
            method="POST",
            headers={
                "Authorization": self._basic_auth_header(),
                "Content-Type": "application/xml",
            },
        )
        try:
            with self._opener(request, timeout=10) as response:
                body = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            parsed = self._parse_response(body)
            if parsed is not None:
                return parsed
            return RuntimeCommandResult(
                command=command,
                ok=False,
                fault_code="HTTPError",
                fault_string=f"HTTP {exc.code}: {exc.reason}",
            )
        except URLError as exc:
            return RuntimeCommandResult(
                command=command,
                ok=False,
                fault_code="URLError",
                fault_string=str(exc.reason),
            )

        parsed = self._parse_response(body)
        if parsed is None:
            return RuntimeCommandResult(
                command=command,
                ok=False,
                fault_code="ParseError",
                fault_string="Could not parse SOAP runtime response.",
            )
        return parsed

    def _build_envelope(self, command: str) -> str:
        escaped = (
            command.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return (
            '<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" '
            'xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" '
            'xmlns:xsi="http://www.w3.org/1999/XMLSchema-instance" '
            'xmlns:xsd="http://www.w3.org/1999/XMLSchema" '
            'xmlns:ns1="urn:AC">'
            '<SOAP-ENV:Body>'
            '<ns1:executeCommand>'
            f'<command>{escaped}</command>'
            '</ns1:executeCommand>'
            '</SOAP-ENV:Body>'
            '</SOAP-ENV:Envelope>'
        )

    def _basic_auth_header(self) -> str:
        token = f"{self.settings.soap_user}:{self.settings.soap_password}".encode("utf-8")
        return "Basic " + base64.b64encode(token).decode("ascii")

    def _parse_response(self, body: str) -> RuntimeCommandResult | None:
        if not body.strip():
            return None
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            return None

        fault = root.find(f".//{{{SOAP_NS}}}Fault")
        if fault is not None:
            fault_code = fault.findtext("faultcode")
            fault_string = fault.findtext("faultstring")
            return RuntimeCommandResult(
                command="",
                ok=False,
                fault_code=fault_code,
                fault_string=unescape(fault_string or "SOAP fault"),
            )

        result = root.findtext(f".//{{{AC_NS}}}executeCommandResponse/result")
        if result is None:
            for node in root.iter():
                if node.tag.endswith("result") and node.text is not None:
                    result = node.text
                    break
        if result is None:
            return None
        return RuntimeCommandResult(command="", ok=True, result=unescape(result))


def build_default_quest_reload_commands(*, questgiver_entry: int | None = None) -> list[str]:
    commands = [
        ".reload creature_queststarter",
        ".reload creature_questender",
        ".reload all quest",
    ]
    if questgiver_entry is not None:
        commands.append(f".reload creature_template {int(questgiver_entry)}")
    return commands
