from wm.character.reader import CharacterStateBundle
from wm.character.overview import build_character_overview


def test_overview_summarizes_bundle_counts_and_status():
    bundle = CharacterStateBundle(
        profile=None,
        arc_states=[object(), object()],
        unlocks=[object()],
        rewards=[],
        conversation_steering=[object()],
        prompt_queue=[object(), object(), object()],
        status="WORKING",
        notes=["seeded"],
    )
    ov = build_character_overview(
        player_guid=5408, bundle=bundle,
        readiness={"ok": True}, proposal_counts={"pending": 2, "issues": 1},
    )
    assert ov["player_guid"] == 5408
    assert ov["status"] == "WORKING"
    assert ov["has_profile"] is False
    assert ov["counts"] == {
        "arc_states": 2, "unlocks": 1, "rewards": 0,
        "conversation_steering": 1, "prompt_queue": 3,
    }
    assert ov["readiness"] == {"ok": True}
    assert ov["proposals"] == {"pending": 2, "issues": 1}
    assert ov["notes"] == ["seeded"]


def test_overview_handles_missing_optionals():
    bundle = CharacterStateBundle(status="UNKNOWN")
    ov = build_character_overview(player_guid=1, bundle=bundle)
    assert ov["player_guid"] == 1
    assert ov["status"] == "UNKNOWN"
    assert ov["has_profile"] is False
    assert ov["counts"]["arc_states"] == 0
    assert ov["readiness"] is None
    assert ov["proposals"] is None
