from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "fe-ui-review" / "scripts" / "compare_images.py"


class CompareImagesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def save_image(
        self,
        name: str,
        *,
        size: tuple[int, int] = (4, 4),
        color: tuple[int, int, int, int] = (0, 0, 0, 255),
    ) -> Path:
        path = self.root / name
        Image.new("RGBA", size, color).save(path)
        return path

    def run_compare(
        self,
        reference: Path,
        actual: Path,
        *,
        output_name: str,
        masks: list[str] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        output_dir = self.root / output_name
        command = [
            sys.executable,
            str(SCRIPT),
            "--reference",
            str(reference),
            "--actual",
            str(actual),
            "--output-dir",
            str(output_dir),
            "--channel-threshold",
            "0",
            "--max-diff-ratio",
            "0",
        ]
        for mask in masks or []:
            command.extend(["--mask", mask])
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        result = json.loads((output_dir / "result.json").read_text(encoding="utf-8"))
        return completed, result

    def test_identical_images_pass_and_emit_artifacts(self) -> None:
        reference = self.save_image("reference.png", color=(10, 20, 30, 255))
        actual = self.save_image("actual.png", color=(10, 20, 30, 255))

        completed, result = self.run_compare(
            reference,
            actual,
            output_name="identical",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["metrics"]["effective"]["diffRatio"], 0)
        self.assertIn("comparisonBoard", result["artifacts"])
        self.assertIn("comparisonBoardManifest", result["artifacts"])
        board_path = Path(result["artifacts"]["comparisonBoard"]["path"])
        manifest_path = Path(result["artifacts"]["comparisonBoardManifest"]["path"])
        self.assertTrue(board_path.is_file())
        self.assertTrue(manifest_path.is_file())
        with Image.open(board_path) as board:
            self.assertEqual(board.size, (1280, 976))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertTrue(manifest["displayOnly"])
        self.assertEqual(
            [panel["label"] for panel in manifest["panels"]],
            [
                "Reference / Figma",
                "Actual / Target",
                "Overlay",
                "Diff",
            ],
        )
        for artifact in result["artifacts"].values():
            self.assertTrue(Path(artifact["path"]).is_file())
            self.assertEqual(len(artifact["sha256"]), 64)

    def test_changed_pixel_fails_strict_contract(self) -> None:
        reference = self.save_image("reference.png")
        actual = self.save_image("actual.png")
        with Image.open(actual) as image:
            changed = image.copy()
        changed.putpixel((0, 0), (255, 255, 255, 255))
        changed.save(actual)

        completed, result = self.run_compare(
            reference,
            actual,
            output_name="changed",
        )

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(result["metrics"]["raw"]["changedPixels"], 1)
        self.assertEqual(result["metrics"]["effective"]["diffRatio"], 1 / 16)

    def test_mask_reports_raw_difference_but_excludes_effective_pixel(self) -> None:
        reference = self.save_image("reference.png")
        actual = self.save_image("actual.png")
        with Image.open(actual) as image:
            changed = image.copy()
        changed.putpixel((0, 0), (255, 255, 255, 255))
        changed.save(actual)

        completed, result = self.run_compare(
            reference,
            actual,
            output_name="masked",
            masks=["0,0,1,1"],
        )

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["metrics"]["raw"]["changedPixels"], 1)
        self.assertEqual(result["metrics"]["effective"]["changedPixels"], 0)
        self.assertEqual(result["metrics"]["maskedPixels"], 1)

    def test_dimension_mismatch_is_inconclusive_without_resizing(self) -> None:
        reference = self.save_image("reference.png", size=(4, 4))
        actual = self.save_image("actual.png", size=(5, 4))

        completed, result = self.run_compare(
            reference,
            actual,
            output_name="dimension-mismatch",
        )

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(result["verdict"], "INCONCLUSIVE")
        self.assertEqual(
            result["comparability"]["issues"][0]["code"],
            "DIMENSION_MISMATCH",
        )
        self.assertEqual(result["artifacts"], {})


if __name__ == "__main__":
    unittest.main()
