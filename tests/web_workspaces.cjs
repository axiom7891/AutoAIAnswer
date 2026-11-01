const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({headless: true, channel: process.env.BROWSER_CHANNEL || undefined});
  try {
    const page = await browser.newPage({viewport: {width: 390, height: 844}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => {
      window.sent = [];
      localStorage.setItem('modelTier:test', 'openrouter-qwen-32b');
      window.copied = '';
      document.execCommand = () => {
        window.copied = document.activeElement.value;
        return true;
      };
      window.WebSocket = class {
        static OPEN = 1;
        constructor() { this.readyState = 1; window.ws = this; setTimeout(() => this.onopen(), 0); }
        send(value) { window.sent.push(JSON.parse(value)); }
      };
      window.deliver = (type, request_id, payload) => window.ws.onmessage({data: JSON.stringify({type, request_id, payload})});
    });
    await page.route('http://assistant.test/**', async route => {
      const url = new URL(route.request().url());
      const name = url.pathname.startsWith('/static/') ? path.basename(url.pathname) : 'index.html';
      await route.fulfill({body: fs.readFileSync(path.join(__dirname, '../ai_screenshot_assistant/web/static', name)),
        contentType: name.endsWith('.js') ? 'application/javascript' : name.endsWith('.css') ? 'text/css' : 'text/html'});
    });
    await page.goto('http://assistant.test/?session_id=test');
    await page.waitForFunction(() => window.sent.length > 0);
    assert.equal(await page.evaluate(() => sent[0].type), 'command.get_model');
    const openrouterOptions = await page.locator('#model-route option[value^="openrouter-"]').evaluateAll(
      nodes => nodes.map(node => node.value));
    assert.deepEqual(openrouterOptions, ['openrouter-qwen-235b', 'openrouter-qwen-27b',
      'openrouter-qwen-flash', 'openrouter-qwen-plus', 'openrouter-glm', 'openrouter-minimax']);
    await page.evaluate(() => deliver('prompt.current', 'prompt', {text: '当前提示词'}));
    assert.equal(await page.locator('#system-prompt').count(), 0);
    assert.equal(await page.evaluate(() => sent.some(x => x.type === 'command.get_prompt')), false);
    await page.locator('#fullscreen-button').click();
    const first = await page.evaluate(() => sent.at(-1).payload.client_request_id);
    await page.locator('#fullscreen-button').click();
    const second = await page.evaluate(() => sent.at(-1).payload.client_request_id);
    assert.notEqual(first, second);
    await page.locator('#question-input').fill('对话问题');
    await page.locator('#ask-button').click();
    const chat = await page.evaluate(() => sent.at(-1).payload.client_request_id);
    await page.evaluate(({first, second, chat}) => {
      deliver('answer.started', chat, {chat: true});
      deliver('answer.delta', chat, {delta: '对话答案'});
      deliver('answer.started', second, {});
      deliver('answer.delta', first, {delta: '过期答案'});
      deliver('answer.delta', second, {delta: '搜题答案'});
      deliver('answer.completed', chat, {result: {text: '对话答案\n```python\nprint(1)\n```'}});
    }, {first, second, chat});
    assert.equal(await page.locator('#output').innerText(), '搜题答案');
    await page.locator('#copy-direct').click();
    assert.equal(await page.evaluate(() => copied), '搜题答案');
    await page.locator('.copy-answer').click();
    assert.equal(await page.evaluate(() => copied), '对话答案\n```python\nprint(1)\n```');
    await page.locator('#clear-direct').click();
    assert.match(await page.locator('#chat-list').innerText(), /对话答案/);
    await page.evaluate(second => deliver('answer.completed', second, {result: {text: '旧答案回流'}}), second);
    assert.doesNotMatch(await page.locator('#output').innerText(), /旧答案/);
    await page.evaluate(() => deliver('device.presence', 'system', {desktop: true, mobiles: 3}));
    assert.equal(await page.locator('#status').innerText(), '电脑已连接 · 3 台手机');
    await page.evaluate(() => {
      deliver('answer.started', 'chat-remote', {chat: true, user_text: '另一台手机的提问', image_count: 0});
      deliver('answer.started', 'chat-remote', {chat: true, user_text: '另一台手机的提问', image_count: 0});
      deliver('answer.delta', 'chat-remote', {delta: '共享回答'});
      deliver('answer.completed', 'chat-remote', {result: {text: '共享回答'}});
    });
    assert.equal(await page.locator('#chat-list').getByText('另一台手机的提问').count(), 1);
    assert.match(await page.locator('#chat-list').innerText(), /共享回答/);
    await page.evaluate(() => {
      const longText = Array.from({length: 80}, (_, index) => `第 ${index + 1} 行：这是一段用于测试自动翻页的长答案。`).join('\n');
      deliver('answer.started', 'fullscreen-long', {});
      deliver('answer.completed', 'fullscreen-long', {result: {text: longText}});
    });
    const pageText = await page.locator('#output-page').innerText();
    const totalPages = Number(pageText.split('/')[1].trim());
    assert.ok(totalPages > 1, `expected multiple answer pages, got ${pageText}`);
    const beforeNext = await page.evaluate(() => document.getElementById('output').scrollTop);
    await page.locator('#output-next').click();
    await page.waitForTimeout(500);
    const afterNext = await page.evaluate(() => document.getElementById('output').scrollTop);
    assert.ok(afterNext > beforeNext, 'next page should scroll down');
    await page.locator('#output-prev').click();
    await page.waitForTimeout(500);
    const afterPrev = await page.evaluate(() => document.getElementById('output').scrollTop);
    assert.ok(afterPrev < afterNext, 'previous page should scroll up');
    await page.locator('#output-auto-enabled').check();
    await page.locator('#output-auto-seconds').fill('3');
    await page.locator('#output-auto-seconds').press('Tab');
    await page.waitForTimeout(3600);
    const autoScrolled = await page.evaluate(() => document.getElementById('output').scrollTop);
    assert.ok(autoScrolled > 0, 'auto paging should advance after the configured seconds');
    await page.locator('#output-auto-enabled').uncheck();
    assert.deepEqual(errors, []);
    console.log('Browser checks passed: replacement, isolation, clear, copy, no mobile prompt, answer paging');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
