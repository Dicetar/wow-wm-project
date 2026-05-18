"""Tests for Track II living world modules."""
from __future__ import annotations


def test_zone_mood_no_db():
    from wm.living.zone_mood import evaluate_zone_mood
    zm = evaluate_zone_mood(player_guid=5406, zone_id=12, db_client=None)
    assert zm.mood_key == "neutral"
    assert zm.intensity == 1


def test_zone_mood_pressure_tiers():
    from wm.living.zone_mood import _compute_mood
    assert _compute_mood(0) == ("neutral", 1)
    assert _compute_mood(5)[0] == "tense"
    assert _compute_mood(15)[0] == "hostile"
    assert _compute_mood(40)[1] == 5


def test_mentor_manager_no_db():
    from wm.content.mentor_task import MentorStep, MentorTask
    from wm.living.mentor import MentorManager
    mgr = MentorManager(db_client=None)
    task = MentorTask("t1", 3100, [MentorStep("s1", "x", "kill")])
    mgr.start_task(5406, task)  # must not raise
    assert mgr.get_progress(5406, "t1") is None


def test_patron_manager_no_db():
    from wm.living.patron import PatronManager
    pm = PatronManager(db_client=None)
    assert pm.get_favor(5406) == 0
    pm.set_favor(5406, 50)  # must not raise


def test_patron_manager_apply_completion():
    from wm.living.patron import PatronManager
    pm = PatronManager(db_client=None)
    decision = pm.apply_completion(5406, "Jecia", completed_wm_count=10)
    assert decision.eligible
    assert decision.plan.favor == 100  # 10 * 10


def test_nemesis_manager_no_db():
    from wm.living.nemesis import NemesisManager
    nm = NemesisManager(db_client=None)
    assert not nm.is_awakened(5406, 46)
    nm.record_awakening(5406, 46, "Murloc the Unforgotten", "nemesis:5406:46")
    nm.record_slain(5406, 46)


def test_nemesis_manager_evaluate_and_record():
    from wm.living.nemesis import NemesisManager, NemesisTrigger
    nm = NemesisManager(db_client=None)
    trigger = NemesisTrigger(player_guid=5406, subject_entry=46,
                              subject_name="Murloc", kill_count=12)
    decision = nm.evaluate_and_record(trigger)
    assert decision.eligible


def test_oath_watcher_no_db():
    from wm.living.oath_watcher import OathWatcher
    ow = OathWatcher(db_client=None)
    ow.swear(5406, "no_kill", "Do not kill", 5)  # must not raise
    ow.increment(5406, "no_kill")                 # must not raise
    assert ow.evaluate(5406, "no_kill") is None   # None when no db
    assert ow.load(5406, "no_kill") is None


def test_rumor_dispatcher_no_db():
    from wm.living.rumor import RumorTrigger
    from wm.living.rumor_propagation import RumorDispatcher
    rd = RumorDispatcher(db_client=None)
    trigger = RumorTrigger(player_guid=5406, player_name="Jecia",
                            subject_name="Wolves", deed_count=10)
    record = rd.maybe_dispatch_rumor(trigger, subject_entry=46)
    assert record is not None
    assert "Jecia" in record.line


def test_ecology_evaluator_no_db():
    from wm.living.ecology import EcologyEvaluator
    ev = EcologyEvaluator(db_client=None, dry_run=True)
    report = ev.evaluate_zone(zone_id=12, player_guid=5406)
    assert report.total_kills == 0
    assert report.pressure_level == 0
    assert report.dry_run is True


def test_ecology_pressure_and_actions():
    from wm.living.ecology import EcologyEvaluator, _pressure_level, _propose_actions
    assert _pressure_level(0) == 0
    assert _pressure_level(8) == 2
    assert _pressure_level(100) == 5
    actions = _propose_actions(zone_id=12, pressure=3, kill_counts={46: 25})
    kinds = [a.kind for a in actions]
    assert "spawn_reinforcements" in kinds


def test_scene_sequencer_dry_run():
    from wm.scenes.models import SceneOutcome
    from wm.scenes.sequencer import SceneContext, SceneSequencer, SceneStep
    seq = SceneSequencer(native_client=None, dry_run=True)
    ctx = SceneContext(scene_key="test_scene", player_guid=5406)
    steps = [
        SceneStep("creature_yell", {"text": "Hello", "arc_key": "x"}, "yell test"),
        SceneStep("world_announce_to_player", {"message": "hi"}, "announce test"),
    ]
    outcome = seq.execute(ctx, steps)
    assert outcome.scene_key == "test_scene"
    assert outcome.result == "skipped"
    assert outcome.steps_total == 2
    assert outcome.steps_executed == 0
    assert outcome.dry_run is True


def test_journal_trigger_v2_no_db():
    from wm.living.journal_trigger import (
        build_nemesis_trigger_from_journal_v2,
        build_rumor_trigger_from_journal_v2,
        load_subject_journal_counts_v2,
    )
    kills, skins, total = load_subject_journal_counts_v2(
        db_client=None, player_guid=5406, subject_entry=46
    )
    assert kills == 0 and skins == 0 and total == 0

    t = build_nemesis_trigger_from_journal_v2(
        db_client=None, player_guid=5406, subject_entry=46,
        subject_name="Murloc"
    )
    assert t.kill_count == 0

    rt = build_rumor_trigger_from_journal_v2(
        db_client=None, player_guid=5406, player_name="Jecia", subject_entry=46
    )
    assert rt.deed_count == 0
