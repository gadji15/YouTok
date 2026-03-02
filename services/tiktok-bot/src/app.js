const express = require('express');

const { createHealthRouter } = require('./routes/health');
const { createJobsRouter } = require('./routes/jobs');
const { createPublishRouter } = require('./routes/publish');
const { createAccountsRouter } = require('./routes/accounts');
const { requireInternalSecret } = require('./middleware/requireInternalSecret');

function createApp({ queues }) {
  const app = express();

  app.disable('x-powered-by');
  app.use(express.json({ limit: '10mb' }));

  // Public health endpoint (used for container liveness).
  app.use('/health', createHealthRouter());

  // Internal endpoints (must be protected).
  app.use(requireInternalSecret);
  app.use('/', createAccountsRouter());
  app.use('/', createPublishRouter({ queues }));
  app.use('/', createJobsRouter({ queues }));

  return app;
}

module.exports = {
  createApp,
};
