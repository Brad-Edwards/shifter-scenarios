import http from 'k6/http';
import { check } from 'k6';

const requestedRate = Number.parseInt(__ENV.CLIENT_RATE || '1', 10);
const requestedSeconds = Number.parseInt(__ENV.CLIENT_SECONDS || '10', 10);
const requestedVUs = Number.parseInt(__ENV.CLIENT_MAX_VUS || '4', 10);
const target = __ENV.TARGET_URL || 'http://edge-registry.keplerops.lab:8481/healthz'; // NOSONAR -- range-local test service is intentionally HTTP-only.

if (!Number.isInteger(requestedRate) || requestedRate < 1 || requestedRate > 5) {
  throw new Error('CLIENT_RATE must be an integer between 1 and 5');
}
if (!Number.isInteger(requestedSeconds) || requestedSeconds < 1 || requestedSeconds > 60) {
  throw new Error('CLIENT_SECONDS must be an integer between 1 and 60');
}
if (!Number.isInteger(requestedVUs) || requestedVUs < 1 || requestedVUs > 10) {
  throw new Error('CLIENT_MAX_VUS must be an integer between 1 and 10');
}

const rangeLocalTarget = /^https?:\/\/(localhost|127\.0\.0\.1|[a-z0-9][a-z0-9.-]*\.keplerops\.lab)(:\d{1,5})?\/[a-zA-Z0-9/_-]*$/;
if (!rangeLocalTarget.test(target)) {
  throw new Error('TARGET_URL must be a query-free range-local HTTP URL');
}

export const options = {
  discardResponseBodies: false,
  scenarios: {
    bounded_clients: {
      executor: 'constant-arrival-rate',
      rate: requestedRate,
      timeUnit: '1s',
      duration: `${requestedSeconds}s`,
      preAllocatedVUs: Math.min(requestedVUs, 2),
      maxVUs: requestedVUs,
      gracefulStop: '1s',
      tags: { workload: 'keplerops-bounded-client' },
    },
  },
  thresholds: {
    'http_req_failed{workload:keplerops-bounded-client}': ['rate<0.25'],
    'http_req_duration{workload:keplerops-bounded-client}': ['p(95)<3000'],
  },
};

export default function boundedClient() {
  const requestHeaders = { 'User-Agent': 'keplerops-k6-client/1.0', Accept: 'application/json' };
  const response = http.get(target, {
    headers: requestHeaders,
    redirects: 0,
    timeout: '3s',
    tags: { workload: 'keplerops-bounded-client' },
  });
  const responseBody = response.body || '';
  const complete = responseBody.length <= 16384;
  console.log(JSON.stringify({
    schema_version: '1',
    event_type: 'synthetic_client.response',
    request: { method: 'GET', url: target, headers: requestHeaders },
    response: {
      status: response.status,
      body: complete ? responseBody : responseBody.slice(0, 16384),
      body_complete: complete,
      observed_chars: responseBody.length,
    },
  }));
  check(response, { 'range endpoint responded': (result) => result.status >= 200 && result.status < 500 });
}

export function handleSummary(data) {
  return {
    '/var/lib/keplerops-k6/summary.json': JSON.stringify({
      schema_version: '1',
      target,
      requested_rate: requestedRate,
      requested_seconds: requestedSeconds,
      requested_max_vus: requestedVUs,
      metrics: data.metrics,
    }),
    stdout: JSON.stringify({ schema_version: '1', event_type: 'synthetic_client.summary', target }),
  };
}
