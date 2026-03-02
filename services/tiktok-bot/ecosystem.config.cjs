module.exports = {
  apps: [
    {
      name: "tiktok-bot",
      script: "src/index.js",
      cwd: __dirname,
      env: {
        NODE_ENV: "production",
      },
    },
  ],
};
