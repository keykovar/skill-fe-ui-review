# Report Contract

## Purpose

Produce an auditable result for both UI Review and UI Fix. A complete report has:

- a concise human-readable Markdown summary;
- machine-readable JSON;
- local visual artifacts with provenance;
- inline visual evidence in the final response when the host can render local
  images.

Never report only a similarity percentage.

The local batch runner produces a pixel-evidence subset with comparisonScope=pixels
and analysisStatus=PENDING_AGENT_REVIEW, plus a portable offline HTML viewer. Its
suiteVerdict does not close the broader UI acceptance. Complete this report's
diagnosis and required checks, keeping pixel verdict and full review verdict
distinct. See [batch-runner.md](batch-runner.md) for execution and viewer details.

## Run Summary

~~~yaml
schemaVersion: 1
runId: generated-run-id
suiteId: checkout-ui
mode: review
startedAt: ...
finishedAt: ...
suiteVerdict: FAIL
summary:
  total: 6
  pass: 3
  fail: 2
  inconclusive: 1
source:
  repository: optional
  commit: optional
  worktreeDirty: true
tooling:
  figmaCapture: ...
  targetCapture: ...
  comparator: ...
cases: []
closure: {}
~~~

Record the source commit when known. If the worktree is dirty, say so explicitly;
do not describe the run as validation of the clean commit alone.

For web cases, show `collection.strategy` prominently as LIVE or FIXTURE, with
fixture/code provenance and scope. Preserve independent strategy verdicts in
`strategySummary`; fixture PASS cannot close a live INCONCLUSIVE or FAIL.

## Case Result

~~~yaml
cases:
  - id: checkout-web-390-default
    verdict: FAIL
    comparability:
      valid: true
      issues: []
    reference:
      nodeId: "123:456"
      versionId: ...
      imageHash: ...
    target:
      type: web
      url: ...
      imageHash: ...
    normalizedEnvironment: {}
    preparation: {}
    comparisonInputs: {}
    resolvedThresholds: {}
    metrics: {}
    artifacts:
      comparisonBoard: {}
      comparisonBoardManifest: {}
    findings: []
    recommendations: []
    closure:
      status: NOT_APPLICABLE
~~~

For every non-PASS case, provide an explicit reason and next action.

When batch color preparation is requested, `reference` and `actual` retain the
original supplied image records. `comparisonInputs` identifies the transformed
images actually used for pixel metrics and visual layers. Include normalization
manifests and assumptions in `preparation`; display the color contract and offer
separate original downloads. Do not call comparison copies original screenshots.

## Comparability

Report capture validity separately from visual findings:

~~~yaml
comparability:
  valid: false
  issues:
    - code: FONT_NOT_READY
      message: Target font was not loaded before capture
~~~

Common issue codes include:

- REFERENCE_UNAVAILABLE
- TARGET_UNAVAILABLE
- WRONG_ROUTE_OR_STATE
- AUTHENTICATION_BLOCKED
- DIMENSION_MISMATCH
- ORIENTATION_MISMATCH
- FONT_NOT_READY
- ASSET_NOT_READY
- DEVICE_METADATA_MISSING
- MASK_INVALID
- THRESHOLD_UNRESOLVED
- REFERENCE_CHANGED
- ENVIRONMENT_CHANGED

When comparability.valid is false, verdict must be INCONCLUSIVE.
Measurement-only results may have comparable images (`valid=true`) while their
verdict remains INCONCLUSIVE because no acceptance threshold was supplied. Label
them as descriptive measurement and show their generated overlay/diff artifacts.

## Required Artifacts

For each valid case, retain whenever available:

- reference image;
- actual target image;
- normalized reference and target, if normalization was required;
- 50/50 overlay;
- raw diff before masks;
- effective diff after masks;
- a display-only \`comparison-board.png\` containing Reference / Figma, Actual /
  Target, Overlay, and Diff;
- a \`comparison-board.json\` manifest describing panel source dimensions and any
  presentation-only thumbnail scaling;
- optional crops for important findings;
- result JSON from the deterministic comparator.

For each artifact, record an absolute path or URI, pixel dimensions, hash, and
whether any crop, normalization, or privacy processing was applied.

Do not overwrite original captures.

## Inline Visual Evidence

The final human-readable response must embed the comparison board when it exists;
returning only a path is insufficient:

~~~markdown
![UI comparison board](/absolute/path/to/case/comparison-board.png)
~~~

The board is a presentation artifact only. It may contain aspect-ratio-preserving
thumbnails, but all verdicts, metrics, and findings must reference original-size
images and the machine-readable result.

Rendering policy:

- Single case: embed its board, then link individual artifacts.
- Small suite: embed every required-case board.
- Large suite: embed FAIL and INCONCLUSIVE boards; link every PASS board and keep
  all cases in JSON.
- INCONCLUSIVE case: show available source/target images only with an explicit
  invalid-comparison label.
- UI Fix: embed both before and after boards and state the unchanged comparison
  contract beside them.

If the execution host cannot render local images, provide absolute paths and say
that inline rendering was unavailable. Do not silently omit visual evidence.

## Metrics

Report raw values and their resolved thresholds. Include:

- pixel difference ratio before and after masks;
- mean and maximum channel delta;
- changed-pixel bounding box;
- masked pixel count and ratio;
- geometry offsets, dimensions, spacing, alignment, and wrapping when observable;
- optional perceptual metrics when a trustworthy tool is available;
- independent results for critical regions.

Global metrics cannot overrule a failed critical region. Perceptual scores help
with antialiasing and shadows but do not replace layout or state inspection.

Raw/effective pixel metrics mean before/after masks, both after any explicitly
declared color preparation. They are not a comparison of encoded versus sRGB
images. Keep color preparation unchanged when verifying a previous finding.

## Findings

~~~yaml
findings:
  - id: F-001
    category: layout
    severity: major
    region: bottom-action
    observation: Button top edge is 8 CSS px lower than the reference
    evidence:
      artifact: /absolute/path/diff.png
    hypothesis:
      text: Container may include duplicate safe-area padding
      confidence: medium
~~~

Categories:

- layout
- typography
- color
- asset
- responsive
- platform
- state
- interaction

Severities:

- blocker: prevents a trustworthy or usable implementation;
- major: clearly violates a primary layout, state, or visual requirement;
- minor: localized polish difference without major semantic impact.

Keep observation, hypothesis, and recommendation separate. Never write a suspected
root cause as confirmed without source or runtime evidence.

## Recommendations

~~~yaml
recommendations:
  - findingId: F-001
    priority: P1
    proposedChange: Remove duplicated bottom safe-area padding
    likelyTargets:
      - CheckoutFooter
    impact:
      platforms: [web, ios]
      relatedCases:
        - checkout-web-375-default
    risks:
      - May affect sticky footer behavior
    validation:
      - Recapture the original case
      - Run both small-screen cases
~~~

Describe the likely ownership layer, concrete change, impact, risk, and exact
verification. Do not stop at "adjust CSS."

When source is unavailable, identify DOM/computed-style/design/platform symptoms
without inventing source files. A supplied native screenshot without source or a
live environment supports recommendations, not a verified fix.

## UI Review Output

UI Review:

- remains read-only;
- reports verdicts, evidence, findings, hypotheses, and recommendations;
- sets closure.status to NOT_APPLICABLE unless a prior report is being rechecked;
- never updates code, fixtures, masks, thresholds, or baselines.

When rechecking a previous report in UI Review, map each previous finding to:

- RESOLVED
- PARTIALLY_RESOLVED
- UNRESOLVED
- CANNOT_VERIFY

List new findings separately as NEW_REGRESSION.

## UI Fix Output

UI Fix must retain initial and final evidence:

~~~yaml
closure:
  status: VERIFIED_CLOSED
  initialVerdict: FAIL
  finalVerdict: PASS
  referenceUnchanged: true
  environmentUnchanged: true
  contractChanges: []
  changes:
    files: []
    summary: ...
  validations:
    affectedCases: []
    engineeringChecks: []
  resolvedFindings: []
  remainingFindings: []
  regressions: []
~~~

Closure statuses:

- NOT_APPLICABLE: ordinary UI Review;
- NO_CHANGE_REQUIRED: UI Fix started with a valid PASS;
- VERIFIED_CLOSED: unchanged contract, final PASS, and no related regression;
- OPEN: valid visual failures remain;
- AWAITING_RECAPTURE: a change exists but required new target evidence is missing;
- INCONCLUSIVE: final evidence or environment is invalid.

VERIFIED_CLOSED requires all of:

1. Identical approved reference for initial and final capture.
2. Same declared environment, viewport/device, state, crop, masks, and thresholds.
3. Original required case finishes PASS.
4. Related required cases have no new FAIL or INCONCLUSIVE result.
5. The result was not achieved through baseline replacement, mask expansion,
   threshold loosening, or state substitution.

A smaller diff that still exceeds the contract remains OPEN.

## Batch Summary

For multiple cases, summarize:

- PASS, FAIL, and INCONCLUSIVE by platform, viewport/device, state, and theme;
- blocker, major, and minor finding counts;
- shared root causes such as tokens, fonts, common components, and safe areas;
- a deduplicated repair order;
- UI Fix before/after suite verdicts;
- native screenshots or other evidence still required.

Do not discard valid cases because another case was blocked.

## Privacy and Integrity

- Exclude credentials, cookies, tokens, authorization headers, and production
  personal data from reports.
- Prefer test fixtures for avatars, messages, orders, and payment data.
- Record privacy masks in the same mask audit as visual masks.
- Never alter evidence images except declared crop, normalization, mask
  visualization, overlay, and diff generation.
- Treat baseline updates, threshold changes, and mask expansion as separate
  approval actions outside UI Fix.
