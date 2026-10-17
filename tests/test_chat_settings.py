"""Persistent reasoning and research controls, including older conversation records."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from backend.store import Store, default_settings, validate_settings


class ChatSettingsTests(unittest.TestCase):
    def test_legacy_settings_receive_defaults_without_changing_participation(self):
        legacy = {"participants": ["gemini"], "mode": "all", "maxRounds": 2}
        result = validate_settings({}, legacy, "zzz-trio")
        self.assertEqual(result["reasoning"], "auto")
        self.assertEqual(result["webSearch"], "auto")
        self.assertEqual(result["participants"], ["gemini"])
        self.assertNotIn("reasoning", legacy)
        for room in ("standard", "zzz-trio"):
            self.assertEqual(default_settings(room)["reasoning"], "auto")
            self.assertEqual(default_settings(room)["webSearch"], "auto")

    def test_settings_survive_reload_and_reject_invalid_update_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            item = store.create("zzz-trio")
            identifier = item["id"]
            updated = store.update(identifier, {"settings": {"reasoning": "deep", "webSearch": "always"}})
            self.assertEqual(Store(directory).get(identifier), updated)
            for key, values in (("reasoning", ("ultra", "", None, True, [], {})),
                                ("webSearch", ("yes", "", None, True, [], {}))):
                for value in values:
                    with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                        store.update(identifier, {"title": "must not save", "settings": {key: value}})
                    self.assertEqual(store.get(identifier), updated)
                    self.assertEqual(Store(directory).get(identifier), updated)
            disabled = store.update(identifier, {"settings": {"webSearch": "off"}})
            self.assertEqual(disabled["settings"]["webSearch"], "off")
            self.assertEqual(disabled["settings"]["reasoning"], "deep")

    def test_loading_old_records_does_not_rewrite_chat_file(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            item = store.create()
            item["settings"].pop("reasoning")
            item["settings"].pop("webSearch")
            payload = json.dumps({"version": 1, "conversations": [item]}, ensure_ascii=False)
            store.path.write_text(payload, encoding="utf-8")
            reloaded = Store(directory)
            self.assertEqual(reloaded.path.read_text(encoding="utf-8"), payload)
            update = reloaded.update(item["id"], {"settings": {"reasoning": "deep"}})
            self.assertEqual(update["settings"]["webSearch"], "auto")


@unittest.skipUnless(shutil.which("node"), "Node.js is needed for browser logic checks")
class ResearchUITests(unittest.TestCase):
    def test_research_renders_only_status_without_exposing_or_mutating_metadata(self):
        script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[1], 'utf8');
const start = source.indexOf('function researchLabel(');
const end = source.indexOf('const localTime =', start);
class Element {
  constructor(tag) {this.tag = tag; this.children = []; this.textContent = '';}
  append(...children) {this.children.push(...children);}
  set innerHTML(_) {throw new Error('Research must not use innerHTML');}
}
const context = vm.createContext({URL, Date, Set, document:{createElement:tag => new Element(tag)}});
vm.runInContext(source.slice(start,end),context);
const hostileTitle = '<img src=x onerror=alert(1)>';
context.input = {status:'complete',checkedAt:'2026-10-16T07:30:00Z',summary:'PRIVATE SUMMARY',sources:[
  {title:hostileTitle,url:'https://example.com/article'},
  {title:'duplicate',url:'https://example.com/article'},
  {title:'script',url:'javascript:alert(1)'},
  {title:'credentials',url:'https://name:password@example.com/'},
  {title:'data',url:'data:text/html,<script>alert(1)</script>'},
  {title:'relative',url:'/api/auth/logout'},
  {title:'control',url:'https://example.com/\n'},
  {title:'',url:'http://source.example/news'}
]};
const original = JSON.stringify(context.input);
context.container = new Element('div');
vm.runInContext('renderWebResearch(container,input)',context);
const tree = context.container.children[0];
assert.equal(tree.textContent,'已查阅相关信息');
assert.equal(tree.children.length,0);
for (const hidden of ['PRIVATE SUMMARY',hostileTitle,'https:','javascript:','2026-10-16','查询于']) {
  assert(!JSON.stringify(tree).includes(hidden));
}
assert.equal(JSON.stringify(context.input),original);
context.input.status='failed';context.input.error='<script>private error</script>';
context.container = new Element('div');
vm.runInContext('renderWebResearch(container,input)',context);
assert.equal(context.container.children[0].textContent,'联网查询未完成');
assert.equal(context.container.children[0].children.length,0);
assert(!JSON.stringify(context.container).includes('private error'));
context.input={status:'complete',sources:[{url:'file:///C:/secret'}]};context.container=new Element('div');
vm.runInContext('renderWebResearch(container,input)',context);
assert.equal(context.container.children[0].textContent,'已查阅相关信息');
assert.equal(context.container.children[0].children.length,0);
for (const input of [null,{}, {status:'searching'}, {status:'<script>private status</script>'}]) {
  context.input=input;context.container=new Element('div');
  vm.runInContext('renderWebResearch(container,input)',context);
  assert.equal(context.container.children.length,0);
}
assert.equal(vm.runInContext("researchLabel({research:{stage:'searching',model:'gpt-6.1-sol'}})",context),'正在联网查询资料…');
assert.equal(vm.runInContext('researchLabel({research:{}})',context),'');
"""
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([shutil.which("node"), "-e", script, str(root / "web" / "app.js")],
                                capture_output=True, text=True, encoding="utf-8", timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
