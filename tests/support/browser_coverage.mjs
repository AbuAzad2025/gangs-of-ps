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

    await page.coverage.startJSCoverage({ resetOnNavigation: true, reportAnonymousScripts: true });
    for (const route of ['/', '/login', '/register']) {
      await page.goto(`${baseUrl}${route}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(300);
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
      for (const range of item.ranges || []) {
        const start = Number(range.startOffset ?? 0);
        const end = Number(range.endOffset ?? 0);
        const size = Math.max(0, end - start);
        totalBytes += size;
        if ((range.count ?? 0) > 0) {
          executedBytes += size;
        }
      }
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
