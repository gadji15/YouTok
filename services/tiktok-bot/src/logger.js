function serializeError(err) {
  if (!err || typeof err !== 'object') {
    return { message: String(err) };
  }

  return {
    name: err.name,
    message: err.message,
    stack: err.stack,
  };
}

function createLogger({ service = 'tiktok-bot' } = {}) {
  function write(level, fields, msg) {
    const entry = {
      time: new Date().toISOString(),
      level,
      service,
      msg,
      ...fields,
    };

    const line = JSON.stringify(entry);

    if (level === 'error') {
      console.error(line);
    } else {
      console.log(line);
    }
  }

  return {
    info(fields = {}, msg = '') {
      write('info', fields, msg);
    },
    warn(fields = {}, msg = '') {
      write('warn', fields, msg);
    },
    error(fields = {}, msg = '') {
      write('error', fields, msg);
    },
    serializeError,
  };
}

module.exports = {
  createLogger,
  serializeError,
};
