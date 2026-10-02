from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import hashlib
import json
from pathlib import Path
import time
from typing import Any

from wm.config import Settings
from wm.control._cli import write_json
from wm.world.tools import execute_action


def _resolve_references(value: Any, results: list[dict[str, Any]]) -> Any:
    if isinstance(value, dict):
        if set(value) == {"from_step", "field"}:
            index = value["from_step"]
            if type(index) is not int or index < 0 or index >= len(results):
                raise ValueError("from_step must refer to an earlier completed step")
            fields = results[index].get("result", {}).get("world_result", {})
            if value["field"] not in fields:
                raise ValueError(f"Step {index} has no native result field {value['field']}")
            return fields[value["field"]]
        return {key: _resolve_references(item, results) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_references(item, results) for item in value]
    return value


def _has_references(value: Any) -> bool:
    if isinstance(value, dict):
        return set(value) == {"from_step", "field"} or any(_has_references(item) for item in value.values())
    return isinstance(value, list) and any(_has_references(item) for item in value)


def run_bundle(*, path: Path, player_guid: int, run_key: str, mode: str,
               confirm_live_apply: bool = False) -> dict[str, Any]:
    spec = json.loads(path.read_text(encoding="utf-8-sig"))
    if spec.get("schema_version") != "wm.world.bundle.v1" or not spec.get("id"):
        raise ValueError("Expected wm.world.bundle.v1 with an id")
    steps = spec.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("Bundle needs ordered steps")
    if mode == "apply" and not confirm_live_apply:
        raise ValueError("Apply requires --confirm-live-apply")
    results = []
    settings = Settings.from_env()
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"Step {index} must be an object")
        kind = step.get("kind")
        if kind not in {"native", "publish_quest", "publish_item", "publish_spell", "publish_shell", "wait"}:
            raise ValueError(f"Unsupported bundle step {index}: {kind}")
    for index, step in enumerate(steps):
        kind = step["kind"]
        try:
            if kind == "native":
                payload = step.get("payload", {})
                if mode == "dry-run" and _has_references(payload):
                    result, ok = {"status": "deferred", "note": "This step needs an earlier native receipt; it will be resolved during apply."}, True
                else:
                    payload = _resolve_references(payload, results)
                    result = execute_action(action_kind=step["action_kind"], payload=payload,
                                            player_guid=player_guid, run_key=f"bundle:{spec['id']}:{run_key}:{index}",
                                            mode=mode, settings=settings, confirm_live_apply=confirm_live_apply)
                    ok = result.get("status") in {"dry-run", "applied"}
            elif kind == "wait":
                seconds = float(step["seconds"])
                if not 0 <= seconds <= 600:
                    raise ValueError("wait seconds must be between 0 and 600")
                if mode == "apply":
                    time.sleep(seconds)
                result, ok = {"seconds": seconds, "executed": mode == "apply"}, True
            else:
                if isinstance(step.get("draft"), dict):
                    # Preserve inline authoring artifacts beside the bundle/job, not in system temp.
                    key = hashlib.sha256(f"{spec['id']}:{run_key}:{index}".encode()).hexdigest()[:20]
                    draft = path.parent / "bundle-drafts" / f"{key}.json"
                    draft.parent.mkdir(parents=True, exist_ok=True)
                    draft.write_text(json.dumps(step["draft"], indent=2) + "\n", encoding="utf-8")
                else:
                    draft = (path.parent / step["draft_json"]).resolve()
                if kind == "publish_quest":
                    from wm.quests.live_publish import main as publish
                    arguments = ["--draft-json", str(draft), "--mode", mode]
                else:
                    from wm.content.workbench import main as publish
                    arguments = [kind.replace("_", "-"), "--draft-json", str(draft), "--mode", mode]
                output = io.StringIO()
                with redirect_stdout(output):
                    code = publish(arguments)
                result, ok = {"exit_code": code, "output": output.getvalue()}, code == 0
            results.append({"index": index, "kind": kind, "ok": ok, "result": result})
            if not ok:
                break
        except Exception as exc:
            results.append({"index": index, "kind": kind, "ok": False, "error": str(exc)})
            break
    complete = len(results) == len(steps) and all(item["ok"] for item in results)
    return {"bundle_id": spec["id"], "run_key": run_key, "mode": mode,
            "status": "complete" if complete else "partial" if any(item["ok"] for item in results) else "failed",
            "steps": results, "note": "Ordered execution, not a transaction. Earlier applied steps remain if a later step fails."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish content and trigger an ordered world event bundle.")
    parser.add_argument("--bundle-json", type=Path, required=True)
    parser.add_argument("--player-guid", type=int, required=True)
    parser.add_argument("--run-key", required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--confirm-live-apply", action="store_true")
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args(argv)
    result = run_bundle(path=args.bundle_json, player_guid=args.player_guid, run_key=args.run_key,
                        mode=args.mode, confirm_live_apply=args.confirm_live_apply)
    write_json(result, args.output_json)
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
