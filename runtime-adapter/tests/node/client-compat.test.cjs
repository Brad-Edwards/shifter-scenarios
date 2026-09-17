'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { normalize } = require('../../src/shifter_panw_adapter/assets/client-compat.cjs');
const ORIGIN = 'https://broker.example.test';
const BODY = { model: 'model.main', messages: [{ role: 'user', content: 'hello' }], max_tokens: 8 };
const HEADERS = {
  'content-type': 'application/json', 'anthropic-version': '2023-06-01',
  'anthropic-beta': 'claude-code-20250219,effort-2025-11-24',
  'authorization': 'Bearer synthetic',
};
const options = (body = BODY, headers = HEADERS) => ({ method: 'POST', headers, body: JSON.stringify(body) });

test('only inert client annotations are removed; model, prompt and auth survive', async () => {
  const request = await normalize(ORIGIN + '/v1/messages?beta=true', options({
    ...BODY, metadata: { user_id: 'synthetic client telemetry' },
  }), ORIGIN);
  assert.equal(request.url, ORIGIN + '/v1/messages');
  assert.equal(request.headers.get('anthropic-beta'), null);
  assert.equal(request.headers.get('authorization'), HEADERS.authorization);
  assert.deepEqual(await request.json(), BODY);
  assert.equal(request.redirect, 'error');
});

for (const path of ['/v1/access/refresh', '/control/v1/enroll', '/v1/messages?beta=false',
  '/v1/messages?beta=true&model=other', '/v1/messages?beta=true&beta=true']) {
  test('reject route ' + path, async () => {
    await assert.rejects(normalize(ORIGIN + path, options(), ORIGIN), /unsupported/);
  });
}
for (const body of [
  { ...BODY, thinking: { type: 'enabled', budget_tokens: 100 } },
  { ...BODY, output_config: { effort: 'high' } },
  { ...BODY, service_tier: 'auto' },
  { ...BODY, metadata: { user_id: 'x', role: 'admin' } },
  { ...BODY, metadata: { user_id: 'x'.repeat(1025) } },
]) {
  test('reject unsupported body shape ' + JSON.stringify(Object.keys(body)), async () => {
    await assert.rejects(normalize(ORIGIN + '/v1/messages', options(body), ORIGIN), /unsupported/);
  });
}
test('reject unknown betas, alternate destinations and compressed requests', async () => {
  for (const headers of [
    { ...HEADERS, 'anthropic-beta': 'context-1m-2025-08-07' },
    { ...HEADERS, 'anthropic-beta': 'interleaved-thinking-2025-05-14' },
    { ...HEADERS, 'content-encoding': 'gzip' },
  ]) await assert.rejects(normalize(ORIGIN + '/v1/messages', options(BODY, headers), ORIGIN), /unsupported/);
  await assert.rejects(normalize('https://elsewhere.example.test/v1/messages', options(), ORIGIN), /unsupported/);
});
test('body size and malformed JSON fail closed', async () => {
  for (const body of ['{', JSON.stringify({ ...BODY, system: 'x'.repeat(1000000) })]) {
    await assert.rejects(normalize(ORIGIN + '/v1/messages', { method: 'POST', headers: HEADERS, body }, ORIGIN), /unsupported/);
  }
});

test('identical SDK credentials become one header; conflicting credentials are rejected', async () => {
  const headers = { ...HEADERS, 'x-api-key': 'synthetic' };
  const request = await normalize(ORIGIN + '/v1/messages', options(BODY, headers), ORIGIN);
  assert.equal(request.headers.get('x-api-key'), 'synthetic');
  assert.equal(request.headers.get('authorization'), null);
  await assert.rejects(normalize(ORIGIN + '/v1/messages', options(BODY, {
    ...headers, 'authorization': 'Bearer different',
  }), ORIGIN), /unsupported/);
});
