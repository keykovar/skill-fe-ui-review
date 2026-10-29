/** Collect live or fixture evidence through an existing Ego Browser Page. */
import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';

export async function captureWeb(page, config, outputDir) {
  if (!['live', 'fixture'].includes(config.strategy)) throw new Error('strategy must be live or fixture');
  const url = new URL(config.url);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error('An HTTP URL without credentials is required');
  if (config.strategy === 'fixture' && !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)) throw new Error('Fixture capture must use an isolated local server');
  if (config.strategy === 'fixture' && (!config.fixture?.id || !config.fixture?.reusedComponents?.length || !config.code?.revision)) throw new Error('Fixture identity, real component paths and code revision are required');
  if (!config.readySelector) throw new Error('An expected-state readySelector is required');
  const { width, height } = config.environment.viewport;
  if (![width, height, config.environment.dpr].every(value => Number.isFinite(value) && value > 0)) throw new Error('Positive viewport and DPR are required');
  try { if ((await fs.readdir(outputDir)).length) throw new Error('Capture output directory must be new or empty'); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  await fs.mkdir(outputDir, { recursive: true });
  const receiptPath = path.join(outputDir, 'capture.json');
  try { await fs.access(receiptPath); throw new Error('Existing capture evidence must not be overwritten'); }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  const issues = [];
  await page.cdp('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: config.environment.dpr, mobile: false });
  if (config.environment.locale) await page.cdp('Emulation.setLocaleOverride', { locale: config.environment.locale });
  if (config.environment.locale) await page.cdp('Emulation.setUserAgentOverride', { userAgent: await page.evaluate(() => navigator.userAgent), acceptLanguage: config.environment.locale });
  if (config.environment.timezone) await page.cdp('Emulation.setTimezoneOverride', { timezoneId: config.environment.timezone });
  await page.cdp('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }, { name: 'prefers-color-scheme', value: 'light' }] });
  try {
    if (config.navigate !== false) await page.goto(config.url);
    else {
      const current = new URL(await page.url());
      if (current.origin !== url.origin || current.pathname !== url.pathname) throw new Error('CURRENT_ROUTE_MISMATCH');
    }
    await page.waitForFunction(({ selector, text }) => [...document.querySelectorAll(selector)].some(node => (!text || node.textContent.trim() === text) && node.getBoundingClientRect().width > 0 && node.getBoundingClientRect().height > 0), { selector: config.readySelector, text: config.readyText }, { timeout: config.timeout ?? 20000 });
  } catch (error) {
    issues.push({ code: 'WRONG_ROUTE_OR_STATE', message: `Navigation or expected-state wait failed (${error.code ?? error.name ?? 'Error'}).` });
  }
  // Stabilization is declared in the receipt; no content, layout or application state is changed.
  await page.evaluate(() => {
    const style = document.createElement('style');
    style.dataset.uiReviewStabilization = 'true';
    style.textContent = '*,*::before,*::after{animation-play-state:paused!important;transition:none!important;caret-color:transparent!important;scroll-behavior:auto!important}';
    document.head.append(style);
    for (const animation of document.getAnimations()) { animation.pause(); animation.currentTime = 0; }
  });
  try {
    await page.waitForFunction(() => document.fonts.status === 'loaded' && [...document.images].filter(image => image.getBoundingClientRect().width && image.getBoundingClientRect().height).every(image => image.complete && image.naturalWidth > 0), undefined, { timeout: config.timeout ?? 20000 });
  } catch {
    issues.push({ code: 'RESOURCE_NOT_READY', message: 'Fonts or visible images were not ready.' });
  }
  const observed = await page.evaluate(({ selector, readyText, forbiddenTexts }) => {
    const el = [...document.querySelectorAll(selector)].find(node => (!readyText || node.textContent.trim() === readyText) && node.getBoundingClientRect().width > 0 && node.getBoundingClientRect().height > 0);
    const rect = el?.getBoundingClientRect();
    const front = rect && document.elementFromPoint(Math.max(0, Math.min(innerWidth - 1, rect.x + rect.width / 2)), Math.max(0, Math.min(innerHeight - 1, rect.y + rect.height / 2)));
    return {
      viewport: { width: innerWidth, height: innerHeight }, dpr: devicePixelRatio,
      locale: navigator.language, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      userAgent: navigator.userAgent, fontsReady: document.fonts.status === 'loaded',
      targetPresent: Boolean(el && rect?.width && rect?.height),
      targetUnobscuredAtCenter: Boolean(el && (front === el || el.contains(front))),
      blockedBy: forbiddenTexts.filter(text => [...document.querySelectorAll('h1,h2,h3,h4,[role=dialog]')].some(node => node.textContent.includes(text) && node.getBoundingClientRect().width && getComputedStyle(node).visibility !== 'hidden')),
      fixtureId: document.querySelector('[data-ui-review-fixture]')?.getAttribute('data-ui-review-fixture') ?? null,
    };
  }, { selector: config.readySelector, readyText: config.readyText, forbiddenTexts: config.forbiddenTexts ?? [] });
  if (observed.viewport.width !== width || observed.viewport.height !== height || observed.dpr !== config.environment.dpr) issues.push({ code: 'CAPTURE_ENVIRONMENT_MISMATCH', message: 'Observed viewport or DPR differs from the requested capture contract.' });
  if (!observed.targetPresent || !observed.targetUnobscuredAtCenter || observed.blockedBy.length) issues.push({ code: 'WRONG_ROUTE_OR_STATE', message: 'The expected target is absent, obscured, or a declared blocking state is visible.' });
  if (config.strategy === 'fixture' && observed.fixtureId !== config.fixture.id) issues.push({ code: 'FIXTURE_ID_MISMATCH', message: 'The rendered fixture does not match the declared identity.' });
  const rawPath = path.join(outputDir, 'actual-private.png');
  await page.screenshot({ path: rawPath });
  const first = await fs.readFile(rawPath);
  const secondPath = path.join(outputDir, 'stability-private.png');
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  await page.screenshot({ path: secondPath });
  const second = await fs.readFile(secondPath);
  const pngSize = bytes => bytes.length >= 24 && bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])) ? { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) } : null;
  const expectedPixelSize = { width: Math.round(width * config.environment.dpr), height: Math.round(height * config.environment.dpr) };
  const actualPixelSizes = [pngSize(first), pngSize(second)];
  if (actualPixelSizes.some(size => !size || size.width !== expectedPixelSize.width || size.height !== expectedPixelSize.height)) issues.push({ code: 'CAPTURE_PIXEL_SIZE_MISMATCH', message: 'Screenshot dimensions differ from viewport × DPR; no resizing was performed.' });
  const hash = bytes => createHash('sha256').update(bytes).digest('hex');
  const stable = hash(first) === hash(second);
  if (!stable) issues.push({ code: 'CAPTURE_UNSTABLE', message: 'Two consecutive captures differ; no best sample was selected.' });
  const valid = issues.length === 0;
  const publish = valid && config.publish === true;
  let publicPath = null;
  if (publish) { publicPath = path.join(outputDir, 'actual.png'); await fs.copyFile(rawPath, publicPath); }
  const receipt = {
    schemaVersion: 1, capturedAt: new Date().toISOString(),
    collection: { strategy: config.strategy, subjectId: config.subjectId, fixture: config.fixture ?? null, code: config.code ?? null },
    target: { type: 'web', platform: 'web', url: config.url, ...(publicPath ? { path: publicPath } : {}) },
    requestedEnvironment: config.environment,
    environment: observed, capture: { valid, reason: issues.map(issue => issue.message).join(' '), expectedPixelSize, actualPixelSizes, navigationPerformed: config.navigate !== false, stabilitySamples: 2, stable, rawImagePrivate: rawPath, sha256: hash(first), publicImage: publicPath, stabilization: 'CSS animations paused at time zero; transitions/caret disabled; no layout or content changes' },
    issues,
  };
  await fs.writeFile(receiptPath, JSON.stringify(receipt, null, 2) + '\n');
  return receipt;
}
