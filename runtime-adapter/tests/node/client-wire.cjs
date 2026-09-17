const http = require('http');
const assert = require('node:assert/strict');
const path = require('node:path');
const clientRoot = process.env.CLIENT_PACKAGE_ROOT || '/client';
assert.equal(require(path.join(clientRoot, 'package.json')).version, '2.1.108');
const fs = require('fs');
const cp = require('child_process');
const requests = [];
fs.writeFileSync('/tmp/compat-fixture.txt','synthetic tool result');
fs.writeFileSync('/tmp/access-helper.cjs',"process.stdout.write('00000000-0000-0000-0000-000000000001.'+'a'.repeat(43));");
fs.writeFileSync('/tmp/client-settings.json',JSON.stringify({apiKeyHelper:'node /tmp/access-helper.cjs'}));
const server = http.createServer((req,res) => {
 let chunks=[];
 req.on('data',c=>chunks.push(c));
 req.on('end',()=>{
  const body=JSON.parse(Buffer.concat(chunks).toString()||'{}');
  requests.push({path:req.url,headers:req.headers,body});
  if(req.url.includes('count_tokens')){
   res.writeHead(200,{'content-type':'application/json'});res.end(JSON.stringify({input_tokens:25}));return;
  }
  const message={id:'msg_wire_check',type:'message',role:'assistant',model:'model.main',content:[],stop_reason:null,stop_sequence:null,usage:{input_tokens:25,output_tokens:1}};
  if(!body.stream){res.writeHead(200,{'content-type':'application/json'});res.end(JSON.stringify({...message,content:[{type:'text',text:'OK'}],stop_reason:'end_turn'}));return;}
  const events=[
   {type:'message_start',message},
   {type:'content_block_start',index:0,content_block:{type:'text',text:''}},
   {type:'content_block_delta',index:0,delta:{type:'text_delta',text:'OK'}},
   {type:'content_block_stop',index:0},
   {type:'message_delta',delta:{stop_reason:'end_turn',stop_sequence:null},usage:{output_tokens:1}},
   {type:'message_stop'}
  ];
  if(requests.length===1) {
    events.splice(1,4,
      {type:'content_block_start',index:0,content_block:{type:'tool_use',id:'toolu_fake',name:'Read',input:{}}},
      {type:'content_block_delta',index:0,delta:{type:'input_json_delta',partial_json:JSON.stringify({file_path:'/tmp/compat-fixture.txt'})}},
      {type:'content_block_stop',index:0},
      {type:'message_delta',delta:{stop_reason:'tool_use',stop_sequence:null},usage:{output_tokens:10}}
    );
  }
  res.writeHead(200,{'content-type':'text/event-stream'});
  res.end(events.map(event=>`event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`).join(''));
 });
});
server.listen(8044,'127.0.0.1',()=>{
 const env={...process.env,ANTHROPIC_BASE_URL:'http://127.0.0.1:8044',ANTHROPIC_MODEL:'model.main',ANTHROPIC_DEFAULT_SONNET_MODEL:'model.main',ANTHROPIC_DEFAULT_HAIKU_MODEL:'model.main',ANTHROPIC_DEFAULT_OPUS_MODEL:'model.main',CLAUDE_CONFIG_DIR:'/tmp/client-config',CLAUDE_CODE_API_KEY_HELPER_TTL_MS:'1000',CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS:'1',DISABLE_PROMPT_CACHING:'1',CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC:'1',DISABLE_NON_ESSENTIAL_MODEL_CALLS:'1',DISABLE_INTERLEAVED_THINKING:'1',CLAUDE_CODE_EFFORT_LEVEL:'unset',MAX_THINKING_TOKENS:'0',CLAUDE_CODE_MAX_OUTPUT_TOKENS:'1024'};
 const child=cp.spawn('node',['--require','/work/src/shifter_panw_adapter/assets/client-compat.cjs',path.join(clientRoot, 'cli.js'),'--settings','/tmp/client-settings.json','-p','Read /tmp/compat-fixture.txt then reply OK.','--model','model.main','--max-turns','2','--tools','Read','--allowedTools','Read','--no-session-persistence'],{env,cwd:'/tmp',stdio:['ignore','pipe','pipe']});
 let output='',error='';child.stdout.on('data',c=>output+=c);child.stderr.on('data',c=>error+=c);
 const timer=setTimeout(()=>child.kill('SIGKILL'),45000);
 child.on('exit',(status)=>{
  clearTimeout(timer);
  try {
   assert.equal(status,0); assert.equal(output.trim(),'OK'); assert.equal(error,'');
   assert.equal(requests.length,2);
   for (const request of requests) {
    assert.equal(request.path,'/v1/messages');
    assert.equal(request.headers['anthropic-beta'],undefined);
    assert.equal(request.headers.authorization,undefined);
    assert.equal(request.headers['x-api-key'].length,80);
    assert.equal(request.body.metadata,undefined);
    assert.equal(request.body.model,'model.main');
    assert.equal(request.body.stream,true);
   }
   assert(requests[1].body.messages.some(message => Array.isArray(message.content)
    && message.content.some(block => block.type==='tool_result'
     && JSON.stringify(block.content).includes('synthetic tool result'))));
   console.log(JSON.stringify({client_version:'2.1.108',status:'passed',
     message_requests:requests.length,streaming:true,local_tool_result:true,helper_authentication:true}));
  } catch { process.exitCode=1; console.error('Pinned client wire qualification failed'); }
  server.close();
 });
});
