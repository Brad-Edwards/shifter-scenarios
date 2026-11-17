'use strict';
const limits = require('./limits.json');
const version = require('./package.json').version;

exports.consume = function consume(request) {
  if (!request || request.schema !== 'fieldkest.connector/v2') {
    throw new TypeError('Unsupported connector interface');
  }
  if (typeof request.tenant_id !== 'string' || typeof request.asset_id !== 'string') {
    throw new TypeError('A tenant and asset are required');
  }
  const measurements = request.measurements || {};
  const latency = measurements.callback_latency_ms;
  const count = measurements.sample_count;
  if (latency !== undefined && (!Number.isFinite(latency) || latency < 0)) {
    throw new TypeError('Invalid callback latency');
  }
  if (count !== undefined && (!Number.isInteger(count) || count < 0)) {
    throw new TypeError('Invalid sample count');
  }
  const assessment = latency === undefined ? 'awaiting-measurements'
    : latency > limits.maximum_callback_latency_ms ? 'callback-review-required'
    : count === undefined || count < limits.minimum_sample_count ? 'additional-samples-required' : 'within-operating-limits';
  return {
    schema: 'fieldkest.rehearsal-result/v1', tenant_id: request.tenant_id,
    asset_id: request.asset_id, connector_version: version, assessment,
    observations: {callback_latency_ms: latency ?? null, sample_count: count ?? null}
  };
};
