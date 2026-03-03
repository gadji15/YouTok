const fs = require('fs/promises');
const path = require('path');

function getCookieDir() {
  return process.env.COOKIE_DIR || path.join(process.cwd(), 'storage', 'cookies');
}

function getCookieFilePath(accountId) {
  return path.join(getCookieDir(), `${accountId}.json`);
}

async function loadStorageState(accountId) {
  const filePath = getCookieFilePath(accountId);

  let raw;
  try {
    raw = await fs.readFile(filePath, 'utf-8');
  } catch (e) {
    if (e && e.code === 'ENOENT') return null;
    throw e;
  }

  try {
    return JSON.parse(raw);
  } catch (e) {
    const err = new Error('Invalid JSON in storageState file');
    err.code = 'BAD_STORAGE_STATE';
    err.cause = e;
    throw err;
  }
}

async function saveStorageState(accountId, state) {
  const filePath = getCookieFilePath(accountId);
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, JSON.stringify(state, null, 2));
}

module.exports = {
  getCookieDir,
  loadStorageState,
  saveStorageState,
};
