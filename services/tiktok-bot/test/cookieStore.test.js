process.env.NODE_ENV = 'test';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');

const { loadStorageState, saveStorageState } = require('../src/storage/cookieStore');

test('cookieStore returns null when missing', async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'cookieStore-'));
  process.env.COOKIE_DIR = dir;

  const state = await loadStorageState('acct_missing');
  assert.equal(state, null);
});

test('cookieStore saves and loads JSON', async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'cookieStore-'));
  process.env.COOKIE_DIR = dir;

  await saveStorageState('acct_1', { cookies: [], origins: [] });
  const state = await loadStorageState('acct_1');

  assert.deepEqual(state, { cookies: [], origins: [] });
});

test('cookieStore throws BAD_STORAGE_STATE on invalid JSON', async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'cookieStore-'));
  process.env.COOKIE_DIR = dir;

  await fs.writeFile(path.join(dir, 'acct_1.json'), '{not json}', 'utf-8');

  await assert.rejects(async () => loadStorageState('acct_1'), (err) => {
    assert.equal(err.code, 'BAD_STORAGE_STATE');
    return true;
  });
});
