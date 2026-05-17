from __future__ import annotations

import argparse
import json
import sys

from wm.status.feature_status import (
    load_feature_status,
    summarize_by_status,
    validate_feature_status,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="wm status", description="Render machine-checkable feature status.")
    p.add_argument("--layer", default=None, help="filter by layer")
    p.add_argument("--validate", action="store_true", help="only validate the file (exit 1 on issues)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    validation = validate_feature_status()
    if args.validate:
        if args.json:
            print(json.dumps({"ok": validation.ok, "issues": validation.issues}, indent=2))
        else:
            print("OK" if validation.ok else "INVALID")
            for issue in validation.issues:
                print(f"  - {issue}")
        return 0 if validation.ok else 1

    doc = load_feature_status()
    entries = [e for e in doc.entries if args.layer is None or e.layer == args.layer]
    if args.json:
        print(json.dumps({"schema_version": doc.schema_version, "entries": [e.to_dict() for e in entries]}, indent=2))
        return 0 if validation.ok else 1

    counts = summarize_by_status(doc)
    print(f"feature status ({doc.schema_version})  gameplay: " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if not validation.ok:
        print(f"  WARNING: file invalid ({len(validation.issues)} issues) - run `wm status --validate`")
    width = max((len(e.feature_key) for e in entries), default=10)
    for e in sorted(entries, key=lambda x: (x.layer, x.feature_key)):
        print(f"  [{e.repo_status:<7}/{e.gameplay_status:<7}] {e.feature_key:<{width}}  {e.scope}")
    return 0 if validation.ok else 1


if __name__ == "__main__":
    sys.exit(main())
