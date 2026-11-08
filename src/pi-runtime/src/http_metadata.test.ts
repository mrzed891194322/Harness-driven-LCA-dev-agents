import test from 'node:test';
import assert from 'node:assert/strict';
import {channel} from 'node:diagnostics_channel';
import {observeFetch, attachPreflightMetadata} from './http_metadata.js';
const URL_BASE='https://agi.tongji.edu.cn/v1/chat/completions';
const KEY='wf:preflight:1234abcd';
test('403/429: zero body access, no retry, no secret output',async()=>{
 for(const status of [403,429]){
  const records:any[]=[];let calls=0;
  const raw=new Response('BODY_CANARY',{status,headers:{'x-request-id':'ee87553bebae32c92b93addd01144855','set-cookie':'COOKIE_CANARY'}});
  const response=new Proxy(raw,{get(t,k){if(['body','clone','text','json','arrayBuffer'].includes(String(k)))throw Error('body accessed');return Reflect.get(t,k,t);}});
  const f=observeFetch(async(input,init)=>{calls++;assert.equal((init?.headers as any).Authorization,'AUTH_CANARY');return response;},x=>records.push(x),KEY);
  assert.equal(await f(URL_BASE+'?key=QUERY_CANARY#FRAGMENT_CANARY',{method:'POST',headers:{Authorization:'AUTH_CANARY'},body:'REQUEST_CANARY'}),response);
  assert.equal(calls,1);assert.equal(records[1].status,status);assert.ok(!JSON.stringify(records).includes('CANARY'));assert.equal(raw.bodyUsed,false);
 }
});
test('sensitive path/userinfo and malformed request id omitted',async()=>{
 const records:any[]=[];await observeFetch(async()=>new Response('x',{status:403,headers:{'x-request-id':'SECRET_CANARY'}}),x=>records.push(x),KEY)('https://USER_CANARY:PASS_CANARY@agi.tongji.edu.cn/SECRET_CANARY?key=CANARY',{method:'POST'});
 assert.ok(!JSON.stringify(records).includes('CANARY'));assert.equal(records[0].path,'[omitted]');
});
test('transport exception identity retained, message suppressed',async()=>{
 const e=new Error('SECRET_CANARY');const records:any[]=[];let n=0;
 await assert.rejects(observeFetch(async()=>{n++;throw e;},x=>records.push(x),KEY)(URL_BASE),x=>x===e);
 assert.equal(n,1);assert.ok(!JSON.stringify(records).includes('CANARY'));
});
test('sink failure leaves response intact',async()=>{const r=new Response('ok');assert.equal(await observeFetch(async()=>r,()=>{throw Error('x');},KEY)(URL_BASE),r);});
test('supported channel emits safe socket tuple only within context',async()=>{
 const records:any[]=[];const f=observeFetch(async()=>{channel('undici:client:sendHeaders').publish({headers:'HEADER_CANARY',socket:{localAddress:'127.0.0.1',localPort:50000,remoteAddress:'198.18.0.76',remotePort:443,password:'CANARY'}});return new Response('ok');},x=>records.push(x),KEY);
 await f(URL_BASE,{method:'POST'});assert.equal(records[1].phase,'socket');assert.equal(records[1].socket.localPort,50000);assert.ok(!JSON.stringify(records).includes('CANARY'));
 channel('undici:client:sendHeaders').publish({socket:{localPort:123}});assert.equal(records.length,3);
});
test('adapter retains options and unrelated calls',()=>{
 const calls:any[]=[];const runtime={streamSimple(...args:any[]){calls.push(args);return 'sentinel';}};
 attachPreflightMetadata(runtime,()=>{},KEY);const opts={maxRetries:0,timeoutMs:101};
 runtime.streamSimple({provider:'other'},[],opts);assert.equal(calls[0][2],opts);
 runtime.streamSimple({provider:'Tongji',id:'Qwen3.8-27B',api:'openai-completions',baseUrl:'https://agi.tongji.edu.cn/v1'},[],opts);
 assert.equal(calls[1][2].timeoutMs,101);assert.equal(calls[1][2].maxRetries,0);assert.equal(typeof calls[1][2].fetch,'function');
});
test('installed Pi/OpenAI SDK fake-fetch captures actual 403 URL/method',async()=>{
 const {stream}=await import(new URL('../../../node_modules/@earendil-works/pi-ai/dist/api/openai-completions.js',import.meta.url).href);
 const records:any[]=[];let n=0;
 const f=observeFetch(async(input,init)=>{n++;assert.equal(String(input),URL_BASE);assert.equal(init?.method,'POST');return new Response('{"error":{"code":403,"message":"BODY_CANARY"}}',{status:403,headers:{'content-type':'application/json'}});},x=>records.push(x),KEY);
 const model={id:'Qwen3.8-27B',name:'Qwen3.8-27B',api:'openai-completions',provider:'Tongji',baseUrl:'https://agi.tongji.edu.cn/v1',reasoning:false,input:['text'],cost:{input:0,output:0,cacheRead:0,cacheWrite:0},contextWindow:32768,maxTokens:32};
 const result=await stream(model,{messages:[{role:'user',content:'REQUEST_CANARY',timestamp:0}]},{apiKey:'DUMMY_CANARY',fetch:f,maxRetries:0,env:{}}).result();
 assert.equal(n,1);assert.equal(result.stopReason,'error');assert.equal(records.at(-1).status,403);assert.ok(!JSON.stringify(records).includes('CANARY'));
});
