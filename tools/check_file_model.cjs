const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const model = vm.createContext({});
vm.runInContext(fs.readFileSync(__dirname + '/../ui/studio/models/DraftFiles.js', 'utf8').replace('.pragma library', ''), model);
const document = {nodes: [
    {id: 'client', command: ['/bin/sh', 'scripts/start.sh'], files: [{source: 'assets/shared', target: '.'}]},
    {id: 'server', files: [{source: 'assets/shared', target: '.'}]}
], documentation: 'assets/shared/readme.md'};
const assets = [{path: 'assets/shared/scripts/start.sh', kind: 'file'},
    {path: 'assets/shared/readme.md', kind: 'file'}, {path: 'assets/shared/empty', kind: 'directory'}];
let state = model.initial(document, assets);
assert.equal(model.project(state.document, state.assets, 'client').length, 4);
state = model.create(state, 'client', 'scripts/hello.sh', false);
assert.equal(model.project(state.document, state.assets, 'client').find(row => row.path === 'scripts/hello.sh').kind, 'file');
assert.equal(state.document.nodes[1].files[0].source, 'assets/shared');
assert.equal(state.document.documentation, 'assets/shared/readme.md');
assert.throws(() => model.create(state, 'client', 'scripts/hello.sh', false));
assert.throws(() => model.create(state, 'client', '../bad', false));
state = model.rename(state, 'client', 'scripts', 'bin');
assert.equal(state.document.nodes[0].command[1], 'bin/start.sh');
assert.equal(model.project(state.document, state.assets, 'client').some(row => row.path === 'scripts'), false);
assert.throws(() => model.rename(state, 'client', 'bin', 'empty'));
assert.throws(() => model.remove(state, 'client', 'bin'), /khởi động/);
state = model.remove(state, 'client', 'bin/hello.sh');
assert.equal(model.project(state.document, state.assets, 'client').some(row => row.path === 'bin/hello.sh'), false);
assert.equal(model.project(state.document, state.assets, 'server').some(row => row.path === 'scripts/start.sh'), true);
state = model.create(state, 'client', 'empty/nested', true);
assert.equal(model.project(state.document, state.assets, 'client').find(row => row.path === 'empty/nested').kind, 'directory');
const binaryCopy = Object.values(state.pending).find(entry => entry.copy === 'assets/shared/scripts/start.sh');
assert.ok(binaryCopy);
assert.ok(!state.removals.includes('assets/shared/readme.md'));
console.log('File model: create, rename, delete, collision, paths, shared files, startup and empty folders passed');
const savedDocument = {nodes: [{id: 'client', files: [{source: 'assets/editor/client', target: '.'}]}]};
let saved = model.initial(savedDocument, [{path: 'assets/editor/client/a.txt', kind: 'file'}]);
saved.roots.client = 'assets/editor/client';
saved.pending['assets/editor/client/a.txt'] = {text: 'changed'};
const removed = model.remove(saved, 'client', 'a.txt');
assert.ok(removed.removals.includes('assets/editor/client/a.txt'));
const renamed = model.rename(saved, 'client', 'a.txt', 'b.txt');
assert.ok(renamed.removals.includes('assets/editor/client/a.txt'));
assert.equal(renamed.pending['assets/editor/client/b.txt'].text, 'changed');
saved.document.nodes.push({id: 'server', files: [{source: 'assets/editor/client', target: '.'}]});
const sharedAgain = model.remove(saved, 'client', 'a.txt');
assert.ok(!sharedAgain.removals.includes('assets/editor/client/a.txt'));
assert.ok(model.project(sharedAgain.document, sharedAgain.assets, 'server').some(row => row.path === 'a.txt'));
const unusual = model.initial({nodes: [{id: 'constructor', files: [{source: 'assets/data', target: '.'}]}]}, [
    {path: 'assets/data/__proto__', kind: 'file'}, {path: 'assets/data/constructor', kind: 'file'}]);
assert.equal(model.project(unusual.document, unusual.assets, 'constructor').length, 2);
const privateUnusual = model.create(unusual, 'constructor', 'new.txt', false);
assert.equal(model.project(privateUnusual.document, privateUnusual.assets, 'constructor').length, 3);
assert.throws(() => model.create(model.initial({nodes: [{id: 'client'}]}, []), 'client', 'a/b/c/d/e/f.txt', false));
console.log('File model: persisted delete/rename, newly shared roots, prototype filenames and full path limits passed');
