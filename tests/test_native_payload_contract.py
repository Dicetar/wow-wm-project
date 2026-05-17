from __future__ import annotations

import unittest

from wm.sources.native_bridge.payload_contract import (
    audit_contract_coverage,
    validate_native_action_payload,
)


class PayloadContractTests(unittest.TestCase):
    def test_valid_payload_passes(self) -> None:
        issues = validate_native_action_payload(
            action_kind="creature_set_name",
            payload={"name": "Grizzlemaw the Returned", "object_id": 42},
        )
        self.assertEqual(issues, [])

    def test_missing_required_field_flagged(self) -> None:
        issues = validate_native_action_payload(
            action_kind="creature_set_name",
            payload={"object_id": 42},
        )
        self.assertTrue(any("missing required" in i and "name" in i for i in issues))

    def test_required_any_none_present_flagged(self) -> None:
        issues = validate_native_action_payload(
            action_kind="creature_set_name",
            payload={"name": "X"},  # no object_id/live_guid/arc_key
        )
        self.assertTrue(any("at least one of" in i for i in issues))

    def test_required_any_one_present_ok(self) -> None:
        self.assertEqual(
            validate_native_action_payload(
                action_kind="wm_counter_increment",
                payload={"counter_key": "oath:no_death"},
            ),
            [],
        )

    def test_unknown_kind_flagged(self) -> None:
        issues = validate_native_action_payload(action_kind="not_a_real_kind", payload={})
        self.assertTrue(issues and "unknown native action kind" in issues[0])

    def test_kind_without_contract_is_not_blocked(self) -> None:
        # debug_ping is implemented but intentionally payload-free / freeform.
        self.assertEqual(
            validate_native_action_payload(action_kind="debug_ping", payload={}),
            [],
        )

    def test_empty_value_counts_as_missing(self) -> None:
        issues = validate_native_action_payload(
            action_kind="player_add_title",
            payload={"title_id": ""},
        )
        self.assertTrue(any("title_id" in i for i in issues))

    def test_coverage_has_no_orphan_contracts(self) -> None:
        cov = audit_contract_coverage()
        self.assertEqual(cov.orphan_contracts, [], f"orphans: {cov.orphan_contracts}")

    def test_implemented_kinds_without_contract_are_only_freeform_debug(self) -> None:
        cov = audit_contract_coverage()
        allowed = {"debug_ping", "debug_echo", "debug_fail", "context_snapshot_request"}
        leaked = [k for k in cov.implemented_without_contract if k not in allowed]
        self.assertEqual(leaked, [], f"implemented kinds missing a contract: {leaked}")


class SubmitEnforcementTests(unittest.TestCase):
    def test_submit_rejects_bad_payload_before_db(self) -> None:
        from wm.config import Settings
        from wm.sources.native_bridge.actions import NativeBridgeActionClient

        class _NoDb:
            def query(self, **_kw):
                raise AssertionError("DB must not be touched when the contract fails")

        client = NativeBridgeActionClient(client=_NoDb(), settings=Settings())
        with self.assertRaises(ValueError) as ctx:
            client.submit(
                idempotency_key="k1",
                player_guid=5406,
                action_kind="creature_set_name",
                payload={"object_id": 1},  # missing required 'name'
            )
        self.assertIn("contract violation", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
