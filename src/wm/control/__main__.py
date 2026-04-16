from __future__ import annotations

import argparse


COMMANDS = {
    "inspect": "python -m wm.control.inspect --event-id <id>",
    "new": "python -m wm.control.new --event-id <id> --recipe <id> --action <kind>",
    "validate": "python -m wm.control.validate --proposal <path>",
    "apply": "python -m wm.control.apply --proposal <path> --mode dry-run",
    "audit": "python -m wm.control.audit --idempotency-key <key>",
    "propose": "python -m wm.control.propose --event-id <id>",
    "export-schemas": "python -m wm.control.export_schemas",
    "manual-grant-quest": "python -m wm.control.manual_grant_quest --player-guid <guid> --quest-id <id>",
    "manual-announce": "python -m wm.control.manual_announce --player-guid <guid> --text <text> --manual-reason <reason>",
    "manual-noop": "python -m wm.control.manual_noop --player-guid <guid> --reason <reason> --manual-reason <reason>",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List WM control workbench commands.")
    parser.add_argument("--summary", action="store_true")
    parser.parse_args(argv)
    print("WM control commands:")
    for name, command in COMMANDS.items():
        print(f"{name}: {command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
