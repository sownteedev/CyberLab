# Công cụ phát triển và quản trị

Cài đặt dùng `bash install.sh` tại gốc repository; cập nhật từ checkout dùng
`bash install.sh --update`. Không gọi các module shell nội bộ thay entrypoint.
Máy đã cài nhưng chỉ có BusyBox dùng `bash install.sh --prepare-ubuntu` sau
khi lưu/đóng Studio và dừng các phiên. Cài mới tự chuẩn bị Ubuntu; cập nhật
thông thường không tự thay chính sách môi trường.

## Cấu trúc

```text
tools/
├── install/       Bộ cài, kiểm tra môi trường, backup và rollback
├── admin/         Quản trị chủ động: chuyển kho, chuẩn bị image
├── dev/           Bảo trì tài nguyên phục vụ phát triển
├── tests/
│   ├── unit/      Kiểm thử cách ly: logic, CLI, dữ liệu, chính sách
│   ├── ui/        Model JavaScript, QML và luồng UI cách ly
│   └── runtime/   Nghiệm thu Docker/display thật và helper liên quan
├── run_studio.sh  Chạy Studio từ source
└── run_studio.py  Launcher tương thích cho lệnh/shortcut cũ
```

Giữ các test chống lỗi tái phát dù ứng dụng không gọi trực tiếp. `unit/` gồm
cả tích hợp dùng private D-Bus và MemoryRuntime, không chỉ unit test thuần.

## Cài đặt và quản trị

| Công cụ | Mục đích |
| --- | --- |
| [install/system.sh](install/system.sh) | Điều phối bộ cài, được gọi qua `install.sh` ở gốc repo. |
| [install/runtime_admin.py](install/runtime_admin.py) | Kiểm tra tài khoản/đường dẫn, build không đặc quyền và xác minh bản cài. |
| [install/quickshell_source.py](install/quickshell_source.py) | Đọc chỉ mục APT có giới hạn để kiểm tra gói Quickshell đúng nền/kiến trúc trước khi thêm nguồn. |
| [install/private_runtime.py](install/private_runtime.py) | Build Quickshell không đặc quyền với Qt riêng; kiểm tra checksum, đường dẫn và QML trước khi cài. Chỉ gọi qua installer có khóa thao tác. |
| [install/gui-runtime.json](install/gui-runtime.json) | Phiên bản, nguồn HTTPS và SHA-256 của runtime riêng; không tự lấy bản Qt mới nhất. |
| [install/upgrade_runtime.py](install/upgrade_runtime.py) | Kiểm tra Session/Studio, backup và cập nhật có rollback. |
| [admin/migrate_catalog.py](admin/migrate_catalog.py) | Chuyển kho bài theo thao tác quản trị được xác nhận. |
| [admin/prepare_lab_images.py](admin/prepare_lab_images.py) | Chuẩn bị image theo recipe được giới hạn. |
| [admin/prepare_ubuntu_workstation.py](admin/prepare_ubuntu_workstation.py) | Recipe Ubuntu dùng chung với cài mới; kiểm tra image, kích hoạt có khóa và phục hồi cấu hình. Dùng qua `install.sh --prepare-ubuntu` cho máy đã cài. |
| [dev/vendor_code_syntax.py](dev/vendor_code_syntax.py) | Cập nhật tài nguyên tô màu cú pháp được đóng gói. |

Các file còn lại trong `install/` là thành phần nội bộ: adapter package manager,
Docker, repository, transaction guard và probe QML. Không xóa riêng từng file.
Xem [cài đặt/cập nhật](../docs/installation/README.md) và
[cấu hình máy](../docs/authoring/machines.md) trước khi thao tác quản trị.
`run_studio.sh` kết nối daemon thật; đây không phải sandbox.

## Kiểm thử

Chạy từ gốc repository, dùng venv có dependency dự án. Ví dụ dưới dùng
interpreter của bản cài, nhưng test kiểm tra **source đang sửa**, không thay
bản cài hoặc dữ liệu thật.

```bash
/usr/lib/cyberlab/venv/bin/python -B tools/tests/unit/check_tool_layout.py
/usr/lib/cyberlab/venv/bin/python -B tools/tests/unit/check_editing_drafts.py
/usr/lib/cyberlab/venv/bin/python -B tools/tests/unit/check_session_state.py
/usr/lib/cyberlab/venv/bin/python -B tools/tests/unit/check_checkwork_regression.py
/usr/lib/cyberlab/venv/bin/python -B tools/tests/unit/check_system_update.py
/usr/lib/cyberlab/venv/bin/python -B tools/tests/unit/check_install_parity.py
node tools/tests/ui/check_account_model.js
python3 -B tools/tests/ui/check_notifications.py --suite editor --native
/usr/lib/cyberlab/venv/bin/python -B tools/tests/ui/check_machine_setup_workflow.py
```

- **Logic:** chọn suite theo tên trong [tests/unit/](tests/unit/). Không chạy
  discovery toàn bộ: một số suite nhập fixture/test của suite khác.
- **UI:** [tests/ui/](tests/ui/) dùng dữ liệu giả, preferences tạm và offscreen
  mặc định. `check_notifications.py --suite` chọn editor, files, lifecycle,
  desktop, quiz, assessment, markdown, components… Dùng `--artifacts` để lưu
  log/ảnh. Không bật `--visible` khi chỉ cần kiểm tra tự động.
- **Cần đầu vào:** `tools/tests/unit/check_labs.py --catalog <kho-thử>` chỉ
  đọc catalog được chỉ định; `tools/tests/unit/check_startup_authoring.py`
  cần `--qml-log <log-editor>` từ suite editor. Không dùng kho thật.
- **Runtime thật:** [tests/runtime/](tests/runtime/) yêu cầu Docker, quyền hoặc
  display thử riêng tùy tool. Đọc mã và `--help` của entrypoint trước khi chạy;
  không chạy hàng loạt cả thư mục trên máy đang thực hành.
- **Helper runtime:** `check_software_gui.py`, `disposable_x11.py`,
  `x11_fixture_client.py`, `x11_relay_probe.py`, `check_xwayland_guest.py` được
  gọi bởi fixture cha; không coi chúng là lệnh nghiệm thu độc lập.

Chỉ dọn tiến trình/tài nguyên do lượt thử tạo. Không kill theo tên, không dọn
catalog, checkpoint hoặc backup của người dùng. QML/offscreen và MemoryRuntime
không thay thế nghiệm thu Docker hoặc cửa sổ thật. Quy trình kiểm thử nằm trong
[hướng dẫn phát triển](../docs/development/README.md).
