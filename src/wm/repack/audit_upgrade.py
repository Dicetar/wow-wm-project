from __future__ import annotations

from argparse import ArgumentParser
import json
from pathlib import Path
import subprocess


def _build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Audit drift between a live repack manifest and a reconstructed source tree.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", action="store_true")
    return parser


def _read_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _compare_config_dists(manifest: dict, source_root: Path) -> list[str]:
    findings: list[str] = []
    dist_root = source_root / "env" / "dist" / "etc"
    for overlay in manifest.get("config_overlays", []):
        dist_relative = overlay.get("dist_relative_path")
        if not dist_relative:
            continue
        source_dist = dist_root / dist_relative
        if source_dist.exists():
            continue
        findings.append(f"Missing upstream dist for {dist_relative}")
    return findings


def _git_head(repo_root: Path) -> str | None:
    if not (repo_root / ".git").exists():
        return None
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def main() -> int:
    args = _build_parser().parse_args()
    manifest = _read_manifest(Path(args.manifest))
    source_root = Path(args.source_root)

    findings = _compare_config_dists(manifest, source_root)
    lines = [
        "# Upgrade Drift Audit",
        "",
        f"- Core manifest commit: `{manifest['core']['commit']}`",
        f"- Local source HEAD: `{_git_head(source_root) or 'unknown'}`",
        "",
        "## Findings",
        "",
    ]
    if findings:
        lines.extend([f"- {finding}" for finding in findings])
    else:
        lines.append("- No config dist drift findings were detected from the available source tree.")
    lines.append("")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    if args.summary:
        print(f"output={output_path} findings={len(findings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
