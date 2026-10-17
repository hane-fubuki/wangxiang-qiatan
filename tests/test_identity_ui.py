"""Behavior checks for independent user and AI identities, using isolated UI state."""
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which("node"), "Node.js is needed for browser logic checks")
class IdentityUITests(unittest.TestCase):
    def test_role_modes_scope_history_and_recovery(self):
        script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let source = fs.readFileSync(process.argv[1],'utf8').replace(/\r\n/g,'\n');
source = source.replace(/^import \{[^}]+\} from '\.\/([^']+)';\n/gm, (_, filename) => fs.readFileSync(require('node:path').join(require('node:path').dirname(process.argv[1]), filename), 'utf8').replace(/\bexport\s+(?=const\b)/g, '') + '\n');
source = source.replace('\nrenderAll();\ninitializeTransport();','\n');
const elements = new Map(), selected = [], calls = [];
class Element {
  constructor() {this.hidden=false;this.open=false;this.value='';this.innerHTML='';this.textContent='';this.listeners={};this.style={};this.dataset={};this.children=[];this.attributes={};this.disabled=false;this.scrollHeight=0;this.scrollTop=0;this.clientHeight=0;this.offsetWidth=140;this.offsetHeight=40;this.maxLength=12000;const values=new Set();this.classList={toggle:(x,on)=>{if(on ?? !values.has(x))values.add(x);else values.delete(x);return values.has(x)},add:x=>values.add(x),remove:x=>values.delete(x),contains:x=>values.has(x)};}
  addEventListener(type,fn){(this.listeners[type] ||= []).push(fn);}
  async fire(type,event={}) {for(const fn of this.listeners[type] || [])await fn(event);}
  setAttribute(name,value){this.attributes[name]=value;}
  getAttribute(name){return this.attributes[name];}
  showModal(){this.open=true;}
  close(){this.open=false;this.fire('close');}
  focus(){}
  click(){}
  setRangeText(text,start=0,end=start){this.value=this.value.slice(0,start)+text+this.value.slice(end);this.selectionStart=this.selectionEnd=start+text.length;}
  append(...xs){this.children.push(...xs);}
  appendChild(x){this.children.push(x);}
  contains(){return false;}
  querySelector(s){return get(this.key + ' ' + s);}
  querySelectorAll(){return [];}
}
function get(key){if(!elements.has(key)){const el=new Element();el.key=key;elements.set(key,el);}return elements.get(key);}
const page = fs.readFileSync(require('node:path').join(require('node:path').dirname(process.argv[1]),'index.html'),'utf8');
const staticIcons = [...page.matchAll(/data-icon="([^"]+)"/g)].map((match,index)=>{const el=get(`static-icon-${index}`);el.dataset.icon=match[1];return el;});
const context=vm.createContext({console,URL,Date,Map,Set,JSON,Promise,AbortController,HTMLImageElement:Element,innerWidth:420,innerHeight:800,
  setTimeout:()=>0,clearTimeout:()=>{},requestAnimationFrame:fn=>fn(),
  document:{querySelector:get,querySelectorAll:s=>s === '#scene-member-picker input:checked' ? selected : s === '[data-icon]' ? staticIcons : [],addEventListener(){},createElement:tag=>new Element(),body:new Element()},
  window:{innerWidth:420,addEventListener(){},matchMedia:()=>({matches:true}),location:{origin:'http://127.0.0.1:8765',assign(){throw Error('unexpected navigation')}}},
  localStorage:{setItem(){},getItem(){return null},removeItem(){}}, fetch:()=>{throw Error('unexpected request')}, selected,calls});
vm.runInContext(source,context);
const run=code=>vm.runInContext(code,context);
const json=code=>JSON.parse(run(`JSON.stringify(${code})`));

async function main(){
  // Belle is an optional AI guest. Lumine is exclusively a human role in Wangsheng.
  for(const room of json('defaultRooms')) {
    assert(room.characters.belle.optional);
    assert.equal(Boolean(room.characters.lumine),false);
    assert.equal(Boolean(room.userCharacters.lumine),room.id==='wangsheng-trio');
    assert(room.userCharacters.belle);
    assert(!json(`defaults(${JSON.stringify(room.id)}).participants`).includes('belle'));
    assert(!json(`defaults(${JSON.stringify(room.id)}).participants`).includes('lumine'));
  }
  assert.equal(run("defaults('wangsheng-trio').userRole"),'lumine');
  assert.equal(run("normalizedIdentity({},'wangsheng-trio').userRole"),'lumine');
  assert.equal(run("normalizedIdentity({userRole:null,interactionMode:'chat'},'wangsheng-trio').userRole"),'self');
  run("state.connected=true;state.roomId='wangsheng-trio';state.settings={...defaults('wangsheng-trio'),userRole:'self',participants:['gemini','belle']};renderAll()");
  assert.deepEqual(json('availableUserRoles()'),['lumine','belle']);
  assert(get('#user-role').innerHTML.includes('荧'));
  assert(get('#user-role').innerHTML.includes('铃'));
  assert.equal(get('#participation-mode').value,'self');
  get('#message-input').value='还没有发送的草稿';
  get('#user-role').value='lumine';get('#participation-mode').value='role';
  await get('#participation-mode').fire('change');
  assert.equal(run('getSettings().userRole'),'lumine');
  assert.deepEqual(json('getSettings().participants'),['gemini','belle']);
  assert.equal(get('#message-input').value,'还没有发送的草稿');
  assert(get('#composer-identity').textContent.includes('荧（你扮演）'));
  assert(get('#message-input').placeholder.includes('以荧的身份'));
  assert(!get('#provider-cards').innerHTML.includes('data-provider="lumine"'));
  assert(!get('#messages').innerHTML.includes('data-character="lumine"'));
  assert.equal(run("isSkillCommand('/设定 荧 简短一些')"),true);
  assert.deepEqual(json('sceneMemberOptions()').filter(([id])=>id==='lumine'),[]);
  assert.equal(json('sceneMemberOptions()')[0][1],'荧（你扮演）');
  // Switching to scene mode does not recruit the formerly controlled role on the user's behalf.
  await run("switchIdentity('scene')");
  assert.equal(run('getSettings().interactionMode'),'scene');
  assert.equal(run('getSettings().userRole'),'self');
  assert.deepEqual(json('getSettings().participants'),['gemini','belle']);
  assert(get('#identity-help').textContent.includes('先让想观察的角色入座'));
  assert(get('#message-input').placeholder.includes('描述地点'));
  // Refuse an empty table, without silently substituting any other character.
  run("state.settings={...defaults('wangsheng-trio'),userRole:'self',participants:['belle']};renderAll()");
  await run("switchIdentity('role','belle')");
  assert.equal(run('getSettings().userRole'),'self');
  assert.deepEqual(json('getSettings().participants'),['belle']);
  assert(get('#toast').textContent.includes('至少一位其他'));
  // A live run can switch identities; persist first, then drop local pending run state.
  run("state.conversations=[{id:'identity',roomId:'wangsheng-trio',settings:{...defaults('wangsheng-trio'),userRole:'self',participants:['gemini','belle']},messages:[{id:'old',role:'user',content:'旧消息',createdAt:'2026-10-17T00:00:00Z',actor:{mode:'chat',characterId:'self',name:'旧名字'}}]}];state.activeId='identity';state.runs.identity='old-run';state.runStates.identity={runId:'old-run',providers:{belle:'typing'}};renderAll()");
  assert.equal(get('#participation-mode').disabled,false);
  run("api=async (path,options={})=>{calls.push({path,options});return {conversation:{...activeConversation(),settings:options.body.settings,identityEpoch:2}}}");
  await run("switchIdentity('role','lumine')");
  assert.equal(calls.at(-1).path,'/api/conversations/identity');
  assert.equal(calls.at(-1).options.method,'PATCH');
  assert.equal(calls.at(-1).options.body.settings.userRole,'lumine');
  assert.equal(run('isRunning()'),false);
  assert.equal(get('#message-input').value,'还没有发送的草稿');
  assert.equal(json('activeConversation().messages').length,1);
  // Failure recovers the server's saved settings rather than claiming the optimistic mode succeeded.
  run("api=async (path,options={})=>{calls.push({path,options});if(options.method==='PATCH')throw Error('保存失败');return {conversation:{...activeConversation(),settings:{...defaults('wangsheng-trio'),userRole:'lumine',participants:['gemini','belle']},identityEpoch:2}}}");
  await run("switchIdentity('scene')");
  assert.equal(run('getSettings().userRole'),'lumine');
  assert.equal(run('getSettings().interactionMode'),'chat');
  assert.equal(get('#message-input').value,'还没有发送的草稿');
  assert.equal(get('#participation-mode').value,'role');
  assert.equal(get('#toast').textContent,'保存失败');
  // Historical labels and avatars come from each message, never the currently selected role.
  run("activeConversation().messages=[{id:'m1',role:'user',content:'作为荧说的话',createdAt:'2026-10-17T00:00:00Z',actor:{mode:'chat',characterId:'lumine',name:'荧'}},{id:'m2',role:'user',content:'作为玲说的话',createdAt:'2026-10-17T00:01:00Z',actor:{mode:'chat',characterId:'belle',name:'玲'}},{id:'m3',role:'user',content:'场景开场',createdAt:'2026-10-17T00:02:00Z',actor:{mode:'scene',characterId:'self',name:'不该冒充的人'}},{id:'m4',role:'user',content:'以自己说的话',createdAt:'2026-10-17T00:03:00Z',actor:{mode:'chat',characterId:'self',name:'旧名字'}},{id:'m5',role:'user',content:'旧版本无元数据',createdAt:'2026-10-17T00:04:00Z'}];state.userProfile={name:'现在的自己',avatar:'/assets/user.png'};renderMessages()");
  const markup=get('#messages').innerHTML;
  for(const text of ['荧','玲','场景描述','旧名字','现在的自己','protagonist-lumine-avatar.png','protagonist-belle-avatar.png']) assert(markup.includes(text));
  assert(!markup.includes('不该冒充的人'));
  assert(run("userMessageAvatar({},'wangsheng-trio')").includes('protagonist-lumine-avatar.png'));
  assert(run("userMessageAvatar({},'zzz-trio')").includes('/assets/user.png'));
  assert(run("userMessageAvatar({actor:{mode:'chat',characterId:'self'}},'wangsheng-trio')").includes('/assets/user.png'));
  assert(run("userMessageAvatar({actor:{mode:'chat',characterId:'belle'}},'wangsheng-trio')").includes('protagonist-belle-avatar.png'));

  assert.equal(run("userMessageName(activeConversation().messages[0])"),'荧');
  assert.equal(run("userMessageName(activeConversation().messages[2])"),'场景描述');
  run("globalThis.Blob=class {constructor(parts){globalThis.downloaded=parts.join('')}};URL.createObjectURL=()=> 'blob:test';URL.revokeObjectURL=()=>{}");
  await get('#export-chat').fire('click');
  for(const name of ['荧','玲','场景描述','旧名字','现在的自己']) assert(run('downloaded').includes('## '+name));
  // Old epochs remain visible history but cannot continue under a newly selected identity.
  run("activeConversation().identityEpoch='new-epoch';activeConversation().messages=[{id:'old',role:'user',content:'过去的话',identityEpoch:'old-epoch'}]");
  assert.equal(run('hasCurrentScenePrompt()'),false);
  run("activeConversation().messages.push({id:'current',role:'user',content:'新身份开场',identityEpoch:'new-epoch'})");
  assert.equal(run('hasCurrentScenePrompt()'),true);
  run("activeConversation().messages[1].audience=['user',...characterIds().filter(id=>id!=='lumine')];activeConversation().messages[1].scene={kind:'public'}");
  assert.equal(run('hasCurrentScenePrompt()'),true);
  // Cross-room stale identity falls back to self; Belle is available even in the ordinary model room.
  run("state.activeId=null;state.roomId='standard';state.settings={...defaults('standard'),userRole:'lumine'};renderAll()");
  assert.deepEqual(json('availableUserRoles()'),['belle']);
  assert.equal(run('getSettings().userRole'),'self');
  assert.equal(get('#participation-mode').value,'self');
  assert(!get('#user-role').innerHTML.includes('荧'));
  assert.equal(get('#skills-open').hidden,false);
  assert.equal(run("isSkillCommand('/设定 玲 简短一些')"),true);
  assert.equal(run("isSkillCommand('/撤销设定 玲')"),true);
  assert.equal(run("isSkillCommand('/设定 荧 简短一些')"),false);
  assert.equal(run("isSkillCommand('请更新玲的skill：保持活泼')"),true);
  assert.equal(run("normalizedIdentity({userRole:'belle'}).userRole"),'self');
  assert.equal(run("normalizedIdentity({userRole:'belle',interactionMode:'scene'}).interactionMode"),'chat');
  assert(get('#provider-cards').innerHTML.includes('data-provider="belle"'));
  run("api=async(path,options={})=>{calls.push({path,options});if(path.startsWith('/api/skills?'))return {skills:[{id:'belle',roomId:'standard',name:'玲',version:1,content:'',history:[],base:'基础设定'}]};return {id:'belle',roomId:'standard',name:'玲',version:2,content:options.body.content,history:[],base:'基础设定'}}");
  await get('#skills-open').fire('click');
  await run('Promise.resolve()');
  assert.equal(get('#skills-dialog').open,true);
  assert.equal(run('state.skills[0].id'),'belle');
  assert(calls.some(call=>call.path==='/api/skills?roomId=standard'));
  run("skillEdit().content='保持简短'");await run('saveSkill()');
  assert.equal(calls.at(-1).options.body.roomId,'standard');
  assert.equal(run('state.skills[0].content'),'保持简短');
  await run("switchIdentity('role','belle')");
  assert.equal(run('getSettings().userRole'),'belle');
  assert(get('#provider-cards').innerHTML.match(/data-provider="belle"[^>]*disabled/));
  assert(get('#message-input').placeholder.includes('以铃的身份'));
  run("state.connected=false;renderAll()");
  assert.equal(get('#participation-mode').disabled,true);
  console.log('identity UI behavioral checks passed');
}
main().catch(error=>{console.error(error);process.exitCode=1});
"""
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([shutil.which("node"), "-e", script, str(root / "web" / "app.js")], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
