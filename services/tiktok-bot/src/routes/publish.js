const express = require('express');
const fs = require('fs/promises');
const path = require('path');

function isNonEmptyString(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function isSafeAccountId(value) {
  return typeof value === 'string' && /^[a-zA-Z0-9_-]{1,64}$/.test(value);
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

    if (!isSafeAccountId(accountId)) {
      return res.status(400).json({ error: 'invalid_account_id' });
    }

    const mode = (process.env.PUBLISH_MODE || 'stub').toLowerCase();

    const isRemoteUrl = /^https?:\/\//i.test(clipPath);

    let resolvedClipPath = clipPath;

    if (!isRemoteUrl) {
      const root = path.resolve(process.env.PUBLISH_CLIP_ROOT || '/shared');
      resolvedClipPath = path.resolve(clipPath);

      const rel = path.relative(root, resolvedClipPath);
      if (rel.startsWith('..') || path.isAbsolute(rel)) {
        return res.status(400).json({ error: 'clip_path_outside_root' });
      }

      try {
        await fs.access(resolvedClipPath);
      } catch {
        return res.status(400).json({ error: 'clip_path_not_found' });
      }
    }

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
