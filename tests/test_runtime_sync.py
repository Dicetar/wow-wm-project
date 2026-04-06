from __future__ import annotations

import io
import unittest

from wm.config import Settings
from wm.runtime_sync.soap import SoapRuntimeClient, build_default_quest_reload_commands


class FakeResponse:
    def __init__(self, body: str) -> None:
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class RuntimeSyncTests(unittest.TestCase):
    def test_build_default_reload_commands(self) -> None:
        commands = build_default_quest_reload_commands(questgiver_entry=197)
        self.assertEqual(commands[0], ".reload creature_queststarter")
        self.assertIn(".reload creature_template 197", commands)

    def test_soap_client_parses_success(self) -> None:
        captured = {}

        def opener(request, timeout=10):
            del timeout
            captured["url"] = request.full_url
            captured["auth"] = request.get_header("Authorization")
            return FakeResponse(
                """<?xml version='1.0' encoding='UTF-8'?>
                <SOAP-ENV:Envelope xmlns:SOAP-ENV='http://schemas.xmlsoap.org/soap/envelope/' xmlns:ns1='urn:AC'>
                  <SOAP-ENV:Body>
                    <ns1:executeCommandResponse>
                      <result>OK&#xD;Reloaded.</result>
                    </ns1:executeCommandResponse>
                  </SOAP-ENV:Body>
                </SOAP-ENV:Envelope>"""
            )

        client = SoapRuntimeClient(
            settings=Settings(
                soap_enabled=True,
                soap_host="127.0.0.1",
                soap_port=7878,
                soap_user="soapuser",
                soap_password="secret",
            ),
            opener=opener,
        )
        result = client.execute_command(".reload all quest")
        self.assertTrue(result.ok)
        self.assertIn("Reloaded", result.result)
        self.assertEqual(captured["url"], "http://127.0.0.1:7878/")
        self.assertTrue(str(captured["auth"]).startswith("Basic "))

    def test_soap_client_parses_fault(self) -> None:
        def opener(request, timeout=10):
            del request, timeout
            return FakeResponse(
                """<?xml version='1.0' encoding='UTF-8'?>
                <SOAP-ENV:Envelope xmlns:SOAP-ENV='http://schemas.xmlsoap.org/soap/envelope/'>
                  <SOAP-ENV:Body>
                    <SOAP-ENV:Fault>
                      <faultcode>SOAP-ENV:Client</faultcode>
                      <faultstring>Error 401: HTTP 401 Unauthorized</faultstring>
                    </SOAP-ENV:Fault>
                  </SOAP-ENV:Body>
                </SOAP-ENV:Envelope>"""
            )

        client = SoapRuntimeClient(settings=Settings(soap_enabled=True), opener=opener)
        result = client.execute_command("server status")
        self.assertFalse(result.ok)
        self.assertEqual(result.fault_code, "SOAP-ENV:Client")
        self.assertIn("Unauthorized", result.fault_string or "")


if __name__ == "__main__":
    unittest.main()
