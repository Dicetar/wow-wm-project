from __future__ import annotations

import json
from pathlib import Path
from dataclasses import asdict

from wm.candidates.providers_v4 import build_item_candidates_v4, build_quest_candidates_v4, build_spell_candidates_v4
from wm.candidates.ranking import build_candidate_context
from wm.character.reader import load_character_state
from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.journal.reader import load_subject_journal_for_creature
from wm.prompt.candidate_package import augment_prompt_package_with_candidates
from wm.prompt.package import build_prompt_package
from wm.subjects.resolver import build_subject_card_from_profile
from wm.targets.resolver import LookupStore, TargetResolver


def main() -> None:
    settings = Settings.from_env()
    client = MysqlCliClient()

    character_guid = 42
    target_entry = 46
    lookup_path = Path(r"D:\WOW\wm-project\data\lookup\creature_template_full.json")
    export_base = Path(r"D:\WOW\db_export\acore_world")

    store = LookupStore.from_json(lookup_path)
    resolver = TargetResolver(store=store)
    target_profile = resolver.resolve_creature_entry(target_entry)
    if target_profile is None:
        raise SystemExit(f"Target entry {target_entry} not found in lookup file: {lookup_path}")

    character_state = load_character_state(
        client=client,
        settings=settings,
        character_guid=character_guid,
    )
    subject_journal = load_subject_journal_for_creature(
        client=client,
        settings=settings,
        player_guid=character_guid,
        creature_entry=target_entry,
        resolved_subject_card=build_subject_card_from_profile(target_profile),
    )
    package = build_prompt_package(
        character_guid=character_guid,
        target_entry=target_entry,
        target_profile=target_profile,
        character_state=character_state,
        subject_journal=subject_journal,
    )
    context = build_candidate_context(
        target_profile=target_profile.to_dict(),
        character_profile=(asdict(character_state.profile) if character_state.profile else None),
    )

    quests = build_quest_candidates_v4(export_base / "quest_template.json", context=context, limit=5)
    items = build_item_candidates_v4(export_base / "item_template.json", context=context, limit=5)
    spells = build_spell_candidates_v4(export_base / "spell_dbc.json", context=context, limit=5)

    enriched = augment_prompt_package_with_candidates(
        package=package,
        quest_candidates=quests,
        item_candidates=items,
        spell_candidates=spells,
    )
    enriched["candidate_context"] = {
        "target_level_hint": context.target_level_hint,
        "positive_terms": context.positive_terms,
        "negative_terms": context.negative_terms,
    }
    print(json.dumps(enriched, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
