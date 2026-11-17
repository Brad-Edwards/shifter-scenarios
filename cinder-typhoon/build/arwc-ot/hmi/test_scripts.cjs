// Execute the authored native script bodies using Node's built-in test runner.
// Run inside the development VM's pinned FUXA container, which supplies Node.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const project = JSON.parse(fs.readFileSync('/tmp/arwc-hmi-project.json', 'utf8'));
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const script = id => project.scripts.find(s => s.id === id).code;

function run(code, value, writes, failure = null) {
    return new AsyncFunction('$getTag', '$setTag', 'setTimeout', code)(
        () => value,
        async (tag, val) => { writes.push([tag, val]); return failure !== val; },
        resolve => resolve(),
    );
}

test('commit consumes the next sequence, including wrap', async () => {
    for (const [seen, next] of [[0, 1], [41, 42], [65535, 1]]) {
        const writes = [];
        await run(script('crr-apply'), seen, writes);
        assert.deepEqual(writes, [['HmiSequence', next]]);
    }
});

test('missing, fractional, and invalid sequences cannot become a command', async () => {
    for (const seen of [null, undefined, -1, 65536, 1.5, NaN]) {
        const writes = [];
        await assert.rejects(run(script('crr-apply'), seen, writes), /sequence unavailable/);
        assert.equal(writes.length, 0);
    }
});

test('fault reset returns the tag low, including a rejected rising write', async () => {
    const writes = [];
    await run(script('crr-reset'), 0, writes);
    assert.deepEqual(writes, [['HmiResetFaults', false], ['HmiResetFaults', true], ['HmiResetFaults', false]]);
    const failed = [];
    await assert.rejects(run(script('crr-reset'), 0, failed, true), /Reset failed/);
    assert.deepEqual(failed, writes);
});

test('sequence validation mutation is detected', async () => {
    const mutant = script('crr-apply').replace('raw === null || raw === undefined || ', '');
    const writes = [];
    await run(mutant, null, writes);
    assert.deepEqual(writes, [['HmiSequence', 1]]);
});

test('missing reset cleanup mutation is detected', async () => {
    const mutant = script('crr-reset').replace('finally { await $setTag("HmiResetFaults", false); }', 'finally {}');
    const writes = [];
    await run(mutant, 0, writes);
    assert.notDeepEqual(writes.at(-1), ['HmiResetFaults', false]);
});
