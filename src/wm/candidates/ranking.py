from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable


@dataclass(slots=True)
class CandidateContext:
    target_level_hint: int | None
    positive_terms: list[str]
    negative_terms: list[str]


def build_candidate_context(*, target_profile: dict[str, Any], character_profile: dict[str, Any] | None) -> CandidateContext:
    positive_terms: list[str] = []
    negative_terms: list[str] = []

    for value in [
        target_profile.get("name"),
        target_profile.get("faction_label"),
        target_profile.get("mechanical_type"),
        target_profile.get("family"),
    ]:
        positive_terms.extend(_extract_terms(value))

    if character_profile:
        for value in character_profile.get("preferred_themes", []):
            positive_terms.extend(_extract_terms(value))
        for value in character_profile.get("avoided_themes", []):
            negative_terms.extend(_extract_terms(value))

    target_level_hint = None
    level_min = target_profile.get("level_min")
    level_max = target_profile.get("level_max")
    if isinstance(level_min, int) and isinstance(level_max, int):
        target_level_hint = (level_min + level_max) // 2

    return CandidateContext(
        target_level_hint=target_level_hint,
        positive_terms=_dedupe_preserve_order(positive_terms),
        negative_terms=_dedupe_preserve_order(negative_terms),
    )


def score_quest_candidate(row: dict[str, Any], label: str, context: CandidateContext | None) -> int:
    score = 0
    corpus = _row_corpus(row, label, ["LogDescription", "QuestDescription", "ObjectiveText1", "ObjectiveText2"])
    if context:
        score += _score_term_matches(corpus, context.positive_terms, 7, 28)
        score -= _score_term_matches(corpus, context.negative_terms, 10, 20)
        score += _score_level_proximity(_as_int(row.get("QuestLevel")), context.target_level_hint, close=18, medium=10, far_penalty=20)
        score += _score_level_proximity(_as_int(row.get("MinLevel")), context.target_level_hint, close=8, medium=4, far_penalty=10)

    if _as_int(row.get("RewardTalents")) > 0:
        score -= 40
    if _as_int(row.get("RequiredPlayerKills")) > 0:
        score -= 10
    if _as_int(row.get("RewardSpell")) > 0 or _as_int(row.get("RewardDisplaySpell")) > 0:
        score += 6
    if _as_int(row.get("RewardNextQuest")) > 0:
        score += 4
    return score


def score_item_candidate(row: dict[str, Any], label: str, context: CandidateContext | None) -> int:
    score = 0
    corpus = _row_corpus(row, label, ["description", "Description"])
    if context:
        score += _score_term_matches(corpus, context.positive_terms, 6, 24)
        score -= _score_term_matches(corpus, context.negative_terms, 10, 20)
        score += _score_level_proximity(_as_int(row.get("RequiredLevel")), context.target_level_hint, close=8, medium=4, far_penalty=10)

    quality = _as_int(row.get("Quality"))
    if quality >= 2 and quality <= 4:
        score += 10
    elif quality == 1:
        score += 4
    elif quality == 0:
        score -= 4
    elif quality >= 5:
        score -= 20

    if _as_int(row.get("spellid_1")) > 0:
        score += 12
    if _as_int(row.get("InventoryType")) > 0:
        score += 4
    if _as_int(row.get("class")) == 15:
        score -= 8
    return score


def score_spell_candidate(row: dict[str, Any], label: str, context: CandidateContext | None) -> int:
    score = 0
    corpus = _row_corpus(row, label, ["Description_Lang_enUS", "Description"])
    lower_label = label.lower()

    if context:
        score += _score_term_matches(corpus, context.positive_terms, 10, 40)
        score -= _score_term_matches(corpus, context.negative_terms, 12, 24)

    noise_terms = ["passive", "on gossip", "proc", "stance", "trigger", "script"]
    for term in noise_terms:
        if term in lower_label:
            score -= 25

    if _as_int(row.get("ManaCost")) > 0:
        score += 5
    if _as_int(row.get("Effect_1")) > 0 or _as_int(row.get("Effect1")) > 0:
        score += 4
    if _as_int(row.get("DurationIndex")) == 0:
        score += 1
    return score


def annotate_summary_with_score(summary: str | None, score: int) -> str:
    if summary:
        return f"score={score}; {summary}"
    return f"score={score}"


def _row_corpus(row: dict[str, Any], label: str, extra_keys: list[str]) -> str:
    pieces = [label]
    for key in extra_keys:
        value = row.get(key)
        if value not in (None, ""):
            pieces.append(str(value))
    return " ".join(pieces).lower()


def _score_term_matches(corpus: str, terms: Iterable[str], per_match: int, cap: int) -> int:
    matched = 0
    for term in terms:
        if term and term in corpus:
            matched += 1
    return min(matched * per_match, cap)


def _score_level_proximity(value: int | None, target: int | None, *, close: int, medium: int, far_penalty: int) -> int:
    if value is None or target is None:
        return 0
    diff = abs(value - target)
    if diff <= 3:
        return close
    if diff <= 8:
        return medium
    if diff >= 30:
        return -far_penalty
    return 0


def _extract_terms(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    text = str(value).lower()
    terms = re.findall(r"[a-z]{4,}", text)
    return [term for term in terms if term not in {"with", "from", "that", "this", "have"}]


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
