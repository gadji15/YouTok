process.env.NODE_ENV = 'test';
process.env.PUBLISH_INTERNAL_SECRET = 'test-secret';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');

const { createApp } = require('../src/app');
const { createQueues } = require('../src/queue');

test('accounts storage-state endpoints work', async () => {
  const cookieDir = await fs.mkdtemp(path.join(os.tmpdir(), 'tiktok-bot-cookies-'));
  process.env.COOKIE_DIR = cookieDir;

  const queues = createQueues();
  await queues.startWorker(async () => {});

  const app = createApp({ queues });

  const server = await new Promise((resolve) => {
    const s = app.listen(0, () => resolve(s));
  });

  try {
    const { port } = server.address();

    const putRes = await fetch(`http://127.0.0.1:${port}/accounts/acct_1/storage-state`, {
      method: 'PUT',
      headers: {
        'content-type': 'application/json',
        'x-internal-secret': 'test-secret',
      },
      body: JSON.stringify({ cookies: [], origins: [] }),
    });

    assert.equal(putRes.status, 200);

    const listRes = await fetch(`http://127.0.0.1:${port}/accounts`, {
      headers: { 'x-internal-secret': 'test-secret' },
    });
    assert.equal(listRes.status, 200);
    const listBody = await listRes.json();
    assert.ok(Array.isArray(listBody.accounts));
    assert.ok(listBody.accounts.includes('acct_1'));

    const getRes = await fetch(`http://127.0.0.1:${port}/accounts/acct_1/storage-state`, {
      headers: { 'x-internal-secret': 'test-secret' },
    });
    assert.equal(getRes.status, 200);
    const state = await getRes.json();
    assert.deepEqual(state, { cookies: [], origins: [] });
  } finally {
    await new Promise((resolve, reject) => {
      server.close((err) => (err ? reject(err) : resolve()));
    });
    await queues.stopWorker();
  }
});
