import http from 'k6/http';
import { check } from 'k6';

const baseUrl = __ENV.TARGET_BASE_URL || 'https://inference-gateway.keplerops.lab';
const targetPath = __ENV.TARGET_PATH || '/healthz';
const requestedRate = Number(__ENV.COHORT_RATE || '2');
const requestedSeconds = Number(__ENV.COHORT_DURATION_SECONDS || '30');
const requestedVUs = Number(__ENV.COHORT_MAX_VUS || '8');

if (!baseUrl.startsWith('https://') && !baseUrl.startsWith('http://')) {
  throw new Error('TARGET_BASE_URL must be HTTP(S)');
}
if (!targetPath.startsWith('/') || targetPath.includes('://')) {
  throw new Error('TARGET_PATH must be an absolute path without a URL');
}
if (!Number.isInteger(requestedRate) || requestedRate < 1 || requestedRate > 10) {
  throw new Error('COHORT_RATE must be an integer between 1 and 10 iterations/second');
}
if (!Number.isInteger(requestedSeconds) || requestedSeconds < 5 || requestedSeconds > 120) {
  throw new Error('COHORT_DURATION_SECONDS must be an integer between 5 and 120');
}
if (!Number.isInteger(requestedVUs) || requestedVUs < 1 || requestedVUs > 20) {
  throw new Error('COHORT_MAX_VUS must be an integer between 1 and 20');
}

export const options = {
  discardResponseBodies: true,
  scenarios: {
    synthetic_client_cohort: {
      executor: 'constant-arrival-rate',
      duration: `${requestedSeconds}s`,
      rate: requestedRate,
      timeUnit: '1s',
      preAllocatedVUs: Math.min(requestedVUs, 4),
      maxVUs: requestedVUs,
      gracefulStop: '5s',
      tags: { cohort: 'keplerops-synthetic' },
    },
  },
  thresholds: {
    'http_req_failed{cohort:keplerops-synthetic}': ['rate<0.05'],
    'http_req_duration{cohort:keplerops-synthetic}': ['p(95)<3000'],
  },
};

export default function syntheticClientCohort() {
  const response = http.get(`${baseUrl}${targetPath}`, {
    redirects: 0,
    tags: { name: 'synthetic-cohort-probe', cohort: 'keplerops-synthetic' },
    timeout: '3s',
  });
  check(response, {
    'cohort response is HTTP success': (result) => result.status >= 200 && result.status < 400,
  });
}
