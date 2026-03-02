const express = require('express');
const fs = require('fs/promises');
const path = require('path');

const { getCookieDir, loadStorageState, saveStorageState } = require('../storage/cookieStore');

function createAccountsRouter() {
  const router = express.Router();

  router.get('/accounts', async (_req, res) => {
    const dir = getCookieDir();

    let entries = [];
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch (e) {
      if (e && e.code === 'ENOENT') {
        return res.json({ accounts: [] });
      }
      throw e;
    }

    const accounts = entries
      .filter((ent) => ent.isFile() && ent.name.endsWith('.json'))
      .map((ent) => ent.name.slice(0, -'.json'.length))
      .sort();

    return res.json({ accounts });
  });

  router.get('/accounts/:id/storage-state', async (req, res) => {
    const accountId = req.params.id;

    const state = await loadStorageState(accountId);
    if (!state) {
      return res.status(404).json({ error: 'not_found' });
    }

    return res.json(state);
  });

  router.put('/accounts/:id/storage-state', async (req, res) => {
    const accountId = req.params.id;

    const state = req.body;
    if (!state || typeof state !== 'object') {
      return res.status(400).json({ error: 'storage_state_must_be_object' });
    }

    await saveStorageState(accountId, state);

    const filePath = path.join(getCookieDir(), `${accountId}.json`);

    return res.status(200).json({ status: 'ok', account_id: accountId, path: filePath });
  });

  return router;
}

module.exports = {
  createAccountsRouter,
};
