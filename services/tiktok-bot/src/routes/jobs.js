const express = require('express');

function createJobsRouter({ queues }) {
  const router = express.Router();

  router.get('/jobs/:id', async (req, res) => {
    const job = await queues.getPublishJob(req.params.id);

    if (!job) {
      return res.status(404).json({ error: 'job_not_found' });
    }

    return res.json(job);
  });

  return router;
}

module.exports = {
  createJobsRouter,
};
