// Exercises the original local OASIS acquisition, never the legacy surface archive.
const { chromium } = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
    const page = await context.newPage(); const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    const base = process.env.IMAGING_BASE_URL || 'http://127.0.0.1:8001';
    const login = await context.request.post(`${base}/api/auth/demo-enter`, { data: { username: 'dr.layla' } });
    if (!login.ok()) throw new Error('Local research sign-in failed.');
    await page.goto(base);
    await page.getByRole('button', { name: /Brain Analytics|تحليل صور الدماغ/ }).click();
    await page.getByRole('button', { name: 'Import & processing', exact: true }).click();
    await page.getByRole('heading', { name: 'Import & processing', exact: true }).waitFor();
    const sampleResponse = page.waitForResponse(r => r.url().endsWith('/api/imaging/native/sample') && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Prepare existing original scan', exact: true }).click();
    const sample = await sampleResponse;
    if (!sample.ok()) throw new Error(await sample.text());
    const sampleRun = await sample.json();
    await page.getByText(`Attempt ${sampleRun.id.slice(0, 8)}`, { exact: true }).waitFor();
    await page.getByText('Native display prepared from the original scan. No imported segmentation or mesh used.', { exact: true }).waitFor({ timeout: 90000 });
    await page.getByText('Orientation unverified: voxel axes only. Do not infer anatomical directions from this preview.', { exact: true }).waitFor();
    await page.getByLabel('Native MRI axis 1', { exact: true }).waitFor();
    await page.getByLabel('Native slice axis 1', { exact: true }).fill('100');
    await page.getByLabel('Native slice axis 2', { exact: true }).fill('100');
    await page.getByLabel('Native slice axis 3', { exact: true }).fill('60');
    const output = path.resolve(__dirname, '../../backend/imaging_data/verification'); fs.mkdirSync(output, { recursive: true });
    await page.screenshot({ path: path.join(output, 'native-workflow.png'), fullPage: true });
    let run = await (await context.request.get(`${base}/api/imaging/native/runs/${sampleRun.id}`)).json();
    if (run.status !== 'awaiting_review' || run.producer_version !== 'neurotwin-native/0.1') throw new Error('Expected native preparation with pending review.');
    if (run.stages.filter(s => s.status === 'blocked').length !== 4) throw new Error('Unavailable models should remain blocked.');
    const pixels = await page.getByLabel('Native MRI axis 1', { exact: true }).evaluate(canvas => {
      const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
      return [...pixels].filter((v, i) => i % 4 !== 3 && v > 20).length;
    });
    if (!pixels) throw new Error('Native MRI canvas is empty.');
    // Also exercise the real multipart import path, including the identity confirmation.
    const source = path.resolve(__dirname, `../../backend/imaging_data/native/${run.scan_id}/source`);
    await page.getByLabel('Original MRI files', { exact: true }).setInputFiles([path.join(source, 'original.hdr'), path.join(source, 'original.img')]);
    await page.getByRole('checkbox').check();
    const imported = page.waitForResponse(r => r.url().endsWith('/api/imaging/native/import') && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Import & prepare', exact: true }).click();
    const importResponse = await imported;
    if (!importResponse.ok()) throw new Error(await importResponse.text());
    const newRun = await importResponse.json();
    await page.getByText(`Attempt ${newRun.id.slice(0, 8)}`, { exact: true }).waitFor();
    await page.getByText('Native display prepared from the original scan. No imported segmentation or mesh used.', { exact: true }).waitFor({ timeout: 90000 });
    run = await (await context.request.get(`${base}/api/imaging/native/runs/${newRun.id}`)).json();
    if (run.status !== 'awaiting_review') throw new Error('Uploaded original did not prepare successfully.');
    await page.reload();
    await page.getByRole('button', { name: /Brain Analytics|تحليل صور الدماغ/ }).click();
    await page.getByRole('button', { name: 'Import & processing', exact: true }).click();
    await page.getByText(`Attempt ${run.id.slice(0, 8)}`, { exact: true }).waitFor();
    await page.setViewportSize({ width: 420, height: 900 });
    await page.screenshot({ path: path.join(output, 'native-mobile.png'), fullPage: true });
    if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2)) throw new Error('Native page overflows phone width.');
    if (errors.length) throw new Error(errors.join('\n'));
    console.log(JSON.stringify({ status: 'passed', run: run.id, sourceShape: run.result.source_shape,
      stages: run.stages.map(s => ({ stage: s.id, status: s.status })), nonzeroCanvasValues: pixels, browserErrors: errors }));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
