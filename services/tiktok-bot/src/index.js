const { createApp } = require('./app');
const { createQueues } = require('./queue');
const { createPublishProcessor } = require('./publishWorker');
const { createLogger } = require('./logger');

const logger = createLogger({ service: 'tiktok-bot' });

const port = Number(process.env.PORT || 3000);

async function main() {
  const queues = createQueues();

  // Start background worker (bullmq or memory driver).
  await queues.startWorker(createPublishProcessor());

  const app = createApp({ queues });

  const server = app.listen(port, () => {
    logger.info({ port, queue_driver: queues.driver }, 'http.listening');
  });

  async function shutdown(signal) {
    logger.info({ signal }, 'shutdown.start');
    server.close(async () => {
      try {
        await queues.stopWorker();
      } catch (e) {
        logger.error({ err: logger.serializeError(e) }, 'shutdown.worker_close_failed');
      }
      process.exit(0);
    });
  }

  process.on('SIGINT', () => shutdown('SIGINT'));
  process.on('SIGTERM', () => shutdown('SIGTERM'));
}

main().catch((err) => {
  logger.error({ err: logger.serializeError(err) }, 'fatal');
  process.exit(1);
});
