from __future__ import annotations

import json
from pathlib import Path

from wm.candidates.providers_v2 import build_item_candidates_v2, build_quest_candidates_v2, build_spell_candidates_v2


def main() -> None:
    base = Path(r"D:\WOW\db_export\acore_world")

    quests = build_quest_candidates_v2(base / "quest_template.json", limit=5)
    items = build_item_candidates_v2(base / "item_template.json", limit=5)
    spells = build_spell_candidates_v2(base / "spell_dbc.json", limit=5)

    print(json.dumps(
        {
            "quests": {
                "kind": quests.kind,
                "source_path": quests.source_path,
                "options": [
                    {
                        "entry_id": x.entry_id,
                        "label": x.label,
                        "summary": x.summary,
                    }
                    for x in quests.options
                ],
            },
            "items": {
                "kind": items.kind,
                "source_path": items.source_path,
                "options": [
                    {
                        "entry_id": x.entry_id,
                        "label": x.label,
                        "summary": x.summary,
                    }
                    for x in items.options
                ],
            },
            "spells": {
                "kind": spells.kind,
                "source_path": spells.source_path,
                "options": [
                    {
                        "entry_id": x.entry_id,
                        "label": x.label,
                        "summary": x.summary,
                    }
                    for x in spells.options
                ],
            },
        },
        indent=2,
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
