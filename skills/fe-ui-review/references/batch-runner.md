# Batch Runner and Device Presets

## Execution Boundary

The runner executes pixel comparisons on already captured local raster images.
It does not authenticate, navigate pages, fetch Figma files, apply crops, resize
images, run setup actions, modify application source, or declare UI Fix closure.
Continue using the host's Figma and browser tools for collection and preparation.
Local paths on Figma and web objects identify those prepared captures; URLs remain
provenance rather than instructions to the runner.

Color normalization is an explicit optional preparation step: request
`preparation.colorSpace=srgb` to produce separate ICC-aware comparison copies.
The default `encoded` compares supplied pixel values without a color transform.
Original source files and hashes remain separate from comparison inputs.

The runner's PASS/FAIL/INCONCLUSIVE and suiteVerdict concern pixel evidence only.
Every report records comparisonScope=pixels and PENDING_AGENT_REVIEW. The agent
must still evaluate state, geometry, critical regions, interactions, accessibility,
and evidence validity before issuing the full review verdict. Never copy a pixel
PASS into an unqualified whole-page acceptance conclusion.

## Commands

Use an existing Python environment with Pillow. No new dependency is needed for
JSON parsing, batching, presets, or HTML generation. Do not install dependencies
without authorization. Run from the skill directory, or use absolute script paths:

~~~bash
python3 scripts/run_suite.py --list-devices
python3 scripts/run_suite.py --suite /absolute/suite.json --validate-only
python3 scripts/run_suite.py --suite /absolute/suite.json --output-dir /absolute/new-run
~~~

--validate-only validates the manifest and expands presets; it does not inspect
images, access URLs, or create artifacts. Output directories must be new or empty,
so reruns require a new directory. Exit codes are 0 PASS, 1 FAIL, 2 INCONCLUSIVE.
Invalid suite identity/JSON/duplicate IDs reject the run with exit 2. Invalid case
fields become INCONCLUSIVE without discarding other cases.

Use [example-suite.json](../assets/example-suite.json) as a small executable input
example. Copy it beside your captures, set the actual paths and case mapping, and
resolve thresholds from the project or explicit acceptance contract. Its zero
thresholds illustrate strict synthetic comparison; they are not default UI gates.

## Executable JSON Subset

Use schemaVersion=1, a suiteId, optional mode=review/fix, defaults, and a nonempty
cases array. Cases require unique safe IDs of up to 80 letters, digits, dots,
underscores, or hyphens, starting with a letter or digit.

Each case explicitly maps reference and target. Defaults cannot supply either
mapping. Relative image paths resolve beside the manifest, not beside the script.
No case or device Cartesian product is generated.

Supported fields include:

- reference.type=image/figma with path; figma also requires the exact nodeId;
- target.type=screenshot/web with path and platform=web/ios/android/unknown;
- required (boolean, default true);
- deviceProfile (one preset ID);
- environment, state, capture, masks, and thresholds;
- preparation.colorSpace=encoded/srgb (also accepted in suite defaults);
- capture.expectedPixelSize={width,height} to validate prepared raster dimensions;
- capture.valid=false and capture.reason to preserve an upstream collection block.
- collection.strategy=live/fixture with shared subjectId and source provenance;
  fixture requires id, reusedComponents, and code.revision. See
  [web-collection.md](web-collection.md) for collection and adapter preparation.

For uncropped viewport/full-device captures, missing expectedPixelSize is derived
from resolved logical dimensions multiplied by DPR/display scale/density (rounded
to integer pixels), and the derivation is recorded. For app-content/custom crops,
declare the actual prepared-image dimensions explicitly. Presets never resize the
images to make them match.

If a Figma/web object has only a URL, the case is INCONCLUSIVE and asks for a local
capture. A web target must use platform=web. Keep credentials and session material
out of the manifest and report. State and capture fields record collector evidence;
the runner cannot infer their truth from an image.

Set thresholds.pixel.channelDelta to an integer from 0 through 255, and
thresholds.pixel.maxDiffRatio to a finite number from 0 through 1. Both are required
after defaults expansion. Geometry, critical-region, perceptual, and unknown
assertions are rejected instead of silently ignored; evaluate them separately.
For descriptive measurement without acceptance, use thresholds.measurementOnly=true,
provide pixel.channelDelta, and omit pixel.maxDiffRatio. Images and metrics are
generated, but the case remains INCONCLUSIVE; no hidden acceptance threshold is used.

## Color Preparation

To compare both inputs in sRGB, add this parameter to a case or suite defaults:

~~~json
{"preparation": {"colorSpace": "srgb"}}
~~~

The runner preserves the source records in `reference` and `actual`, writes new
PNGs and normalization manifests under `cases/ID/prepared/`, and records the
actual pixel inputs separately in `comparisonInputs`. `preparation.inputs`
contains source/output hashes, embedded ICC identity, geometry, and assumptions.
An untagged input is explicitly assumed sRGB. This assumption still needs agent
review; a synthetic color-control PASS does not prove UI acceptance.

Masks and pixel thresholds operate on these same-size comparison copies. Raw
metrics mean before masks, after the declared color preparation. Color preparation
never resizes images, loosens thresholds, changes capture stability, or closes a
previous finding under a different contract. A bad ICC profile or unavailable
color engine makes only that case INCONCLUSIVE; subsequent cases still run.
Already blocked captures skip preparation. `--validate-only` validates the option
without reading images or writing any copies.

The viewer labels the applied color processing, uses comparison copies for the
slider/overlay/diff, and offers separate original-image downloads. Audit metadata
includes both source and comparison records. `encoded` is recorded as
NOT_REQUESTED, requested but blocked work as SKIPPED, successful preparation as
APPLIED, and conversion errors as FAILED.

## Prepared Masks

Masks must already be resolved to physical pixels:

~~~json
{
  "id": "status-time",
  "reason": "Non-deterministic system clock outside the application content",
  "unit": "physical-px",
  "rectangle": {"x": 16, "y": 8, "width": 40, "height": 16}
}
~~~

Selector masks need the browser collector to resolve them first. Preserve the ID,
reason, owner, expiry, and original selector in collector evidence. The agent still
checks expiry and whether a mask obscures critical content. When crop/contentRegion
metadata is present, set capture.prepared=true only after applying that declared
crop to a separate image. The runner does not perform it.

## Device Presets

[device-profiles.json](../assets/device-profiles.json) contains ten generic presets:

| Preset | Logical size | Scale | Platform |
|---|---|---|---|
| web-phone-320 | 320 x 568 CSS px | DPR 1 | Web |
| web-phone-360 | 360 x 800 CSS px | DPR 1 | Web |
| web-phone-390 | 390 x 844 CSS px | DPR 1 | Web |
| web-phone-430 | 430 x 932 CSS px | DPR 1 | Web |
| web-tablet-768 | 768 x 1024 CSS px | DPR 1 | Web |
| web-tablet-landscape | 1024 x 768 CSS px | DPR 1 | Web |
| web-desktop-1440 | 1440 x 900 CSS px | DPR 1 | Web |
| web-desktop-1920 | 1920 x 1080 CSS px | DPR 1 | Web |
| ios-phone-390 | 390 x 844 pt | Display scale 3 | iOS image |
| android-phone-360 | 360 x 800 dp | Density 3 | Android image |

These are capture configurations, not named device emulations or verified hardware.
Native presets are examples; override them using actual screenshot metadata. They
do not supply OS versions, browser engines, user agents, safe areas, navigation
insets, or native automation. A Web viewport does not emulate mobile browser UA,
touch, or Native behavior by itself.

Environment resolution order is preset -> suite defaults -> case overrides, using
deep object merge; lists are replaced. Explicit values win, invalid dimensions or
platform/orientation conflicts are INCONCLUSIVE. Expansion is recorded in the JSON.
Collectors must apply the resolved values and record their actual environment.

## Outputs and Viewer

Each run retains report.json, summary.md, report.html, and cases/ID/result.json plus
the existing per-case original-size pixel artifacts and comparison board.

The HTML is a portable offline file with embedded raster images, no CDN, no remote
scripts, and no network requests. It supports verdict/platform/search filtering,
reference/actual drag comparison, overlay/diff views, 2x zoom with scrolling,
keyboard-accessible controls, image downloads, and expandable audit metadata.
Invalid comparisons show available source images with a visible invalid label.
Live and fixture evidence has visible labels, a source filter, and separate
strategySummary verdicts. Unlabeled old captures remain unrecorded. A fixture
result never substitutes for real-site acceptance.
The original files, thresholds, metrics, and verdict are unaffected by viewer use.

Suite aggregation uses required cases only: any FAIL wins; otherwise any
INCONCLUSIVE wins; otherwise PASS. A suite with no required cases is INCONCLUSIVE.
Optional results remain visible in all outputs. Finish the agent analysis and
follow the report contract's inline board display requirements after running.
