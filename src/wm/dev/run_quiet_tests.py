from __future__ import annotations

import argparse
import io
import json
import sys
import time
import unittest
from pathlib import Path
from typing import Any


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.dev.run_quiet_tests")
    parser.add_argument(
        "targets",
        nargs="*",
        help="Optional dotted unittest targets such as tests.test_item_pipeline",
    )
    parser.add_argument("--output-json", type=Path)
    return parser


def _run_suite(targets: list[str]) -> tuple[unittest.result.TestResult, float]:
    loader = unittest.defaultTestLoader
    if targets:
        suite = loader.loadTestsFromNames(targets)
    else:
        suite = loader.discover("tests", pattern="test_*.py")
    stream = io.StringIO()
    started = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
    elapsed = time.perf_counter() - started
    return result, elapsed


def _summarize(result: unittest.result.TestResult, elapsed_seconds: float) -> dict[str, Any]:
    skipped = len(getattr(result, "skipped", []))
    expected_failures = len(getattr(result, "expectedFailures", []))
    unexpected_successes = len(getattr(result, "unexpectedSuccesses", []))
    payload = {
        "ok": bool(result.wasSuccessful()),
        "tests_run": int(result.testsRun),
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": skipped,
        "expected_failures": expected_failures,
        "unexpected_successes": unexpected_successes,
        "duration_seconds": round(elapsed_seconds, 3),
    }
    return payload


def _render_summary(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"ok: {str(bool(payload['ok'])).lower()}",
            f"tests_run: {payload['tests_run']}",
            f"failures: {payload['failures']}",
            f"errors: {payload['errors']}",
            f"skipped: {payload['skipped']}",
            f"duration_seconds: {payload['duration_seconds']}",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result, elapsed = _run_suite(args.targets)
    payload = _summarize(result, elapsed)
    raw = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(raw, encoding="utf-8")
    print(_render_summary(payload))
    if args.output_json is not None:
        print("")
        print(f"output_json: {args.output_json}")
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
