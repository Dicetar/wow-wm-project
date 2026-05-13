from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
REQUIRED_OPENAI_FIELDS = {"display_name", "short_description", "default_prompt"}


@dataclass(frozen=True)
class SkillIssue:
    path: Path
    message: str


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str, list[SkillIssue]]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text, [SkillIssue(path, "SKILL.md must start with YAML frontmatter.")]
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text, [SkillIssue(path, "SKILL.md frontmatter is not closed.")]

    raw_frontmatter = text[4:end].strip()
    body = text[end + 4 :].lstrip()
    values: dict[str, str] = {}
    issues: list[SkillIssue] = []
    for line_number, line in enumerate(raw_frontmatter.splitlines(), start=2):
        if not line.strip():
            continue
        if line.startswith((" ", "\t")) or ":" not in line:
            issues.append(SkillIssue(path, f"Unsupported frontmatter line {line_number}: {line!r}."))
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = _strip_quotes(value)
    return values, body, issues


def parse_openai_yaml(path: Path) -> tuple[set[str], list[SkillIssue]]:
    if not path.exists():
        return set(), []
    fields: set[str] = set()
    issues: list[SkillIssue] = []
    in_interface = False
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "interface:":
            in_interface = True
            continue
        if not in_interface:
            issues.append(SkillIssue(path, f"Only interface metadata is allowed before line {line_number}."))
            continue
        if not line.startswith((" ", "\t")) or ":" not in stripped:
            issues.append(SkillIssue(path, f"Unsupported interface line {line_number}: {line!r}."))
            continue
        key, value = stripped.split(":", 1)
        if not _strip_quotes(value):
            issues.append(SkillIssue(path, f"interface.{key.strip()} must not be empty."))
        fields.add(key.strip())
    return fields, issues


def validate_skill_dir(skill_dir: Path) -> list[SkillIssue]:
    skill_path = skill_dir / "SKILL.md"
    if not skill_path.exists():
        return [SkillIssue(skill_dir, "Missing SKILL.md.")]

    frontmatter, body, issues = parse_frontmatter(skill_path)
    if set(frontmatter) != {"name", "description"}:
        got = ", ".join(sorted(frontmatter)) or "none"
        issues.append(SkillIssue(skill_path, f"Frontmatter keys must be exactly name and description; got {got}."))

    name = frontmatter.get("name", "")
    if name != skill_dir.name:
        issues.append(SkillIssue(skill_path, f"Skill name `{name}` must match folder `{skill_dir.name}`."))
    if not SKILL_NAME_RE.fullmatch(name):
        issues.append(SkillIssue(skill_path, "Skill name must be lowercase letters, digits, and hyphens only."))
    if len(frontmatter.get("description", "").strip()) < 40:
        issues.append(SkillIssue(skill_path, "Description should clearly explain when to use the skill."))
    if not body.strip().startswith("# "):
        issues.append(SkillIssue(skill_path, "Body must start with a Markdown H1 after frontmatter."))

    openai_fields, openai_issues = parse_openai_yaml(skill_dir / "agents" / "openai.yaml")
    issues.extend(openai_issues)
    if openai_fields and openai_fields != REQUIRED_OPENAI_FIELDS:
        got = ", ".join(sorted(openai_fields))
        issues.append(SkillIssue(skill_dir / "agents" / "openai.yaml", f"interface fields must be {sorted(REQUIRED_OPENAI_FIELDS)}; got {got}."))
    return issues


def validate_all(skills_root: Path) -> list[SkillIssue]:
    if not skills_root.exists():
        return [SkillIssue(skills_root, "Skills root does not exist.")]
    issues: list[SkillIssue] = []
    for skill_dir in sorted(path for path in skills_root.iterdir() if path.is_dir()):
        issues.extend(validate_skill_dir(skill_dir))
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate WM repo-local agent skills.")
    parser.add_argument("--skills-root", default=".agents/skills", help="Directory containing skill folders.")
    args = parser.parse_args(argv)

    issues = validate_all(Path(args.skills_root))
    if issues:
        for issue in issues:
            print(f"{issue.path}: {issue.message}", file=sys.stderr)
        return 1
    print(f"OK: validated skills under {args.skills_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
