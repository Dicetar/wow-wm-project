from __future__ import annotations

import unittest

from wm.llm.lmstudio import LmStudioClient
from wm.llm.lmstudio import LmStudioSettings


class FakeLmStudioClient(LmStudioClient):
    def __init__(self, responses):
        super().__init__(LmStudioSettings(model="local-model"))
        self.responses = list(responses)
        self.payloads = []

    def _request_json(self, method, path, payload=None):
        self.last_method = method
        self.last_path = path
        self.last_payload = payload
        self.payloads.append(payload)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class LmStudioClientTests(unittest.TestCase):
    def test_model_listing_uses_models_endpoint(self) -> None:
        client = FakeLmStudioClient([{"data": [{"id": "model-a"}, {"id": "model-b"}]}])

        models = client.list_models()

        self.assertEqual(models, ["model-a", "model-b"])
        self.assertEqual(client.last_path, "/models")

    def test_structured_generation_inlines_json_schema(self) -> None:
        client = FakeLmStudioClient([
            {
                "choices": [
                    {
                        "message": {
                            "content": "{\"schema_version\":\"wm.quest.release.repeatable_bounty.v1\"}"
                        }
                    }
                ]
            }
        ])
        schema = {"type": "object", "properties": {"schema_version": {"type": "string"}}}

        result = client.generate_json(
            schema_version="wm.quest.release.repeatable_bounty.v1",
            schema=schema,
            instruction="make a bounty",
        )

        self.assertEqual(result["parsed"]["schema_version"], "wm.quest.release.repeatable_bounty.v1")
        self.assertEqual(client.last_path, "/chat/completions")
        self.assertEqual(client.last_payload["response_format"]["json_schema"]["schema"], schema)
        self.assertEqual(
            client.last_payload["response_format"]["json_schema"]["name"],
            "wm_quest_release_repeatable_bounty_v1",
        )

    def test_malformed_llm_json_raises(self) -> None:
        client = FakeLmStudioClient([
            {"choices": [{"message": {"content": "not json"}}]},
        ])

        with self.assertRaises(ValueError):
            client.generate_json(schema_version="x", schema={"type": "object"}, instruction="x")

    def test_structured_generation_falls_back_to_text_on_400(self) -> None:
        client = FakeLmStudioClient([
            RuntimeError("LM Studio request failed: HTTP Error 400: Bad Request"),
            {"choices": [{"message": {"content": "{\"schema_version\":\"x\"}"}}]},
        ])
        schema = {"type": "object", "properties": {"schema_version": {"const": "x"}}}

        result = client.generate_json(schema_version="x", schema=schema, instruction="make json")

        self.assertEqual(result["parsed"], {"schema_version": "x"})
        self.assertEqual(client.payloads[0]["response_format"]["type"], "json_schema")
        self.assertEqual(client.payloads[1]["response_format"]["type"], "text")
        self.assertIn("json_schema", client.payloads[1]["messages"][1]["content"])

    def test_text_generation_requests_text_response_format(self) -> None:
        client = FakeLmStudioClient([
            {"choices": [{"message": {"content": "Follow the smoke east."}}]},
        ])
        client.settings = LmStudioSettings(model="local-model", schema_mode="text")

        result = client.generate_text(messages=[{"role": "user", "content": "What now?"}])

        self.assertEqual(result["content"], "Follow the smoke east.")
        self.assertEqual(client.last_path, "/chat/completions")
        self.assertEqual(client.last_payload["response_format"], {"type": "text"})
        self.assertEqual(client.last_payload["messages"][0]["content"], "What now?")

    def test_text_generation_can_extract_short_reasoning_fallback(self) -> None:
        client = FakeLmStudioClient([
            {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "reasoning_content": "Thinking Process:\n\nDecision: `qwen path active.`",
                        }
                    }
                ]
            }
        ])
        client.settings = LmStudioSettings(model="qwen-test", schema_mode="text")

        result = client.generate_text(messages=[{"role": "user", "content": "test"}])

        self.assertEqual(result["content"], "qwen path active.")
        self.assertTrue(result["reasoning_fallback"])


if __name__ == "__main__":
    unittest.main()
