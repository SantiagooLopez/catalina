import {test, after} from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {rmSync} from 'node:fs';
execFileSync(process.execPath, ['node_modules/typescript/bin/tsc','src/api.ts','--outDir','.test-build','--target','ES2022','--module','ESNext','--moduleResolution','Bundler','--skipLibCheck']);
globalThis.window = new EventTarget();
const {api, ApiError} = await import('../.test-build/api.js');
const user = {id:1,email:'test@example.com',nombre:'Prueba',rol:'estudiante',activo:true};
const json = (data, status=200) => new Response(JSON.stringify(data), {status,headers:{'Content-Type':'application/json'}});
const tokens = {access_token:'access',refresh_token:'refresh',refresh_expires_at:'2099-01-01',user};
after(()=>rmSync('.test-build',{recursive:true,force:true}));
test('login, paginated history, answer payload, and logout use the API contract', async()=>{
 const calls=[];
 globalThis.fetch = async(url,init)=>{
  calls.push({url,...init});
  if(url.endsWith('/auth/login')) return json(tokens);
  assert.equal(init.headers.Authorization, url.endsWith('/auth/logout') ? undefined : 'Bearer access');
  if(url.includes('offset=0')) return json({items:Array.from({length:100},(_,id)=>({id})),limit:100,offset:0});
  if(url.includes('offset=100')) return json({items:[{id:100}],limit:100,offset:100});
  if(url.endsWith('/answers')) {assert.deepEqual(JSON.parse(init.body),{conversation_id:9,query:'Pregunta'});return json({text:'Respuesta',citations:[]});}
  if(url.endsWith('/auth/logout')) return new Response(null,{status:204});
  throw new Error('Unexpected URL: '+url);
 };
 assert.deepEqual(await api.login(user.email,'password'),user);
 assert.equal((await api.conversations()).length,101);
 assert.equal((await api.answer(9,'Pregunta')).text,'Respuesta');
 await api.logout();
 await assert.rejects(api.conversations(),e=>e instanceof ApiError && e.status===401);
 assert.deepEqual(JSON.parse(calls[0].body),{email:user.email,password:'password'});
});
test('concurrent 401 responses share a single refresh and use rotated tokens', async()=>{
 let refreshes=0;
 globalThis.fetch = async(url,init)=>{
  if(url.endsWith('/auth/login')) return json(tokens);
  if(url.endsWith('/auth/refresh')) {refreshes++;await new Promise(r=>setTimeout(r,20));return json({...tokens,access_token:'rotated',refresh_token:'rotated-refresh'});}
  if(init.headers.Authorization==='Bearer access') return json({error:{message:'Expired'}},401);
  assert.equal(init.headers.Authorization,'Bearer rotated');return json({items:[],limit:100,offset:0});
 };
 await api.login(user.email,'password');
 await Promise.all([api.conversations(),api.messages(1)]);
 assert.equal(refreshes,1);
});
test('failed refresh clears auth and emits expiry; API errors preserve useful details', async()=>{
 let expired=0;window.addEventListener('catalina:expired',()=>expired++,{once:true});
 globalThis.fetch=async(url)=>url.endsWith('/auth/login')?json(tokens):json({error:{message:'Sesión no válida'}},401);
 await api.login(user.email,'password');
 await assert.rejects(api.conversations(),/Sesión no válida/);
 assert.equal(expired,1);
 await assert.rejects(api.messages(1),/Inicia sesión/);
 globalThis.fetch=async()=>json({error:{message:'Servicio en mantenimiento'}},503);
 await assert.rejects(api.health(),/Servicio en mantenimiento/);
});
