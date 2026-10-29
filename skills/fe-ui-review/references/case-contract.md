# Case Contract

## Purpose

Define reproducible inputs for Figma-to-implementation visual acceptance. One case
represents one explicit mapping:

~~~text
one Figma node or reference image
x one target page or screenshot
x one platform
x one viewport or device
x one UI state
~~~

Represent multiple pages, devices, themes, locales, or states as separate cases.
Never create an implicit Cartesian product.

## V1 Scope

V1 supports:

- exact Figma node to web URL with automated web capture;
- exact Figma node to a supplied iOS or Android screenshot;
- reference image to web URL or supplied screenshot;
- one case or an explicit case suite;
- UI Review and explicitly authorized UI Fix.

V1 does not promise automated iOS Simulator, Android Emulator, or physical-device
control. Use supplied screenshots when live native capture is unavailable.

## Suite Shape

~~~yaml
schemaVersion: 1
suiteId: checkout-ui
mode: review
defaults:
  environment:
    locale: en-US
    timezone: Asia/Shanghai
    theme: light
    reducedMotion: true
cases:
  - id: checkout-web-390-default
    required: true
    reference: {}
    target: {}
    environment: {}
    state: {}
    capture: {}
    masks: []
    thresholds: {}
~~~

Rules:

- Set mode to review or fix. Mode does not replace explicit write authorization.
- Keep every case ID unique and stable within the suite.
- Expand defaults into each normalized case before capture and record the expanded
  values in the report.
- Changing the Figma node, platform, viewport/device, or state changes the
  contract. Do not silently reuse old evidence.

Cases may select one generic `deviceProfile`. Resolve preset environment values,
then suite defaults, then case overrides; never expand presets into implicit cases.
For the JSON batch runner's supported fields and available profiles, read
[batch-runner.md](batch-runner.md). The runner executes prepared-image pixel checks;
this broader contract still governs the agent's complete visual acceptance.

## Reference

Prefer an exact Figma node:

~~~yaml
reference:
  type: figma
  url: https://www.figma.com/design/FILE/NAME?node-id=123-456
  nodeId: "123:456"
  versionId: optional
  expectedFrame:
    width: 390
    height: 844
~~~

Or use an immutable local reference:

~~~yaml
reference:
  type: image
  path: /absolute/path/reference.png
  logicalSize:
    width: 390
    height: 844
  scale: 3
~~~

Requirements:

- Resolve the exact requested node; do not substitute a nearby frame.
- Record file/node/version when available, capture time, exported pixel size, and
  image hash.
- Keep the same reference throughout UI Fix verification.
- Return INCONCLUSIVE when the reference is inaccessible, invalid, stale relative
  to the requested design, or cannot be mapped to the target dimensions.
- Never update a reference or Figma baseline as part of UI Fix.

## Web Target

~~~yaml
target:
  type: web
  url: https://example.test/checkout
  setup:
    - action: use-existing-session
    - action: navigate
  readyWhen:
    selector: "[data-page-ready='true']"
  captureRegion:
    type: viewport
~~~

Capture region may be viewport, full-page, selector, or an explicit rectangle.

For `live` and `fixture` collection, see [web-collection.md](web-collection.md).
Store provenance in case-level `collection`: strategy, shared subjectId, fixture
identity/reusedComponents/scope, and code revision/dirty status when known.
Create separate case IDs for both strategies; do not substitute fixture evidence
for a live page or infer that the deployed version matches local source.

Requirements:

- Use only URLs accessible through authorized tools and sessions.
- Reuse an authorized session or a project-supported storage state. Do not store
  credentials, cookies, tokens, or headers in the contract.
- Wait for the expected route/state, fonts, images, and required content.
- Freeze animations, transitions, caret blinking, time, randomness, carousels,
  and deterministic network data where possible.
- Return INCONCLUSIVE for authentication blocks, wrong routes, error pages,
  incomplete resources, or incorrect UI state.

## Supplied Screenshot Target

~~~yaml
target:
  type: screenshot
  platform: ios
  path: /absolute/path/checkout-ios.png
  device:
    name: iPhone 15
    osVersion: "18.x"
    orientation: portrait
    logicalWidth: 390
    logicalHeight: 844
    scale: 3
  contentRegion:
    x: 0
    y: 177
    width: 1170
    height: 2355
~~~

Set platform to ios, android, web, or unknown.

Requirements:

- Record screenshot source, original hash, pixel dimensions, direction, and known
  device metadata.
- Prefer an explicit application-controlled content region.
- Do not assume one Figma unit equals one physical screenshot pixel.
- Do not stretch or arbitrarily scale screenshots to improve similarity.
- Allow only declared logical-unit-to-pixel conversion and proportional
  normalization supported by device metadata.
- If UI Fix changes native source but no new screenshot can be captured, keep the
  case open with AWAITING_RECAPTURE.

## Environment and State

~~~yaml
environment:
  viewport:
    width: 390
    height: 844
  dpr: 1
  locale: en-US
  timezone: Asia/Shanghai
  theme: light
  colorScheme: light
  fontScale: 1
  renderer: chromium
  rendererVersion: recorded-at-runtime
  reducedMotion: true

state:
  name: default
  fixture: checkout-default-v2
  frozenTime: "2026-07-24T10:00:00+08:00"
  notes: No modal; cart contains two fixed products
~~~

Fix and record, when applicable:

- viewport, DPR/display scale/density, and orientation;
- renderer/browser, device, OS, and application build;
- locale, timezone, theme, color scheme, and font scale;
- authentication, test fixture, flags, and navigation state;
- time, random values, remote assets, and other dynamic content.

Prefer deterministic fixtures over masks. If state cannot be reproduced, explain
the gap and return INCONCLUSIVE rather than comparing the wrong state.

Color preparation is a separate explicit comparison parameter. The local runner
accepts `preparation.colorSpace=encoded` (default, no transform) or `srgb`
(ICC-aware copies, preserving original files). Record untagged-image assumptions,
original and comparison hashes, and keep this parameter unchanged across a UI Fix
verification. See [batch-runner.md](batch-runner.md) for executable behavior.

## Capture and Coordinate Space

~~~yaml
capture:
  region: app-content
  crop:
    x: 0
    y: 0
    width: 390
    height: 844
    unit: css-px
  waitFor:
    fonts: true
    images: true
    selector: "[data-page-ready='true']"
  stabilitySamples: 2
~~~

Region values:

- full-device: include system-owned regions only when the design includes them;
- app-content: compare the application-controlled area;
- custom: use an explicit crop and coordinate unit.

Record whether coordinates use CSS px, pt, dp, or physical pixels. Dimension,
orientation, or aspect-ratio mismatch is a comparability error. Diagnostic
alignment may be generated separately but must not determine PASS.

## Mask Governance

~~~yaml
masks:
  - id: rotating-banner
    kind: dynamic
    selector: "[data-testid='rotating-banner']"
    reason: Remote campaign content is not deterministic
    owner: checkout-team
    expiresAt: "2026-09-01"
~~~

For supplied screenshots, use an explicit rectangle and record its normalized
coordinate space.

Rules:

- Prefer stable selectors for web masks.
- Require an ID and reason for every mask. Long-lived masks should include owner
  and expiry.
- Never mask critical actions, prices, primary text, errors, or missing content.
- Do not silently create, expand, or move a mask.
- Report mask count, coverage, raw metrics before masks, and effective metrics
  after masks.
- Return INCONCLUSIVE when a mask target is missing, unexpectedly moved, or masks
  make critical UI unverifiable.

## Thresholds

~~~yaml
thresholds:
  source: project-config
  profile: checkout-web
  pixel:
    channelDelta: 8
    maxDiffRatio: 0.002
  geometry:
    maxOffset: 2
  criticalRegions:
    - id: purchase-action
      maxDiffRatio: 0
~~~

Rules:

- Prefer project-owned thresholds, then explicit user thresholds.
- Expand profiles into concrete values in the normalized case and report.
- Never use a hidden universal similarity threshold.
- Do not use a global score as the only gate; evaluate critical regions and
  geometry separately.
- If no trustworthy threshold is available, collect metrics and findings but
  return INCONCLUSIVE rather than declaring PASS.
- The executable suite supports `thresholds.measurementOnly=true` with an explicit
  pixel channelDelta and no maxDiffRatio, producing descriptive images/metrics.
- Exact zero-difference thresholds are valid only when the rendering environment
  is controlled and zero difference is the actual contract.

## Comparability Gate

Before comparison, validate:

- exact reference/target mapping;
- expected page and state;
- reference and target dimensions/orientation;
- declared coordinate conversion and crop;
- renderer/device, locale, theme, font scale, and DPR/scale;
- loaded fonts, images, icons, and required data;
- mask validity and threshold resolution.

Capture problems are evidence problems, not visual regressions.

## Verdict Aggregation

Allow only:

- PASS: valid evidence and every required assertion passes;
- FAIL: valid evidence and at least one required assertion fails;
- INCONCLUSIVE: evidence or contract is insufficient for a trustworthy verdict.

Suite verdict:

- FAIL when any required case is FAIL;
- otherwise INCONCLUSIVE when any required case is INCONCLUSIVE;
- otherwise PASS when every required case is PASS.

Optional-case failures remain visible but do not silently change required-case
semantics.
