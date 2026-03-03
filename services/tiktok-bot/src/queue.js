const { Queue, Worker } = require('bullmq');
const IORedis = require('ioredis');

const { createLogger } = require('./logger');

function createRedisConnection(redisUrl) {
  // ioredis accepts a URL string.
  return new IORedis(redisUrl, {
    maxRetriesPerRequest: null,
    enableReadyCheck: true,
  });
}

function createInMemoryQueue() {
  const logger = createLogger({ service: 'tiktok-bot.queue.memory' });

  const jobs = new Map();

  // set by createQueues
  let processFn = async () => {};

  async function enqueue(name, data) {
    const id = `${Date.now()}_${Math.random().toString(16).slice(2)}`;
    const job = {
      id,
      name,
      data,
      status: 'queued',
      attemptsMade: 0,
      failedReason: null,
      result: null,
      createdAt: Date.now(),
      updatedAt: Date.now(),
      processedOn: null,
      finishedOn: null,
    };
    jobs.set(id, job);

    // Fire and forget processing.
    setImmediate(async () => {
      try {
        job.status = 'active';
        job.processedOn = Date.now();
        job.updatedAt = Date.now();

        job.result = await processFn(job.data, { jobId: job.id });

        job.status = 'completed';
        job.finishedOn = Date.now();
        job.updatedAt = Date.now();
      } catch (e) {
        job.status = 'failed';
        job.failedReason = e?.message || String(e);
        job.finishedOn = Date.now();
        job.updatedAt = Date.now();
        logger.error({ err: logger.serializeError(e), job_id: id }, 'job.failed');
      }
    });

    return { id };
  }

  async function getJob(id) {
    return jobs.get(id) || null;
  }

  function setProcessor(fn) {
    processFn = fn;
  }

  return {
    driver: 'memory',
    enqueue,
    getJob,
    setProcessor,
  };
}

function createQueues() {
  const mode = (process.env.PUBLISH_MODE || 'stub').toLowerCase();
  const isTest = process.env.NODE_ENV === 'test';
  const isProduction = process.env.NODE_ENV === 'production';
  const redisUrl = isTest ? '' : process.env.PUBLISH_REDIS_URL || '';

  if (isProduction && !redisUrl) {
    throw new Error('PUBLISH_REDIS_URL must be set in production (redis queue required)');
  }

  if (!redisUrl) {
    const q = createInMemoryQueue();
    return {
      driver: q.driver,
      mode,
      enqueuePublish: (data) => q.enqueue('publish', data),
      getPublishJob: async (id) => {
        const job = await q.getJob(id);
        if (!job) return null;

        return {
          id: job.id,
          name: job.name,
          status: job.status,
          attemptsMade: job.attemptsMade,
          failedReason: job.failedReason,
          data: job.data,
          returnvalue: job.result,
          timestamp: job.createdAt,
          processedOn: job.processedOn,
          finishedOn: job.finishedOn,
        };
      },
      startWorker: async (processor) => q.setProcessor(processor),
      stopWorker: async () => {},
    };
  }

  const logger = createLogger({ service: 'tiktok-bot.queue' });

  const connection = createRedisConnection(redisUrl);

  const publishQueue = new Queue('publish', { connection });

  let worker;

  async function startWorker(processor) {
    if (worker) return;

    worker = new Worker(
      'publish',
      async (job) => {
        return processor(job.data, { jobId: job.id });
      },
      {
        connection,
        concurrency: Number(process.env.PUBLISH_CONCURRENCY || 1),
      },
    );

    worker.on('completed', (job) => {
      logger.info({ job_id: job.id }, 'job.completed');
    });

    worker.on('failed', (job, err) => {
      logger.error({ job_id: job?.id, err: logger.serializeError(err) }, 'job.failed');
    });

    logger.info({ mode }, 'worker.started');
  }

  async function stopWorker() {
    if (worker) {
      await worker.close();
      worker = undefined;
    }
    await publishQueue.close();
    await connection.quit();
  }

  async function enqueuePublish(data) {
    const attempts = Number(process.env.PUBLISH_ATTEMPTS || 3);
    const backoffSeconds = Number(process.env.PUBLISH_BACKOFF_SECONDS || 30);

    const job = await publishQueue.add('publish', data, {
      attempts,
      backoff: { type: 'exponential', delay: backoffSeconds * 1000 },
      removeOnComplete: false,
      removeOnFail: false,
    });

    return { id: job.id };
  }

  async function getPublishJob(id) {
    const job = await publishQueue.getJob(id);
    if (!job) return null;

    const state = await job.getState();

    return {
      id: job.id,
      name: job.name,
      status: state,
      attemptsMade: job.attemptsMade,
      failedReason: job.failedReason,
      data: job.data,
      returnvalue: job.returnvalue,
      timestamp: job.timestamp,
      processedOn: job.processedOn,
      finishedOn: job.finishedOn,
    };
  }

  return {
    driver: 'bullmq',
    mode,
    enqueuePublish,
    getPublishJob,
    startWorker,
    stopWorker,
  };
}

module.exports = {
  createQueues,
};
