---
name: fe-ui-review
description: Review implemented UI against explicit Figma nodes or reference screenshots, produce evidence-backed visual findings and repair plans, and optionally apply authorized UI fixes with mandatory recapture and re-verification. Use when comparing Figma with web pages or supplied iOS/Android screenshots, auditing one or many screens, checking visual fidelity or 1:1 claims, diagnosing layout, typography, color, asset, responsive, platform, or state differences, rechecking prior UI fixes, or explicitly asking Codex to fix UI differences. UI Review is read-only by default; UI Fix requires clear modification authorization.
---

# FE UI Review

## Purpose

Run a reproducible visual acceptance workflow:

~~~text
map cases -> collect references -> capture targets -> validate comparability
-> compare -> diagnose -> propose repairs -> optionally fix -> recapture
~~~

Treat "1:1" as acceptance within the recorded device, renderer, state, comparison
region, masks, and thresholds. Never promise universal zero-pixel difference across
Web, iOS, and Android.

Reuse available Figma design-to-code capabilities for design context and assets.
Reuse available browser or Playwright capabilities for web capture. This skill owns
case mapping, evidence integrity, comparison, diagnosis, reporting, and the
authorized fix loop; it does not duplicate browser automation or Figma code
generation.

## Load References

Before acting:

1. Read [case-contract.md](references/case-contract.md) for every run.
2. Read [report-contract.md](references/report-contract.md) before producing a
   report or entering UI Fix.
3. Read [platform-adapters.md](references/platform-adapters.md) for every target
   type used by the suite.
4. For automated local batching, device presets, or the offline HTML viewer, read
   [batch-runner.md](references/batch-runner.md).
5. For web collection or deterministic component fixtures, read
   [web-collection.md](references/web-collection.md).

Keep platform-specific details in references. Keep the core workflow here.

## Select One Mode

### UI Review

Use UI Review by default for requests to compare, review, audit, inspect,
diagnose, verify, or provide a repair plan.

UI Review is read-only. Do not modify source code, configuration, fixtures,
thresholds, masks, screenshots, or baselines.

When a previous report is supplied, rerun the same cases and report closure
statuses. This is still UI Review, not a third mode.

### UI Fix

Use UI Fix only when the user explicitly asks to modify, fix, adjust, implement,
or align the UI. A request for a "fix plan" alone remains UI Review.

UI Fix includes mandatory re-verification. Do not consider a change complete
until the original cases are recaptured under the same contract and related cases
are checked for regressions.

Platform, case count, viewport, state, and strictness are parameters, not modes.
Do not introduce Quick, Deep, Batch, Web, iOS, Android, or Verify modes.

Web capture has two strategies: `live` (the real site and session) and `fixture`
(real implementation components with fixed test inputs). Keep their cases and
verdicts separate. Fixture success never closes a blocked or failing live case.
Preparing a new fixture or adapter is a file change requiring task authorization;
UI Review may consume an existing fixture without editing it. Never rewrite the
UI from Figma to manufacture the implementation under review.

## Choose Tools Safely

- For Figma references, use the Figma tools and prerequisite skills exposed by
  the current environment. Fetch the exact mapped node screenshot. Fetch design
  context only when diagnosis or implementation needs structure, variables,
  components, or assets.
- For web targets, use an available browser or Playwright tool. Prefer an
  existing authenticated session when the user has authorized it.
- For supplied screenshots, preserve the original file and record its provenance.
- For UI Fix, inspect repository instructions, worktree state, source ownership,
  and existing UI conventions before editing.
- Never install dependencies automatically. Discover existing tools first and
  report a missing capability when none is available.
- Never use image generation or image editing to manufacture comparison evidence.

Do not guess unavailable tool results. Separate captured evidence, source evidence,
and inference.

## Build the Case Suite

Map every case explicitly as:

~~~text
one reference x one target x one platform x one viewport/device x one state
~~~

Use one stable ID per case. Do not create an implicit Cartesian product when the
user supplies multiple Figma nodes, pages, devices, or states.

The minimum usable input is an exact Figma node or reference image plus a target
URL or screenshot. Record viewport or device, locale, theme, state, comparison
region, masks, and thresholds whenever known.

Infer a non-critical value only when the evidence supports it, and disclose the
assumption. If mapping, authentication, page state, dimensions, fonts, or
thresholds prevent a trustworthy verdict, continue collecting useful evidence but
mark the case INCONCLUSIVE.

Never persist credentials, cookies, tokens, or production user data in the case,
artifacts, or report.

## Run UI Review

For each case:

1. **Preflight** — Validate reference access, target access, mapping, environment,
   state setup, comparison region, masks, and threshold source.
2. **Collect reference** — Capture the exact Figma node or preserve the supplied
   reference. Record node/version or capture time, pixel dimensions, and hash.
3. **Capture target** — Fix viewport/device, DPR or scale, locale, timezone, theme,
   font scale, data, and state. Wait for fonts, images, and required content.
4. **Stabilize** — Disable or freeze animations, cursors, clocks, randomness,
   carousels, remote data, and other dynamic content. Prefer deterministic
   fixtures over masks.
5. **Validate comparability** — Confirm dimensions, orientation, crop, coordinate
   mapping, state, and resources. Never silently resize, stretch, or auto-align an
   invalid capture to make it pass.
6. **Compare** — Produce reference, actual, overlay, diff, raw metrics, effective
   metrics after masks, and region-level evidence.
   Inspect ICC metadata first. For an explicit sRGB comparison, use
   [normalize_srgb.py](scripts/normalize_srgb.py) on separate copies and retain
   its manifests; see the web collection reference. Do not compare differently
   encoded color values as if they directly measured visual color fidelity.
7. **Diagnose** — Classify findings and separate observed facts from root-cause
   hypotheses and recommendations.
8. **Build visual evidence** — Create a comparison board containing Reference /
   Figma, Actual / Target, Overlay, and Diff. The board is display-only; it must
   never replace or overwrite the original captures.
9. **Report** — Produce per-case results plus batch totals, shared root causes,
   repair order, evidence boundaries, and unverified areas.

Capture failure is not a visual failure. Use INCONCLUSIVE for invalid evidence.

## Use the Deterministic Image Comparator

When both normalized images are local and Pillow is already available, run
[compare_images.py](scripts/compare_images.py). Supply explicit thresholds; do not
invent a universal pass threshold.

~~~bash
python3 scripts/compare_images.py \
  --reference /absolute/reference.png \
  --actual /absolute/actual.png \
  --output-dir /absolute/artifacts/case-id \
  --channel-threshold 0 \
  --max-diff-ratio 0
~~~

Add one or more explicit masks with:

~~~text
--mask x,y,width,height
~~~

The comparator exits 0 for PASS, 1 for FAIL, and 2 for INCONCLUSIVE or invalid
input. Treat its JSON and images as pixel evidence, not as a substitute for
geometry, DOM, accessibility, interaction, or state analysis.

For an explicit suite of prepared captures, use [run_suite.py](scripts/run_suite.py)
with a JSON manifest. It reuses this comparator, expands generic device presets,
continues past blocked cases, and writes JSON, Markdown, and a portable HTML viewer.
Use `--list-devices` to inspect presets and `--validate-only` to check configuration
without creating artifacts. Read the batch reference for the executable subset.
The runner never collects remote pages or claims complete UI acceptance; finish
the agent review of state, geometry, critical regions, and other required checks.

Without an acceptance threshold, use `--measure-only` on the comparator or
`thresholds.measurementOnly=true` with an explicit pixel channelDelta in a suite.
This generates valid diagnostic images and metrics but returns INCONCLUSIVE.
It is a measurement parameter, not a new review mode.

Batch color preparation is also a parameter: set `preparation.colorSpace=srgb`
to generate ICC-aware comparison copies with source hashes and manifests. The
default `encoded` performs no color transform. Reports preserve original sources,
label comparison copies, and expose both for download. Read the batch reference
before using this option, and keep it unchanged during UI Fix verification.

## Display Visual Evidence

Always show visual evidence in the final response when image artifacts exist; do
not only provide filesystem paths.

For every valid case, embed the generated comparison board with an absolute path:

~~~markdown
![UI comparison board](/absolute/path/to/case/comparison-board.png)
~~~

Then provide links to the individual reference, actual, overlay, diff, and
machine-readable result artifacts. The board uses thumbnails for presentation
only; all verdicts and metrics must come from the original-size artifacts.

For a single case, show the board inline by default. For a suite, generate one
board per case and show all required cases when the suite is small; for a large
suite, show FAIL and INCONCLUSIVE boards inline and link every PASS board.
Never omit a case from the machine report.

If comparison is INCONCLUSIVE but source images are available, show the available
images with a clear "comparison invalid" label rather than presenting them as
passing evidence. If the host cannot render local images, provide absolute
paths and state that inline rendering was unavailable.

For UI Fix, show before and after comparison boards separately and list the
unchanged reference, environment, threshold, and mask contract beside them.

## Diagnose Findings

Classify findings as layout, typography, color, asset, responsive, platform,
state, or interaction. Assign blocker, major, or minor severity.

For every finding, provide:

- the observed difference and evidence region;
- the affected case or cases;
- the likely cause and confidence;
- the smallest viable repair;
- expected impact and regression surface;
- the exact recapture or engineering check needed.

With source access, cite real components and files. With only a deployed URL or
screenshot, give DOM, computed-style, design-token, or platform-level guidance
without inventing source locations.

Aggregate shared causes such as fonts, tokens, common components, safe-area
handling, and global resets before suggesting page-by-page patches.

## Run UI Fix

Continue from a valid initial review:

1. Confirm explicit write authorization and the editable repository scope.
2. Inspect repository rules, dirty worktree, current implementation, shared
   tokens, and affected components.
3. Preserve user changes and exclude unrelated files.
4. Fix the smallest correct ownership layer: shared token, shared component,
   responsive/platform adapter, then page-local style.
5. Avoid screenshot-specific absolute positioning, unexplained magic numbers,
   broad important overrides, and accessibility regressions.
6. Run focused type, lint, unit, build, or interaction checks as appropriate.
   Report these separately from visual verification.
7. Recapture the original case with the same reference, environment, state,
   crop, masks, and thresholds.
8. Recheck related viewports, states, themes, and platforms affected by the
   ownership layer.
9. Produce Before/After evidence, changed files, engineering checks, resolved
   findings, remaining findings, regressions, and evidence gaps.

Include the before and after boards inline when they exist. Do not claim closure
from a board image; closure still requires the original-size recapture and report
contract.

Do not close a failure by updating the Figma reference, expanding masks, loosening
thresholds, or changing the tested state. If native code was changed but a new
iOS or Android screenshot cannot be captured, use AWAITING_RECAPTURE.

UI Fix never authorizes branch creation, commit, push, deployment, baseline
approval, package installation, or production data mutation.

## Verdicts and Closure

Use exactly these case verdicts:

- **PASS** — Evidence is valid and every required threshold or critical-region
  assertion passes.
- **FAIL** — Evidence is valid and at least one required visual assertion fails.
- **INCONCLUSIVE** — Evidence, environment, mapping, or thresholds are
  insufficient for a trustworthy pass/fail result.

Use the closure statuses defined in the report contract. VERIFIED_CLOSED requires
an unchanged reference and contract, a final PASS, and no new required-case
regression.

## Non-Negotiable Rules

- Keep UI Review read-only and require explicit authorization for UI Fix.
- Never claim visual verification from build, lint, type-check, or source review.
- Never compare a wrong page, login screen, loading state, or stale design as if
  it were the requested UI.
- Never hide crop, masks, inferred values, threshold changes, or environment
  differences.
- Never treat a single similarity percentage as sufficient evidence.
- Never mask core content, prices, actions, errors, or other critical regions.
- Never silently modify baselines, thresholds, or masks.
- Never expose authentication or personal data in artifacts.
- Never promise cross-platform zero-pixel identity.
- Never auto-commit or auto-push.
