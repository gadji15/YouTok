const fs = require('fs/promises');
const path = require('path');

const { createLogger } = require('./logger');

async function ensureDir(p) {
  await fs.mkdir(p, { recursive: true });
}

async function writeJson(filePath, data) {
  await ensureDir(path.dirname(filePath));
  await fs.writeFile(filePath, JSON.stringify(data, null, 2));
}

function createPublishProcessor() {
  const logger = createLogger({ service: 'tiktok-bot.publish-worker' });

  const mode = (process.env.PUBLISH_MODE || 'stub').toLowerCase();
  const artifactRoot = process.env.PUBLISH_ARTIFACT_DIR || '/app/storage/artifacts';

  return async function processPublishJob(data, { jobId }) {
    const startedAt = Date.now();
    const jobDir = path.join(artifactRoot, String(jobId));

    await ensureDir(jobDir);

    logger.info({ job_id: jobId, mode, clip_path: data.clipPath, account_id: data.accountId }, 'publish.start');

    try {
      if (mode === 'playwright') {
        const { publishClip } = require('./playwright/publishClip');

        const result = await publishClip({
          clipPath: data.clipPath,
          caption: data.caption,
          accountId: data.accountId,
          artifactDir: jobDir,
        });

        await writeJson(path.join(jobDir, 'result.json'), { ok: true, result });

        logger.info({ job_id: jobId, took_ms: Date.now() - startedAt }, 'publish.done');
        return result;
      }

      // stub
      const result = {
        status: 'stubbed',
        accountId: data.accountId,
        clipPath: data.clipPath,
      };
      await writeJson(path.join(jobDir, 'result.json'), { ok: true, result });
      logger.info({ job_id: jobId, took_ms: Date.now() - startedAt }, 'publish.done.stub');
      return result;
    } catch (err) {
      await writeJson(path.join(jobDir, 'error.json'), { ok: false, error: logger.serializeError(err) });
      logger.error({ job_id: jobId, err: logger.serializeError(err) }, 'publish.failed');
      throw err;
    }
  };
}

module.exports = {
  createPublishProcessor,
};
