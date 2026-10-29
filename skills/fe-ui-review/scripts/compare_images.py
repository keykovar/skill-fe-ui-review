#!/usr/bin/env python3
"""Generate deterministic pixel-comparison artifacts without resizing inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from functools import reduce
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageChops, ImageDraw, ImageStat, UnidentifiedImageError
except ModuleNotFoundError as error:  # pragma: no cover - exercised without Pillow
    Image = None  # type: ignore[assignment]
    ImageChops = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]
    ImageStat = None  # type: ignore[assignment]
    UnidentifiedImageError = OSError  # type: ignore[assignment,misc]
    PILLOW_IMPORT_ERROR: ModuleNotFoundError | None = error
else:
    PILLOW_IMPORT_ERROR = None


PASS = 0
FAIL = 1
INCONCLUSIVE = 2


def parse_mask(value: str) -> tuple[int, int, int, int]:
    """Parse x,y,width,height without accepting ambiguous coordinates."""
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("mask must be x,y,width,height")
    try:
        x, y, width, height = (int(part) for part in parts)
    except ValueError as error:
        raise argparse.ArgumentTypeError("mask values must be integers") from error
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError(
            "mask x/y must be non-negative and width/height must be positive"
        )
    return x, y, width, height


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare two same-size images, generate overlay/diff artifacts, "
            "and emit an auditable JSON result. Inputs are never resized."
        )
    )
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--actual", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--channel-threshold",
        required=True,
        type=int,
        help="A pixel differs when its maximum RGBA channel delta exceeds this value.",
    )
    verdict_options = parser.add_mutually_exclusive_group(required=True)
    verdict_options.add_argument(
        "--max-diff-ratio",
        type=float,
        help="Maximum allowed changed-pixel ratio after masks, from 0 to 1.",
    )
    verdict_options.add_argument("--measure-only", action="store_true", help="Generate metrics and images without an acceptance threshold or PASS/FAIL.")
    parser.add_argument(
        "--mask",
        action="append",
        default=[],
        type=parse_mask,
        metavar="X,Y,WIDTH,HEIGHT",
        help="Exclude an explicit physical-pixel rectangle; repeat as needed.",
    )
    return parser


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_record(path: Path, size: tuple[int, int]) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "pixelSize": {"width": size[0], "height": size[1]},
    }


def artifact_record(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        size = image.size
    return image_record(path, size)


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
    }


def build_comparison_board(
    panels: list[tuple[str, Any]],
    output_path: Path,
    manifest_path: Path,
) -> None:
    """Create a display-only 2x2 board without changing source evidence."""
    panel_width = 640
    panel_height = 450
    label_height = 38
    padding = 20
    board = Image.new(
        "RGB",
        (panel_width * 2, (panel_height + label_height) * 2),
        (232, 235, 239),
    )
    draw = ImageDraw.Draw(board)
    manifest_panels: list[dict[str, Any]] = []

    for index, (label, source) in enumerate(panels):
        row, column = divmod(index, 2)
        left = column * panel_width
        top = row * (panel_height + label_height)
        panel = Image.new("RGB", (panel_width, panel_height + label_height), "white")
        panel_draw = ImageDraw.Draw(panel)
        panel_draw.rectangle(
            (0, 0, panel_width, label_height - 1),
            fill=(35, 42, 52),
        )
        panel_draw.text((padding, 10), label, fill="white")

        display_image = source.convert("RGB").copy()
        original_size = display_image.size
        display_image.thumbnail(
            (panel_width - padding * 2, panel_height - padding * 2),
            Image.Resampling.LANCZOS,
        )
        image_left = (panel_width - display_image.width) // 2
        image_top = label_height + (panel_height - display_image.height) // 2
        panel.paste(display_image, (image_left, image_top))
        board.paste(panel, (left, top))
        manifest_panels.append(
            {
                "label": label,
                "sourceSize": {
                    "width": original_size[0],
                    "height": original_size[1],
                },
                "displaySize": {
                    "width": display_image.width,
                    "height": display_image.height,
                },
                "displayOnlyScaling": True,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    board.save(output_path)
    manifest_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "displayOnly": True,
                "boardSize": {
                    "width": board.width,
                    "height": board.height,
                },
                "panels": manifest_panels,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def write_result(output_dir: Path, payload: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "result.json"
    result_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result_path


def inconclusive(
    output_dir: Path,
    code: str,
    message: str,
    *,
    reference: dict[str, Any] | None = None,
    actual: dict[str, Any] | None = None,
) -> int:
    payload: dict[str, Any] = {
        "schemaVersion": 1,
        "verdict": "INCONCLUSIVE",
        "comparability": {
            "valid": False,
            "issues": [{"code": code, "message": message}],
        },
        "artifacts": {},
    }
    if reference is not None:
        payload["reference"] = reference
    if actual is not None:
        payload["actual"] = actual
    result_path = write_result(output_dir, payload)
    print(
        json.dumps(
            {
                "verdict": payload["verdict"],
                "result": str(result_path.resolve()),
                "issue": code,
            },
            sort_keys=True,
        )
    )
    return INCONCLUSIVE


def validate_args(args: argparse.Namespace) -> str | None:
    if not 0 <= args.channel_threshold <= 255:
        return "channel threshold must be between 0 and 255"
    if not getattr(args, "measure_only", False) and (args.max_diff_ratio is None or not 0 <= args.max_diff_ratio <= 1):
        return "max diff ratio must be between 0 and 1"
    if args.reference.resolve() == args.actual.resolve():
        return "reference and actual must be different files"
    return None


def max_channel_image(delta: Any) -> Any:
    channels = delta.split()
    return reduce(ImageChops.lighter, channels)


def changed_count(binary: Any) -> int:
    return binary.histogram()[255]


def bbox_record(box: tuple[int, int, int, int] | None) -> dict[str, int] | None:
    if box is None:
        return None
    left, top, right, bottom = box
    return {
        "x": left,
        "y": top,
        "width": right - left,
        "height": bottom - top,
    }


def make_heatmap(max_delta: Any, threshold: int, include: Any | None = None) -> Any:
    intensity = max_delta.point(
        lambda value: 0 if value <= threshold else max(64, value)
    )
    if include is not None:
        intensity = ImageChops.multiply(intensity, include)
    zero = Image.new("L", max_delta.size, 0)
    opaque = Image.new("L", max_delta.size, 255)
    return Image.merge("RGBA", (intensity, zero, zero, opaque))


def run(args: argparse.Namespace) -> int:
    output_dir: Path = args.output_dir.resolve()
    argument_error = validate_args(args)
    if argument_error:
        return inconclusive(output_dir, "INVALID_ARGUMENT", argument_error)

    if PILLOW_IMPORT_ERROR is not None:
        return inconclusive(
            output_dir,
            "MISSING_DEPENDENCY",
            "Pillow is required; use an existing Python environment that provides PIL.",
        )

    reference_path = args.reference.resolve()
    actual_path = args.actual.resolve()
    if not reference_path.is_file() or not actual_path.is_file():
        missing = [
            str(path)
            for path in (reference_path, actual_path)
            if not path.is_file()
        ]
        return inconclusive(
            output_dir,
            "INPUT_NOT_FOUND",
            "Missing input file(s): " + ", ".join(missing),
        )

    try:
        with Image.open(reference_path) as source:
            source.load()
            reference = source.convert("RGBA")
        with Image.open(actual_path) as source:
            source.load()
            actual = source.convert("RGBA")
    except (OSError, UnidentifiedImageError) as error:
        return inconclusive(output_dir, "IMAGE_DECODE_FAILED", str(error))

    reference_record = image_record(reference_path, reference.size)
    actual_record = image_record(actual_path, actual.size)

    if reference.size != actual.size:
        return inconclusive(
            output_dir,
            "DIMENSION_MISMATCH",
            (
                f"Reference is {reference.size[0]}x{reference.size[1]} but actual "
                f"is {actual.size[0]}x{actual.size[1]}; inputs were not resized."
            ),
            reference=reference_record,
            actual=actual_record,
        )

    width, height = reference.size
    for x, y, mask_width, mask_height in args.mask:
        if x + mask_width > width or y + mask_height > height:
            return inconclusive(
                output_dir,
                "MASK_OUT_OF_BOUNDS",
                (
                    f"Mask {x},{y},{mask_width},{mask_height} exceeds "
                    f"{width}x{height}."
                ),
                reference=reference_record,
                actual=actual_record,
            )

    total_pixels = width * height
    include = Image.new("L", reference.size, 255)
    mask_draw = ImageDraw.Draw(include)
    for x, y, mask_width, mask_height in args.mask:
        mask_draw.rectangle(
            (x, y, x + mask_width - 1, y + mask_height - 1),
            fill=0,
        )

    compared_pixels = include.histogram()[255]
    if compared_pixels == 0:
        return inconclusive(
            output_dir,
            "ALL_PIXELS_MASKED",
            "Masks exclude the entire image.",
            reference=reference_record,
            actual=actual_record,
        )

    delta = ImageChops.difference(reference, actual)
    max_delta = max_channel_image(delta)
    binary = max_delta.point(
        lambda value: 255 if value > args.channel_threshold else 0
    )
    effective_binary = ImageChops.multiply(binary, include)

    raw_changed = changed_count(binary)
    effective_changed = changed_count(effective_binary)
    masked_pixels = total_pixels - compared_pixels

    masked_max_delta = ImageChops.multiply(max_delta, include)
    max_effective_delta = masked_max_delta.getextrema()[1]
    channel_means = ImageStat.Stat(delta, mask=include).mean
    mean_channel_delta = sum(channel_means) / len(channel_means)

    raw_ratio = raw_changed / total_pixels
    effective_ratio = effective_changed / compared_pixels
    measurement_only = getattr(args, "measure_only", False)
    verdict = "INCONCLUSIVE" if measurement_only else "PASS" if effective_ratio <= args.max_diff_ratio else "FAIL"

    output_dir.mkdir(parents=True, exist_ok=True)
    overlay_path = output_dir / "overlay.png"
    raw_diff_path = output_dir / "diff-raw.png"
    effective_diff_path = output_dir / "diff.png"
    mask_path = output_dir / "comparison-mask.png"
    board_path = output_dir / "comparison-board.png"
    board_manifest_path = output_dir / "comparison-board.json"

    overlay = Image.blend(reference, actual, 0.5)
    raw_diff = make_heatmap(max_delta, args.channel_threshold)
    effective_diff = make_heatmap(max_delta, args.channel_threshold, include)
    overlay.save(overlay_path)
    raw_diff.save(raw_diff_path)
    effective_diff.save(effective_diff_path)
    include.save(mask_path)
    build_comparison_board(
        [
            ("Reference / Figma", reference),
            ("Actual / Target", actual),
            ("Overlay", overlay),
            ("Diff", effective_diff),
        ],
        board_path,
        board_manifest_path,
    )

    payload: dict[str, Any] = {
        "schemaVersion": 1,
        "verdict": verdict,
        "comparability": {"valid": True, "issues": [{"code": "THRESHOLD_UNRESOLVED", "message": "Images are comparable; metrics are descriptive only because no acceptance threshold was supplied."}] if measurement_only else []},
        "measurementOnly": measurement_only,
        "reference": reference_record,
        "actual": actual_record,
        "thresholds": {
            "channelDelta": args.channel_threshold,
            "maxDiffRatio": args.max_diff_ratio,
        },
        "masks": [
            {"x": x, "y": y, "width": mask_width, "height": mask_height}
            for x, y, mask_width, mask_height in args.mask
        ],
        "metrics": {
            "totalPixels": total_pixels,
            "comparedPixels": compared_pixels,
            "maskedPixels": masked_pixels,
            "maskedRatio": masked_pixels / total_pixels,
            "raw": {
                "changedPixels": raw_changed,
                "diffRatio": raw_ratio,
                "boundingBox": bbox_record(binary.getbbox()),
            },
            "effective": {
                "changedPixels": effective_changed,
                "diffRatio": effective_ratio,
                "meanChannelDelta": mean_channel_delta,
                "normalizedMeanChannelDelta": mean_channel_delta / 255,
                "maxChannelDelta": max_effective_delta,
                "boundingBox": bbox_record(effective_binary.getbbox()),
            },
        },
        "artifacts": {
            "overlay": artifact_record(overlay_path),
            "rawDiff": artifact_record(raw_diff_path),
            "diff": artifact_record(effective_diff_path),
            "comparisonMask": artifact_record(mask_path),
            "comparisonBoard": artifact_record(board_path),
            "comparisonBoardManifest": file_record(board_manifest_path),
        },
    }
    result_path = write_result(output_dir, payload)
    print(
        json.dumps(
            {
                "verdict": verdict,
                "result": str(result_path.resolve()),
                "diffRatio": effective_ratio,
            },
            sort_keys=True,
        )
    )
    return {"PASS": PASS, "FAIL": FAIL, "INCONCLUSIVE": INCONCLUSIVE}[verdict]


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return run(args)
    except Exception as error:  # Defensive boundary for machine-readable failure.
        output_dir = args.output_dir.resolve()
        return inconclusive(output_dir, "TOOL_ERROR", str(error))


if __name__ == "__main__":
    sys.exit(main())
