# Platform Adapters

## Unified Capture Output

Every target adapter should produce:

~~~yaml
capture:
  rawImage: /absolute/path/actual.png
  pixelSize:
    width: 1170
    height: 2532
  logicalSize:
    width: 390
    height: 844
  logicalUnit: pt
  scale: 3
  insets:
    top: 59
    right: 0
    bottom: 34
    left: 0
  region: app-content
  includesSystemUi: false
  provenance:
    platform: ios
    osVersion: ...
    device: ...
    rendererOrBuild: ...
    locale: en-US
    theme: light
    fontScale: 1
  warnings: []
~~~

Missing metadata may still allow descriptive image analysis, but it prevents
trustworthy geometry mapping or an unqualified visual acceptance verdict.

## Web Adapter

V1 supports live web capture when an available browser or Playwright capability
can access the URL.

Required or discoverable inputs:

- URL and exact route;
- viewport and DPR;
- locale, timezone, theme, color scheme, and reduced-motion setting;
- authorized session or project-supported state preparation;
- expected page state and readiness condition;
- capture region and scroll position.

Capture rules:

- Confirm the expected page rather than assuming successful navigation.
- Wait for document fonts, required images, and target content.
- Disable CSS animations, transitions, caret blinking, and smooth scrolling where
  this does not change the intended state.
- Stabilize time, randomness, remote fixtures, ads, and carousels.
- Capture the same state twice when instability is likely. If samples differ
  materially, return INCONCLUSIVE rather than selecting the best screenshot.
- Exclude browser chrome. Declare whether scrollbars are part of the contract.

For authenticated pages, reuse an authorized existing session. Do not extract or
persist credentials outside the task.

## Image Adapter

V1 supports supplied PNG, JPEG, or WebP captures from any platform when the
available image runtime can decode them.

Preserve:

- original path and hash;
- pixel dimensions and orientation;
- platform, device, OS, and application build when known;
- logical dimensions and scale/density when known;
- whether system UI, keyboard, dialogs, or privacy redaction are present;
- explicit crop and masks.

Do not infer precise pt/dp/CSS-px geometry from a screenshot with missing scale or
device metadata. Do not edit or regenerate the supplied screenshot.

## iOS Adapter

V1 treats iOS as a supplied-image target. It does not promise Simulator or
physical-device automation.

iOS live capture requires:

- macOS and a compatible Xcode runtime;
- a booted Simulator or authorized physical device;
- a Simulator-compatible app, buildable scheme, or signed device build;
- bundle ID and deterministic page-entry method;
- an existing navigation mechanism such as deep links, XCUITest, Maestro, or
  Appium when manual navigation is insufficient.

An App Store link or device IPA alone is not sufficient for Simulator automation.
If live prerequisites are missing, ask for a screenshot and provenance rather than
claiming native runtime validation.

Record:

- logical size in pt and display scale;
- device and OS version;
- orientation, Dynamic Type/font scale, appearance, and locale;
- safe-area insets;
- whether status bar, Home Indicator, keyboard, permission sheets, or other
  system-owned UI are included.

## Android Adapter

V1 treats Android as a supplied-image target. It does not promise Emulator or
physical-device automation.

Android live capture requires:

- Android SDK/platform-tools and an ADB-visible Emulator or authorized device;
- an ABI-compatible APK or a buildable project;
- package/activity or deep-link entry;
- stable state setup and, when needed, Espresso, UIAutomator, Maestro, or Appium.

An AAB is not directly installable as a single APK. A Play Store link alone does
not provide deterministic device navigation.

Record:

- logical size in dp, density, and font scale for sp;
- device, API/OS version, orientation, locale, theme, and navigation mode;
- display cutout and system bar insets;
- whether keyboard, permission dialogs, status bar, or navigation bar are present.

## Coordinate Rules

- Web layout uses CSS px; screenshot pixels are commonly CSS px multiplied by DPR.
- iOS layout uses pt; screenshot pixels are pt multiplied by display scale.
- Android layout uses dp, while text also responds to sp/font scale; screenshot
  pixels depend on density.
- Figma units map to CSS px, pt, or dp only when the target frame and logical
  content region intentionally share those dimensions.
- Never assume one Figma unit equals one screenshot pixel.
- Treat dimension or aspect-ratio mismatch as a configuration problem.
- Use declared, proportional logical-to-physical conversion only.
- Automatic translation, scaling, or edge alignment may produce a diagnostic
  view, but PASS must use the contract's original coordinate mapping.

## Safe Area and System UI

Choose one region:

- full-device when the Figma frame intentionally contains system-owned UI;
- app-content for the application-controlled region;
- custom for an explicit crop.

Rules:

- Dynamic status-bar time, carrier, battery, Home Indicator, and Android
  navigation content may be explicitly masked.
- Do not mask an entire safe area when safe-area placement is being tested.
- Treat keyboard, permission sheets, system pickers, and modal system UI as
  separate states when they are part of acceptance.
- Record every system or privacy mask; never apply one silently.

## Capability Boundary

Generic dimensions and scale presets are available in
[device-profiles.json](../assets/device-profiles.json); usage is documented in
[batch-runner.md](batch-runner.md). Apply them through the existing collector and
record actual capture metadata. Presets do not add browser or native-device
automation and do not establish a verified hardware matrix.

Accurate language:

> Provide reproducible visual acceptance within the declared device, renderer,
> state, comparison region, masks, and thresholds.

Do not promise:

- cross-platform zero-pixel identity;
- automated native navigation from only a store link;
- recovery of pt, dp, DPR, or density from metadata-free images;
- all responsive devices from one Figma frame;
- identical antialiasing across SF Pro, Roboto, browsers, and OS versions;
- stable results from unfrozen video, animation, time, network data, or remote
  assets;
- verified native fixes without a recaptured target.

Prefer platform-specific Figma frames. A shared frame may validate design structure
and intent, but not universal pixel identity.
