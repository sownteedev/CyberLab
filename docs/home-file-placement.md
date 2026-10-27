# Home-relative initial files

## Behavior

Configured node users receive initial files relative to their home. CyberLab
no longer adds an implicit `lab/` directory. A node with Alice's configured
home `/home/alice` and this mapping receives `/home/alice/message.txt`:

```yaml
files:
  - source: assets/client/message.txt
    target: message.txt
```

An explicit target such as `exercises/message.txt` keeps that subdirectory.
Directory mappings keep their target directory, including empty directories.
The special directory target `.` copies the source directory's contents directly
into the workspace. For example, `source: assets/server` with `target: .` places
`assets/server/banner.txt` at `/home/bob/banner.txt`, while
`assets/server/data/banner.txt` becomes `/home/bob/data/banner.txt`.
Only a directory source may use this target. The root mapping must be the only
mapping on its node to avoid overlapping destinations. Dot components in other
paths, traversal and absolute destinations remain forbidden; the generated seed
archive never contains a `.` entry. Existing mappings are not migrated.
Nodes without a configured user retain `/tmp/lab`. No host home is mounted.
The configured account must already exist in the approved image; CyberLab
does not provision accounts or change its runtime security policy.

The bootstrap accepts an existing empty home tmpfs or creates the legacy
workspace. It refuses a symlink workspace or existing contents, including
hidden entries and dangling symlinks, before extraction. Validated archives
still contain only bounded regular files and directories. Initialization
must complete before the node's original command runs.

## API and Studio

Lab and Session dictionaries add `workspaces` (`a(ss)`, node ID and absolute
workspace) and `seed_directories` (`a(sas)`, node ID and relative directories).
Existing `seed_files` contains relative regular-file paths; `files` contains
absolute mapping destinations. No new method, privilege or transport is added.
Session metadata comes from its captured Lab rather than the current catalog.

Studio displays the daemon's workspace and import receipt `path` rather than
inventing an `imports/` directory or using the current Lab as a fallback.
Older daemons without `workspaces` retain their historical home/lab display.
Imports outside that workspace are displayed with their absolute paths.
Imports still use unique `cyberlab-import-<id>-<name>` filenames; this change
does not add arbitrary destination selection or overwrite.

This is a list of initial snapshot entries and completed import receipts,
not a live container file browser. Files created, renamed or removed through
the terminal are not tracked. Missing metadata is distinguished from an
empty recorded list. Selecting another Session or resetting invalidates old
import responses to avoid displaying another Session's files.

## Compatibility and validation

Repository changes do not upgrade the installed daemon automatically. System
deployment needs separate approval, and stopping/restarting the daemon can
discard active Sessions and their temporary work. Do not restart it until
needed work has been saved.

Existing catalog definitions are not migrated or rewritten by this change.
In particular, example mappings targeting `exercises` or `data` still create
those explicitly requested directories, now directly under home. To put files
at home root, author a single-file mapping as shown above or map a directory to
`.`. Do not flatten an
existing Lab's targets silently; its instructions may depend on them.

A newly started Session loads the current definition. Reset uses the Session's
captured mappings and contents, not later edits to the catalog. Initial files
are restored; imported and terminal-created files are disposable.

## Tạo Lab mới và upload vào home

Chọn `Soạn bài mới`, nhập mã và tên Lab rồi nhấn `Tạo`. Bản nháp ban đầu
không được đưa vào thư viện và chưa chạy được; Studio tạo cấu hình từng bước:

1. Thêm máy. ID được gợi ý lần lượt là `client`, `server`, rồi `node-N`.
   Chọn image được daemon cho phép; Studio không tự đoán account trong image.
   Để dùng `/home/bob`, bật account trong mục `Máy lab` và khai báo đúng
   `user.name`, UID/GID, home và shell đã có sẵn trong image.
2. Thêm mạng nội bộ, chọn mạng cho từng máy và khai báo subnet/IP nếu cần.
3. Chọn image đã có trong allowlist, lệnh khởi động và số terminal.
4. Trong `File ban đầu`, chọn file hoặc folder cho máy. Studio lưu nguồn theo
   `assets/<node>/` nhưng mặc định đặt nội dung trực tiếp vào home của account.
5. Nhập hướng dẫn, lưu bản nháp, kiểm tra rồi mới `Lưu vào thư viện`.

Ví dụ với node `server` có user `bob`:

```text
assets/server/banner.txt  →  /home/bob/banner.txt
```

Folder được chọn sẽ chép **nội dung bên trong**, không chép thêm tên folder
gốc. Chỉ khi nhập thư mục con tùy chọn `configs` mới nhận được:

```text
assets/server/configs/<file>  →  /home/bob/configs/<file>
```

Đổi tên user làm thay đổi home mà không cần đổi thư mục nguồn. Đổi ID node
không tự di chuyển tài nguyên đã upload; mapping đã có vẫn giữ nguồn cũ.
Node không khai báo `user` vẫn dùng workspace `/tmp/lab`; Studio hiển thị
đường dẫn này rõ ràng, không giả định mọi image đều chứa account `bob`.

## Studio home upload workflow

Authoring info advertises `home_directory_target: true` for compatible daemons.
Studio enables its home upload workflow only when this field is present. No
System D-Bus method signature changes. An older daemon still supports the
existing explicit mappings via the advanced section.

Select a node, select a local file or folder, and optionally enter a home-relative
subdirectory. Studio stores resources under `assets/<node>/` and adds one mapping
from that directory to `.`. Folder uploads copy contents, not the selected folder's
basename; nested directories are preserved. Empty folders are still unsupported by
the draft upload API. Existing mapped destinations are never silently replaced.
The preview tree expands mappings against draft asset metadata, not the host or a
live container. The home upload action refuses sources shared with another node,
sources overlapping documentation (including the default `assets/docs` directory),
and sources that are regular files. It also refuses to implicitly map an existing
unmapped resource directory; inspect its contents and explicitly map it through
the advanced section first. These are Studio upload safeguards, not new daemon
restrictions on intentional shared mappings.
Upload is followed by saving the definition; if that second step
fails, the draft retains the assets and unsaved mapping for an explicit retry.
The validator still reports `runtime_verified: false`; validation does not prove
that images or accounts exist, and it never starts a container.

Startup errors distinguish a missing preloaded image from Docker failures while
creating networks, creating containers or starting a named node. Environment
initialization failures include the node and its workspace, so an incorrect
account/home can be traced back to the node configuration. Raw Docker exception
text is not returned to clients. These diagnostics use the existing Session
`error` field; neither CLI nor Studio gets Docker access or a new transport.

Run focused checks without Docker or changes to the installed service:

```sh
.venv/bin/python -m pytest tests/test_seeding.py tests/test_node_environment.py tests/test_studio_session_files.py tests/test_studio_ui.py -q
```

After a separately approved daemon upgrade, verify with a disposable Lab whose
mapping targets `message.txt`: start it, inspect `cyberlab status SESSION_ID`
and `/home/alice/message.txt` inside the client, edit the file, reset, reopen
the terminal, and check the original contents. Also check another node and
Session stay independent, and stop only the disposable Session afterward.
Local shell and memory-runtime tests do not prove real Docker acceptance.
