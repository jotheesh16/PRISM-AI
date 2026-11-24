// Invoked by test_browser.py against a temporary workspace.
const { chromium } = require(process.env.PRISM_PLAYWRIGHT);
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(process.env.PRISM_TEST_URL + '/#research');
    await page.locator('#files').setInputFiles({name: 'browser-note.txt', mimeType: 'text/plain', buffer: Buffer.from('Browser upload integration test document.')});
    await page.waitForURL('**/#library');
    await page.getByText('browser-note.txt', {exact: true}).waitFor();
    await page.getByRole('button', {name: 'Research chat', exact: true}).click();
    const question = page.getByLabel('Research question', {exact: true});
    await question.fill('Quote the passage containing "revenue"');
    await page.getByRole('button', {name: 'Ask question', exact: true}).click();
    await page.locator('.message').waitFor();
    assert.match(await page.locator('.message').innerText(), /42 million/);
    await question.fill('Unsubmitted input to clear');
    await page.getByRole('button', {name: 'Clear conversation', exact: true}).click();
    await page.waitForFunction(() => document.querySelectorAll('.message').length === 0 && document.querySelector('#question')?.value === '');
    await page.reload();
    await page.getByLabel('Research question', {exact: true}).waitFor();
    assert.equal(await page.locator('.message').count(), 0);
    await page.getByRole('button', {name: 'History', exact: true}).click();
    await page.getByRole('button', {name: 'Open conversation', exact: true}).click();
    await page.locator('.message').waitFor();
    await page.getByLabel('Research question', {exact: true}).fill('Quote the passage containing "audited"');
    await page.getByRole('button', {name: 'Ask question', exact: true}).click();
    await page.waitForFunction(() => document.querySelectorAll('.message').length === 2);
    await page.reload();
    await page.waitForFunction(() => document.querySelectorAll('.message').length === 2);
    await page.getByRole('button', {name: 'History', exact: true}).click();
    assert.match(await page.locator('#main').innerText(), /2 messages/);
    if (process.env.PRISM_LIVE_TEST === '1') {
      await page.getByRole('button', {name: 'Research chat', exact: true}).click();
      await page.getByLabel('Research question', {exact: true}).fill('What was revenue in 2025?');
      await page.getByRole('button', {name: 'Ask question', exact: true}).click();
      await page.waitForFunction(() => document.querySelectorAll('.message').length === 3);
      assert.match(await page.locator('.message').last().innerText(), /42 million/);
      assert.ok(await page.locator('.message').last().locator('[data-cite]').count());
      await page.getByRole('button', {name: 'Comparisons', exact: true}).click();
      await page.getByLabel('Comparison question').fill('What was revenue in 2025?');
      await page.getByRole('button', {name: 'Compare reports', exact: true}).click();
      await page.waitForFunction(() => !document.querySelector('#compare button')?.disabled);
      assert.match(await page.locator('.message').last().innerText(), /42 million/);
      assert.ok(await page.locator('.message').last().locator('[data-cite]').count());
      await page.getByRole('button', {name: 'Evaluation', exact: true}).click();
      await page.getByLabel('Questions', {exact: true}).fill('What was revenue in 2025?');
      await page.getByRole('button', {name: 'Run evaluation', exact: true}).click();
      await page.locator('.results div.answer').waitFor();
      assert.match(await page.locator('.results div.answer').innerText(), /42 million/);
      assert.ok(await page.locator('.results [data-cite]').count());
      console.log('PASS: live model answers and citation buttons visible in Chat, Comparisons and Evaluation');
    }
    assert.deepEqual(errors, []);
    console.log('PASS: ask, clear draft/messages, reload, history, reopen, continue, persistence; no browser errors');
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e); process.exitCode = 1; });
