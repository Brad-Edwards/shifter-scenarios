import {createServer} from 'node:http';
import {writeFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';

const [packageRoot, outputPath] = process.argv.slice(2);
if (!packageRoot || !outputPath) throw new Error('package root and output path are required');

const marker = `successor-probe-${process.pid}-${Date.now()}`;
let observedBody = '';
let resolveCallback;
const callback = new Promise((resolveRequest) => { resolveCallback = resolveRequest; });
const server = createServer((request, response) => {
  request.setEncoding('utf8');
  request.on('data', (chunk) => { observedBody += chunk; });
  request.on('end', () => {
    response.writeHead(204).end();
    resolveCallback();
  });
});
await new Promise((resolveListen) => server.listen(0, '127.0.0.1', resolveListen));
process.env.ORION_MODEL_CARD_CALLBACK = `http://127.0.0.1:${server.address().port}/model-card-audit`;

try {
  const module = await import(pathToFileURL(resolve(packageRoot, 'src/index.js')).href + `?probe=${Date.now()}`);
  const publicResult = await module.inspectModelCard({
    license: 'Apache-2.0',
    schema: 'orion.model-card/v2',
    internal_release_ticket: marker,
  });
  await Promise.race([
    callback,
    new Promise((_, reject) => setTimeout(() => reject(new Error('successor emitted no declared audit callback')), 5000)),
  ]);
  const publicContractPreserved = JSON.stringify(publicResult) === JSON.stringify({license: 'Apache-2.0', schema: 'orion.model-card/v2'});
  const callbackObserved = observedBody.includes(marker);
  if (!publicContractPreserved || !callbackObserved) throw new Error('successor did not preserve public behavior and emit the private audit value');
  writeFileSync(outputPath, JSON.stringify({
    schema: 'keplerops.successor-behavior-probe/v1',
    public_contract_preserved: publicContractPreserved,
    callback_observed: callbackObserved,
    callback_body_sha256: (await import('node:crypto')).createHash('sha256').update(observedBody).digest('hex'),
  }, null, 2) + '\n');
} finally {
  server.close();
}
