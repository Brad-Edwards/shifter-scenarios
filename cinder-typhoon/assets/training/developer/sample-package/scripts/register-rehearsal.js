const fs = require('node:fs');
const http = require('node:http');

const source = '/opt/cinder-sample/fixtures/rehearsal-source.json';
const destination = 'http://developer.training:8084/api/rehearsal/ingest';
const body = fs.readFileSync(source);
const request = http.request(destination, {method: 'POST', headers: {'content-type': 'application/json', 'content-length': body.length}});
request.end(body);
