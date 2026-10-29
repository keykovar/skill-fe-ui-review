from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "fe-ui-review"


class SkillStructureTest(unittest.TestCase):
    def test_required_files_and_metadata_are_present(self) -> None:
        required = [
            SKILL_DIR / "SKILL.md",
            SKILL_DIR / "agents" / "openai.yaml",
            SKILL_DIR / "references" / "case-contract.md",
            SKILL_DIR / "references" / "report-contract.md",
            SKILL_DIR / "references" / "platform-adapters.md",
            SKILL_DIR / "scripts" / "compare_images.py",
        ]
        for path in required:
            self.assertTrue(path.is_file(), str(path))

        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("TODO", skill)
        self.assertLess(len(skill.splitlines()), 500)

        match = re.match(r"^---\n(?P<header>.*?)\n---\n", skill, re.DOTALL)
        self.assertIsNotNone(match)
        keys = {
            line.split(":", 1)[0]
            for line in match.group("header").splitlines()
            if ":" in line
        }
        self.assertEqual(keys, {"name", "description"})
        self.assertIn("name: fe-ui-review", match.group("header"))

        agent = (SKILL_DIR / "agents" / "openai.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("$fe-ui-review", agent)
        self.assertNotIn("TODO", agent)
        self.assertIn("comparison board", skill.lower())
        self.assertIn("![ui comparison board]", skill.lower())

    def test_skill_links_each_reference(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        for name in (
            "case-contract.md",
            "report-contract.md",
            "platform-adapters.md",
        ):
            self.assertIn(f"(references/{name})", skill)


if __name__ == "__main__":
    unittest.main()
