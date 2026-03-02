process.env.NODE_ENV = 'test';
process.env.PUBLISH_INTERNAL_SECRET = 'test-secret';

const test = require('node:test');
const assert = require('node:assert/strict');

const { createApp } = require('../src/app');
const { createQueues } = require('../src/queue');

test('GET /health returns ok (no auth required)', async () => {
  const queues = createQueues();
  await queues.startWorker(async () => {});

  const app = createApp({ queues });

  const server = await new Promise((resolve) => {
    const s = app.listen(0, () => resolve(s));
  });

  try {
    const { port } = server.address();

    const res = await fetch(`http://127.0.0.1:${port}/health`);
    assert.equal(res.status, 200);

    const body = await res.json();
    assert.equal(body.status, 'ok');
  } finally {
    await new Promise((resolve, reject) => {
      server.close((err) => (err ? reject(err) : resolve()));
    });
    await queues.stopWorker();
  }
});
