const assert = require('node:assert/strict');
const {pathToFileURL} = require('node:url');
const fs = require('node:fs');
const vm = require('node:vm');
const root = __dirname + '/../../../ui/studio/';
(async function() {
const language = vm.createContext({});
vm.runInContext(fs.readFileSync(root + 'models/CodeLanguage.js', 'utf8').replace('.pragma library', ''), language);
const syntax = {...await import(pathToFileURL(root + 'models/CodeSyntax.mjs')), languageFor: language.languageFor};

function decode(html) {
    return html.replace(/<font color="#[a-f0-9]+">|<\/font>/g, '').replace(/<br>/g, '\n')
        .replace(/&nbsp;/g, ' ').replace(/&#9;/g, '\t').replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&amp;/g, '&');
}

const examples = {
    'demo.py': '# comment\nimport sys\nclass Greeter:\n\tdef greet(self, name="Xin chao"):\n\t\treturn f"Hello {name}: {42}"\n',
    'start.sh': '#!/bin/sh\nvalue="hello"\necho "$value"\n',
    'config.json': '{"enabled": true, "port": 8080}',
    'config.yaml': 'enabled: true\nport: 8080\n',
    'app.js': 'const answer = 42; // example\nconsole.log("Hello");\n',
    'guide.md': '# Title\n\n**bold** and `code`\n\n```python\nprint(42)\n```\n'
};
for (const [path, text] of Object.entries(examples)) {
    for (const dark of [true, false]) {
        const rendered = syntax.render(text, syntax.languageFor(path, text), dark);
        assert.match(rendered, /<font color=/, path);
        assert.equal(decode(rendered), text, path);
    }
}
const hostile = '# <img src="file:///etc/passwd">\nvalue = "<b>&nbsp;</b>"\n\n';
const rendered = syntax.render(hostile, 'python', true);
assert.equal(decode(rendered), hostile);
assert.ok(!rendered.includes('<img'));
assert.ok(!rendered.includes('<b>'));
assert.equal(syntax.languageFor('run', '#!/usr/bin/env python3\n'), 'python');
assert.equal(syntax.languageFor('HELLO.PY', ''), 'python');
assert.equal(syntax.languageFor('constructor', ''), '');
assert.equal(syntax.languageFor('readme.txt', ''), '');
assert.equal(syntax.render('unchanged', '', true), '');
const triple = 'message = """first line\n# still a string\nlast line"""\nprint(message)';
assert.equal(decode(syntax.render(triple, 'python', true)), triple);
const maximum = ('print("Hello") # comment\n').repeat(2700).slice(0, 65536);
const start = performance.now();
assert.equal(decode(syntax.render(maximum, 'python', true)), maximum);
console.log(`Code syntax: languages, themes, escaping, multiline, whitespace and 64 KiB passed (${Math.round(performance.now() - start)} ms large fixture)`);
})().catch(error => { console.error(error); process.exitCode = 1; });
