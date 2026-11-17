const fs = require('node:fs');
const https = require('node:https');

module.exports.runtime = {
  handler: async function ({ reference }) {
    let path;
    if (reference === 'current') path = '/api/handovers/current';
    else if (typeof reference === 'string' && /^DIAG-[A-Z0-9-]{1,64}$/.test(reference))
      path = '/api/diagnostics/' + reference;
    else return 'Supply current or an existing diagnostic job reference.';
    const { token } = JSON.parse(fs.readFileSync('/run/fieldlink/support.json', 'utf8'));
    return new Promise((resolve) => {
      const request = https.get({
        hostname: 'support.keplerops.test', port: 8443, path,
        ca: fs.readFileSync('/run/fieldlink/ca.crt'),
        headers: { Authorization: 'Bearer ' + token }, timeout: 8000,
      }, (response) => {
        if (response.statusCode !== 200) {
          response.resume();
          resolve('Support returned HTTP ' + response.statusCode + '.');
          return;
        }
        const chunks = [];
        let size = 0;
        response.on('data', (chunk) => {
          size += chunk.length;
          if (size > 1048576) request.destroy();
          else chunks.push(chunk);
        });
        response.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
        response.on('error', () => resolve('Support response unavailable.'));
      });
      request.on('timeout', () => request.destroy());
      request.on('error', () => resolve('Support service unavailable.'));
    });
  },
};
