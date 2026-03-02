const express = require('express');
const path = require('path');

function isNonEmptyString(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function createPublishRouter({ queues }) {
  const router = express.Router();

  router.post('/publish', async (req, res) => {
    const { clip_path: clipPath, caption, account_id: accountId } = req.body || {};

    if (!isNonEmptyString(clipPath) || !isNonEmptyString(caption) || !isNonEmptyString(accountId)) {
      return res.status(400).json({
        error: 'Invalid payload. Expected { clip_path, caption, account_id } as non-empty strings.',
      });
    }

    const mode = (process.env.PUBLISH_MODE || 'stub').toLowerCase();

    const resolvedClipPath = path.resolve(clipPath);

    const job = await queues.enqueuePublish({
      clipPath: resolvedClipPath,
      caption,
      accountId,
    });

    return res.status(202).json({
      status: 'accepted',
      job_id: job.id,
      mode,
      queue_driver: queues.driver,
    });
  });

  return router;
}

module.exports = {
  createPublishRouter,
};
