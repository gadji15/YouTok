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

async function safeWriteText(filePath, content) {
  try {
    await fs.mkdir(path.dirname(filePath), { recursive: true });
    await fs.writeFile(filePath, content, 'utf-8');
  } catch {
    // ignore
  }
}

async function maybeClick(page, { name, timeoutMs = 2000 }) {
  try {
    const btn = page.getByRole('button', { name });
    if (await btn.first().isVisible({ timeout: timeoutMs })) {
      await btn.first().click({ timeout: timeoutMs });
      return true;
    }
  } catch {
    // ignore
  }
  return false;
}

async function dismissCommonPopups(page) {
  // Best-effort cookie / consent banners.
  await maybeClick(page, { name: /accept all|accept|agree/i, timeoutMs: 1500 });
  await maybeClick(page, { name: /close|not now/i, timeoutMs: 1500 });
}

async function findFirstLocatorInFrames(page, selector) {
  for (const frame of page.frames()) {
    try {
      const loc = frame.locator(selector);
      if ((await loc.count()) > 0) {
        return loc.first();
      }
    } catch {
      // ignore
    }
  }
  return null;
}

async function waitUntilEnabled(locator, { timeoutMs = 180000 } = {}) {
  const start = Date.now();
  // eslint-disable-next-line no-constant-condition
  while (true) {
    try {
      if (await locator.isEnabled()) return;
    } catch {
      // ignore
    }

    if (Date.now() - start > timeoutMs) {
      throw new Error('timeout_waiting_for_enabled');
    }

    await new Promise((r) => setTimeout(r, 500));
  }
}

async function waitUntilNotEnabled(locator, { timeoutMs = 60000 } = {}) {
  const start = Date.now();
  // eslint-disable-next-line no-constant-condition
  while (true) {
    try {
      if (!(await locator.isEnabled())) return;
    } catch {
      // If the button disappears, that also counts.
      return;
    }

    if (Date.now() - start > timeoutMs) {
      throw new Error('timeout_waiting_for_disabled');
    }

    await new Promise((r) => setTimeout(r, 500));
  }
}

async function publishClip({ clipPath, caption, accountId, artifactDir, options }) {
  clipPath = await ensureLocalClipFile({ clipPath, artifactDir });

  const headless = (process.env.PLAYWRIGHT_HEADLESS || '1') !== '0';

  const existingState = await loadStorageState(accountId);

  const browser = await chromium.launch({ headless });

  try {
    const context = await browser.newContext(existingState ? { storageState: existingState } : {});
    const page = await context.newPage();

    const publishOptions = {
      privacy: 'public',
      allowComments: true,
      allowDuet: true,
      allowStitch: true,
      ...(options || {}),
    };

    await page.goto('https://www.tiktok.com/upload?lang=en', {
      waitUntil: 'domcontentloaded',
      timeout: 60000,
    });

    await dismissCommonPopups(page);
    await safeScreenshot(page, path.join(artifactDir || '.', '01_upload_page.png'));
    await safeWriteText(path.join(artifactDir || '.', 'page_upload.html'), await page.content());

    const bodyText = await page.textContent('body');
    const looksLoggedOut = bodyText && /log in|sign in/i.test(bodyText);

    if (looksLoggedOut) {
      const err = new Error('not_logged_in: TikTok appears to require login (refresh storageState)');
      err.code = 'NOT_LOGGED_IN';
      throw err;
    }

    // 1) Upload video
    const fileInput = await findFirstLocatorInFrames(page, 'input[type="file"]');
    if (!fileInput) {
      throw new Error('upload_input_not_found');
    }

    await fileInput.setInputFiles(clipPath);
    await safeScreenshot(page, path.join(artifactDir || '.', '02_file_selected.png'));

    // 2) Caption
    // TikTok uses a contenteditable textbox; role=textbox catches it in most builds.
    const captionBox = page.getByRole('textbox', { name: /caption|describe/i }).first();

    try {
      if (caption && caption.trim()) {
        await captionBox.click({ timeout: 15000 });
        await captionBox.fill(caption.slice(0, 2200));
      }
    } catch {
      // Fallback: attempt any textbox.
      const anyBox = page.getByRole('textbox').first();
      if (caption && caption.trim()) {
        await anyBox.click({ timeout: 15000 });
        await anyBox.fill(caption.slice(0, 2200));
      }
    }

    await safeScreenshot(page, path.join(artifactDir || '.', '03_caption_filled.png'));

    // 3) Privacy (best-effort)
    try {
      const privacyCombo = page.getByRole('combobox', { name: /who can watch|privacy/i }).first();
      if (await privacyCombo.isVisible({ timeout: 3000 })) {
        await privacyCombo.click();
        await page.getByRole('option', { name: /public/i }).click({ timeout: 5000 });
      }
    } catch {
      // ignore
    }

    // 4) Toggles (best-effort)
    async function ensureSwitchOn(labelRegex) {
      // Preferred: an actual ARIA switch with a name.
      try {
        const switchLoc = page.getByRole('switch', { name: labelRegex }).first();
        if (await switchLoc.isVisible({ timeout: 1500 })) {
          const state = await switchLoc.getAttribute('aria-checked');
          if (state !== 'true') {
            await switchLoc.click();
          }
          return;
        }
      } catch {
        // ignore
      }

      // Fallback: find the label text and look for a nearby checkbox/switch.
      try {
        const label = page.getByText(labelRegex).first();
        if (!(await label.isVisible({ timeout: 1500 }))) return;

        const containers = [
          label.locator('xpath=..'),
          label.locator('xpath=../..'),
          label.locator('xpath=../../..'),
        ];

        for (const container of containers) {
          const roleSwitch = container.locator('[role="switch"]').first();
          if ((await roleSwitch.count()) > 0) {
            const state = await roleSwitch.getAttribute('aria-checked');
            if (state !== 'true') {
              await roleSwitch.click();
            }
            return;
          }

          const ariaCheckedButton = container.locator('button[aria-checked]').first();
          if ((await ariaCheckedButton.count()) > 0) {
            const state = await ariaCheckedButton.getAttribute('aria-checked');
            if (state !== 'true') {
              await ariaCheckedButton.click();
            }
            return;
          }

          const cb = container.locator('input[type="checkbox"]').first();
          if ((await cb.count()) > 0) {
            const checked = await cb.isChecked().catch(() => false);
            if (!checked) await cb.click();
            return;
          }
        }
      } catch {
        // ignore
      }
    }

    if (publishOptions.allowComments) await ensureSwitchOn(/comments/i);
    if (publishOptions.allowDuet) await ensureSwitchOn(/duet/i);
    if (publishOptions.allowStitch) await ensureSwitchOn(/stitch/i);

    await safeScreenshot(page, path.join(artifactDir || '.', '04_options.png'));

    // 5) Post
    const postBtn = page
      .locator('button:has-text("Post")')
      .or(page.locator('button:has-text("Publish")'))
      .first();

    await postBtn.waitFor({ state: 'visible', timeout: 180000 });
    await waitUntilEnabled(postBtn, { timeoutMs: 180000 });

    await safeScreenshot(page, path.join(artifactDir || '.', '05_before_post.png'));
    await postBtn.click({ timeout: 15000 });

    // Post triggers background processing; UIs differ. We wait for an observable change.
    try {
      await waitUntilNotEnabled(postBtn, { timeoutMs: 60000 });
    } catch {
      // ignore
    }

    try {
      await page
        .getByText(/uploaded|processing|your video|posted/i)
        .first()
        .waitFor({ state: 'visible', timeout: 180000 });
    } catch {
      // ignore
    }

    await dismissCommonPopups(page);
    await safeScreenshot(page, path.join(artifactDir || '.', '06_after_post.png'));
    await safeWriteText(path.join(artifactDir || '.', 'page_after_post.html'), await page.content());

    const newState = await context.storageState();
    await saveStorageState(accountId, newState);

    await context.close();

    return {
      status: 'posted',
      accountId,
      clipPath,
      privacy: publishOptions.privacy,
      allowComments: publishOptions.allowComments,
      allowDuet: publishOptions.allowDuet,
      allowStitch: publishOptions.allowStitch,
    };
  } finally {
    await browser.close();
  }
}

module.exports = {
  publishClip,
};
