# Phát triển và kiểm thử

Đọc [AGENTS.md](../../AGENTS.md) và [kiến trúc](../architecture/README.md)
trước khi sửa backend/chính sách. Không dùng dữ liệu thực hành thật làm fixture.

## Chạy từ source

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
bash tools/run_studio.sh --require-native
```

Dùng Python từ 3.12 và Quickshell/Qt native tương thích. Launcher này kết nối
**daemon thật**, không phải sandbox. Sửa backend chưa tự cập nhật daemon đang
cài; triển khai qua [updater có bảo vệ](../installation/README.md), không
chép file vào runtime.

## Chọn đúng kiểm thử

| Tầng | Công cụ tiêu biểu | Phạm vi |
| --- | --- | --- |
| Logic/dữ liệu | `tools/tests/unit/check_editing_drafts.py`, `tools/tests/unit/check_session_state.py`, `tools/tests/unit/check_exchange_v3.py` | Fixture, database tạm, runtime mô phỏng |
| Đánh giá | `tools/tests/unit/check_checkwork_regression.py`, `tools/tests/unit/check_assessment_quiz.py`, `tools/tests/unit/check_result_collection.py` | Result/Goal/Quiz, lỗi capture và báo cáo |
| Bảo vệ | `tools/tests/unit/check_edit_protection.py`, `tools/tests/unit/check_private_catalog.py`, `tools/tests/unit/check_maintenance.py` | Quyền, revision và khóa bảo trì cách ly |
| Installer/update | `tools/tests/unit/check_installer_distros.py`, `tools/tests/unit/check_system_update.py`, `tools/tests/unit/check_upgrade_runtime.py` | Adapter, metadata và transaction mô phỏng |
| UI | `tools/tests/ui/check_notifications.py`, `tools/tests/ui/check_account_editor.py`, `tools/tests/ui/check_file_picker.py` | Control, callback và layout offscreen |
| Xuyên tầng | `tools/tests/ui/check_machine_setup_workflow.py` | QML → CLI → private D-Bus với MemoryRuntime |
| Artifact | `tools/tests/unit/check_qml_manifest.py` và tải wheel | Registry/tài nguyên thực sự đóng gói |
| Runtime thật | `tools/tests/runtime/check_network_runtime.py`, `tools/tests/runtime/check_software_runtime.py`, `tools/tests/runtime/check_workstation_runtime.py`, `tools/tests/runtime/check_machine_setup_runtime.py` | Docker/mạng/package, cần môi trường và quyền riêng |

Không chạy mù toàn bộ `check_*.py`. `tools/tests/unit/check_startup_authoring.py` cần
`--qml-log`, `tools/tests/unit/check_labs.py` cần catalog thử, test X11 có thể cần display Xvfb
riêng. Đọc `--help` và [`tools/README.md`](../../tools/README.md) trước.

Ví dụ từ repo, dùng runtime đã cài làm interpreter:

```bash
/usr/lib/cyberlab/venv/bin/python -B tools/tests/unit/check_session_state.py
/usr/lib/cyberlab/venv/bin/python -B tools/tests/unit/check_assessment_quiz.py
/usr/lib/cyberlab/venv/bin/python -B tools/tests/unit/check_result_collection.py
/usr/lib/cyberlab/venv/bin/python -B tools/tests/unit/check_installer_distros.py
python3 -B tools/tests/ui/check_notifications.py --suite editor --native
git diff --check
```

Nếu chưa cài runtime, dùng venv có dependency dự án. QML/offscreen đạt không
chứng minh cửa sổ thật, terminal, polkit hay GPU. MemoryRuntime không thay
nghiệm thu Docker. Không dùng cờ test trong daemon sản xuất.

## Quy trình sửa và nghiệm thu

1. Ghi môi trường/cách tái hiện; thêm test thất bại cho lỗi đã xác nhận.
2. Sửa ở tầng sở hữu lỗi, chạy test liên quan rồi hồi quy.
3. Kiểm tra wheel mới; không tái sử dụng `build/lib` còn resource đã xóa.
4. Nghiệm thu luồng tạo → xuất/nhập → Quiz → chạy hai máy → Checkwork → nộp
   → lưu/tiếp tục/reset trong môi trường riêng.
5. Kiểm tra cài/cập nhật, phiên đang chạy và rollback bằng lỗi tiêm có kiểm soát.

Thử Checkwork khi chưa làm, làm sai, làm đúng, thiếu tệp và capture lỗi.
Kiểm tra mật khẩu qua CLI/D-Bus, không chỉ nút UI. Không tăng timeout/bỏ
assertion để che test chập chờn chưa rõ nguyên nhân.

Chỉ dọn tiến trình/container/network do lượt thử tạo, không kill theo tên
hoặc dọn backup/image/Session của người dùng. Nếu thiếu môi trường, ghi
**chưa xác minh/bị chặn**. Sẵn sàng push khác đã cài được trên máy mới.

## Quy ước tài liệu

Mỗi chủ đề có một hướng dẫn chính; chỉ tách reference khi thực sự cần tra cứu.
Không tạo file theo từng lần sửa UI/cuộc thảo luận. Cập nhật nội dung hiện
hành vào đúng chủ đề, không chép nhật ký triển khai và hash artifact vào đó.

Bằng chứng có ngày/phạm vi/môi trường nằm ở [lưu trữ](../archive/README.md).
Báo cáo cũ không chứng minh trạng thái bản cài hiện tại, kế hoạch cũ không tự
trở thành roadmap đã cam kết. Khi chuyển tài liệu, kiểm tra liên kết, anchor,
code fence và đường dẫn trong README/công cụ/chuỗi gợi ý installer.
