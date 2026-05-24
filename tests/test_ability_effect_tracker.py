"""Tests for ActiveEffectTracker — aura-bound effect contract."""
from __future__ import annotations

from datetime import datetime, timedelta

from wm.abilities.models import EffectApplyRequest
from wm.abilities.tracker import ActiveEffectTracker, _make_effect_key


def _req(**kwargs) -> EffectApplyRequest:
    defaults = dict(
        target_kind="player",
        target_guid=5406,
        source_player_guid=5406,
        ability_key="wm.ability.test_dot",
        aura_spell_id=946001,
        effect_kind="damage_dot",
        effect_params={"damage_per_tick": 50, "tick_interval": 3},
        duration_seconds=30.0,
    )
    defaults.update(kwargs)
    return EffectApplyRequest(**defaults)


# --- no-DB mode (all graceful) ---

def test_apply_no_db_returns_effect():
    tracker = ActiveEffectTracker(db_client=None)
    result = tracker.apply(_req())
    assert result.ok
    assert result.effect is not None
    assert result.effect.state == "active"
    assert result.effect.aura_spell_id == 946001
    assert result.effect.effect_kind == "damage_dot"
    assert result.effect.expires_at is not None


def test_apply_permanent_no_db():
    tracker = ActiveEffectTracker(db_client=None)
    result = tracker.apply(_req(duration_seconds=None))
    assert result.ok
    assert result.effect.is_permanent
    assert result.effect.expires_at is None


def test_end_no_db():
    tracker = ActiveEffectTracker(db_client=None)
    result = tracker.end("any_key", reason="ended")
    assert result.ok
    assert result.reason == "ended"


def test_is_active_no_db_returns_false():
    # Without DB there is no tracking — gate defaults to False (safe)
    tracker = ActiveEffectTracker(db_client=None)
    assert tracker.is_active(target_guid=5406, target_kind="player", aura_spell_id=946001) is False


def test_on_dispelled_no_db_returns_empty():
    tracker = ActiveEffectTracker(db_client=None)
    results = tracker.on_dispelled(target_guid=5406, target_kind="player", aura_spell_id=946001)
    assert results == []


def test_expire_due_no_db_returns_empty():
    tracker = ActiveEffectTracker(db_client=None)
    assert tracker.expire_due() == []


def test_get_active_no_db_returns_empty():
    tracker = ActiveEffectTracker(db_client=None)
    assert tracker.get_active(target_guid=5406, target_kind="player") == []


def test_load_no_db_returns_none():
    tracker = ActiveEffectTracker(db_client=None)
    assert tracker.load("anything") is None


# --- model / key logic ---

def test_effect_key_is_deterministic():
    k1 = _make_effect_key("wm.ability.dot", "player", 5406)
    k2 = _make_effect_key("wm.ability.dot", "player", 5406)
    assert k1 == k2


def test_effect_key_differs_by_target():
    k1 = _make_effect_key("wm.ability.dot", "player", 5406)
    k2 = _make_effect_key("wm.ability.dot", "player", 9999)
    assert k1 != k2


def test_effect_key_differs_by_ability():
    k1 = _make_effect_key("wm.ability.dot", "player", 5406)
    k2 = _make_effect_key("wm.ability.slow", "player", 5406)
    assert k1 != k2


def test_seconds_remaining_positive():
    from wm.abilities.models import ActiveEffect
    now = datetime.utcnow()
    effect = ActiveEffect(
        effect_key="k",
        target_kind="player",
        target_guid=5406,
        source_player_guid=5406,
        ability_key="wm.ability.dot",
        aura_spell_id=946001,
        effect_kind="damage_dot",
        effect_params={},
        state="active",
        applied_at=now,
        expires_at=now + timedelta(seconds=30),
    )
    remaining = effect.seconds_remaining(now)
    assert remaining is not None
    assert 29.0 < remaining <= 30.0


def test_seconds_remaining_past_is_zero():
    from wm.abilities.models import ActiveEffect
    now = datetime.utcnow()
    effect = ActiveEffect(
        effect_key="k",
        target_kind="player",
        target_guid=5406,
        source_player_guid=5406,
        ability_key="wm.ability.dot",
        aura_spell_id=946001,
        effect_kind="damage_dot",
        effect_params={},
        state="active",
        applied_at=now - timedelta(seconds=60),
        expires_at=now - timedelta(seconds=10),
    )
    assert effect.seconds_remaining(now) == 0.0


def test_is_active_property():
    from wm.abilities.models import ActiveEffect
    now = datetime.utcnow()
    e = ActiveEffect("k", "player", 1, 1, "a", 1, "dot", {}, "active", now, None)
    assert e.is_active
    e2 = ActiveEffect("k", "player", 1, 1, "a", 1, "dot", {}, "dispelled", now, None)
    assert not e2.is_active


# --- in-memory DB stub ---

class _MemDB:
    """Minimal stub that supports execute() + query() for tracker tests."""

    def __init__(self):
        import json as _json
        self._rows: dict[str, dict] = {}
        self._json = _json

    def execute(self, sql: str) -> None:
        if sql.strip().upper().startswith("INSERT"):
            self._parse_insert(sql)
        elif sql.strip().upper().startswith("UPDATE"):
            self._parse_update(sql)

    def query(self, sql: str) -> list[dict]:
        import re as _re
        results = list(self._rows.values())

        upper = sql.upper().replace(" ", "")

        # state filter
        m = _re.search(r"state='(\w+)'", sql, _re.IGNORECASE)
        if m:
            results = [r for r in results if r.get("state") == m.group(1)]

        # target_guid filter
        m = _re.search(r"target_guid\s*=\s*(\d+)", sql, _re.IGNORECASE)
        if m:
            val = int(m.group(1))
            results = [r for r in results if int(r.get("target_guid", -1)) == val]

        # target_kind filter
        m = _re.search(r"target_kind\s*=\s*'(\w+)'", sql, _re.IGNORECASE)
        if m:
            val = m.group(1)
            results = [r for r in results if r.get("target_kind") == val]

        # aura_spell_id filter
        m = _re.search(r"aura_spell_id\s*=\s*(\d+)", sql, _re.IGNORECASE)
        if m:
            val = int(m.group(1))
            results = [r for r in results if int(r.get("aura_spell_id", -1)) == val]

        # effect_key filter
        m = _re.search(r"effect_key\s*=\s*'([^']+)'", sql, _re.IGNORECASE)
        if m:
            val = m.group(1)
            results = [r for r in results if r.get("effect_key") == val]

        # expires_at IS NOT NULL + expires_at <= cutoff
        if "EXPIRES_AT IS NOT NULL" in upper:
            results = [r for r in results if r.get("expires_at") is not None]
        m = _re.search(r"expires_at\s*<=\s*'([^']+)'", sql, _re.IGNORECASE)
        if m:
            cutoff = datetime.fromisoformat(m.group(1))
            results = [
                r for r in results
                if r.get("expires_at") and datetime.fromisoformat(str(r["expires_at"])) <= cutoff
            ]

        if "LIMIT 1" in sql.upper():
            results = results[:1]
        return results

    def _parse_insert(self, sql: str) -> None:
        import re, json as _json
        upper = sql.upper()
        values_idx = upper.find("VALUES")
        if values_idx == -1:
            return
        start_idx = sql.find("(", values_idx)
        if start_idx == -1:
            return
        depth = 0
        in_string = False
        end_idx = -1
        for i, ch in enumerate(sql[start_idx:], start=start_idx):
            if ch == "'" and not in_string:
                in_string = True
            elif ch == "'" and in_string:
                in_string = False
            elif not in_string:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        end_idx = i
                        break
        if end_idx == -1:
            return
        vals_raw = sql[start_idx + 1:end_idx]
        cols = [
            "effect_key", "target_kind", "target_guid", "source_player_guid", "ability_key",
            "aura_spell_id", "effect_kind", "effect_params_json", "state", "applied_at", "expires_at",
        ]
        vals = self._split_sql_values(vals_raw)
        if len(vals) < len(cols):
            return
        row = {}
        for col, val in zip(cols, vals):
            v = val.strip().strip("'")
            if col in ("target_guid", "source_player_guid", "aura_spell_id"):
                row[col] = int(v) if v != "NULL" else None
            elif col in ("applied_at", "expires_at"):
                row[col] = v if v != "NULL" else None
            else:
                row[col] = None if v == "NULL" else v
        key = row.get("effect_key", "")
        if key in self._rows and "ON DUPLICATE" in sql.upper():
            existing = self._rows[key]
            existing["state"] = "active"
            existing["applied_at"] = row["applied_at"]
            existing["expires_at"] = row["expires_at"]
            existing["ended_at"] = None
            existing["effect_params_json"] = row.get("effect_params_json")
        else:
            row["ended_at"] = None
            self._rows[key] = row

    def _parse_update(self, sql: str) -> None:
        import re
        m_key = re.search(r"effect_key='([^']+)'", sql, re.IGNORECASE)
        if not m_key:
            return
        key = m_key.group(1)
        if key not in self._rows:
            return
        m_state = re.search(r"state='([^']+)'", sql, re.IGNORECASE)
        if m_state:
            self._rows[key]["state"] = m_state.group(1)
        m_ended = re.search(r"ended_at='([^']+)'", sql, re.IGNORECASE)
        if m_ended:
            self._rows[key]["ended_at"] = m_ended.group(1)

    @staticmethod
    def _split_sql_values(raw: str) -> list[str]:
        parts = []
        depth = 0
        current = ""
        in_string = False
        for ch in raw:
            if ch == "'" and not in_string:
                in_string = True
                current += ch
            elif ch == "'" and in_string:
                in_string = False
                current += ch
            elif ch == "," and not in_string:
                parts.append(current.strip())
                current = ""
            else:
                current += ch
        if current.strip():
            parts.append(current.strip())
        return parts


def test_apply_with_stub_db():
    db = _MemDB()
    tracker = ActiveEffectTracker(db_client=db)
    result = tracker.apply(_req())
    assert result.ok
    assert result.effect_key is not None
    assert result.effect.state == "active"


def test_is_active_after_apply():
    db = _MemDB()
    tracker = ActiveEffectTracker(db_client=db)
    tracker.apply(_req())
    assert tracker.is_active(target_guid=5406, target_kind="player", aura_spell_id=946001)


def test_is_active_wrong_aura_returns_false():
    db = _MemDB()
    tracker = ActiveEffectTracker(db_client=db)
    tracker.apply(_req(aura_spell_id=946001))
    assert not tracker.is_active(target_guid=5406, target_kind="player", aura_spell_id=946999)


def test_end_clears_is_active():
    db = _MemDB()
    tracker = ActiveEffectTracker(db_client=db)
    res = tracker.apply(_req())
    tracker.end(res.effect_key, reason="ended")
    assert not tracker.is_active(target_guid=5406, target_kind="player", aura_spell_id=946001)


def test_on_dispelled_clears_effect():
    db = _MemDB()
    tracker = ActiveEffectTracker(db_client=db)
    tracker.apply(_req())
    results = tracker.on_dispelled(target_guid=5406, target_kind="player", aura_spell_id=946001)
    assert len(results) == 1
    assert results[0].reason == "dispelled"
    assert not tracker.is_active(target_guid=5406, target_kind="player", aura_spell_id=946001)


def test_expire_due_ends_overdue_effect():
    db = _MemDB()
    tracker = ActiveEffectTracker(db_client=db)
    tracker.apply(_req(duration_seconds=1))
    future = datetime.utcnow() + timedelta(seconds=60)
    results = tracker.expire_due(now=future)
    assert len(results) == 1
    assert results[0].reason == "expired"


def test_expire_due_skips_permanent():
    db = _MemDB()
    tracker = ActiveEffectTracker(db_client=db)
    tracker.apply(_req(duration_seconds=None))
    future = datetime.utcnow() + timedelta(days=999)
    results = tracker.expire_due(now=future)
    assert results == []


def test_get_active_returns_applied():
    db = _MemDB()
    tracker = ActiveEffectTracker(db_client=db)
    tracker.apply(_req(ability_key="wm.ability.dot", aura_spell_id=946001))
    effects = tracker.get_active(target_guid=5406, target_kind="player")
    assert len(effects) == 1
    assert effects[0].ability_key == "wm.ability.dot"


def test_duplicate_apply_reactivates():
    db = _MemDB()
    tracker = ActiveEffectTracker(db_client=db)
    r1 = tracker.apply(_req())
    tracker.end(r1.effect_key, reason="ended")
    r2 = tracker.apply(_req())
    assert r2.ok
    assert tracker.is_active(target_guid=5406, target_kind="player", aura_spell_id=946001)


def test_creature_target_kind():
    db = _MemDB()
    tracker = ActiveEffectTracker(db_client=db)
    result = tracker.apply(_req(target_kind="creature", target_guid=12345))
    assert result.ok
    assert tracker.is_active(target_guid=12345, target_kind="creature", aura_spell_id=946001)
    assert not tracker.is_active(target_guid=12345, target_kind="player", aura_spell_id=946001)
