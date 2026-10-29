# Web collection: live and fixture

Both strategies capture a browser-rendered implementation. Select `live` when the
real page can reach the mapped state; use `fixture` for reproducible visual checks
when account flows or dynamic data prevent it. A fixture complements live evidence.
Do not silently replace the live case, change its required status, or combine the
two screenshots into one verdict.

## Shared collector

`scripts/capture_web.mjs` exports `captureWeb(page, config, outputDir)` for an
existing authorized Ego Browser Page. It does not launch a browser, read cookies,
log in, install packages, or implement a product-specific state flow. Follow the
available browser skill to obtain the Page, retain the task space across rounds,
and finish it when done.

Example in an Ego Browser script:

~~~js
const { captureWeb } = await import('/absolute/skill/scripts/capture_web.mjs');
const task = await taskSpace('project visual review');
const receipt = await captureWeb(task.page('p1'), {
  strategy: 'live',
  subjectId: 'checkout-default',
  url: 'https://example.test/checkout',
  readySelector: '[data-page-ready="true"]',
  forbiddenTexts: ['Subscription Renewal'],
  environment: { viewport: { width: 390, height: 844 }, dpr: 1, locale: 'en-US', timezone: 'Asia/Shanghai' },
  publish: true,
}, '/absolute/new-capture-directory');
console.log(receipt);
~~~

The collector applies viewport/DPR, locale, timezone, light appearance and reduced
motion; records the actual environment; checks the ready element and its center
occlusion; waits for fonts and visible images; pauses animation at time zero; and
captures two samples. Sample mismatch or an unavailable/wrong state is
INCONCLUSIVE. Center occlusion is a useful preflight check, not proof that every
region or interaction is valid. Finish the agent review of critical regions.
The collector also rejects an observed viewport/DPR or PNG raster size that no
longer matches the requested environment; a stable image alone is insufficient.
Use a stable selector rather than production CSS module class names; optional
`readyText` requires an exact visible text match inside that selector (for example,
`readySelector: 'button', readyText: 'Start chatting'`).
Set `navigate=false` only to capture an already-reached authorized state; the
collector checks the current origin and pathname and records that no navigation
was performed. This avoids resetting dynamic data solely to collect a screenshot.

Outputs: `capture.json`, two private raw screenshots, and `actual.png` only when
the capture is valid and `publish=true`. Before enabling publication, ensure test
data can appear in the report. Blocked screenshots remain private by default;
never embed them automatically. The directory must be new or empty. Preserve raw
files and declare any comparison crop in a separate prepared image.

Inspect image color metadata before pixel comparison. Browser PNGs can carry an
ICC profile whose encoded values differ from CSS sRGB even when appearance is
correct. When an sRGB comparison is intended, run `scripts/normalize_srgb.py
--input /absolute/raw.png --output /absolute/new-srgb.png` on both sources before
cropping. It preserves geometry/alpha and original files, embeds sRGB, and writes
a sidecar manifest containing hashes and the transform. An untagged image is
explicitly assumed sRGB; record whether that assumption is justified. Keep the
normalization manifests in `capture.normalization` and disclose this contract
change when comparing with older reports. Never use color normalization to relax
stability checks, silently replace a reference, or close an old finding.
For prepared captures passed to the batch runner, prefer its explicit
`preparation.colorSpace=srgb` option so original and comparison records are kept
separately. When copies were already normalized manually, use `encoded` in the
runner and retain the earlier normalization manifests; do not silently repeat or
change the preparation contract.

Copy receipt `collection`, `target`, and `capture` into an explicit suite case;
use the recorded environment and reference mapping. The batch runner still only
compares prepared captures; it does not collect URLs itself.

## Fixture adapter

A fixture must import actual production components, styles, fonts, assets and
providers. Prefer the original route with mocked APIs when practical. If full App
bootstrapping has side effects, use a component entry and declare the excluded
route lifecycle, auth, subscription, IM, telemetry and navigation behavior.

Fix props/store inputs or intercept test APIs in the isolated local environment.
Keep requests away from real accounts and external mutations. Do not delete live
page elements, alter real storage, fake fonts, replace production styles, or draw
reference screenshots into the implementation. Record any fixture-only container
or device settings; do not adjust them merely to reduce image difference.

Fixture configuration additionally requires:

~~~js
{
  strategy: 'fixture',
  subjectId: 'checkout-default',
  url: 'http://127.0.0.1:5188/',
  fixture: {
    id: 'checkout-default-v1',
    reusedComponents: ['src/pages/checkout/App.tsx'],
    scope: 'component-fixture; auth and real API flow excluded'
  },
  code: { repository: '/absolute/project', revision: 'actual-git-head', worktreeDirty: true }
}
~~~

The local entry must expose `data-ui-review-fixture` with the same ID. Record
component file hashes when a dirty worktree or concurrent edits matter. A local
revision does not identify deployed code unless deployment provenance confirms it.
The collector accepts fixture URLs only on loopback hosts.

Preparing a new adapter is authorized development work, separate from read-only UI
Review. Use existing project tooling; do not install a framework or build a generic
code-to-Mock generator. Page-specific data contracts require a small project adapter.

## Reporting

Use one case ID per strategy, sharing `collection.subjectId` for the same design
and state. Record `collection.strategy`, fixture identity, code revision/dirty
status, data provenance, and limitations. The HTML viewer labels and filters both
strategies; `strategySummary` retains independent verdicts. Unlabeled legacy images
are shown as unrecorded, never inferred as live or fixture.

No accepted pixel threshold: set `thresholds.measurementOnly=true` and
`thresholds.pixel.channelDelta=0` (or an explicitly justified measurement setting),
omit `maxDiffRatio`. Comparable images still produce overlays/diffs and descriptive
metrics, but the result remains INCONCLUSIVE pending an acceptance contract.
