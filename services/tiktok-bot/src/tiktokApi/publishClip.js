async function publishClipViaApi({ clipPath, caption, accountId, artifactDir, options }) {
  void clipPath;
  void caption;
  void accountId;
  void artifactDir;
  void options;

  const err = new Error('tiktok_api_not_configured: Content Posting API is not configured/enabled');
  err.code = 'TIKTOK_API_NOT_CONFIGURED';
  throw err;
}

module.exports = {
  publishClipViaApi,
};
