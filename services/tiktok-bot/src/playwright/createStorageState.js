const { chromium } = require('playwright');
const readline = require('readline/promises');

const { saveStorageState } = require('../storage/cookieStore');

async function main() {
  const accountId = process.argv[2];
  if (!accountId) {
    // eslint-disable-next-line no-console
    console.error('Usage: node src/playwright/createStorageState.js <account_id>');
    process.exit(2);
  }

  const headless = false;

  const browser = await chromium.launch({ headless });

  try {
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto('https://www.tiktok.com/', { waitUntil: 'domcontentloaded', timeout: 60000 });

    // eslint-disable-next-line no-console
    console.log('Log into TikTok in the opened browser window.');
    // eslint-disable-next-line no-console
    console.log('When you are fully logged in, press Enter here to save the session.');

    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    await rl.question('> ');
    rl.close();

    const state = await context.storageState();
    await saveStorageState(accountId, state);

    // eslint-disable-next-line no-console
    console.log(`Saved storageState for account ${accountId}.`);

    await context.close();
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  // eslint-disable-next-line no-console
  console.error(err);
  process.exit(1);
});
