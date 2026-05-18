"""Tests for Track III LLM layer: recipe_prompt, proposal_parser, provenance, narratives, confidence, critique."""
from __future__ import annotations


def test_recipe_prompt_builder():
    from wm.llm.recipe_prompt import RecipePromptBuilder
    builder = RecipePromptBuilder()
    prompt = builder.build(instruction="Make a wolf hunting recipe", recipe_key="wolves")
    msgs = prompt.to_messages()
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert "wm.recipe.v1" in msgs[1]["content"]
    assert "wolves" in msgs[1]["content"]


def test_recipe_schema_structure():
    from wm.llm.recipe_prompt import RECIPE_SCHEMA
    assert RECIPE_SCHEMA["schema_version"] == "wm.recipe.v1"
    assert "steps" in RECIPE_SCHEMA["required"]


def test_proposal_parser_clean():
    from wm.llm.proposal_parser import ProposalParser
    parser = ProposalParser()
    raw = '{"schema_version": "wm.quest.v1", "title": "Hunt the Wolves"}'
    result = parser.parse(raw)
    assert result.ok
    assert result.schema_version == "wm.quest.v1"
    assert result.parsed is not None


def test_proposal_parser_rejects_sql():
    from wm.llm.proposal_parser import ProposalParser
    parser = ProposalParser()
    raw = '{"schema_version": "wm.test.v1", "sql": "DELETE FROM quest_template WHERE ID=1"}'
    result = parser.parse(raw)
    assert not result.ok
    assert any("DELETE FROM" in i for i in result.issues)


def test_proposal_parser_rejects_bad_schema_prefix():
    from wm.llm.proposal_parser import ProposalParser
    parser = ProposalParser()
    raw = '{"schema_version": "evil.payload.v1", "data": 1}'
    result = parser.parse(raw)
    assert not result.ok


def test_provenance_logger_no_db():
    from wm.llm.provenance import ProvenanceLogger
    logger = ProvenanceLogger(db_client=None)
    result = logger.log(
        schema_version="wm.quest.v1",
        instruction="Generate a quest",
        raw_response='{"schema_version": "wm.quest.v1"}',
    )
    assert result is None
    logger.adopt(1)   # must not raise
    logger.reject(1)  # must not raise
    assert logger.load(1) is None
    assert logger.list_pending() == []


def test_narrative_generator_build_messages():
    from wm.llm.narratives import NarrativeGenerator
    gen = NarrativeGenerator()
    msgs = gen.build_messages(quest_id=90001, instruction="Write a wolf hunting quest narrative")
    assert any(m["role"] == "system" for m in msgs)
    assert "90001" in msgs[-1]["content"]


def test_narrative_generator_parse():
    from wm.llm.narratives import NarrativeGenerator
    gen = NarrativeGenerator()
    raw = '{"schema_version": "wm.quest_narrative.v1", "quest_id": 1, "log_title": "T", "log_description": "D", "objective_text": "O", "offer_reward_text": "R", "request_items_text": "I", "quest_completion_log": "C"}'
    nt = gen.parse_response(raw)
    assert nt.log_title == "T"
    assert nt.schema_version == "wm.quest_narrative.v1"


def test_confidence_score_clean():
    from wm.llm.confidence import score_proposal_confidence
    parsed = {"schema_version": "wm.quest.v1", "title": "Hunt the Wolves", "description": "A fine quest."}
    score = score_proposal_confidence(parsed, [])
    assert score.value == 1.0
    assert score.label == "high"


def test_confidence_score_with_issues():
    from wm.llm.confidence import score_proposal_confidence
    parsed = {"schema_version": "wm.quest.v1", "title": "x", "description": ""}
    score = score_proposal_confidence(parsed, ["missing objective"])
    assert score.value < 1.0


def test_confidence_no_parsed():
    from wm.llm.confidence import score_proposal_confidence
    score = score_proposal_confidence(None, ["parse error"])
    assert score.value == 0.0
    assert score.label == "low"


def test_critique_quest_clean():
    from wm.llm.critique import critique_quest_proposal
    parsed = {
        "schema_version": "wm.quest_draft.v1",
        "title": "Hunt the Wolves",
        "quest_level": 20,
        "min_level": 15,
    }
    result = critique_quest_proposal(parsed)
    assert result.ok
    assert result.errors == []


def test_critique_quest_level_error():
    from wm.llm.critique import critique_quest_proposal
    parsed = {
        "schema_version": "wm.quest_draft.v1",
        "title": "Quest",
        "quest_level": 10,
        "min_level": 20,
    }
    result = critique_quest_proposal(parsed)
    assert not result.ok
    assert any("min_level" in e.path for e in result.errors)


def test_critique_empty_title_error():
    from wm.llm.critique import critique_quest_proposal
    result = critique_quest_proposal({"schema_version": "wm.quest_draft.v1", "title": ""})
    assert not result.ok


def test_critique_forbidden_key():
    from wm.llm.critique import critique_quest_proposal
    result = critique_quest_proposal({"schema_version": "wm.quest_draft.v1",
                                       "title": "T", "sql": "DROP TABLE quest_template"})
    assert not result.ok
