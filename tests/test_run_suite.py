from __future__ import annotations

import copy
import base64
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "skills" / "fe-ui-review" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
from run_suite import ContractError, normalize_suite, read_json, run_suite
from render_report import write_reports


class Tags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))


class RunSuiteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.reference = self.root / "reference.png"
        self.actual = self.root / "actual.png"
        self.changed = self.root / "changed.png"
        Image.new("RGB", (8, 12), "white").save(self.reference)
        Image.new("RGB", (8, 12), "white").save(self.actual)
        image = Image.new("RGB", (8, 12), "white")
        image.putpixel((1, 2), (0, 0, 0))
        image.save(self.changed)
        self.source_bytes = self.reference.read_bytes()
        self.profiles = read_json(SCRIPT_DIR.parent / "assets" / "device-profiles.json")["profiles"]

    def tearDown(self) -> None:
        self.assertEqual(self.reference.read_bytes(), self.source_bytes)
        self.temp.cleanup()

    def case(self, case_id: str, actual: str = "actual.png", **extra: object) -> dict:
        return {"id": case_id, "reference": {"type": "image", "path": "reference.png"}, "target": {"type": "screenshot", "platform": "web", "path": actual}, **extra}

    def suite(self, *cases: dict) -> dict:
        return {"schemaVersion": 1, "suiteId": "sample", "defaults": {"thresholds": {"pixel": {"channelDelta": 0, "maxDiffRatio": 0}}}, "cases": list(cases)}

    def execute(self, document: dict) -> tuple[int, dict, Path]:
        manifest = self.root / "suite.json"
        manifest.write_text(json.dumps(document), encoding="utf-8")
        output = self.root / "output"
        code, result = run_suite(manifest, output)
        return code, result, output

    def test_optional_failure_is_retained_without_failing_required_suite(self) -> None:
        code, report, output = self.execute(self.suite(self.case("required"), self.case("optional", "changed.png", required=False)))
        self.assertEqual(code, 0)
        self.assertEqual(report["suiteVerdict"], "PASS")
        self.assertEqual(report["summary"], {"total": 2, "required": 1, "pass": 1, "fail": 1, "inconclusive": 0})
        self.assertEqual(len(report["cases"]), 2)
        self.assertTrue((output / "report.html").is_file())
        self.assertTrue((output / "summary.md").is_file())
        self.assertEqual(report["analysisStatus"], "PENDING_AGENT_REVIEW")

    def test_blocked_case_does_not_discard_other_results(self) -> None:
        code, report, _ = self.execute(self.suite(self.case("good"), self.case("missing", "absent.png"), self.case("different", "changed.png")))
        self.assertEqual(code, 1)
        self.assertEqual([case["verdict"] for case in report["cases"]], ["PASS", "INCONCLUSIVE", "FAIL"])

    def test_unknown_device_is_inconclusive_and_next_case_runs(self) -> None:
        code, report, _ = self.execute(self.suite(self.case("bad-profile", deviceProfile="not-a-device"), self.case("good")))
        self.assertEqual(code, 2)
        self.assertEqual(report["cases"][1]["verdict"], "PASS")
        self.assertEqual(report["cases"][0]["reference"]["path"], str(self.reference.resolve()))

    def test_profiles_merge_without_implicit_matrix_or_mutating_input(self) -> None:
        document = self.suite(self.case("phone", deviceProfile="web-phone-390", environment={"viewport": {"width": 412}, "dpr": 2}))
        original = copy.deepcopy(document)
        document["defaults"]["environment"] = {"locale": "en-US", "theme": "light"}
        cases = normalize_suite(document, self.root, self.profiles)
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["environment"]["viewport"], {"width": 412, "height": 844})
        self.assertEqual(cases[0]["environment"]["dpr"], 2)
        self.assertEqual(cases[0]["environment"]["locale"], "en-US")
        self.assertEqual(self.profiles["web-phone-390"]["environment"]["viewport"]["width"], 390)
        self.assertEqual(document["cases"], original["cases"])

    def test_missing_threshold_or_unsupported_assertion_cannot_pass(self) -> None:
        document = self.suite(self.case("no-threshold", thresholds={"pixel": {"channelDelta": None}}), self.case("geometry", thresholds={"geometry": {"maxOffset": 2}}))
        code, report, _ = self.execute(document)
        self.assertEqual(code, 2)
        self.assertTrue(all(case["verdict"] == "INCONCLUSIVE" for case in report["cases"]))

    def test_declared_capture_size_is_checked_without_resizing(self) -> None:
        code, report, _ = self.execute(self.suite(self.case("wrong-size", capture={"expectedPixelSize": {"width": 390, "height": 844}})))
        self.assertEqual(code, 2)
        self.assertEqual(report["cases"][0]["comparability"]["issues"][0]["code"], "EXPECTED_SIZE_MISMATCH")
        with Image.open(self.reference) as image:
            self.assertEqual(image.size, (8, 12))

    def test_native_preset_scale_checks_physical_pixels_without_emulating_devices(self) -> None:
        good = self.case("ios-image", deviceProfile="ios-phone-390", environment={"logicalSize": {"width": 8, "height": 12}, "scale": 1})
        good["target"]["platform"] = "ios"
        wrong_scale = copy.deepcopy(good)
        wrong_scale["id"] = "ios-wrong-scale"
        wrong_scale["environment"]["scale"] = 2
        code, report, _ = self.execute(self.suite(good, wrong_scale))
        self.assertEqual(code, 2)
        self.assertEqual([case["verdict"] for case in report["cases"]], ["PASS", "INCONCLUSIVE"])
        self.assertEqual(report["cases"][0]["capture"]["expectedPixelSize"], {"width": 8, "height": 12})
        self.assertEqual(report["cases"][1]["capture"]["expectedPixelSize"], {"width": 16, "height": 24})

    def test_mask_contract_is_audited_and_applied(self) -> None:
        mask = {"id": "fixture-dot", "reason": "Explicit synthetic fixture", "unit": "physical-px", "rectangle": {"x": 1, "y": 2, "width": 1, "height": 1}}
        code, report, _ = self.execute(self.suite(self.case("masked", "changed.png", masks=[mask])))
        self.assertEqual(code, 0)
        case = report["cases"][0]
        self.assertEqual(case["metrics"]["raw"]["changedPixels"], 1)
        self.assertEqual(case["metrics"]["effective"]["changedPixels"], 0)
        self.assertEqual(case["declaredMasks"][0]["reason"], mask["reason"])

    def test_duplicate_or_unsafe_ids_reject_manifest(self) -> None:
        for cases in ((self.case("same"), self.case("same")), (self.case("../outside"),)):
            with self.subTest(cases=cases), self.assertRaises(ContractError):
                normalize_suite(self.suite(*cases), self.root, self.profiles)

    def test_conflicting_platform_orientation_and_unknown_assertions_are_rejected(self) -> None:
        cases = [self.case("platform", deviceProfile="ios-phone-390"), self.case("orientation", deviceProfile="web-phone-390", environment={"orientation": "landscape"}), self.case("unsupported", thresholds={"perceptual": {"ssim": 0.99}})]
        code, report, _ = self.execute(self.suite(*cases))
        self.assertEqual(code, 2)
        self.assertEqual(report["summary"]["inconclusive"], 3)

    def test_suite_with_only_optional_cases_has_no_acceptance_verdict(self) -> None:
        code, report, _ = self.execute(self.suite(self.case("optional", required=False)))
        self.assertEqual(code, 2)
        self.assertEqual(report["cases"][0]["verdict"], "PASS")

    def test_malformed_case_metadata_cannot_break_report_for_valid_cases(self) -> None:
        malformed = self.case("bad-platform")
        malformed["target"]["platform"] = []
        code, report, output = self.execute(self.suite(malformed, self.case("bad-capture", capture={"valid": "false"}), self.case("good")))
        self.assertEqual(code, 2)
        self.assertEqual(report["cases"][0]["platform"], "unknown")
        self.assertEqual(len(report["cases"][0]["actual"]["sha256"]), 64)
        self.assertEqual(report["cases"][2]["verdict"], "PASS")
        self.assertTrue((output / "report.html").is_file())

    def test_existing_output_evidence_cannot_be_overwritten(self) -> None:
        _, _, output = self.execute(self.suite(self.case("good")))
        before = (output / "report.json").read_bytes()
        with self.assertRaises(ContractError):
            run_suite(self.root / "suite.json", output)
        self.assertEqual((output / "report.json").read_bytes(), before)

    def test_report_is_offline_and_does_not_execute_untrusted_text(self) -> None:
        _, report, output = self.execute(self.suite(self.case("good"), self.case("blocked", capture={"valid": False, "reason": "Wrong route"})))
        report["suiteId"] = '</title><script id="owned">alert(1)</script>'
        write_reports(report, output)
        content = (output / "report.html").read_text(encoding="utf-8")
        parser = Tags()
        parser.feed(content)
        self.assertEqual(len([tag for tag, _ in parser.tags if tag == "script"]), 1)
        self.assertFalse(any(attrs.get("id") == "owned" for _, attrs in parser.tags))
        images = [attrs["src"] for tag, attrs in parser.tags if tag == "img"]
        self.assertTrue(images)
        self.assertTrue(all(src.startswith("data:image/") for src in images))
        self.assertEqual(len([attrs for _, attrs in parser.tags if attrs.get("class") == "image-stage"]), 1)
        self.assertIn("比较无效", content)
        self.assertNotIn("@@TITLE@@", content)

    def test_validate_only_has_no_artifact_side_effects(self) -> None:
        manifest = self.root / "suite.json"
        manifest.write_text(json.dumps(self.suite(self.case("good", preparation={"colorSpace": "srgb"}))), encoding="utf-8")
        completed = subprocess.run([sys.executable, str(SCRIPT_DIR / "run_suite.py"), "--suite", str(manifest), "--validate-only"], capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(json.loads(completed.stdout)["valid"])
        self.assertFalse((self.root / "output").exists())

    def test_fixture_pass_cannot_close_blocked_live_case(self) -> None:
        fixture = self.case("fixture", collection={"strategy": "fixture", "subjectId": "same-page", "fixture": {"id": "fixed-v1", "reusedComponents": ["src/Page.tsx"]}, "code": {"revision": "local-commit", "worktreeDirty": True}})
        live = self.case("live", capture={"valid": False, "reason": "Subscription blocked"}, collection={"strategy": "live", "subjectId": "same-page"})
        code, report, output = self.execute(self.suite(fixture, live))
        self.assertEqual(code, 2)
        self.assertEqual(report["strategySummary"]["fixture"]["verdict"], "PASS")
        self.assertEqual(report["strategySummary"]["live"]["verdict"], "INCONCLUSIVE")
        self.assertTrue(report["cases"][0]["collection"]["code"]["worktreeDirty"])
        content = (output / "report.html").read_text(encoding="utf-8")
        self.assertIn('data-strategy="fixture"', content)
        self.assertIn('data-strategy="live"', content)
        self.assertIn('strategy-filter', content)

    def test_fixture_without_provenance_cannot_pass(self) -> None:
        code, report, _ = self.execute(self.suite(self.case("untracked", collection={"strategy": "fixture"})))
        self.assertEqual(code, 2)
        self.assertEqual(report["cases"][0]["comparability"]["issues"][0]["code"], "CASE_CONTRACT_INVALID")

    def test_measurement_produces_visuals_without_inventing_acceptance(self) -> None:
        case = self.case("measure", "changed.png", thresholds={"measurementOnly": True, "pixel": {"channelDelta": 0, "maxDiffRatio": None}})
        code, report, output = self.execute(self.suite(case))
        self.assertEqual(code, 2)
        result = report["cases"][0]
        self.assertEqual(result["verdict"], "INCONCLUSIVE")
        self.assertTrue(result["comparability"]["valid"])
        self.assertEqual(result["metrics"]["raw"]["changedPixels"], 1)
        self.assertIsNone(result["thresholds"]["maxDiffRatio"])
        self.assertTrue(Path(result["artifacts"]["comparisonBoard"]["path"]).is_file())
        content = (output / "report.html").read_text(encoding="utf-8")
        self.assertIn('class="image-stage"', content)
        self.assertIn("仅测量差异", content)

    def color_control(self) -> None:
        control = read_json(ROOT / "tests/fixtures/capture-color-profile.json")
        Image.new("RGB", (8, 12), tuple(control["expectedSrgb"])).save(self.reference)
        self.source_bytes = self.reference.read_bytes()
        Image.new("RGB", (8, 12), tuple(control["encodedRgb"])).save(self.actual, icc_profile=base64.b64decode(control["base64"]))

    def test_srgb_normalization_uses_comparison_copies_and_retains_original_downloads(self) -> None:
        self.color_control()
        actual_bytes = self.actual.read_bytes()
        code, report, output = self.execute(self.suite(self.case("color", preparation={"colorSpace": "srgb"})))
        self.assertEqual(code, 0)
        case = report["cases"][0]
        self.assertEqual(case["metrics"]["raw"]["changedPixels"], 0)
        self.assertEqual(case["preparation"]["status"], "APPLIED")
        self.assertEqual(case["actual"]["path"], str(self.actual.resolve()))
        self.assertEqual(case["actual"]["sha256"], hashlib.sha256(actual_bytes).hexdigest())
        self.assertEqual(self.actual.read_bytes(), actual_bytes)
        comparison = case["comparisonInputs"]["actual"]
        self.assertNotEqual(comparison["path"], case["actual"]["path"])
        with Image.open(comparison["path"]) as image:
            self.assertEqual(image.size, (8, 12))
            self.assertEqual(image.getpixel((0, 0)), (172, 52, 88))
        self.assertEqual(case["preparation"]["inputs"]["reference"]["operation"], "untagged-assumed-srgb")
        parser = Tags()
        parser.feed((output / "report.html").read_text())
        download_tags = [attrs for tag, attrs in parser.tags if tag == "a" and "download" in attrs]
        self.assertEqual(len(download_tags), 6)
        original = next(attrs for attrs in download_tags if attrs["download"] == "case-0-source-actual.png")
        self.assertEqual(base64.b64decode(original["href"].split(",", 1)[1]), actual_bytes)
        displayed = next(attrs for tag, attrs in parser.tags if attrs.get("data-image") == "actual")
        with Image.open(io.BytesIO(base64.b64decode(displayed["src"].split(",", 1)[1]))) as image:
            self.assertEqual(image.getpixel((0, 0)), (172, 52, 88))

    def test_default_encoded_comparison_does_not_silently_normalize(self) -> None:
        self.color_control()
        code, report, output = self.execute(self.suite(self.case("encoded")))
        self.assertEqual(code, 1)
        case = report["cases"][0]
        self.assertEqual(case["metrics"]["raw"]["changedPixels"], 96)
        self.assertEqual(case["preparation"], {"colorSpace": "encoded", "status": "NOT_REQUESTED", "inputs": {}})
        self.assertNotIn("comparisonInputs", case)
        self.assertFalse((output / "cases/encoded/prepared").exists())

    def test_invalid_color_profile_blocks_one_case_without_discarding_next_case(self) -> None:
        invalid = self.root / "invalid-profile.png"
        Image.new("RGB", (8, 12), "white").save(invalid, icc_profile=b"invalid ICC bytes")
        before = invalid.read_bytes()
        code, report, _ = self.execute(self.suite(self.case("invalid", invalid.name, preparation={"colorSpace": "srgb"}), self.case("good")))
        self.assertEqual(code, 2)
        self.assertEqual([c["verdict"] for c in report["cases"]], ["INCONCLUSIVE", "PASS"])
        self.assertEqual(report["cases"][0]["preparation"]["status"], "FAILED")
        self.assertEqual(report["cases"][0]["comparability"]["issues"][0]["code"], "COLOR_NORMALIZATION_FAILED")
        self.assertNotIn("comparisonInputs", report["cases"][0])
        self.assertEqual(invalid.read_bytes(), before)

    def test_color_preparation_is_explicitly_validated_and_case_override_wins(self) -> None:
        document = self.suite(self.case("invalid-mode", preparation={"colorSpace": "display-p3"}), self.case("unknown-option", preparation={"resize": True}), self.case("encoded-override", preparation={"colorSpace": "encoded"}), self.case("normalized-default"))
        document["defaults"]["preparation"] = {"colorSpace": "srgb"}
        code, report, _ = self.execute(document)
        self.assertEqual(code, 2)
        self.assertEqual([c["verdict"] for c in report["cases"]], ["INCONCLUSIVE", "INCONCLUSIVE", "PASS", "PASS"])
        self.assertEqual(report["cases"][2]["preparation"]["status"], "NOT_REQUESTED")
        self.assertEqual(report["cases"][3]["preparation"]["status"], "APPLIED")

    def test_blocked_live_capture_skips_color_preparation_and_stays_independent(self) -> None:
        fixture = self.case("fixture", preparation={"colorSpace": "srgb"}, collection={"strategy": "fixture", "fixture": {"id": "fixed-v1", "reusedComponents": ["src/Page.tsx"]}, "code": {"revision": "local-commit"}})
        live = self.case("live", preparation={"colorSpace": "srgb"}, capture={"valid": False, "reason": "Wrong state"}, collection={"strategy": "live"})
        code, report, output = self.execute(self.suite(fixture, live))
        self.assertEqual(code, 2)
        self.assertEqual(report["strategySummary"]["fixture"]["verdict"], "PASS")
        self.assertEqual(report["strategySummary"]["live"]["verdict"], "INCONCLUSIVE")
        self.assertEqual(report["cases"][1]["preparation"]["status"], "SKIPPED")
        self.assertFalse((output / "cases/live/prepared").exists())


if __name__ == "__main__":
    unittest.main()
