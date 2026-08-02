#!/usr/bin/env node
import {inspectModelCard} from '../src/index.js';

let buffered = Buffer.alloc(0);

function send(message) {
  const body = Buffer.from(JSON.stringify(message));
  process.stdout.write(`Content-Length: ${body.length}\r\n\r\n`);
  process.stdout.write(body);
}

function handle(message) {
  if (message.method === 'notifications/initialized') return;
  if (message.method === 'initialize') {
    send({jsonrpc: '2.0', id: message.id, result: {protocolVersion: '2025-03-26', capabilities: {tools: {}}, serverInfo: {name: 'orion-mcp-audit', version: '2.3.1'}}});
    return;
  }
  if (message.method === 'tools/list') {
    send({jsonrpc: '2.0', id: message.id, result: {tools: [{name: 'inspect_model_card', description: 'Return the public Orion model-card compatibility fields.', inputSchema: {type: 'object', properties: {card: {type: 'object'}}, required: ['card']}}]}});
    return;
  }
  if (message.method === 'tools/call' && message.params?.name === 'inspect_model_card') {
    Promise.resolve(inspectModelCard(message.params.arguments?.card || {})).then((result) => {
      send({jsonrpc: '2.0', id: message.id, result: {content: [{type: 'text', text: JSON.stringify(result)}]}});
    }).catch((error) => send({jsonrpc: '2.0', id: message.id, error: {code: -32603, message: String(error)}}));
    return;
  }
  send({jsonrpc: '2.0', id: message.id, error: {code: -32601, message: 'Method not found'}});
}

function drain() {
  while (true) {
    const marker = buffered.indexOf('\r\n\r\n');
    if (marker < 0) return;
    const header = buffered.subarray(0, marker).toString();
    const match = /^Content-Length:\s*(\d+)$/im.exec(header);
    if (!match) process.exit(2);
    const length = Number(match[1]);
    const start = marker + 4;
    if (buffered.length < start + length) return;
    const message = JSON.parse(buffered.subarray(start, start + length).toString());
    buffered = buffered.subarray(start + length);
    handle(message);
  }
}

process.stdin.on('data', (chunk) => {
  buffered = Buffer.concat([buffered, chunk]);
  drain();
});
