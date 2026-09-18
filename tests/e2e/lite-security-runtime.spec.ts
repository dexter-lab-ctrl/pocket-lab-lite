import { expect, test } from '@playwright/test';

const forbiddenPorts=new Set(['14222','18181','18222']);
function wsUrl(baseURL:string){const u=new URL(baseURL);u.protocol=u.protocol==='https:'?'wss:':'ws:';u.pathname='/ws/events';u.search='';return u.toString();}

test('browser egress remains same-origin',async({page,baseURL})=>{
  const seen:string[]=[]; page.on('request',r=>seen.push(r.url())); await page.goto('/?screen=home');
  const origin=new URL(baseURL!).origin;
  for(const raw of seen){const u=new URL(raw);expect(u.origin).toBe(origin);expect(forbiddenPorts.has(u.port)).toBeFalsy();expect(u.protocol==='nats:').toBeFalsy();}
});

test('hostile origin cannot read Pocket Lab API',async({page,baseURL})=>{
  await page.goto('data:text/html,<title>hostile</title>');
  const r=await page.evaluate(async target=>{try{const x=await fetch(new URL('/api/lite/status',target),{credentials:'include',mode:'cors'});return{readable:true,status:x.status,body:Boolean(await x.text())};}catch{return{readable:false,status:0,body:false};}},baseURL!);
  expect(r.readable&&r.body).toBeFalsy();
});

test('cross-origin mutation-shaped assurance request is rejected',async({page,baseURL})=>{
  await page.goto('data:text/html,<title>hostile</title>');
  const r=await page.evaluate(async target=>{try{const x=await fetch(new URL('/api/lite/harness/security-assurance/runs',target),{method:'POST',credentials:'include',mode:'cors',headers:{'Content-Type':'application/json'},body:JSON.stringify({suite_id:'smoke'})});return{accepted:x.status>=200&&x.status<300};}catch{return{accepted:false};}},baseURL!);
  expect(r.accepted).toBeFalsy();
});

test('unauthenticated event websocket discloses no runtime events',async({page,baseURL})=>{
  await page.goto('data:text/html,<title>hostile</title>');
  const r=await page.evaluate(async url=>await new Promise<{opened:boolean,message:boolean}>(resolve=>{const s=new WebSocket(url);let opened=false,message=false,done=false;const finish=()=>{if(done)return;done=true;try{s.close();}catch{}resolve({opened,message});};s.onopen=()=>{opened=true;};s.onmessage=()=>{message=true;finish();};s.onerror=finish;s.onclose=finish;setTimeout(finish,1800);}),wsUrl(baseURL!));
  expect(r.opened).toBeFalsy(); expect(r.message).toBeFalsy();
});

test('PWA caches and browser storage expose no obvious authority keys',async({page,context,baseURL})=>{
  await page.goto('/?screen=home'); const origin=new URL(baseURL!).origin;
  const urls=await page.evaluate(async()=>{const out:string[]=[];for(const n of await caches.keys()){for(const r of await (await caches.open(n)).keys())out.push(r.url);}return out;});
  for(const raw of urls)expect(new URL(raw).origin).toBe(origin);
  const keys=await page.evaluate(()=>({local:Object.keys(localStorage),session:Object.keys(sessionStorage)}));
  expect(JSON.stringify(keys)).not.toMatch(/password|authorization|private[_-]?key|api[_-]?key/i);
  for(const c of (await context.cookies(origin)).filter(x=>/session|auth|pocket/i.test(x.name))){expect(c.secure).toBeTruthy();expect(c.httpOnly).toBeTruthy();expect(['Strict','Lax']).toContain(c.sameSite);}
});
