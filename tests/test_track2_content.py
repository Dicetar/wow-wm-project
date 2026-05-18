"""Tests for Track II content models: artifact, rumor, letter, mentor_task."""
from __future__ import annotations


def test_artifact_to_dict():
    from wm.content.artifact import ManagedArtifact
    a = ManagedArtifact(artifact_id=90001, kind="quest", status="active",
                        label="Test Quest", owner_key="wm.arc.test")
    d = a.to_dict()
    assert d["artifact_id"] == 90001
    assert d["kind"] == "quest"
    assert d["status"] == "active"


def test_artifact_registry_no_db():
    from wm.content.artifact import ArtifactRegistry, ManagedArtifact
    reg = ArtifactRegistry(db_client=None)
    a = ManagedArtifact(artifact_id=1, kind="item", status="reserved",
                        label="x", owner_key="k")
    reg.register(a)  # must not raise
    assert reg.load(1, "item") is None
    assert reg.list_active() == []


def test_rumor_bundle_best_line():
    from wm.content.rumor import RumorBundle, RumorLine
    bundle = RumorBundle(
        bundle_key="wolves",
        lines=[
            RumorLine("w1", "{player} killed some wolves.", min_deed_count=1),
            RumorLine("w2", "{player} is the bane of wolves.", min_deed_count=10),
        ],
    )
    assert bundle.best_line(5).line_key == "w1"
    assert bundle.best_line(12).line_key == "w2"
    assert bundle.best_line(0) is None


def test_rumor_line_render():
    from wm.content.rumor import RumorLine
    line = RumorLine("k", "{player} slew {subject}.")
    assert line.render(player="Jecia", subject="Murloc") == "Jecia slew Murloc."


def test_letter_render_body():
    from wm.content.letter import LetterDelivery, WMLetter
    letter = WMLetter(letter_key="lk", subject_line="Greetings",
                      body_template="Hello {player}, you have done {deed_count} deeds.")
    delivery = LetterDelivery(player_guid=5406, letter=letter,
                               context_vars={"player": "Jecia", "deed_count": 7})
    assert "Jecia" in delivery.rendered_body()
    assert "7" in delivery.rendered_body()


def test_mentor_task_step_by_key():
    from wm.content.mentor_task import MentorStep, MentorTask
    task = MentorTask(
        task_key="t1",
        mentor_npc_entry=3100,
        steps=[
            MentorStep("s1", "Kill 5 murlocs", "kill", target_entry=46, count=5),
            MentorStep("s2", "Talk to Jecia", "talk"),
        ],
    )
    assert task.total_steps() == 2
    assert task.step_by_key("s1").objective_text == "Kill 5 murlocs"
    assert task.step_by_key("nope") is None
