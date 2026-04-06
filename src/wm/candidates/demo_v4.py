from __future__ import annotations

import json
from pathlib import Path

from wm.candidates.providers_v4 import build_item_candidates_v4, build_quest_candidates_v4, build_spell_candidates_v4
from wm.candidates.ranking import build_candidate_context
from wm.character.reader import load_character_state
from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
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

    character_state = load_character_state(client=client, settings=settings, character_guid=character_guid)
    context = build_candidate_context(
        target_profile=target_profile.to_dict(),
        character_profile=(character_state.profile.__dict__ if character_state.profile else None),
    )

    quests = build_quest_candidates_v4(export_base / "quest_template.json", context=context, limit=5)
    items = build_item_candidates_v4(export_base / "item_template.json", context=context, limit=5)
    spells = build_spell_candidates_v4(export_base / "spell_dbc.json", context=context, limit=5)

    print(json.dumps(
        {
            "context": {
                "target_level_hint": context.target_level_hint,
                "positive_terms": context.positive_terms,
                "negative_terms": context.negative_terms,
            },
            "quests": {
                "kind": quests.kind,
                "source_path": quests.source_path,
                "options": [
                    {"entry_id": x.entry_id, "label": x.label, "summary": x.summary}
                    for x in quests.options
                ],
            },
            "items": {
                "kind": items.kind,
                "source_path": items.source_path,
                "options": [
                    {"entry_id": x.entry_id, "label": x.label, "summary": x.summary}
                    for x in items.options
                ],
            },
            "spells": {
                "kind": spells.kind,
                "source_path": spells.source_path,
                "options": [
                    {"entry_id": x.entry_id, "label": x.label, "summary": x.summary}
                    for x in spells.options
                ],
            },
        },
        indent=2,
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
