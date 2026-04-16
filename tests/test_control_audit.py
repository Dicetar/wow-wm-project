import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from wm.config import Settings
from wm.control import audit as control_audit
from wm.control.store import ControlAuditRecord
from wm.control.store import ControlAuditStore
from wm.control.summary import native_request_refs_from_execution
from wm.events.models import WMEvent


def _row(**overrides):
    row = {
        "ProposalID": "12",
        "IdempotencyKey": "control:test",
        "SchemaVersion": "control.proposal.v1",
        "RegistryHash": "abc",
        "SchemaHash": "def",
        "AuthorMode": "manual",
        "AuthorName": "test",
        "PlayerGUID": "5406",
        "SourceEventID": "77",
        "SourceEventKey": "native_bridge:77",
        "SelectedRecipe": "kill_burst_bounty",
        "ActionKind": "quest_grant",
        "Status": "applied",
        "RawProposalJSON": json.dumps({"source_event": {"event_id": 77}}),
        "NormalizedProposalJSON": json.dumps({"ok": True}),
        "ValidationJSON": json.dumps({"ok": True, "issues": []}),
        "DryRunJSON": json.dumps({"status": "preview", "steps": []}),
        "ApplyJSON": json.dumps(
            {
                "status": "applied",
                "steps": [
                    {
                        "kind": "quest_grant",
                        "status": "applied",
                        "details": {
                            "native_request": {
                                "request_id": 31,
                                "idempotency_key": "control:test:native:quest_add:910000",
                                "player_guid": 5406,
                                "action_kind": "quest_add",
                                "status": "done",
                            }
                        },
                    }
                ],
            }
        ),
        "PolicyDecisionJSON": json.dumps({"id": "direct_apply"}),
        "CreatedAt": "2026-04-16 12:00:00",
        "UpdatedAt": "2026-04-16 12:01:00",
    }
    row.update(overrides)
    return row


class FakeMysqlClient:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def query(self, **kwargs):
        self.queries.append(kwargs["sql"])
        return self.rows


class FakeAuditStore:
    def __init__(self, *, client, settings):
        del client, settings

    def get_record(self, *, idempotency_key):
        if idempotency_key != "control:test":
            return None
        return ControlAuditRecord(
            proposal_id=12,
            idempotency_key="control:test",
            schema_version="control.proposal.v1",
            registry_hash="abc",
            schema_hash="def",
            author_mode="manual",
            author_name="test",
            player_guid=5406,
            source_event_id=77,
            source_event_key="native_bridge:77",
            selected_recipe="kill_burst_bounty",
            action_kind="quest_grant",
            status="applied",
            raw_proposal={"source_event": {"event_id": 77}},
            normalized_proposal={"idempotency_key": "control:test"},
            validation={"ok": True, "issues": []},
            dry_run={"status": "preview", "steps": []},
            apply={
                "status": "applied",
                "steps": [
                    {
                        "kind": "native_bridge_action",
                        "status": "applied",
                        "details": {
                            "request": {
                                "request_id": 44,
                                "idempotency_key": "control:test:native:debug_ping",
                                "player_guid": 5406,
                                "action_kind": "debug_ping",
                                "status": "done",
                            }
                        },
                    }
                ],
            },
            policy_decision={"id": "direct_apply"},
            created_at="2026-04-16 12:00:00",
            updated_at="2026-04-16 12:01:00",
        )

    def list_records(self, *, source_event_id=None, player_guid=None, limit=20):
        del source_event_id, player_guid, limit
        return [self.get_record(idempotency_key="control:test")]


class FakeEventStore:
    def __init__(self, *, client, settings):
        del client, settings

    def get_event(self, *, event_id):
        return WMEvent(
            event_id=event_id,
            event_class="observed",
            event_type="kill",
            source="native_bridge",
            source_event_key=f"native_bridge:{event_id}",
            occurred_at="2026-04-16 12:00:00",
            player_guid=5406,
            subject_type="creature",
            subject_entry=6,
        )

    def get_event_by_source_key(self, *, source, source_event_key):
        del source, source_event_key
        return None


class ControlAuditTests(unittest.TestCase):
    def test_store_fetches_and_decodes_audit_record(self) -> None:
        client = FakeMysqlClient([_row()])
        store = ControlAuditStore(client=client, settings=Settings())

        record = store.get_record(idempotency_key="control:test")

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.proposal_id, 12)
        self.assertEqual(record.validation, {"ok": True, "issues": []})
        refs = native_request_refs_from_execution(record.apply)
        self.assertEqual(refs[0]["request_id"], 31)
        self.assertEqual(refs[0]["action_kind"], "quest_add")

    def test_store_lists_by_event_and_player(self) -> None:
        client = FakeMysqlClient([_row()])
        store = ControlAuditStore(client=client, settings=Settings())

        records = store.list_records(source_event_id=77, player_guid=5406, limit=5)

        self.assertEqual(len(records), 1)
        self.assertIn("SourceEventID = 77", client.queries[0])
        self.assertIn("PlayerGUID = 5406", client.queries[0])
        self.assertIn("LIMIT 5", client.queries[0])

    def test_audit_cli_summary_exposes_native_request(self) -> None:
        output = io.StringIO()
        with (
            patch.object(control_audit, "ControlAuditStore", FakeAuditStore),
            patch.object(control_audit, "EventStore", FakeEventStore),
            redirect_stdout(output),
        ):
            exit_code = control_audit.main(["--idempotency-key", "control:test", "--summary"])

        self.assertEqual(exit_code, 0)
        rendered = output.getvalue()
        self.assertIn("proposal_id=12", rendered)
        self.assertIn("source_event id=77", rendered)
        self.assertIn("request_id=44", rendered)
        self.assertIn("action_kind=debug_ping", rendered)


if __name__ == "__main__":
    unittest.main()
