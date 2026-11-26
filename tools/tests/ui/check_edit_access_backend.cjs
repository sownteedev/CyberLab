const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../../../ui/studio/services/Backend.qml'), 'utf8');
const functions = source.slice(source.indexOf('    function editResource'), source.indexOf('    visible: false'));
function backend() {
    const state = {editGrants: {}, editWaiting: [], editPrompt: null, editGeneration: 0,
        pending: [], startupActive: false, foregroundActive: false, foregroundLoading: false,
        inFlight: false, prefix: ['python', '-m', 'cyberlab_cli.main'], calls: [], signals: [],
        Qt: {callLater: callback => callback()}, console: {warn: () => { throw Error('Unexpected log'); }},
        editUnlockRequested: (...args) => state.signals.push(args), editUnlockDismissed: () => {},
        errorChanged: () => {}, notificationRequested: () => {}};
    state.backend = state;
    vm.createContext(state);
    vm.runInContext(functions, state);
    state.pump = () => {};
    return state;
}
function failedJob(state, input = 'retained unsaved input') {
    state.request(['draft', 'save', 'fixture', '--stdin'], () => { state.done = true; }, input);
    const job = state.pending.shift();
    const process = {job, output: {text: ''}, errors: {text: 'FAIL: org.ptit.CyberLab1.Error.EditLocked: ' +
        JSON.stringify({kind: 'draft', id: 'fixture', message: 'Locked'})}, destroy: () => {}};
    state.finish(process, 1, 0);
    return job;
}
{
    const state = backend();
    const original = failedJob(state);
    assert.equal(state.done, undefined);
    assert.equal(state.error, undefined);
    assert.equal(state.signals.length, 1);
    state.unlockEditing('wrong', (_result, error) => { state.passwordError = error; });
    const wrong = state.pending.shift();
    wrong.callback(null, 'org.ptit.CyberLab1.Error.EditPassword');
    assert.ok(state.passwordError);
    assert.equal(state.editWaiting[0], original);
    state.unlockEditing('right', () => {});
    state.pending.shift().callback({token: 'memory-grant', edit_protected: true}, '');
    assert.equal(state.pending[0], original);
    assert.equal(original.input, 'retained unsaved input');
    assert.equal(state.editGrants['draft:fixture'], 'memory-grant');
    failedJob(state);
    assert.equal(state.editWaiting.length, 1, 'expired/restarted grant re-prompts without callback');
}
{
    const state = backend();
    state.editGrants = {'draft:fixture': 'secret-grant'};
    failedJob(state);
    state.editGrants = {'draft:fixture': 'secret-grant'};
    state.clearEditing();
    assert.equal(Object.keys(state.editGrants).length, 0);
    assert.equal(state.editWaiting.length, 0);
    assert.equal(state.editPrompt, null);
    assert.equal(state.done, true);
    assert.ok(state.pending.some(job => job.arguments.join(' ') === 'edit-access revoke' && JSON.parse(job.input).token === 'secret-grant'));
    assert.ok(state.pending.every(job => !job.arguments.join(' ').includes('secret-grant')));
}
{
    const state = backend();
    failedJob(state);
    state.unlockEditing('private-password', () => { throw Error('stale callback'); });
    const unlock = state.pending.shift();
    state.clearEditing();
    unlock.callback({token: 'late-grant', edit_protected: true}, '');
    assert.equal(Object.keys(state.editGrants).length, 0);
    assert.ok(state.pending.some(job => JSON.parse(job.input).token === 'late-grant'));
}
{
    const state = backend();
    state.editGrants = {'lab:source': 'source-grant'};
    let adopted;
    state.request(['draft', 'clone', 'source'], result => { adopted = result; });
    state.finish({job: state.pending.shift(), output: {text: JSON.stringify({id: 'clone', edit_token: 'independent-grant', edit_protected: true})},
        errors: {text: ''}, destroy: () => {}}, 0, 0);
    assert.equal(adopted.edit_token, undefined);
    assert.equal(state.editGrants['draft:clone'], 'independent-grant');
    state.clearEditing(null, 'draft:clone');
    assert.equal(state.editGrants['draft:clone'], 'independent-grant');
    assert.equal(state.editGrants['lab:source'], undefined);
}
{
    const state = backend();
    state.editGrants = {'draft:fixture': 'secret-grant'};
    state.worker = {createObject: (_parent, options) => { state.created = options; return {}; }};
    vm.runInContext(functions, state);
    state.request(['draft', 'save', 'fixture', '--stdin'], () => {}, 'original content');
    assert.ok(state.created.command.includes('--edit-context'));
    assert.ok(!state.created.command.join(' ').includes('secret-grant'));
    assert.equal(JSON.parse(state.created.payload).token, 'secret-grant');
    assert.equal(JSON.parse(state.created.payload).input, 'original content');
}
console.log('PASS: unlock retry, restart, close revocation, stale unlock, clone family, stdin-only transport');
