from wm.character.memory import apply_memory_action
from wm.character.memory import memory_action_sql
from wm.config import Settings


class _Client:
    def __init__(self, rows=None, affected_rows=1):
        self.rows = rows or []
        self.affected_rows = int(affected_rows)
        self.sql: list[str] = []

    def query(self, **kwargs):
        self.sql.append(kwargs["sql"])
        if kwargs["sql"].startswith("SELECT CharacterGUID"):
            return list(self.rows)
        return [{"affected_rows": str(self.affected_rows)}]


def test_memory_actions_are_scoped_and_audited():
    sql = memory_action_sql(player_guid=77, steering_key="preferred_name", action="suppress")

    assert "wm_character_memory_action" in sql
    assert "CharacterGUID = 77" in sql
    assert "SteeringKey = 'preferred_name'" in sql
    assert "IsActive = 0" in sql
    assert "SELECT ROW_COUNT() AS affected_rows" in sql


def test_memory_forget_redacts_body_and_deactivates():
    sql = memory_action_sql(player_guid=77, steering_key="private_fact", action="forget")

    assert "Body = ''" in sql
    assert "IsActive = 0" in sql
    assert "'forgotten', true" in sql


def test_memory_action_dry_run_requires_existing_key():
    client = _Client()
    result = apply_memory_action(
        client=client,
        settings=Settings(),
        player_guid=77,
        steering_key="missing",
        action="pin",
        mode="dry-run",
    )

    assert result["status"] == "not_found"
    assert len(client.sql) == 1


def test_memory_action_apply_executes_transaction_after_preview_lookup():
    client = _Client(rows=[{"CharacterGUID": 77, "SteeringKey": "preferred_name", "IsActive": 1, "Priority": 10}])
    result = apply_memory_action(
        client=client,
        settings=Settings(),
        player_guid=77,
        steering_key="preferred_name",
        action="pin",
        mode="apply",
    )

    assert result["status"] == "applied"
    assert result["affected_rows"] == 1
    assert len(client.sql) == 2
    assert client.sql[1].startswith("START TRANSACTION")


def test_memory_action_apply_requires_one_affected_row():
    client = _Client(rows=[{"CharacterGUID": 77, "SteeringKey": "preferred_name", "IsActive": 1, "Priority": 10}], affected_rows=0)
    result = apply_memory_action(
        client=client,
        settings=Settings(),
        player_guid=77,
        steering_key="preferred_name",
        action="pin",
        mode="apply",
    )

    assert result["ok"] is False
    assert result["status"] == "not_applied"
    assert result["affected_rows"] == 0
