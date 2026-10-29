#!/usr/bin/env python3
"""Compare an explicit suite of prepared local captures; never drive remote UIs."""

from __future__ import annotations

import argparse
import copy
import io
import json
import math
import re
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import compare_images
from render_report import write_reports


SKILL_DIR = Path(__file__).resolve().parents[1]
PROFILE_PATH = SKILL_DIR / "assets" / "device-profiles.json"
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
VERDICTS = {"PASS": 0, "FAIL": 1, "INCONCLUSIVE": 2}


class ContractError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise ContractError(f"Non-finite JSON number: {value}")

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)


def merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def object_value(value: Any, name: str) -> dict:
    if not isinstance(value, dict):
        raise ContractError(f"{name} must be an object")
    return value


def issue(code: str, message: str) -> dict:
    return {"code": code, "message": message}


def positive_number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def normalize_case(raw: Any, defaults: dict, base: Path, profiles: dict) -> dict:
    raw = object_value(raw, "case")
    case = merge(defaults, raw)
    profile_id = case.get("deviceProfile")
    profile = {}
    if profile_id is not None:
        if not isinstance(profile_id, str) or profile_id not in profiles:
            raise ContractError(f"Unknown deviceProfile: {profile_id}")
        profile = profiles[profile_id]

    reference = object_value(case.get("reference"), "reference")
    target = object_value(case.get("target"), "target")
    if reference.get("type") not in ("image", "figma"):
        raise ContractError("reference.type must be image or figma")
    if target.get("type") not in ("screenshot", "web"):
        raise ContractError("target.type must be screenshot or web")
    platform = target.get("platform", "web" if target["type"] == "web" else profile.get("platform", "unknown"))
    if platform not in ("web", "ios", "android", "unknown"):
        raise ContractError("Unknown target platform")
    if target["type"] == "web" and platform != "web":
        raise ContractError("A web target must use platform=web")
    if profile and platform != profile["platform"]:
        raise ContractError("deviceProfile platform does not match target platform")
    target["platform"] = platform

    environment = merge(profile.get("environment", {}), object_value(case.get("environment", {}), "environment"))
    for key in ("viewport", "logicalSize"):
        if key in environment:
            size = object_value(environment[key], key)
            if not all(positive_number(size.get(axis)) for axis in ("width", "height")):
                raise ContractError(f"{key} requires positive width and height")
    for key in ("dpr", "scale", "density", "fontScale"):
        if key in environment and not positive_number(environment[key]):
            raise ContractError(f"{key} must be positive")
    if "orientation" in environment and environment["orientation"] not in ("portrait", "landscape"):
        raise ContractError("orientation must be portrait or landscape")
    logical_size = environment.get("viewport", environment.get("logicalSize"))
    if logical_size and environment.get("orientation"):
        width, height = logical_size["width"], logical_size["height"]
        if width != height and (width > height) != (environment["orientation"] == "landscape"):
            raise ContractError("orientation conflicts with declared logical dimensions")
    case["environment"] = environment

    for label, source in (("reference", reference), ("target", target)):
        path = source.get("path")
        if path is not None:
            if not isinstance(path, str) or not path.strip():
                raise ContractError(f"{label}.path must be a non-empty local path")
            local_path = Path(path).expanduser()
            source["path"] = str((base / local_path).resolve())
    if reference["type"] == "figma" and (not isinstance(reference.get("nodeId"), str) or not reference["nodeId"].strip()):
        raise ContractError("Figma captures require the exact nodeId")

    if type(case.get("required", True)) is not bool:
        raise ContractError("required must be boolean")
    case["required"] = case.get("required", True)
    thresholds = object_value(case.get("thresholds", {}), "thresholds")
    if set(thresholds) - {"source", "profile", "pixel", "geometry", "criticalRegions", "measurementOnly"}:
        raise ContractError("Unsupported threshold assertion; only pixel assertions are executed")
    if thresholds.get("geometry") or thresholds.get("criticalRegions"):
        raise ContractError("Geometry and critical-region assertions require separate evaluation; this runner only executes pixel thresholds")
    pixel = object_value(thresholds.get("pixel", {}), "thresholds.pixel")
    if set(pixel) - {"channelDelta", "maxDiffRatio"}:
        raise ContractError("Unsupported pixel assertion")
    channel, ratio = pixel.get("channelDelta"), pixel.get("maxDiffRatio")
    measurement_only = thresholds.get("measurementOnly", False)
    if type(measurement_only) is not bool:
        raise ContractError("thresholds.measurementOnly must be boolean")
    if type(channel) is not int or not 0 <= channel <= 255:
        raise ContractError("Explicit thresholds.pixel.channelDelta (0..255) is required")
    if measurement_only and ratio is not None:
        raise ContractError("measurementOnly must not declare an acceptance maxDiffRatio")
    if not measurement_only and (type(ratio) not in (int, float) or not math.isfinite(ratio) or not 0 <= ratio <= 1):
        raise ContractError("Explicit thresholds.pixel.maxDiffRatio (0..1) is required")

    preparation = object_value(case.get("preparation", {}), "preparation")
    if set(preparation) - {"colorSpace"} or preparation.get("colorSpace", "encoded") not in ("encoded", "srgb"):
        raise ContractError("preparation supports only colorSpace=encoded or srgb")
    case["preparation"] = {"colorSpace": preparation.get("colorSpace", "encoded")}

    masks = case.get("masks", [])
    if not isinstance(masks, list):
        raise ContractError("masks must be a list")
    seen_masks = set()
    for mask in masks:
        mask = object_value(mask, "mask")
        mask_id = mask.get("id")
        if not isinstance(mask_id, str) or not mask_id or mask_id in seen_masks or not isinstance(mask.get("reason"), str) or not mask["reason"].strip():
            raise ContractError("Every mask requires a unique id and a reason")
        seen_masks.add(mask_id)
        if mask.get("unit") != "physical-px" or "selector" in mask:
            raise ContractError("Resolve masks to explicit physical-px rectangles before running")
        rect = object_value(mask.get("rectangle"), "mask.rectangle")
        values = [rect.get(key) for key in ("x", "y", "width", "height")]
        if any(type(value) is not int for value in values) or min(values[:2]) < 0 or min(values[2:]) <= 0:
            raise ContractError("Mask rectangle requires nonnegative x/y and positive integer width/height")
    case["masks"] = masks
    capture = object_value(case.get("capture", {}), "capture")
    if "valid" in capture and type(capture["valid"]) is not bool:
        raise ContractError("capture.valid must be boolean")
    if (capture.get("crop") or target.get("contentRegion")) and capture.get("prepared") is not True:
        raise ContractError("Crop/contentRegion must already be applied to separate captures and declared capture.prepared=true")
    expected = capture.get("expectedPixelSize")
    if expected is None and capture.get("region", "viewport") in ("viewport", "full-device") and not capture.get("crop") and not target.get("contentRegion"):
        logical = environment.get("viewport", environment.get("logicalSize"))
        scale = environment.get({"web": "dpr", "ios": "scale", "android": "density"}.get(platform, "scale"))
        if logical and scale is not None:
            expected = {axis: round(logical[axis] * scale) for axis in ("width", "height")}
            capture["expectedPixelSize"] = expected
            capture["sizeSource"] = "resolved-environment"
    if expected is not None:
        expected = object_value(expected, "capture.expectedPixelSize")
        if any(type(expected.get(axis)) is not int or expected[axis] <= 0 for axis in ("width", "height")):
            raise ContractError("expectedPixelSize requires positive integer width and height")
    case["capture"] = capture
    case["state"] = object_value(case.get("state", {}), "state")
    collection = object_value(case.get("collection", {}), "collection")
    if collection:
        if collection.get("strategy") not in ("live", "fixture"):
            raise ContractError("collection.strategy must be live or fixture")
        if collection["strategy"] == "fixture":
            fixture = object_value(collection.get("fixture", {}), "collection.fixture")
            code = object_value(collection.get("code", {}), "collection.code")
            components = fixture.get("reusedComponents")
            if (not isinstance(fixture.get("id"), str) or not fixture["id"].strip()
                    or not isinstance(components, list) or not components
                    or any(not isinstance(value, str) or not value.strip() for value in components)
                    or not isinstance(code.get("revision"), str) or not code["revision"].strip()):
                raise ContractError("Fixture collection requires fixture.id, reusedComponents and code.revision")
    case["collection"] = collection
    return case


def normalize_suite(document: Any, base: Path, profiles: dict) -> list[dict]:
    document = object_value(document, "suite")
    if type(document.get("schemaVersion")) is not int or document["schemaVersion"] != 1:
        raise ContractError("schemaVersion must be 1")
    if not isinstance(document.get("suiteId"), str) or not document["suiteId"].strip():
        raise ContractError("suiteId is required")
    if document.get("mode", "review") not in ("review", "fix"):
        raise ContractError("mode must be review or fix")
    defaults = object_value(document.get("defaults", {}), "defaults")
    if "reference" in defaults or "target" in defaults:
        raise ContractError("Reference and target mappings must be explicit in each case")
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ContractError("cases must be a non-empty list")
    ids = [raw.get("id") if isinstance(raw, dict) else None for raw in cases]
    if any(not isinstance(case_id, str) or not ID_PATTERN.fullmatch(case_id) for case_id in ids):
        raise ContractError("Case IDs must be safe names of 1..80 letters, digits, dots, underscores or hyphens")
    if len(set(ids)) != len(ids):
        raise ContractError("Case IDs must be unique")
    normalized = []
    for raw in cases:
        try:
            case = normalize_case(raw, defaults, base, profiles)
            case["inputIssues"] = []
        except (ContractError, TypeError, ValueError) as error:
            case = {"id": raw["id"], "required": raw.get("required") is not False, "inputIssues": [issue("CASE_CONTRACT_INVALID", str(error))]}
            if isinstance(raw.get("collection"), dict):
                case["collection"] = {key: raw["collection"][key] for key in ("strategy", "subjectId") if isinstance(raw["collection"].get(key), str)}
            # Preserve available source images even when another case field is invalid.
            for key in ("reference", "target"):
                if isinstance(raw.get(key), dict):
                    source = {name: raw[key][name] for name in ("type", "platform", "nodeId", "url", "path") if name in raw[key]}
                    if isinstance(source.get("path"), str):
                        source["path"] = str((base / Path(source["path"]).expanduser()).resolve())
                    else:
                        source.pop("path", None)
                    case[key] = source
        normalized.append(case)
    return normalized


def aggregate(cases: list[dict]) -> str:
    required = [case for case in cases if case["required"]]
    if not required:
        return "INCONCLUSIVE"
    if any(case["verdict"] == "FAIL" for case in required):
        return "FAIL"
    if any(case["verdict"] == "INCONCLUSIVE" for case in required):
        return "INCONCLUSIVE"
    return "PASS"


def evaluate_case(case: dict, output_dir: Path) -> dict:
    issues = list(case["inputIssues"])
    preparation = {"colorSpace": case.get("preparation", {}).get("colorSpace", "encoded"), "status": "NOT_REQUESTED", "inputs": {}}
    source_fields = {"type", "url", "nodeId", "versionId", "path", "platform", "device", "logicalSize", "scale", "expectedFrame", "contentRegion", "captureRegion", "capturedAt"}
    sources = {key: {name: value for name, value in case.get(key, {}).items() if name in source_fields} for key in ("reference", "target")}
    for key, source in sources.items():
        if not issues and not source.get("path"):
            issues.append(issue(f"{key.upper()}_UNAVAILABLE", f"Collect {key} using the existing Figma/browser tools and set its local path"))
    if case.get("capture", {}).get("valid") is False:
        issues.append(issue("CAPTURE_INVALID", str(case["capture"].get("reason", "Capture was marked invalid by its collector"))))
    expected = case.get("capture", {}).get("expectedPixelSize")
    if not issues and expected and compare_images.Image is not None:
        for key, source in sources.items():
            try:
                with compare_images.Image.open(source["path"]) as image:
                    if image.size != (expected["width"], expected["height"]):
                        issues.append(issue("EXPECTED_SIZE_MISMATCH", f"{key} is {image.size}; expected {expected['width']}x{expected['height']}. No resizing was performed"))
            except OSError:
                pass  # The comparator reports missing or undecodable inputs.
    comparison_sources = copy.deepcopy(sources)
    if preparation["colorSpace"] == "srgb":
        preparation["status"] = "SKIPPED"
        if not issues:
            try:
                # Load color tooling only when requested; device/manifest commands need no Pillow.
                from normalize_srgb import normalize_srgb

                for key, source in sources.items():
                    record = normalize_srgb(Path(source["path"]), output_dir / "prepared" / f"{key}-srgb.png")
                    preparation["inputs"][key] = record
                    comparison_sources[key] = record["output"]
                preparation["status"] = "APPLIED"
            except Exception as error:
                preparation["status"] = "FAILED"
                issues.append(issue("COLOR_NORMALIZATION_FAILED", str(error)))
    if issues:
        result = {"schemaVersion": 1, "verdict": "INCONCLUSIVE", "comparability": {"valid": False, "issues": issues}, "artifacts": {}}
        compare_images.write_result(output_dir, result)
    else:
        pixel = case["thresholds"]["pixel"]
        masks = [tuple(mask["rectangle"][key] for key in ("x", "y", "width", "height")) for mask in case["masks"]]
        args = argparse.Namespace(reference=Path(comparison_sources["reference"]["path"]), actual=Path(comparison_sources["target"]["path"]), output_dir=output_dir, channel_threshold=pixel["channelDelta"], max_diff_ratio=pixel.get("maxDiffRatio"), measure_only=case["thresholds"].get("measurementOnly", False), mask=masks)
        try:
            with redirect_stdout(io.StringIO()):
                compare_images.run(args)
        except Exception as error:
            compare_images.inconclusive(output_dir, "COMPARATOR_ERROR", str(error))
        result = read_json(output_dir / "result.json")
    platform = sources["target"].get("platform", "unknown")
    if not isinstance(platform, str) or platform not in ("web", "ios", "android", "unknown"):
        platform = "unknown"
    result.update({
        "id": case["id"], "required": case["required"], "comparisonScope": "pixels",
        "platform": platform,
        "deviceProfile": case.get("deviceProfile"),
        "normalizedEnvironment": case.get("environment", {}),
        "state": case.get("state", {}), "capture": case.get("capture", {}),
        "preparation": preparation,
        "collection": case.get("collection", {}),
        "resolvedThresholds": case.get("thresholds", {}), "declaredMasks": case.get("masks", []),
        "analysisStatus": "PENDING_AGENT_REVIEW", "findings": [], "recommendations": [],
        "closure": {"status": "NOT_APPLICABLE"},
    })
    for key, source in sources.items():
        record_key = "actual" if key == "target" else "reference"
        if preparation["status"] == "APPLIED":
            result.setdefault("comparisonInputs", {})[record_key] = merge(comparison_sources[key], result.get(record_key, {}))
            result[record_key] = copy.deepcopy(source)
        else:
            result[record_key] = merge(source, result.get(record_key, {}))
        if source.get("path") and "sha256" not in result[record_key] and compare_images.Image is not None:
            try:
                with compare_images.Image.open(source["path"]) as image:
                    image.verify()
                    size = image.size
                result[record_key].update(compare_images.image_record(Path(source["path"]), size))
            except (OSError, ValueError, compare_images.Image.DecompressionBombError):
                pass  # Keep invalid or unavailable sources marked inconclusive.
    result["nextAction"] = {
        "PASS": "继续检查页面状态、布局、关键区域和可访问性，再作完整 UI 验收。",
        "FAIL": "检查原始截图与差异图，定位原因，并在相同条件下重新截图验证。",
        "INCONCLUSIVE": "先解决列出的采集或配置问题，再重新执行此案例。",
    }[result["verdict"]]
    if result.get("measurementOnly"):
        result["nextAction"] = "结合原图、叠加图和差异图描述差异；由项目确定验收阈值后再进行 PASS/FAIL 判定。"
    compare_images.write_result(output_dir, result)
    return result


def run_suite(suite_path: Path, output_dir: Path, *, validate_only: bool = False) -> tuple[int, dict]:
    profiles = read_json(PROFILE_PATH)["profiles"]
    document = read_json(suite_path)
    cases = normalize_suite(document, suite_path.parent, profiles)
    if validate_only:
        invalid = any(case["inputIssues"] for case in cases)
        return (2 if invalid else 0), {"valid": not invalid, "scope": "manifest-only", "cases": cases}
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise ContractError("Output directory must be new or empty; existing evidence will not be overwritten")
    output_dir.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    results = [evaluate_case(case, output_dir / "cases" / case["id"]) for case in cases]
    verdict = aggregate(results)
    report = {
        "schemaVersion": 1, "runId": output_dir.name, "suiteId": document["suiteId"],
        "mode": document.get("mode", "review"), "comparisonScope": "pixels", "suiteVerdict": verdict,
        "analysisStatus": "PENDING_AGENT_REVIEW", "startedAt": started, "finishedAt": utc_now(),
        "sourceManifest": {"path": str(suite_path.resolve()), "sha256": compare_images.sha256_file(suite_path)},
        "deviceProfiles": {"path": str(PROFILE_PATH), "sha256": compare_images.sha256_file(PROFILE_PATH)},
        "summary": {"total": len(results), "required": sum(case["required"] for case in results), **{value.lower(): sum(case["verdict"] == value for case in results) for value in VERDICTS}},
        "cases": results, "closure": {"status": "NOT_APPLICABLE"},
    }
    report["strategySummary"] = {
        strategy: {
            "verdict": aggregate(group), "caseIds": [case["id"] for case in group],
            **{value.lower(): sum(case["verdict"] == value for case in group) for value in VERDICTS},
        }
        for strategy in ("live", "fixture", "unrecorded")
        if (group := [case for case in results if case.get("collection", {}).get("strategy", "unrecorded") == strategy])
    }
    (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_reports(report, output_dir)
    return VERDICTS[verdict], report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, help="JSON manifest; relative image paths resolve beside this file")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--list-devices", action="store_true")
    args = parser.parse_args()
    if args.list_devices:
        print(json.dumps(read_json(PROFILE_PATH), ensure_ascii=False, indent=2))
        return 0
    if args.suite is None or (args.output_dir is None and not args.validate_only):
        parser.error("--suite and --output-dir are required (output-dir is optional for validate-only)")
    try:
        code, report = run_suite(args.suite.resolve(), (args.output_dir or Path.cwd()).resolve(), validate_only=args.validate_only)
        if args.validate_only:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"suiteVerdict": report["suiteVerdict"], "comparisonScope": "pixels", "summary": report["summary"], "report": str(args.output_dir.resolve() / "report.html")}, ensure_ascii=False))
        return code
    except (ContractError, OSError, ValueError) as error:
        print(json.dumps({"verdict": "INCONCLUSIVE", "issue": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
