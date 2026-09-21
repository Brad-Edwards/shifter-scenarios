'use strict';

const fs = require('node:fs');

// Compatibility for the pinned private client, not a general-purpose proxy.
// Model authority, request validation and billing remain in Shifter's broker.
const METHODS = new Set(['/v1/messages', '/v1/messages/count_tokens']);
const ANNOTATIONS = new Set(['claude-code-20250219', 'effort-2025-11-24']);
const FIELDS = new Set([
  'model', 'messages', 'system', 'tools', 'tool_choice', 'max_tokens', 'stream',
  'temperature', 'top_p', 'top_k', 'stop_sequences', 'metadata',
]);
const MAX_BYTES = 1000000;
const encoder = new TextEncoder();

function unavailable() {
  // Never include a URL, prompt, credential, or provider error in diagnostics.
  throw new Error('Model client request unsupported');
}

async function normalize(input, init, origin) {
  const request = new Request(input, init);
  const url = new URL(request.url);
  if (url.origin !== origin || request.method !== 'POST' || !METHODS.has(url.pathname)
      || !['', '?beta=true'].includes(url.search) || url.hash) unavailable();
  if (request.headers.get('anthropic-version') !== '2023-06-01'
      || request.headers.has('content-encoding')) unavailable();
  const betas = request.headers.get('anthropic-beta');
  if (betas && betas.split(',').some(value => !ANNOTATIONS.has(value.trim()))) unavailable();
  const raw = await request.text();
  if (encoder.encode(raw).byteLength > MAX_BYTES) unavailable();
  let body;
  try { body = JSON.parse(raw); } catch { unavailable(); }
  if (!body || Array.isArray(body) || typeof body !== 'object'
      || Object.keys(body).some(key => !FIELDS.has(key))) unavailable();
  // user_id is client telemetry, never the authenticated participant identity.
  // The effort marker alone changes no inference behavior: output_config and
  // thinking are deliberately absent from FIELDS and cannot pass this shim.
  if ('metadata' in body) {
    const metadata = body.metadata;
    if (!metadata || Array.isArray(metadata) || typeof metadata !== 'object'
        || Object.keys(metadata).some(key => key !== 'user_id')
        || ('user_id' in metadata && (typeof metadata.user_id !== 'string'
          || encoder.encode(metadata.user_id).byteLength > 1024))) unavailable();
    delete body.metadata;
  }
  const headers = new Headers(request.headers);
  // The pinned SDK duplicates apiKeyHelper output into both auth schemes.
  // Shifter intentionally refuses ambiguous authentication; prove equality
  // before selecting one scheme and reject any conflicting identities.
  const key = headers.get('x-api-key');
  const authorization = headers.get('authorization');
  if (key && authorization) {
    if (authorization !== 'Bearer ' + key) unavailable();
    headers.delete('authorization');
  }
  headers.delete('anthropic-beta');
  headers.delete('content-length');
  url.search = '';
  return new Request(url, {
    method: 'POST', headers, body: JSON.stringify(body), signal: request.signal,
    redirect: 'error',
  });
}

const transport = globalThis.fetch.bind(globalThis);
globalThis.fetch = async (input, init) => {
  const base = new URL(process.env.ANTHROPIC_BASE_URL);
  if (base.pathname !== '/' || base.search || base.hash || base.username || base.password) unavailable();
  let request;
  try {
    request = await normalize(input, init, base.origin);
  } catch (error) {
    fs.writeFileSync('/tmp/polaris-model-client-status', 'request-normalization-failed\n');
    throw error;
  }
  try {
    const response = await transport(request);
    let marker = `broker-response-${response.status}`;
    if (!response.ok) {
      try {
        const payload = await response.clone().json();
        const code = payload?.error?.message;
        if (typeof code === 'string' && /^[a-z][a-z0-9_.-]{0,63}$/.test(code)) marker += `-${code}`;
      } catch {}
    }
    fs.writeFileSync('/tmp/polaris-model-client-status', marker + '\n');
    return response;
  } catch (error) {
    fs.writeFileSync('/tmp/polaris-model-client-status', 'broker-transport-failed\n');
    throw error;
  }
};
module.exports = { normalize };
