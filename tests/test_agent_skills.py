from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_agent_skills.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_agent_skills", VALIDATOR_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AgentSkillsTests(unittest.TestCase):
    def test_repo_agent_skills_validate(self) -> None:
        validator = load_validator()

        issues = validator.validate_all(ROOT / ".agents" / "skills")

        self.assertEqual([], issues)

    def test_validator_cli_succeeds(self) -> None:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR_PATH), "--skills-root", str(ROOT / ".agents" / "skills")],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("OK: validated skills", result.stdout)


if __name__ == "__main__":
    unittest.main()
