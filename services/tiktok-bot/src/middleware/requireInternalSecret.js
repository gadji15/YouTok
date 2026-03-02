const crypto = require('crypto');

function getExpectedSecret() {
  return process.env.PUBLISH_INTERNAL_SECRET || process.env.INTERNAL_API_SECRET || '';
}

function requireInternalSecret(req, res, next) {
  const expected = getExpectedSecret();
  const isProduction = process.env.NODE_ENV === 'production';

  if (!expected || (isProduction && expected === 'change-me')) {
    return res.status(500).json({
      error: 'internal_secret_not_configured',
    });
  }

  const provided = req.get('X-Internal-Secret') || '';

  if (!provided) {
    return res.status(403).json({ error: 'forbidden' });
  }

  try {
    const a = Buffer.from(expected);
    const b = Buffer.from(provided);
    if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) {
      return res.status(403).json({ error: 'forbidden' });
    }
  } catch {
    return res.status(403).json({ error: 'forbidden' });
  }

  return next();
}

module.exports = {
  getExpectedSecret,
  requireInternalSecret,
};
