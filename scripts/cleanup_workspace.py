from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


PROTECTED_ROOT_NAMES = {
    ".git",
    ".wm-bootstrap",
    "control",
    "docs",
    "native_modules",
    "src",
}

DEFAULT_FIXED_TARGETS = [
    ".pytest_cache",
    ".pytest-tmp",
    ".wm-pytest-tmp",
    ".wm-test-tmp",
    ".wm-tmp",
    ".tmp",
    "src/wow_wm_project.egg-info",
]

DEFAULT_GLOBS = [
    "pytest-cache-files-*",
    "tmp*",
]

PY_CACHE_SCAN_ROOTS = [
    "scripts",
    "src",
    "tests",
    "tools",
    "wm",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely remove ignored WM workspace scratch/cache paths.")
    parser.add_argument("--root", default=".", help="Workspace root. Defaults to current directory.")
    parser.add_argument("--apply", action="store_true", help="Delete targets. Without this, only prints a dry-run.")
    parser.add_argument(
        "--include-artifact-tmp",
        action="store_true",
        help="Also include temporary children under artifacts/ such as artifacts/tmp*. Proof artifacts are still skipped.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    targets = collect_targets(root, include_artifact_tmp=bool(args.include_artifact_tmp))
    results = [clean_target(root, target, apply=bool(args.apply)) for target in targets]
    if args.json:
        print(json.dumps({"apply": bool(args.apply), "targets": results}, indent=2, sort_keys=True))
    else:
        print_results(results, apply=bool(args.apply))
    denied = [item for item in results if item["status"] == "DENIED"]
    return 2 if denied and args.apply else 0


def collect_targets(root: Path, *, include_artifact_tmp: bool = False) -> list[Path]:
    targets: list[Path] = []
    for relative in DEFAULT_FIXED_TARGETS:
        target = root / relative
        if target.exists():
            targets.append(target)
    for pattern in DEFAULT_GLOBS:
        targets.extend(path for path in root.glob(pattern) if path.exists())
    for scan_root_name in PY_CACHE_SCAN_ROOTS:
        scan_root = root / scan_root_name
        if scan_root.exists():
            targets.extend(scan_for_python_cache(scan_root))
    if include_artifact_tmp:
        artifact_root = root / "artifacts"
        if artifact_root.exists():
            targets.extend(path for path in artifact_root.glob("tmp*") if path.exists())
            codex_tmp = artifact_root / "codex_tmp"
            if codex_tmp.exists():
                targets.append(codex_tmp)
    return prune_nested_targets(sorted({target.resolve() for target in targets}))


def scan_for_python_cache(root: Path) -> list[Path]:
    targets: list[Path] = []
    try:
        targets.extend(path for path in root.rglob("__pycache__") if path.exists())
        targets.extend(path for path in root.rglob("*.pyc") if path.exists() and "__pycache__" not in path.parts)
    except OSError:
        targets.append(root)
    return targets


def prune_nested_targets(targets: list[Path]) -> list[Path]:
    pruned: list[Path] = []
    for target in targets:
        if any(is_relative_to(target, parent) for parent in pruned):
            continue
        pruned.append(target)
    return pruned


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return path != parent


def clean_target(root: Path, target: Path, *, apply: bool) -> dict[str, Any]:
    try:
        resolved = target.resolve()
        assert_safe_target(root, resolved)
        if not apply:
            return result(root, resolved, "DRY_RUN")
        if resolved.is_dir() and not resolved.is_symlink():
            shutil.rmtree(resolved)
        else:
            resolved.unlink()
        return result(root, resolved, "REMOVED")
    except PermissionError as exc:
        return result(root, target, "DENIED", str(exc))
    except OSError as exc:
        return result(root, target, "ERROR", str(exc))
    except ValueError as exc:
        return result(root, target, "SKIPPED", str(exc))


def assert_safe_target(root: Path, target: Path) -> None:
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise ValueError("target is outside workspace") from exc
    if not relative.parts:
        raise ValueError("refusing workspace root")
    top = relative.parts[0]
    if top in PROTECTED_ROOT_NAMES:
        if top == "src" and target.name in {"__pycache__", "wow_wm_project.egg-info"}:
            return
        raise ValueError(f"protected path: {top}")
    if top == "artifacts" and not (target.name.startswith("tmp") or target.name == "codex_tmp"):
        raise ValueError("proof artifacts are not cleanup targets")


def result(root: Path, target: Path, status: str, message: str | None = None) -> dict[str, Any]:
    try:
        relative = str(target.resolve().relative_to(root))
    except Exception:
        relative = str(target)
    item: dict[str, Any] = {"path": relative.replace("\\", "/"), "status": status}
    if message:
        item["message"] = message
    return item


def print_results(results: list[dict[str, Any]], *, apply: bool) -> None:
    action = "cleanup" if apply else "dry-run cleanup"
    print(f"WM {action}: {len(results)} target(s)")
    for item in results:
        line = f"{item['status']:>7}  {item['path']}"
        if item.get("message"):
            line = f"{line}  {item['message']}"
        print(line)


if __name__ == "__main__":
    raise SystemExit(main())
