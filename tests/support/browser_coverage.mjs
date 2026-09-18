import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '../..');
const outputPath = process.argv.includes('--output') ? process.argv[process.argv.indexOf('--output') + 1] : path.join(ROOT, 'coverage', 'browser-coverage.json');
const port = 5007;
const baseUrl = `http://127.0.0.1:${port}`;

function waitForServer(url, timeoutMs = 30000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const tryFetch = async () => {
      try {
        const response = await fetch(url, { signal: AbortSignal.timeout(2500) });
        if (response.ok) {
          // Consume the probe response before resolving. Node's undici parser
          // can fail with "assert(!this.paused)" when a response is left
          // unread while Playwright starts its own network activity.
          await response.arrayBuffer();
          resolve();
          return;
        }
      } catch {
        // retry
      }
      if (Date.now() - start > timeoutMs) {
        reject(new Error(`Server did not start on ${url} within ${timeoutMs}ms`));
        return;
      }
      setTimeout(tryFetch, 500);
    };
    tryFetch();
  });
}

async function main() {
  const env = {
    ...process.env,
    FLASK_ENV: 'testing',
    SECRET_KEY: 'browser-coverage-secret',
    WTF_CSRF_ENABLED: 'False',
    TEST_DATABASE_URL: 'sqlite:///:memory:',
  };

  const child = spawn('python', ['-m', 'flask', '--app', 'factory', 'run', '--host', '127.0.0.1', '--port', String(port)], {
    cwd: ROOT,
    env,
    stdio: 'ignore',
  });

  try {
    await waitForServer(baseUrl);

    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
    const page = await context.newPage();

    await page.coverage.startJSCoverage({ resetOnNavigation: false, reportAnonymousScripts: true });
    for (const route of ['/', '/login', '/register']) {
      await page.goto(`${baseUrl}${route}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(300);
      if (route === '/login') {
        await page.locator('input[name="username"]').fill('coverage-player');
        await page.locator('input[name="password"]').fill('not-the-password');
        const toggle = page.locator('#togglePassword');
        if (await toggle.count()) {
          await toggle.click();
          await toggle.click();
        }
        await page.locator('input[name="username"]').press('Tab');
      } else if (route === '/register') {
        await page.locator('input[name="username"]').fill('coverage-player');
        await page.locator('input[name="birthdate"]').fill('2000-01-01');
        await page.locator('select[name="playstyle"]').selectOption({ index: 1 });
        await page.locator('input[name="password"]').fill('StrongPass123!');
        await page.locator('input[name="confirm_password"]').fill('StrongPass123!');
        const captcha = page.locator('#captchaImage');
        if (await captcha.count()) {
          await captcha.click();
        }
        await page.locator('button[onclick*="togglePasswordVisibility"]').first().click();
        await page.locator('button[onclick*="togglePasswordVisibility"]').first().click();
      }
    }

    const rawCoverage = await page.coverage.stopJSCoverage();
    let totalBytes = 0;
    let executedBytes = 0;
    let scripts = 0;

    for (const item of rawCoverage) {
      const url = item.url || '';
      const source = item.source || '';
      if (!url && !source) {
        continue;
      }
      scripts += 1;
      // Playwright exposes V8 ranges below each function.  Reading
      // item.ranges (the old CDP shape) silently produced zero-byte reports.
      const ranges = (item.functions || [])
        .flatMap((fn) => fn.ranges || [])
        .map((range) => ({
          start: Number(range.startOffset ?? 0),
          end: Number(range.endOffset ?? 0),
          executed: (range.count ?? 0) > 0,
        }))
        .filter((range) => range.end > range.start)
        .sort((left, right) => left.start - right.start || left.end - right.end);

      // V8 offsets are UTF-16 offsets, while coverage is reported in bytes.
      // Convert each merged interval against the source so non-ASCII scripts
      // are measured accurately rather than treating code units as bytes.
      const sourceBytes = (start, end) => Buffer.byteLength(source.slice(start, end), 'utf8');
      totalBytes += source ? Buffer.byteLength(source, 'utf8') : 0;
      // A top-level V8 range covers the complete script with count=1, while
      // nested ranges with count=0 identify unexecuted blocks.  Resolve each
      // source segment to its most-specific range before summing executed
      // bytes; simply unioning all count=1 ranges would report 100% always.
      const boundaries = [...new Set(ranges.flatMap((range) => [range.start, range.end]))].sort((a, b) => a - b);
      const executedSegments = [];
      for (let index = 0; index < boundaries.length - 1; index += 1) {
        const start = boundaries[index];
        const end = boundaries[index + 1];
        const candidates = ranges.filter((range) => range.start <= start && range.end >= end);
        if (!candidates.length) {
          continue;
        }
        candidates.sort((left, right) => (left.end - left.start) - (right.end - right.start));
        if (candidates[0].executed) {
          executedSegments.push({ start, end });
        }
      }
      executedBytes += executedSegments
        .reduce((sum, range) => sum + sourceBytes(range.start, range.end), 0);
    }

    const percent = totalBytes > 0 ? (executedBytes / totalBytes) * 100 : (scripts > 0 ? 0 : 100);
    const result = {
      source: 'playwright chromium js coverage',
      pages_visited: ['/', '/login', '/register'],
      percent: Number(percent.toFixed(2)),
      total_bytes: totalBytes,
      executed_bytes: executedBytes,
      scripts,
      raw_coverage: rawCoverage,
    };

    await fs.mkdir(path.dirname(outputPath), { recursive: true });
    await fs.writeFile(outputPath, JSON.stringify(result, null, 2), 'utf-8');
    console.log(JSON.stringify({
      source: result.source,
      percent: result.percent,
      total_bytes: result.total_bytes,
      executed_bytes: result.executed_bytes,
      scripts: result.scripts,
    }, null, 2));

    await browser.close();
  } finally {
    child.kill('SIGTERM');
    await delay(1000);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
