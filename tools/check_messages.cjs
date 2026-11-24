const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {execFileSync} = require('node:child_process');
const messages = vm.createContext({});
vm.runInContext(fs.readFileSync(__dirname + '/../ui/studio/models/Messages.js', 'utf8').replace('.pragma library', ''), messages);
const addressError = 'Node address must be usable in its subnet and cannot equal the bridge gateway';
assert.equal(messages.text(addressError), 'IP của máy phải nằm trong dải mạng, không trùng địa chỉ mạng, địa chỉ quảng bá hoặc cổng kết nối.');
assert.equal(messages.issue({path: '/', message: addressError}), messages.text(addressError));
assert.equal(messages.issue({path: '/nodes/0/addresses/office', message: addressError}), '/nodes/0/addresses/office: ' + messages.text(addressError));
assert.equal(messages.text('Error: Draft not found'), 'Không tìm thấy bản nháp.');
assert.equal(messages.text('ValueError: Draft not found'), 'Không tìm thấy bản nháp.');
assert.equal(messages.text('Error: Tên tệp không hợp lệ.'), 'Tên tệp không hợp lệ.');
assert.equal(messages.text('FAIL: org.cyberlab.Error.NotFound: Draft not found'), 'Không tìm thấy bản nháp.');
assert.equal(messages.text('required constraint failed'), 'Thiếu thông tin bắt buộc.');
assert.equal(messages.text('Duplicate identity at /nodes/1/id'), 'Mã định danh bị trùng tại /nodes/1/id.');
assert.equal(messages.text('10.241.10.10/24 has host bits set'), 'Dải mạng 10.241.10.10/24 chưa đúng địa chỉ đầu mạng. Ví dụ: 10.241.10.0/24.');
assert.equal(messages.text('assets/notes.md: Draft not found'), 'assets/notes.md: Không tìm thấy bản nháp.');
assert.equal(messages.text('Draft not found\nLab subnets must not overlap'), 'Không tìm thấy bản nháp.\nCác dải mạng trong bài lab không được chồng lấn.');
assert.equal(messages.text('Result collected'), 'Đã lấy kết quả.');
assert.equal(messages.text('Log records require ISO-8601 timestamps with timezone'), 'Mỗi dòng log cần thời gian ISO-8601 kèm múi giờ.');
for (const literal of ['Đã lưu bản nháp.', 'assets/Error:notes.md', 'print("Hello")', 'Unknown third-party diagnostic', 'constructor', '__proto__', '<b>Draft not found</b>']) {
    assert.equal(messages.text(literal), literal);
}
assert.equal(messages.text(null), '');
assert.equal(messages.text('Could not reset saved practice; checkpoint retained'), 'Không thể đặt lại tiến độ. Bản lưu vẫn được giữ; hãy thử lại hoặc dừng phiên rồi tiếp tục từ bản lưu.');
assert.equal(messages.text('Software preparation interrupted; retry when storage is available'), 'Cài phần mềm bị gián đoạn. Hãy kiểm tra dung lượng lưu trữ rồi thử lại.');
assert.equal(messages.text(messages.text(addressError)), messages.text(addressError));
const sources = JSON.parse(execFileSync('python', ['-c', `
import ast, json
from pathlib import Path
root = Path(${JSON.stringify(__dirname + '/..')})
paths = list((root / 'engine/cyberlab/lab').glob('*.py')) + list((root / 'engine/cyberlab/authoring').glob('*.py'))
paths += [root / 'engine/cyberlab/policy/__init__.py', root / 'engine/cyberlab/runtime/docker.py', root / 'engine/cyberlab/runtime/docker_terminal.py', root / 'engine/cyberlab/runtime/software.py', root / 'engine/cyberlab/desktop.py']
paths += [root / 'engine/cyberlab/service.py', root / 'daemon/cyberlabd/authoring.py']
paths += [root / 'engine/cyberlab/runtime/image_storage.py']
messages = set()
for path in paths:
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and node.exc.args:
            value = node.exc.args[0]
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                messages.add(value.value)
print(json.dumps(sorted(messages)))
`], {encoding: 'utf8'}));
const vietnameseSources = new Set([
    'Chọn ít nhất một chủ đề cho bài lab.',
    'Chọn chủ đề trong danh sách được hỗ trợ.',
    'Chủ đề của bài lab không được trùng nhau.',
]);
for (const source of sources) {
    if (vietnameseSources.has(source))
        assert.equal(messages.text(source), source, 'Already Vietnamese message must stay unchanged: ' + source);
    else
        assert.notEqual(messages.text(source), source, 'Missing Vietnamese message: ' + source);
}
console.log('Verified Vietnamese output for static errors in lab validation, authoring, policy, Docker startup, terminal, software and desktop: ' + sources.length);
console.log('Vietnamese messages: network, schema, paths, prefixes, multiline, idempotence and literal content passed');
