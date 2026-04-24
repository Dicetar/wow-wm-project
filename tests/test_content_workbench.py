import unittest
import subprocess
import sys
import tempfile
import io
from contextlib import redirect_stdout
from pathlib import Path

from wm.content.workbench import build_additem_command
from wm.content.workbench import build_direct_spell_grant_metadata
from wm.content.workbench import build_managed_spell_grant_metadata
from wm.content.workbench import build_player_learn_command
from wm.content.workbench import build_player_unlearn_command
from wm.content.workbench import build_send_items_command
from wm.content.workbench import configure_bonebound_servant_runtime
from wm.content.workbench import configure_twin_skeleton_runtime
from wm.content.workbench import describe_wm_spell_scope
from wm.content.workbench import execute_runtime_command
from wm.content.workbench import execute_item_delivery_command
from wm.content.workbench import execute_spell_runtime_action
from wm.content.workbench import create_item_draft
from wm.content.workbench import create_passive_draft
from wm.content.workbench import create_trigger_spell_draft
from wm.content.workbench import create_visible_spell_draft
from wm.content.workbench import publish_result_allows_runtime
from wm.content.workbench import record_spell_grant_state
from wm.content.workbench import resolve_managed_spell_runtime_target
from wm.content.workbench import resolve_shell_target
from wm.content.workbench import _maybe_wait_for_player_online
from wm.content.workbench import _print_publish_summary
from wm.content.workbench import _resolve_player_reference
from wm.content.workbench import _verify_character_spell_runtime_state
from wm.content.workbench import WorkbenchRuntimeResult
from wm.spells.models import ManagedSpellDraft
from wm.reserved.models import ReservedSlot
from wm.runtime_sync import RuntimeCommandResult


class FakeAllocator:
    def __init__(self) -> None:
        self.calls = []
        self.next_item = 910020
        self.next_spell = 947020

    def allocate_next_free_slot(self, **kwargs):
        self.calls.append(kwargs)
        entity_type = kwargs["entity_type"]
        if entity_type == "item":
            reserved_id = self.next_item
            self.next_item += 1
        elif entity_type == "spell":
            reserved_id = self.next_spell
            self.next_spell += 1
        else:
            raise AssertionError(f"Unexpected entity_type: {entity_type}")
        return ReservedSlot(
            entity_type=entity_type,
            reserved_id=reserved_id,
            slot_status="staged",
            arc_key=kwargs.get("arc_key"),
            character_guid=kwargs.get("character_guid"),
            source_quest_id=kwargs.get("source_quest_id"),
            notes=list(kwargs.get("notes") or []),
        )


class DeliveryFallbackTests(unittest.TestCase):
    def test_auto_item_delivery_falls_back_to_mail_after_additem_failure(self) -> None:
        calls = []

        def fake_execute_runtime_command(*, settings, command, mode):
            calls.append(command)
            if command.startswith(".additem "):
                return WorkbenchRuntimeResult(
                    mode=mode,
                    command=command,
                    ok=False,
                    executed=True,
                    fault_string="Item ID 910001 does not exist.",
                )
            return WorkbenchRuntimeResult(
                mode=mode,
                command=command,
                ok=True,
                executed=True,
                result="Mail sent to Jecia",
            )

        original = execute_item_delivery_command.__globals__["execute_runtime_command"]
        execute_item_delivery_command.__globals__["execute_runtime_command"] = fake_execute_runtime_command
        try:
            result = execute_item_delivery_command(
                settings=object(),  # type: ignore[arg-type]
                player_ref={"command_player": "5406", "player_name": "Jecia"},
                item_entry=910001,
                count=1,
                delivery="auto",
                mail_subject="WM Prototype",
                mail_body="Prototype delivery.",
                mode="apply",
            )
        finally:
            execute_item_delivery_command.__globals__["execute_runtime_command"] = original

        self.assertEqual(calls[0], ".additem 5406 910001 1")
        self.assertEqual(calls[1], '.send items Jecia "WM Prototype" "Prototype delivery." 910001:1')
        self.assertTrue(result.ok)
        self.assertTrue(any("Primary .additem delivery failed" in note for note in (result.notes or [])))


class RuntimeCommandTests(unittest.TestCase):
    def test_player_learn_treats_already_known_spell_as_success(self) -> None:
        class FakeSoapRuntimeClient:
            def __init__(self, settings) -> None:
                self.settings = settings

            def execute_command(self, command: str):
                return RuntimeCommandResult(
                    command=command,
                    ok=False,
                    fault_code="SOAP-ENV:Client",
                    fault_string="Target(Jecia) already know that spell.\r\n",
                )

        settings = type(
            "SettingsStub",
            (),
            {
                "soap_enabled": True,
                "soap_user": "wm",
                "soap_password": "wm",
            },
        )()

        original = execute_runtime_command.__globals__["SoapRuntimeClient"]
        execute_runtime_command.__globals__["SoapRuntimeClient"] = FakeSoapRuntimeClient
        try:
            result = execute_runtime_command(
                settings=settings,  # type: ignore[arg-type]
                command=".player learn Jecia 940001",
                mode="apply",
            )
        finally:
            execute_runtime_command.__globals__["SoapRuntimeClient"] = original

        self.assertTrue(result.ok)
        self.assertIsNone(result.fault_code)
        self.assertIsNone(result.fault_string)
        self.assertTrue(any("idempotent" in note.lower() for note in (result.notes or [])))

    def test_verify_character_spell_runtime_state_marks_missing_learn_as_failure(self) -> None:
        class FakeClient:
            def query(self, **kwargs):
                return []

        settings = type(
            "SettingsStub",
            (),
            {
                "char_db_host": "127.0.0.1",
                "char_db_port": 33307,
                "char_db_user": "acore",
                "char_db_password": "acore",
                "char_db_name": "acore_characters",
                "soap_enabled": False,
                "soap_user": "",
                "soap_password": "",
            },
        )()

        result = _verify_character_spell_runtime_state(
            client=FakeClient(),  # type: ignore[arg-type]
            settings=settings,  # type: ignore[arg-type]
            player_guid=5406,
            spell_entry=133,
            action_kind="player_learn_spell",
            result=WorkbenchRuntimeResult(mode="apply", command=".player learn 5406 133", ok=True, executed=True),
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.fault_code, "runtime_verification_failed")
        self.assertIn("expected row to be present", result.fault_string)

    def test_verify_character_spell_runtime_state_accepts_present_learn_row(self) -> None:
        class FakeClient:
            def query(self, **kwargs):
                return [{"guid": "5406", "spell": "133"}]

        settings = type(
            "SettingsStub",
            (),
            {
                "char_db_host": "127.0.0.1",
                "char_db_port": 33307,
                "char_db_user": "acore",
                "char_db_password": "acore",
                "char_db_name": "acore_characters",
                "soap_enabled": False,
                "soap_user": "",
                "soap_password": "",
            },
        )()

        result = _verify_character_spell_runtime_state(
            client=FakeClient(),  # type: ignore[arg-type]
            settings=settings,  # type: ignore[arg-type]
            player_guid=5406,
            spell_entry=133,
            action_kind="player_learn_spell",
            result=WorkbenchRuntimeResult(mode="apply", command=".player learn 5406 133", ok=True, executed=True),
        )

        self.assertTrue(result.ok)
        self.assertIn("character_spell_present=true expected_present=true", " ".join(result.notes or []))

    def test_verify_character_spell_runtime_state_runs_saveall_before_db_check_when_soap_is_available(self) -> None:
        commands = []

        class FakeClient:
            def query(self, **kwargs):
                return [{"guid": "5406", "spell": "133"}]

        settings = type(
            "SettingsStub",
            (),
            {
                "char_db_host": "127.0.0.1",
                "char_db_port": 33307,
                "char_db_user": "acore",
                "char_db_password": "acore",
                "char_db_name": "acore_characters",
                "soap_enabled": True,
                "soap_user": "soap",
                "soap_password": "soap",
            },
        )()

        def fake_execute_runtime_command(*, settings, command, mode):
            commands.append(command)
            return WorkbenchRuntimeResult(mode=mode, command=command, ok=True, executed=True, result="saved")

        original = _verify_character_spell_runtime_state.__globals__["execute_runtime_command"]
        _verify_character_spell_runtime_state.__globals__["execute_runtime_command"] = fake_execute_runtime_command
        try:
            result = _verify_character_spell_runtime_state(
                client=FakeClient(),  # type: ignore[arg-type]
                settings=settings,  # type: ignore[arg-type]
                player_guid=5406,
                spell_entry=133,
                action_kind="player_learn_spell",
                result=WorkbenchRuntimeResult(mode="apply", command=".player learn 5406 133", ok=True, executed=True),
            )
        finally:
            _verify_character_spell_runtime_state.__globals__["execute_runtime_command"] = original

        self.assertEqual(commands, [".saveall"])
        self.assertTrue(result.ok)
        self.assertIn("saveall_ok=true executed=true", " ".join(result.notes or []))

    def test_verify_character_spell_runtime_state_retries_until_unlearn_row_disappears(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.calls = 0

            def query(self, **kwargs):
                self.calls += 1
                if self.calls < 3:
                    return [{"guid": "5406", "spell": "940001"}]
                return []

        settings = type(
            "SettingsStub",
            (),
            {
                "char_db_host": "127.0.0.1",
                "char_db_port": 33307,
                "char_db_user": "acore",
                "char_db_password": "acore",
                "char_db_name": "acore_characters",
                "soap_enabled": False,
                "soap_user": "",
                "soap_password": "",
            },
        )()

        result = _verify_character_spell_runtime_state(
            client=FakeClient(),  # type: ignore[arg-type]
            settings=settings,  # type: ignore[arg-type]
            player_guid=5406,
            spell_entry=940001,
            action_kind="player_unlearn_spell",
            result=WorkbenchRuntimeResult(mode="apply", command=".player unlearn Jecia 940001", ok=True, executed=True),
        )

        self.assertTrue(result.ok)
        joined = " ".join(result.notes or [])
        self.assertIn("character_spell_verify_attempts=3", joined)
        self.assertIn("character_spell_present=false expected_present=false", joined)


class SpellGrantGovernanceTests(unittest.TestCase):
    def test_describe_wm_spell_scope_recognizes_named_shell(self) -> None:
        metadata = describe_wm_spell_scope(spell_id=940000)

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata["grant_scope"], "spell_shell")
        self.assertEqual(metadata["claim_key"], "bonebound_servant_v1")

    def test_describe_wm_spell_scope_recognizes_managed_slot_range(self) -> None:
        metadata = describe_wm_spell_scope(spell_id=947000)

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata["grant_scope"], "managed_spell_slot")
        self.assertEqual(metadata["range_key"], "managed_spell_slots")

    def test_direct_spell_grant_metadata_ignores_stock_spell(self) -> None:
        self.assertIsNone(build_direct_spell_grant_metadata(spell_entry=133, source_command="learn-spell", all_ranks=False))

    def test_resolve_managed_spell_runtime_target_uses_base_visible_spell(self) -> None:
        target = resolve_managed_spell_runtime_target(
            draft=ManagedSpellDraft(
                spell_entry=947020,
                slot_kind="visible_spell_slot",
                name="Visible Proof",
                base_visible_spell_id=133,
            )
        )

        self.assertTrue(target["can_runtime_learn"])
        self.assertEqual(target["artifact_spell_entry"], 947020)
        self.assertEqual(target["runtime_spell_entry"], 133)
        self.assertEqual(target["runtime_source"], "base_visible_spell_id")

    def test_resolve_managed_spell_runtime_target_rejects_nonvisible_managed_slot(self) -> None:
        target = resolve_managed_spell_runtime_target(
            draft=ManagedSpellDraft(
                spell_entry=947000,
                slot_kind="passive_slot",
                name="Passive Proof",
            )
        )

        self.assertFalse(target["can_runtime_learn"])
        self.assertIn("not a directly learnable spell identity", target["reason"])

    def test_publish_result_allows_runtime_requires_apply_success(self) -> None:
        self.assertFalse(
            publish_result_allows_runtime(
                publish_result={
                    "mode": "apply",
                    "validation": {"ok": True},
                    "preflight": {"ok": True},
                    "applied": False,
                }
            )
        )
        self.assertTrue(
            publish_result_allows_runtime(
                publish_result={
                    "mode": "dry-run",
                    "validation": {"ok": True},
                    "preflight": {"ok": True},
                    "applied": False,
                }
            )
        )

    def test_managed_spell_grant_metadata_records_runtime_target(self) -> None:
        metadata = build_managed_spell_grant_metadata(
            draft=ManagedSpellDraft(
                spell_entry=947020,
                slot_kind="visible_spell_slot",
                name="Visible Proof",
                base_visible_spell_id=133,
            ),
            draft_path=None,
            reserved_slot=None,
            source_command="publish-spell",
            all_ranks=False,
        )

        self.assertEqual(metadata["grant_scope"], "managed_spell_slot")
        self.assertEqual(metadata["spell_entry"], 947020)
        self.assertTrue(metadata["runtime_can_learn"])
        self.assertEqual(metadata["runtime_spell_entry"], 133)
        self.assertEqual(metadata["runtime_source"], "base_visible_spell_id")

    def test_record_spell_grant_state_inserts_and_revokes(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.queries = []

            def query(self, **kwargs):
                self.queries.append(kwargs)
                return []

        client = FakeClient()
        settings = type(
            "SettingsStub",
            (),
            {
                "world_db_host": "127.0.0.1",
                "world_db_port": 33307,
                "world_db_user": "acore",
                "world_db_password": "acore",
                "world_db_name": "acore_world",
            },
        )()

        original = record_spell_grant_state.__globals__["_world_table_exists"]
        record_spell_grant_state.__globals__["_world_table_exists"] = lambda **_kwargs: True
        try:
            granted = record_spell_grant_state(
                client=client,  # type: ignore[arg-type]
                settings=settings,  # type: ignore[arg-type]
                player_guid=5406,
                spell_id=947000,
                grant_kind="managed_spell_slot_grant",
                author="wm.content.workbench",
                metadata={"grant_scope": "managed_spell_slot"},
            )
            revoked = record_spell_grant_state(
                client=client,  # type: ignore[arg-type]
                settings=settings,  # type: ignore[arg-type]
                player_guid=5406,
                spell_id=947000,
                grant_kind="managed_spell_slot_revoke",
                author="wm.content.workbench",
                metadata={"grant_scope": "managed_spell_slot"},
                revoked=True,
            )
        finally:
            record_spell_grant_state.__globals__["_world_table_exists"] = original

        self.assertFalse(granted["revoked"])
        self.assertTrue(revoked["revoked"])
        self.assertIn("INSERT INTO wm_spell_grant", client.queries[0]["sql"])
        self.assertIn("ShellSpellID = 947000", client.queries[1]["sql"])

    def test_print_publish_summary_requires_apply_mutation_success(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = _print_publish_summary(
                publish_result={
                    "mode": "apply",
                    "validation": {"ok": True},
                    "preflight": {"ok": True},
                    "applied": False,
                },
                runtime_result=None,
                grant_record=None,
                output_json=None,
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("publish_applied=false", output.getvalue())


class ContentWorkbenchTests(unittest.TestCase):
    def test_module_entrypoint_prints_help(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]

        completed = subprocess.run(
            [sys.executable, "-m", "wm.content.workbench", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("new-item", completed.stdout)
        self.assertIn("new-summon-shell", completed.stdout)
        self.assertIn("grant-shell", completed.stdout)

    def test_create_item_draft_claims_reserved_slot(self) -> None:
        allocator = FakeAllocator()

        draft, slot = create_item_draft(
            allocator=allocator,  # type: ignore[arg-type]
            name="Jecia Test Token",
            base_item_entry=6948,
            player_guid=5406,
        )

        self.assertEqual(slot.reserved_id, 910020)
        self.assertEqual(draft.item_entry, 910020)
        self.assertEqual(draft.base_item_entry, 6948)
        self.assertEqual(draft.name, "Jecia Test Token")
        self.assertTrue(draft.clear_spells)
        self.assertIn("wm_generated", draft.tags)
        self.assertEqual(draft.template_defaults["RandomProperty"], 0)
        self.assertEqual(draft.template_defaults["RandomSuffix"], 0)
        self.assertEqual(allocator.calls[0]["arc_key"], "wm_content:item:jecia-test-token")

    def test_create_passive_draft_uses_passive_slot(self) -> None:
        allocator = FakeAllocator()

        draft, slot = create_passive_draft(
            allocator=allocator,  # type: ignore[arg-type]
            name="Jecia Passive Surge",
            player_guid=5406,
            helper_spell_id=48161,
            aura_description="Temporary passive test hook.",
        )

        self.assertEqual(slot.reserved_id, 947020)
        self.assertEqual(draft.spell_entry, 947020)
        self.assertEqual(draft.slot_kind, "passive_slot")
        self.assertEqual(draft.helper_spell_id, 48161)
        self.assertIn("passive_slot", draft.tags)
        self.assertEqual(allocator.calls[0]["arc_key"], "wm_content:passive:jecia-passive-surge")

    def test_create_trigger_spell_draft_uses_item_trigger_slot(self) -> None:
        allocator = FakeAllocator()

        draft, slot = create_trigger_spell_draft(
            allocator=allocator,  # type: ignore[arg-type]
            name="Jecia Trigger Burst",
            trigger_item_entry=910020,
            player_guid=5406,
            helper_spell_id=133,
        )

        self.assertEqual(slot.reserved_id, 947020)
        self.assertEqual(draft.slot_kind, "item_trigger_slot")
        self.assertEqual(draft.trigger_item_entry, 910020)
        self.assertEqual(draft.helper_spell_id, 133)
        self.assertIn("item_trigger_slot", draft.tags)

    def test_create_visible_spell_draft_uses_visible_slot(self) -> None:
        allocator = FakeAllocator()

        draft, slot = create_visible_spell_draft(
            allocator=allocator,  # type: ignore[arg-type]
            name="Jecia Visible Burst",
            base_visible_spell_id=133,
            player_guid=5406,
        )

        self.assertEqual(slot.reserved_id, 947020)
        self.assertEqual(draft.slot_kind, "visible_spell_slot")
        self.assertEqual(draft.base_visible_spell_id, 133)
        self.assertIn("visible_spell_slot", draft.tags)

    def test_gm_command_builders_match_expected_shapes(self) -> None:
        self.assertEqual(build_additem_command(player="Jecia", item_entry=910020, count=2), ".additem Jecia 910020 2")
        self.assertEqual(
            build_send_items_command(
                player_name="Jecia",
                item_entry=910020,
                count=2,
                subject='WM "Loot"',
                body="Fast prototype delivery.\nUse it well.",
            ),
            '.send items Jecia "WM \'Loot\'" "Fast prototype delivery. Use it well." 910020:2',
        )
        self.assertEqual(build_player_learn_command(player="5406", spell_entry=947020), ".player learn 5406 947020")
        self.assertEqual(
            build_player_unlearn_command(player="5406", spell_entry=947020, all_ranks=True),
            ".player unlearn 5406 947020 all",
        )

    def test_configure_twin_skeleton_runtime_can_preview_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp).joinpath("mod_wm_spells.conf")
            config_path.write_text("[worldserver]\n", encoding="utf-8")
            settings = type("SettingsStub", (), {"wm_spells_config_path": str(config_path), "soap_enabled": False})()

            result = configure_twin_skeleton_runtime(
                settings=settings,  # type: ignore[arg-type]
                player_guid=5406,
                shell_spell_id=940001,
                mode="dry-run",
                config_path=config_path,
                reload_via_soap=False,
            )

            self.assertTrue(result["changed"])
            self.assertEqual(result["new_allowlist"], [5406])
            self.assertEqual(result["new_shell_spell_ids"], [940001])
            self.assertTrue(result["debug_invoke_enabled"])
            self.assertIn("WM shell-bank", " ".join(result["notes"]))
            self.assertEqual(config_path.read_text(encoding="utf-8"), "[worldserver]\n")

    def test_configure_bonebound_servant_runtime_can_preview_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp).joinpath("mod_wm_spells.conf")
            config_path.write_text("[worldserver]\n", encoding="utf-8")
            settings = type("SettingsStub", (), {"wm_spells_config_path": str(config_path), "soap_enabled": False})()

            result = configure_bonebound_servant_runtime(
                settings=settings,  # type: ignore[arg-type]
                player_guid=5406,
                shell_spell_id=940000,
                mode="dry-run",
                config_path=config_path,
                reload_via_soap=False,
            )

            self.assertTrue(result["changed"])
            self.assertEqual(result["new_allowlist"], [5406])
            self.assertEqual(result["new_shell_spell_ids"], [940000])
            self.assertTrue(result["debug_invoke_enabled"])
            self.assertIn("shell-bank", " ".join(result["notes"]))
            self.assertEqual(config_path.read_text(encoding="utf-8"), "[worldserver]\n")

    def test_execute_spell_runtime_action_dry_run_prefers_native_bridge(self) -> None:
        result = execute_spell_runtime_action(
            client=None,  # type: ignore[arg-type]
            settings=object(),  # type: ignore[arg-type]
            player_ref={"player_guid": 5406, "player_name": "Jecia", "command_player": "5406"},
            spell_entry=940000,
            action_kind="player_learn_spell",
            mode="dry-run",
        )

        self.assertTrue(result.ok)
        self.assertFalse(result.executed)
        self.assertIn("native_bridge_action", " ".join(result.notes or []))

    def test_resolve_shell_target_uses_shell_bank_metadata(self) -> None:
        target = resolve_shell_target(shell_key="bonebound_servant_v1")

        self.assertEqual(target["spell_id"], 940000)
        self.assertEqual(target["behavior_kind"], "summon_bonebound_servant_v1")

    def test_resolve_player_reference_uses_explicit_guid_and_name_without_db_lookup(self) -> None:
        player_ref = _resolve_player_reference(
            client=None,  # type: ignore[arg-type]
            settings=None,  # type: ignore[arg-type]
            player_guid=5406,
            player_name="Jecia",
        )

        self.assertEqual(player_ref["player_guid"], 5406)
        self.assertEqual(player_ref["player_name"], "Jecia")
        self.assertEqual(player_ref["command_player"], "Jecia")

    def test_resolve_player_reference_reads_online_state_from_db(self) -> None:
        class FakeClient:
            def query(self, **kwargs):
                return [{"guid": "5406", "name": "Jecia", "online": "1"}]

        settings = type(
            "SettingsStub",
            (),
            {
                "char_db_host": "127.0.0.1",
                "char_db_port": 3306,
                "char_db_user": "acore",
                "char_db_password": "acore",
                "char_db_name": "acore_characters",
            },
        )()

        player_ref = _resolve_player_reference(
            client=FakeClient(),  # type: ignore[arg-type]
            settings=settings,  # type: ignore[arg-type]
            player_guid=5406,
            player_name="Jecia",
        )

        self.assertEqual(player_ref["player_guid"], 5406)
        self.assertTrue(player_ref["online"])

    def test_maybe_wait_for_player_online_polls_until_online(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.calls = 0

            def query(self, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    return [{"guid": "5406", "name": "Jecia", "online": "0"}]
                return [{"guid": "5406", "name": "Jecia", "online": "1"}]

        settings = type(
            "SettingsStub",
            (),
            {
                "char_db_host": "127.0.0.1",
                "char_db_port": 3306,
                "char_db_user": "acore",
                "char_db_password": "acore",
                "char_db_name": "acore_characters",
            },
        )()

        original_sleep = _maybe_wait_for_player_online.__globals__["time"].sleep
        _maybe_wait_for_player_online.__globals__["time"].sleep = lambda *_args, **_kwargs: None
        try:
            player_ref, notes = _maybe_wait_for_player_online(
                client=FakeClient(),  # type: ignore[arg-type]
                settings=settings,  # type: ignore[arg-type]
                player_ref={"player_guid": 5406, "player_name": "Jecia", "command_player": "Jecia", "online": False},
                player_guid=5406,
                player_name="Jecia",
                mode="apply",
                wait_for_player_online=True,
                wait_timeout_seconds=5.0,
                wait_poll_seconds=0.01,
            )
        finally:
            _maybe_wait_for_player_online.__globals__["time"].sleep = original_sleep

        self.assertEqual(player_ref["player_guid"], 5406)
        self.assertTrue(player_ref["online"])
        self.assertTrue(any("waited_for_player_online=true" in note for note in notes))


if __name__ == "__main__":
    unittest.main()
