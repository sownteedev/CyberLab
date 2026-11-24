const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const model = vm.createContext({});
vm.runInContext(fs.readFileSync(__dirname + '/../ui/studio/models/DraftFiles.js', 'utf8').replace('.pragma library', ''), model);
const document = {nodes: [{id: 'client', user: {name: 'student', uid: 2000, gid: 2000},
    files: [{source: 'assets/shared', target: '.'}], setup: {future: {keep: true},
        users: [{name: 'mary', uid: 3001, gid: 3001}], groups: [{name: 'team', gid: 3100}],
        files: [{source: 'assets/shared', target: '/srv/project', owner: 'root', group: 'team', mode: '2775'}],
        home: [{path: 'notes.txt', owner: 'student', group: 'team', mode: '0640', future: true}]}}],
    documentation: 'assets/shared/notes.txt'};
const assets = [{path: 'assets/shared', kind: 'directory'}, {path: 'assets/shared/notes.txt', kind: 'file'}];
let state = model.initial(document, assets);
assert.equal(model.project(document, assets, 'client', 'System').find(row => row.path === '/srv/project/notes.txt')?.source, 'assets/shared/notes.txt');
assert.ok(model.used(document, 'assets/shared'));
state = model.create(state, 'client', '/etc/demo.conf', false);
state = model.rename(state, 'client', '/etc/demo.conf', 'renamed.conf');
state = model.rename(state, 'client', '/etc/renamed.conf', 'demo.conf');
assert.equal(state.document.nodes[0].files[0].source, 'assets/shared');
assert.equal(state.document.nodes[0].setup.files.find(entry => entry.target === '/etc/demo.conf').owner, 'root');
assert.equal(state.document.nodes[0].setup.files.find(entry => entry.target === '/etc/demo.conf').mode, '0644');
for (const path of ['/etc', '/usr/local', '/var/lib', '/home', '/opt', '/srv', '/etc/passwd', '/etc/shadow', '/etc/group',
    '/etc/sudoers.d/test', '/etc/pam.d/login', '/etc/cron.d/job', '/etc/ld.so.preload', '/opt/cyberlab/x', '/srv/../etc/x', '/tmp/x']) {
    assert.throws(() => model.create(state, 'client', path, false), path);
}
state = model.create(state, 'client', '/shared_stuff', true);
state = model.properties(state, 'client', '/shared_stuff', {owner: 'mary', group: 'team', mode: '3770'});
assert.equal(state.document.nodes[0].setup.files.find(entry => entry.target === '/shared_stuff').mode, '3770');
for (const mode of ['4755', '2755', '1755', '755', '0999'])
    assert.throws(() => model.properties(state, 'client', '/etc/demo.conf', {owner: 'root', group: 'root', mode}));
assert.throws(() => model.properties(state, 'client', '/etc/demo.conf', {owner: 'missing', group: 'root', mode: '0644'}));
const systemSourceBeforeHome = model.project(state.document, state.assets, 'client', 'System').find(row => row.path === '/srv/project/notes.txt').source;
state = model.properties(state, 'client', 'notes.txt', {owner: 'mary', group: 'mary', mode: '0600'});
assert.equal(state.document.nodes[0].files[0].source, 'assets/shared');
assert.equal(state.document.nodes[0].setup.home[0].future, true);
state = model.rename(state, 'client', 'notes.txt', 'renamed.txt');
assert.equal(state.document.nodes[0].setup.home[0].path, 'renamed.txt');
assert.equal(state.document.nodes[0].setup.future.keep, true);
assert.equal(model.project(state.document, state.assets, 'client', 'System').find(row => row.path === '/srv/project/notes.txt').source, systemSourceBeforeHome);
state = model.privateSystem(state, 'client');
const row = model.project(state.document, state.assets, 'client', 'System').find(row => row.path === '/srv/project/notes.txt');
assert.notEqual(row.source, 'assets/shared/notes.txt');
assert.ok(!state.removals.includes('assets/shared/notes.txt'));
state = model.properties(state, 'client', '/srv/project/notes.txt', {owner: 'mary', group: 'team', mode: '0640'});
state = model.rename(state, 'client', '/srv/project', 'renamed');
assert.equal(model.metadata(state.document, state.assets, 'client', '/srv/renamed/notes.txt').mode, '0640');
state = model.remove(state, 'client', '/srv/renamed');
assert.ok(!state.document.nodes[0].setup.files.some(entry => entry.target.startsWith('/srv/renamed')));
state = model.remove(state, 'client', 'renamed.txt');
assert.equal(state.document.nodes[0].setup.home.length, 0);
assert.equal(state.document.documentation, 'assets/shared/notes.txt');
console.log('Setup files model: projection, isolation, metadata, path/mode safety, rename/delete and unknown data passed');
const sourceBeforeEdit = model.project(state.document, state.assets, 'client', 'System').find(row => row.path === '/etc/demo.conf').source;
state = model.privateSystem(state, 'client');
assert.equal(model.project(state.document, state.assets, 'client', 'System').find(row => row.path === '/etc/demo.conf').source, sourceBeforeEdit);
const inherited = model.metadata(document, assets, 'client', '/srv/project/notes.txt');
assert.equal(inherited.mode, '0664');
assert.throws(() => model.create(state, 'client', '/home/student/private.txt', false));
for (const path of ['/etc/security/limits.conf', '/etc/subuid', '/etc/ssh/sshd_config', '/etc/apt/sources.list',
    '/etc/polkit-1/rules.d/rule', '/srv/a/b/c/d/e/f/g']) assert.throws(() => model.create(state, 'client', path, false));
let overrides = model.properties(model.initial(document, assets), 'client', '/srv/project/notes.txt', {owner: 'mary', group: 'team', mode: '0600'});
assert.equal(overrides.document.nodes[0].setup.files.length, 2);
assert.equal(model.metadata(overrides.document, overrides.assets, 'client', '/srv/project/notes.txt').mode, '0600');
overrides = model.properties(overrides, 'client', '/srv/project', {owner: 'root', group: 'team', mode: '2750'});
assert.equal(model.metadata(overrides.document, overrides.assets, 'client', '/srv/project/notes.txt').mode, '0600');
overrides = model.privateSystem(overrides, 'client');
const directory = overrides.document.nodes[0].setup.files.find(entry => entry.target === '/srv/project');
const child = overrides.document.nodes[0].setup.files.find(entry => entry.target === '/srv/project/notes.txt');
assert.equal(child.source, directory.source + '/notes.txt');
assert.equal(model.project(overrides.document, overrides.assets, 'client', 'System').filter(row => row.kind === 'file').length, 1);
console.log('Setup files model: inherited permissions, explicit child override, stable sources and backend target policy passed');
let aliases = model.initial({nodes: [{id: 'client', setup: {files: [
    {source: 'assets/data.txt', target: '/srv/one.txt', owner: 'root', group: 'root', mode: '0644'},
    {source: 'assets/data.txt', target: '/srv/two.txt', owner: 'root', group: 'root', mode: '0644'}]}}]},
    [{path: 'assets/data.txt', kind: 'file'}]);
aliases = model.privateSystem(aliases, 'client', '/srv/one.txt');
assert.notEqual(aliases.document.nodes[0].setup.files[0].source, aliases.document.nodes[0].setup.files[1].source);
assert.equal(aliases.document.nodes[0].setup.files[1].source, 'assets/data.txt');
