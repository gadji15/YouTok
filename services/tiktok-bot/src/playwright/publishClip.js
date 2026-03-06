const fs = require('fs/promises');
const fsSync = require('fs');
const path = require('path');
const { Readable } = require('stream');
const { pipeline } = require('stream/promises');
const { chromium } = require('playwright');

const { loadStorageState, saveStorageState } = require('../storage/cookieStore');

async function ensureLocalClipFile({ clipPath, artifactDir }) {
  if (!/^https?:\/\//i.test(String(clipPath))) {
    await fs.access(clipPath);
    return clipPath;
  }

  const target = path.join(artifactDir || '.', 'clip.mp4');
  await fs.mkdir(path.dirname(target), { recursive: true });

  const res = await fetch(clipPath);
  if (!res.ok || !res.body) {
    throw new Error(`failed_to_download_clip: ${res.status} ${res.statusText}`);
  }

  await pipeline(Readable.fromWeb(res.body), fsSync.createWriteStream(target));

  return target;
}

async function safeScreenshot(page, filePath) {
  try {
    await fs.mkdir(path.dirname(filePath), { recursive: true });
    await page.screenshot({ path: filePath, fullPage: true });
  } catch {
    // ignore
  }
}

async function publishClip({ clipPath, caption, accountId, artifactDir }) {
  clipPath = await ensureLocalClipFile({ clipPath, artifactDir });

  const headless = (process.env.PLAYWRIGHT_HEADLESS || '1') !== '0';

  const existingState = await loadStorageState(accountId);

  const browser = await chromium.launch({ headless });

  try {
    const context = await browser.newContext(existingState ? { storageState: existingState } : {});
    const page = await context.newPage();

    // Minimal session check placeholder.
    // We don't attempt real login automation yet; but we detect likely logged-out state.
    await page.goto('https://www.tiktok.com/', { waitUntil: 'domcontentloaded', timeout: 45000 });
    await safeScreenshot(page, path.join(artifactDir || '.', 'tiktok_home.png'));

    const bodyText = await page.textContent('body');
    const looksLoggedOut = bodyText && /log in|sign in/i.test(bodyText);

    if (looksLoggedOut && !existingState) {
      const err = new Error('not_logged_in: no stored session and TikTok appears to require login');
      err.code = 'NOT_LOGGED_IN';
      throw err;
    }

    // --- Upload flow TODO ---
    // Intentionally conservative: we currently do not automate upload.
    // We still persist storageState so session refreshes are kept.
    void caption;

    const newState = await context.storageState();
    await saveStorageState(accountId, newState);

    await context.close();

    return {
      status: 'stubbed_playwright',
      accountId,
      clipPath,
    };
  } finally {
    await browser.close();
  }
}

module.exports = {
  publishClip,
};
