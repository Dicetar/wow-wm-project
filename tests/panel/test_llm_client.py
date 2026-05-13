from __future__ import annotations

import unittest

from wm.llm.lmstudio import LmStudioClient
from wm.llm.lmstudio import LmStudioSettings


class FakeLmStudioClient(LmStudioClient):
    def __init__(self, responses):
        super().__init__(LmStudioSettings(model="local-model"))
        self.responses = list(responses)

    def _request_json(self, method, path, payload=None):
        self.last_method = method
        self.last_path = path
        self.last_payload = payload
        return self.responses.pop(0)


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

    def test_malformed_llm_json_raises(self) -> None:
        client = FakeLmStudioClient([
            {"choices": [{"message": {"content": "not json"}}]},
        ])

        with self.assertRaises(ValueError):
            client.generate_json(schema_version="x", schema={"type": "object"}, instruction="x")


if __name__ == "__main__":
    unittest.main()
