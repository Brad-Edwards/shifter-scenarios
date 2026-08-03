import test from 'node:test';
import assert from 'node:assert/strict';
import {inspectModelCard, normalizeSpdx} from '../src/index.js';

test('test_spdx_with_exception_round_trip', () => {
  assert.equal(
    normalizeSpdx('GPL-2.0-only WITH Classpath-exception-2.0 OR MIT'),
    'GPL-2.0-only WITH Classpath-exception-2.0 OR MIT',
  );
});

test('model-card check returns only public compatibility fields', () => {
  assert.deepEqual(
    inspectModelCard({license: 'Apache-2.0', schema: 'orion.model-card/v2', internal_release_reference: 'not-returned'}),
    {license: 'Apache-2.0', schema: 'orion.model-card/v2'},
  );
});
