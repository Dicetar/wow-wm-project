from __future__ import annotations

import json

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.targets.runtime_resolver import RuntimeTargetResolver


def main() -> None:
    settings = Settings.from_env()
    client = MysqlCliClient()
    resolver = RuntimeTargetResolver(client=client, settings=settings)

    entries = [46, 54, 66, 68, 69, 1498]
    payload: dict[str, object] = {}
    for entry in entries:
        profile = resolver.resolve_creature_entry(entry)
        payload[str(entry)] = profile.to_dict() if profile else None
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
