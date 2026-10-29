import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { captureWeb } from '../skills/fe-ui-review/scripts/capture_web.mjs';

const config = {
  strategy: 'fixture', url: 'http://127.0.0.1:5188/', readySelector: '[data-ui-review-fixture]',
  environment: { viewport: { width: 390, height: 844 }, dpr: 1 },
  fixture: { id: 'fixed-v1', reusedComponents: ['src/Page.tsx'] }, code: { revision: 'test-revision' },
};
const untouchedPage = new Proxy({}, { get() { throw new Error('Browser must not be touched for rejected input'); } });

test('remote targets cannot be mislabeled as isolated fixture captures', async () => {
  await assert.rejects(captureWeb(untouchedPage, { ...config, url: 'https://example.com/' }, '/unused'), /isolated local server/);
});

test('fixture requires component and code provenance before browser actions', async () => {
  await assert.rejects(captureWeb(untouchedPage, { ...config, fixture: { id: 'missing-components' } }, '/unused'), /real component paths/);
});

test('existing evidence is preserved before any browser action', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ui-capture-contract-'));
  const file = path.join(root, 'capture.json');
  try {
    await fs.writeFile(file, 'original evidence');
    await assert.rejects(captureWeb(untouchedPage, config, root), /new or empty/);
    assert.equal(await fs.readFile(file, 'utf8'), 'original evidence');
  } finally { await fs.rm(root, { recursive: true }); }
});

const onePixelPng = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64');
async function captureWithObservedEnvironment(observed, viewport) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ui-capture-environment-'));
  const evaluations = [undefined, observed, undefined];
  const page = {
    cdp: async () => ({}), goto: async () => {}, waitForFunction: async () => {},
    evaluate: async () => evaluations.shift(),
    screenshot: async ({ path: file }) => fs.writeFile(file, onePixelPng),
  };
  try {
    const receipt = await captureWeb(page, { ...config, environment: { viewport, dpr: 1 }, publish: true }, root);
    return { receipt, files: await fs.readdir(root) };
  } finally { await fs.rm(root, { recursive: true }); }
}

const readyObservation = { viewport: { width: 1, height: 1 }, dpr: 1, targetPresent: true, targetUnobscuredAtCenter: true, blockedBy: [], fixtureId: 'fixed-v1' };

test('lost viewport emulation prevents publishing otherwise stable samples', async () => {
  const { receipt, files } = await captureWithObservedEnvironment({ ...readyObservation, viewport: { width: 2, height: 1 } }, { width: 1, height: 1 });
  assert.equal(receipt.capture.stable, true);
  assert.equal(receipt.capture.valid, false);
  assert.ok(receipt.issues.some(issue => issue.code === 'CAPTURE_ENVIRONMENT_MISMATCH'));
  assert.ok(!files.includes('actual.png'));
});

test('raster size is checked independently from the reported browser viewport', async () => {
  const { receipt, files } = await captureWithObservedEnvironment({ ...readyObservation, viewport: { width: 2, height: 2 } }, { width: 2, height: 2 });
  assert.equal(receipt.capture.valid, false);
  assert.ok(receipt.issues.some(issue => issue.code === 'CAPTURE_PIXEL_SIZE_MISMATCH'));
  assert.deepEqual(receipt.capture.actualPixelSizes, [{ width: 1, height: 1 }, { width: 1, height: 1 }]);
  assert.ok(!files.includes('actual.png'));
});
