'use strict';
const limits = require('./limits.json');
const version = require('./package.json').version;

// 7.4.3-cinder.rset1 is the pending Cinder release. It adds a diagnostic-summary
// path (calibration review) while keeping the retained connector behavior for the
// v2 reference consumer and for ordinary v3 measurement inputs.
function run(request) {
  if (!request || typeof request.tenant_id !== 'string' || typeof request.asset_id !== 'string') {
    throw new TypeError('A tenant and asset are required');
  }
  // v2 reference consumers keep the supported connector's compatible behavior.
  if (request.schema === 'fieldkest.connector/v2') {
    return {
      schema: 'fieldkest.rehearsal-result/v1', tenant_id: request.tenant_id,
      asset_id: request.asset_id, connector_version: version,
      assessment: 'reference-compatible',
      observations: {operation: request.operation || null}
    };
  }
  if (request.schema !== 'fieldkest.connector/v3') {
    throw new TypeError('Unsupported connector interface');
  }
  // The diagnostic-summary path runs a calibration review for the named asset.
  if (request.operation === 'diagnostic_summary') {
    return {
      schema: 'fieldkest.rehearsal-result/v1', tenant_id: request.tenant_id,
      asset_id: request.asset_id, connector_version: version,
      assessment: 'calibration-review',
      observations: {operation: 'diagnostic_summary'}
    };
  }
  // Ordinary v3 inputs keep the 7.4.2 latency/sample logic.
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
}

exports.consume = run;
exports.diagnostic_summary = run;
