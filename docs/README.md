# Tài liệu CyberLab

Tài liệu được tổ chức theo **8 chủ đề**. Bắt đầu từ hướng dẫn chính của chủ đề;
chỉ mở phần tra cứu khi cần chi tiết kỹ thuật.

| Chủ đề | Nội dung |
| --- | --- |
| [Kiến trúc](architecture/README.md) | Các tầng, luồng xử lý, dữ liệu và ranh giới quyền |
| [Cài đặt và cập nhật](installation/README.md) | Cài qua link/checkout, cập nhật, rollback và [nền tảng hỗ trợ](installation/platforms.md) |
| [Tạo bài](authoring/README.md) | Bản nháp, tệp, hướng dẫn, xuất bản; [máy, mạng và phần mềm](authoring/machines.md) |
| [Thực hành](practice/README.md) | Terminal, lưu/tiếp tục/reset và [hiển thị GUI](practice/display-security.md) |
| [Đánh giá](assessment/README.md) | Quiz, Checkwork, nộp bài và [tham chiếu Result–Goal](assessment/results-goals.md) |
| [Chia sẻ bài](distribution/README.md) | Nhập/xuất, Labtainer, mật khẩu sửa và [định dạng gói](distribution/package-format.md) |
| [Studio](studio/README.md) | Tổ chức QML, component, theme và quy ước UX |
| [Phát triển](development/README.md) | Chạy source, chọn test an toàn và nghiệm thu trước phát hành |

## Đọc theo nhu cầu

- **Cài để sử dụng:** Cài đặt → Thực hành.
- **Biên soạn bài:** Tạo bài → Đánh giá → Chia sẻ bài.
- **Phát triển ứng dụng:** Kiến trúc → Studio → Phát triển.

Schema chính thức nằm ở [`lab.schema.json`](../schemas/v1/lab.schema.json),
chữ ký API ở [`org.ptit.CyberLab1.xml`](../daemon/cyberlab_ipc/org.ptit.CyberLab1.xml).
Các báo cáo kiểm thử và kế hoạch cũ nằm riêng trong [lưu trữ](archive/README.md),
không phải hướng dẫn cài đặt hay bằng chứng cho mọi môi trường.
