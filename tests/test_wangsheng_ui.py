"""Exercise imported UI behavior with isolated browser state, never real chats."""
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which("node"), "Node.js is needed for browser logic checks")
class WangshengUITests(unittest.TestCase):
    def test_room_scene_connection_and_targeted_delete_behavior(self):
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
  setRangeText(text,start=0,end=start){this.value=this.value.slice(0,start)+text+this.value.slice(end);this.selectionStart=this.selectionEnd=start+text.length;}
  append(...xs){this.children.push(...xs);}
  appendChild(x){this.children.push(x);}
  contains(){return false;}
  querySelector(s){return get(this.key + ' ' + s);}
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
  assert.equal(run('state.roomId'),'zzz-trio');
  assert.deepEqual(json('state.rooms.map(r=>r.id).sort()'),['standard','zzz-trio','wangsheng-trio','zzz-mockingbird','zzz-obol','zzz-yunkui','zzz-krampus','zzz-outer-ring','zzz-roscaelifer'].sort());
  assert.equal(json("defaults('standard').participants").length,4);
  assert.equal(json("defaults('zzz-trio').participants").length,3);
  assert.equal(json("defaults('wangsheng-trio').participants").length,7);
  run('renderAll()');assert.equal(get('#scene-button').hidden,false);assert.equal(get('#local-connection-form').hidden,true);
  const defaultStatic = staticIcons.map(el=>el.innerHTML);
  const roomMenu = id => get('#room-list').innerHTML.match(new RegExp(`<button[^>]*data-room-id="${id}"[\\s\\S]*?</button>`))[0];
  assert(staticIcons.length > 20);assert(staticIcons.every(el=>el.innerHTML.includes('data-icon-theme="default"')));
  run("state.roomId='wangsheng-trio';state.settings=defaults(state.roomId);state.connected=true;state.userProfile={name:'羽吹雪',avatar:'/assets/user-avatar.png'};state.capabilities.localConnection={available:true};renderAll()");
  assert.equal(get('#scene-button').hidden,false);assert.equal(get('#room-privacy-note').hidden,false);assert.equal(get('#local-connection-form').hidden,false);
  assert(get('#app').classList.contains('wangsheng-room'));
  assert(staticIcons.every(el=>el.innerHTML.includes('data-icon-theme="wangsheng"')));
  assert(staticIcons.every((el,index)=>el.innerHTML !== defaultStatic[index]));
  assert(get('#messages').innerHTML.includes('data-icon-theme="wangsheng"'));
  assert(get('#scene-button').innerHTML.includes('data-icon-theme="wangsheng"'));
  assert(get('#brand-image').getAttribute('src').startsWith('data:image/svg+xml,'));
  assert.equal(get('#brand-image').getAttribute('data-icon-theme'),'wangsheng');
  assert(roomMenu('wangsheng-trio').includes('data-icon-theme="wangsheng"'));
  assert(roomMenu('zzz-trio').includes('data-icon-theme="default"'));
  assert(roomMenu('zzz-krampus').includes('data-icon-theme="studio"'));
  assert(roomMenu('standard').includes('data-icon-theme="default"'));
  assert(get('#messages').innerHTML.includes('data-character-count="8"'));
  for(const name of ['胡桃','钟离','若娜瓦','派蒙','香菱','魈','兹白'])assert(get('#messages').innerHTML.includes(name));
  assert(get('#room-list').innerHTML.indexOf('妄想茶话会') < get('#room-list').innerHTML.indexOf('往生堂群聊'));
  assert(run('userAvatar()').includes('/assets/user-avatar.png'));
  await get('#scene-button').fire('click');
  assert(get('#scene-member-picker').innerHTML.includes('value="user" checked>荧（你扮演）'));
  selected.push({value:'user'},{value:'xiao'});assert.equal(run('selectedSceneCommand()'),'/悄悄话 user xiao');
  selected.pop();assert.throws(()=>run('selectedSceneCommand()'),/请选择/);selected.push({value:'xiao'});
  run("state.capabilities.localConnection={available:false};renderProviders()");
  assert.equal(get('#local-connection-form').hidden,true);
  run("api=async (path,options={})=>{calls.push({path,options});return {baseUrl:'https://models.example/v1',hasKey:true,model:'example-chat',message:'ok'}}");
  await run('openSettings()');assert.equal(calls.length,0);
  await run("updateLocalConnection('save')");assert.equal(calls.length,0);
  run('state.capabilities.localConnection.available=true');await run('openSettings()');
  assert.equal(calls[0].path,'/api/local-connection');assert.equal(get('#api-base-url').value,'https://models.example/v1');
  get('#api-secret').value='temporary-secret';get('#settings-dialog').close();assert.equal(get('#api-secret').value,'');
  run("state.modelOptions=[{providerId:'custom',model:'example-chat',name:'自定义接口 · example-chat',configured:true}];state.settings.models={xiao:{providerId:'custom',model:'example-chat'}}");
  assert.equal(run("providerFor('xiao').providerId"),'custom');assert(run("modelChooserMarkup('xiao')").includes('custom:example-chat'));
  run("state.conversations=[{id:'A',roomId:'wangsheng-trio',title:'A桌',settings:defaults('wangsheng-trio'),messages:[],scene:{kind:'private',label:'胡桃与魈',audience:['gemini','xiao']}},{id:'B',roomId:'wangsheng-trio',title:'B桌',settings:defaults('wangsheng-trio'),messages:[]}];state.activeId='A';renderAll()");
  assert.equal(get('#heading-description').textContent,'胡桃与魈');assert(get('#message-input').placeholder.includes('描述在场伙伴'));
  run("requestConversationDelete('B')");assert(get('#delete-dialog .dialog-description').textContent.includes('B桌'));assert.equal(run('state.activeId'),'A');
  await get('#confirm-delete').fire('click');
  assert.equal(calls.at(-1).path,'/api/conversations/B');assert.equal(calls.at(-1).options.method,'DELETE');
  assert.deepEqual(json('state.conversations.map(c=>c.id)'),['A']);assert.equal(run('state.activeId'),'A');
  run("state.activeId=null;state.settings=defaults(state.roomId);state.conversations=[]");
  await get('#web-search-toggle').fire('click');assert.equal(run('getSettings().webSearch'),'off');assert.equal(get('#web-search-toggle').getAttribute('aria-pressed'),'false');
  await get('#web-search-toggle').fire('click');assert.equal(run('getSettings().webSearch'),'auto');
  run("state.roomId='zzz-trio';state.settings=defaults(state.roomId);renderAll()");
  assert.equal(get('#scene-button').hidden,false);assert(!get('#app').classList.contains('wangsheng-room'));assert.equal(get('#room-privacy-note').hidden,true);
  assert.deepEqual(staticIcons.map(el=>el.innerHTML),defaultStatic);
  assert(!get('#messages').innerHTML.includes('data-icon-theme="wangsheng"'));
  assert.equal(get('#brand-image').getAttribute('src'),'/favicon.svg');
  assert.equal(get('link[rel="icon"]').getAttribute('href'),'/favicon.svg');
  run("state.roomId='zzz-krampus';state.settings=defaults(state.roomId);renderAll()");
  const studioBrand = get('#brand-image').getAttribute('src');
  assert.equal(get('#brand-name').textContent,'2493工作室');
  assert(staticIcons.every(el=>el.innerHTML.includes('data-icon-theme="studio"')));
  run("state.roomId='wangsheng-trio';state.settings=defaults(state.roomId);renderAll()");
  assert.notEqual(get('#brand-image').getAttribute('src'),studioBrand);
  run("state.roomId='zzz-krampus';state.settings=defaults(state.roomId);renderAll()");
  assert.equal(get('#brand-image').getAttribute('src'),studioBrand);
  assert(staticIcons.every(el=>el.innerHTML.includes('data-icon-theme="studio"')));

  run("state.roomId='zzz-roscaelifer';state.settings=defaults(state.roomId);renderAll()");
  assert.equal(get('#brand-name').textContent,'天空之城');
  assert(get('#app').classList.contains('roscaelifer-room'));
  assert(staticIcons.every(el=>el.innerHTML.includes('data-icon-theme="roscaelifer"')));
  assert.equal(json("defaults('zzz-roscaelifer').participants").length,6);
  assert(get('#messages').innerHTML.includes('roscaelifer-lindverne-avatar.png'));
  assert(roomMenu('zzz-roscaelifer').includes('天空之城'));
  assert(roomMenu('zzz-mockingbird').includes('法厄同一生推'));
  run("state.roomId='zzz-trio';state.settings=defaults(state.roomId);renderAll()");
  assert(!get('#app').classList.contains('roscaelifer-room'));
  assert.deepEqual(staticIcons.map(el=>el.innerHTML),defaultStatic);

  // Scene selection follows room data, including full attendance and future rosters.
  for (const roomId of ['standard','zzz-trio','wangsheng-trio','zzz-yunkui','zzz-krampus']) {
    run(`state.roomId=${JSON.stringify(roomId)};state.activeId=null;state.settings=defaults(state.roomId);renderAll()`);
    assert.equal(get('#scene-button').hidden,false);
    assert.equal(get('#app').classList.contains('wangsheng-room'),roomId === 'wangsheng-trio');
    await get('#scene-button').fire('click');
    const members = json('sceneMemberOptions()');
    assert(get('#scene-member-help').textContent.includes(`2 至 ${members.length}`));
    for(const [id,name] of members) {
      assert(get('#scene-member-picker').innerHTML.includes(`value="${id}"`));
      assert(get('#scene-member-picker').innerHTML.includes(name));
    }
    selected.splice(0,selected.length,...members.map(([id])=>({value:id})));
    assert.equal(run('selectedSceneCommand()'),'/悄悄话 ' + members.map(([id])=>id).join(' '));
    selected.splice(0,selected.length,{value:'user'},{value:members[1][0]},{value:'not-in-this-room'},{value:members[1][0]});
    assert.equal(run('selectedSceneCommand()'),`/悄悄话 user ${members[1][0]}`);
    selected.splice(0,selected.length,{value:'user'},{value:'not-in-this-room'});
    assert.throws(()=>run('selectedSceneCommand()'),/请选择/);
    get('#scene-dialog').close();
  }
  run("state.rooms.push({id:'future-room',name:'未来频道',description:'新伙伴',characters:Object.fromEntries(Array.from({length:9},(_,i)=>['future-'+i,{name:'伙伴'+i}]))});state.roomId='future-room';state.settings={...defaults(),participants:['future-0']};renderAll()");
  assert.equal(get('#scene-button').hidden,false);
  await get('#scene-button').fire('click');
  assert(get('#scene-member-help').textContent.includes('2 至 10'));
  assert(get('#scene-member-picker').innerHTML.includes('伙伴1（未入座）'));
  selected.splice(0,selected.length,...json('sceneMemberOptions()').map(([id])=>({value:id})));
  assert.equal(run('selectedSceneCommand()'),'/悄悄话 user future-0 future-1 future-2 future-3 future-4 future-5 future-6 future-7 future-8');
  run("state.conversations=[{id:'future-private',roomId:'future-room',settings:state.settings,messages:[],scene:{kind:'private',label:'伙伴0与伙伴1',audience:['future-0','future-1']}}];state.activeId='future-private';renderAll()");
  assert(get('#message-input').placeholder.includes('描述在场伙伴'));
  assert(get('#scene-button').classList.contains('is-private'));
  assert(get('#scene-button').innerHTML.includes('伙伴0与伙伴1'));
  assert(!get('#app').classList.contains('wangsheng-room'));

  // The composer reflects actual responders, not the full room's seated roster.
  run("state.roomId='zzz-trio';state.roomProviders['zzz-trio']=['gemini','deepseek','gpt'].map(id=>({id,name:id,configured:true}));state.capabilities.localConnection={available:false};state.capabilities.imageGeneration={configured:false};state.conversations=[{id:'private-replies',roomId:'zzz-trio',settings:defaults('zzz-trio'),messages:[{id:'public-seed',role:'user',content:'全桌招呼',createdAt:'2026-10-17T00:00:00Z'},{id:'private-seed',role:'user',content:'你好',createdAt:'2026-10-17T00:01:00Z',audience:['user','gpt']}],scene:{kind:'private',label:'你与爱芮',audience:['user','gpt']}}];state.activeId='private-replies';renderAll()");
  assert.deepEqual(json('availableSceneParticipantIds()'),['gpt']);
  assert(get('#composer-participants').innerHTML.includes('爱芮'));
  assert(!get('#composer-participants').innerHTML.includes('千夏'));
  assert(!get('#composer-participants').innerHTML.includes('南宫羽'));
  assert.equal(get('#participant-count').textContent,'3 / 4 位入座');
  get('#message-input').value='';get('#message-input').selectionStart=0;get('#message-input').selectionEnd=0;
  await get('#mention-button').fire('click');assert.equal(get('#message-input').value,'@爱芮 ');
  assert.equal(get('#send-message').disabled,false);assert.equal(get('#continue-chat').disabled,false);
  run("activeConversation().settings.participants=['gemini','deepseek'];renderAll()");
  assert.deepEqual(json('availableSceneParticipantIds()'),[]);
  assert.equal(get('#composer-participants').innerHTML,'');
  assert.equal(get('#mention-button').disabled,true);
  assert.equal(get('#send-message').disabled,true);assert.equal(get('#continue-chat').disabled,true);
  run("activeConversation().settings.participants=['gemini','deepseek','gpt'];state.roomProviders['zzz-trio'].find(p=>p.id==='gpt').configured=false;renderAll()");
  assert.equal(get('#send-message').disabled,true);assert.equal(get('#continue-chat').disabled,true);
  const previousRequests = calls.length;
  await run('sendMessage()');await run('continueChat()');
  assert.equal(calls.length,previousRequests);
  const previousDraft = get('#message-input').value;
  await get('#mention-button').fire('click');assert.equal(get('#message-input').value,previousDraft);
  get('#message-input').value='/全桌';run('renderComposer()');
  assert.equal(get('#send-message').disabled,false);
  // The server owns image intent detection; independent image requests remain possible.
  get('#message-input').value='/生图 画一朵花';
  run('state.capabilities.imageGeneration.configured=true;renderComposer()');
  assert.equal(get('#send-message').disabled,false);
  assert.equal(get('#send-message').title,'当前场景暂无可回应伙伴，仍可发送生图指令');
  assert.equal(get('#continue-chat').disabled,true);
  run("api=async (path,options={})=>{calls.push({path,options});return {conversation:JSON.parse(JSON.stringify(activeConversation())),command:{type:'image',message:'已提交生图'}}}");
  await run('sendMessage()');
  assert.equal(calls.at(-1).path,'/api/conversations/private-replies/messages');
  assert.equal(calls.at(-1).options.body.content,'/生图 画一朵花');
  get('#message-input').value='继续聊聊';run('renderComposer()');
  assert.equal(get('#send-message').disabled,false);
  get('#message-input').value='我们继续';
  run("activeConversation().scene={kind:'public',audience:['user','gemini','deepseek','gpt']};renderAll()");
  assert.deepEqual(json('availableSceneParticipantIds()'),['gemini','deepseek']);
  assert(get('#composer-participants').innerHTML.includes('千夏'));
  assert(get('#composer-participants').innerHTML.includes('南宫羽'));
  assert(!get('#composer-participants').innerHTML.includes('爱芮'));
  assert.equal(get('#send-message').disabled,false);assert.equal(get('#continue-chat').disabled,false);
  get('#message-input').value='';get('#message-input').selectionStart=0;get('#message-input').selectionEnd=0;
  await get('#mention-button').fire('click');assert.equal(get('#message-input').value,'@千夏 ');
  run("state.roomProviders['zzz-trio'].find(p=>p.id==='gpt').configured=true;renderAll()");
  assert.deepEqual(json('availableSceneParticipantIds()'),['gemini','deepseek','gpt']);
  assert(get('#composer-participants').innerHTML.includes('爱芮'));

  // A continue may only reuse the latest shared user prompt with the same audience.
  for (const roomId of ['standard','zzz-trio','wangsheng-trio','zzz-yunkui','zzz-krampus','future-room']) {
    run(`state.roomId=${JSON.stringify(roomId)};state.roomProviders[state.roomId]=characterIds().map(id=>({id,name:id,configured:true}));state.conversations=[{id:'continue-boundary',roomId:state.roomId,settings:{...defaults(state.roomId),participants:characterIds()},messages:[{role:'user',content:'旧全桌消息'}],scene:{kind:'private',audience:['user',characterIds()[0]]}}];state.activeId='continue-boundary';renderAll()`);
    assert.equal(run('hasCurrentScenePrompt()'),false);
    assert.equal(get('#continue-chat').disabled,true);
    assert(get('#continue-chat').title.includes('先在当前场景发送'));
    const beforeContinue = calls.length;
    await run('continueChat()');assert.equal(calls.length,beforeContinue);
    run("activeConversation().messages.push({role:'user',content:'当前私谈',audience:[characterIds()[0],'user']});renderComposer()");
    assert.equal(run('hasCurrentScenePrompt()'),true);
    assert.equal(get('#continue-chat').disabled,false);
    run("activeConversation().messages.push({role:'user',content:'后来全桌话题',audience:['user',...characterIds()]});renderComposer()");
    assert.equal(get('#continue-chat').disabled,true);
    run("activeConversation().messages.pop();activeConversation().messages.push({role:'user',content:'另一处私谈',audience:['user',characterIds()[1]]});renderComposer()");
    assert.equal(get('#continue-chat').disabled,false);
    run("activeConversation().scene={kind:'public'};renderComposer()");
    assert.equal(get('#continue-chat').disabled,false); // Legacy public messages default to the full roster.
    run("activeConversation().messages=[];activeConversation().scene={kind:'private',audience:characterIds().slice(0,2)};renderComposer()");
    assert.equal(get('#continue-chat').disabled,true);
    run("activeConversation().messages.push({role:'user',content:'旁观者场景提示',audience:characterIds().slice(0,2)});renderComposer()");
    assert.equal(get('#continue-chat').disabled,false);
  }
  // Every roster supports concurrent thinking and one queued display at a time.
  for (const roomId of json('state.rooms.map(room => room.id)')) {
    run(`state.roomId=${JSON.stringify(roomId)};state.roomProviders[state.roomId]=characterIds().map(id=>({id,name:id,configured:true}));state.conversations=[{id:'turns',roomId:state.roomId,settings:{...defaults(state.roomId),participants:characterIds()},messages:[{id:'seed',role:'user',content:'我们聊聊吧',createdAt:'2026-10-17T00:00:00Z'}]}];state.activeId='turns';state.runs={turns:'run-concurrent'};state.runStates={turns:{runId:'run-concurrent',status:'running',round:1,providers:Object.fromEntries(characterIds().map(id=>[id,'waiting']))}};renderAll()`);
    const names = json('characterIds().map(id => speakerName(id))');
    assert.equal(get('#run-label').textContent,'第 1 轮讨论 · 伙伴正在准备回应…');
    assert.equal((get('#provider-cards').innerHTML.match(/provider-state active/g)||[]).length,0);
    assert(get('#provider-cards').innerHTML.includes('准备回应'));
    run("for(const id of characterIds())state.runStates.turns.providers[id]='thinking';renderProviders();renderComposer()");
    assert.equal(get('#run-label').textContent,`第 1 轮讨论 · ${names.length > 2 ? names[0] + '等 ' + names.length + ' 位伙伴' : names.join('、')}正在同时思考…`);
    assert.equal((get('#provider-cards').innerHTML.match(/provider-state active/g)||[]).length,names.length);
    run("state.runStates.turns.providers[characterIds()[0]]='typing';renderProviders();renderComposer()");
    assert.equal(get('#run-label').textContent,`第 1 轮讨论 · ${names[0]}正在输入… · ${names.length - 1} 位仍在思考`);
    assert.equal((get('#provider-cards').innerHTML.match(/正在输入…/g)||[]).length,1);
    // The typing role takes priority even when a thinker precedes it in the roster.
    run("for(const id of characterIds())state.runStates.turns.providers[id]='speaking';state.runStates.turns.providers[characterIds()[0]]='thinking';state.runStates.turns.providers[characterIds()[1]]='typing';if(characterIds().length > 2)state.runStates.turns.providers[characterIds()[2]]='queued';activeConversation().settings.reasoning='deep';renderProviders();renderComposer()");
    assert.equal(get('#run-label').textContent,`第 1 轮讨论 · ${names[1]}正在输入… · 1 位仍在深入思考${names.length > 2 ? ' · 1 位等待发送' : ''}`);
    assert.equal((get('#provider-cards').innerHTML.match(/provider-state active/g)||[]).length,2);
    assert.equal((get('#provider-cards').innerHTML.match(/已写好 · 等待发送/g)||[]).length,names.length > 2 ? 1 : 0);
    // Generated replies waiting in the server queue are not shown as still thinking.
    run("for(const id of characterIds())state.runStates.turns.providers[id]='queued';renderProviders();renderComposer()");
    assert.equal(get('#run-label').textContent,`第 1 轮讨论 · ${names.length} 位等待发送`);
    assert.equal((get('#provider-cards').innerHTML.match(/provider-state active/g)||[]).length,0);
    run("state.runStates.turns.providers[characterIds().at(-1)]='typing';renderProviders();renderComposer()");
    assert.equal(get('#run-label').textContent,`第 1 轮讨论 · ${names.at(-1)}正在输入… · ${names.length - 1} 位等待发送`);
    assert.equal((get('#provider-cards').innerHTML.match(/provider-state active/g)||[]).length,1);
    run("for(const id of characterIds())state.runStates.turns.providers[id]='speaking';state.runStates.turns.providers[characterIds()[1]]='thinking';renderProviders();renderComposer()");
    assert.equal(get('#run-label').textContent,`第 1 轮讨论 · ${names[1]}正在深入思考…`);
    assert.equal((get('#provider-cards').innerHTML.match(/provider-state active/g)||[]).length,1);
    assert(get('#provider-cards').innerHTML.includes('已回应 · 正在倾听'));
    run("state.runStates.turns.providers[characterIds()[0]]='thinking';renderComposer()");
    assert.equal(get('#run-label').textContent,`第 1 轮讨论 · ${names[0]}、${names[1]}正在同时深入思考…`);
    assert.equal(run('pollDelay()'),800);
    run('document.hidden=true');assert.equal(run('pollDelay()'),15000);run('document.hidden=false');
    run("delete state.runs.turns;state.runStates.turns.status='idle';state.runStates.turns.reason='stopped';renderProviders();renderComposer()");
    assert(!get('#run-label').textContent.includes('正在'));
    assert.equal((get('#provider-cards').innerHTML.match(/provider-state active/g)||[]).length,0);
    assert.equal(run('pollDelay()'),5000);
  }
  // Server-published messages and reloaded history render immediately, with no replay queue.
  run("transport='sse';globalThis.testEvents={};globalThis.EventSource=class {addEventListener(name,callback){testEvents[name]=callback}};connectEvents();testEvents.message({data:JSON.stringify({conversationId:'turns',message:{id:'published',role:'assistant',provider:characterIds()[0],content:'刚刚这一句，我接上了。',createdAt:'2026-10-17T00:01:00Z'}})})");
  assert(get('#messages').innerHTML.includes('刚刚这一句，我接上了。'));
  run('renderMessages()');assert(get('#messages').innerHTML.includes('刚刚这一句，我接上了。'));
}
main().catch(error=>{console.error(error);process.exitCode=1});
"""
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([shutil.which("node"), "-e", script, str(root / "web/app.js")],
                                capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
