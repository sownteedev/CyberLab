# Kho bài độc lập với mã nguồn

## Cấu trúc

- `/home/student/CyberLab/`: mã nguồn chương trình và công cụ phát triển.
- `/home/student/CyberLab-labs/`: dữ liệu bài lab được giữ qua các lần phát triển.
- Bộ test và bài mẫu đã được lưu ngoài repository; không đi kèm bản cài app.
- `/var/lib/cyberlab/authoring/`: cơ sở dữ liệu bản nháp, không di chuyển trong bước này.

`student` là user của VM hiện tại. Trên VM khác, dùng
`/home/<user>/CyberLab-labs`, không tạo một user mới tên `user`.

Kho bên ngoài không được dùng làm fixture, dọn cùng build, ghi đè khi nâng cấp,
hoặc tự khôi phục bài mẫu vào đó. Quy tắc đã ghi trong `AGENTS.md`. Đây là
quy tắc bảo vệ dữ liệu phát triển, không phải đặt immutable/chỉ đọc: người dùng
vẫn có thể lưu bài mới qua API daemon và các thao tác đã được cho phép.

## Trạng thái chuẩn bị và chuyển cấu hình

Đã sao chép nguyên kho hiện tại ra đường dẫn mới, giữ nội dung và quyền file.
Daemon đang cài vẫn đọc kho cũ cho đến khi quản trị viên chạy lệnh bên dưới.
Không xóa `CyberLab/labs` bằng tay lúc này. Không sửa bài ở hai bản trong khi
chờ chuyển; công cụ sẽ từ chối nếu nội dung, quyền hay owner không còn khớp.

Đóng Studio và không chạy CLI khác trong lúc chuyển. Lưu công việc và dừng
các Session cần thiết trước; công cụ từ chối nếu tài khoản được phép nào còn
Session chưa STOPPED. Trong thư mục `/home/student/CyberLab`, chạy:

```sh
sudo /usr/bin/python3 -I tools/relocate_catalog.py --uid "$(id -u)"
cyberlab labs
```

Công cụ giữ nguyên allowlist image, UID, authoring và các thiết lập khác;
chỉ đổi catalog và đường dẫn ghi của systemd. Nó không cài wheel, không build
hay pull image, không sửa nội dung bài ở thư mục mới.

Sau khi dừng daemon, công cụ kiểm tra lại hai bản, đổi cấu hình, chuyển kho cũ
khỏi repository vào thư mục backup quản trị riêng trong
`/var/tmp/cyberlab-catalog-backup-*`, rồi khởi động daemon và so danh sách bài.
Backup giữ cả cấu hình cũ và kho cũ. Nếu có lỗi sau khi bắt đầu chuyển, công cụ
thử khôi phục cấu hình/kho cũ và khởi động lại daemon; không xóa kho bên ngoài.
Nếu rollback lỗi, giữ nguyên mọi thứ và kiểm tra backup, không chạy lại mù quáng.
Việc archive cần source và `/var/tmp` cùng filesystem; khác filesystem thì từ chối
trước khi dừng dịch vụ. Công cụ không phải bộ migration tổng quát cho mọi máy.

Thay đổi này không nâng cấp package daemon đã cài. Đây là thao tác chuyển kho,
độc lập với bước cập nhật code runtime đường dẫn home.

## Phát triển sau đó

Chế độ demo/smoke chỉ dùng được khi khôi phục bộ fixture độc lập; nó không tự
chuyển sang kho thật khi thiếu fixture. Studio bình thường tiếp tục lấy danh
sách qua daemon; CLI/UI không tự ghi vào catalog.

Không dùng lại `tools/switch_catalog_to_home.sh`; công cụ đó đã bị vô hiệu hóa
vì trước đây ghi đè cấu hình và cài package không liên quan. Công cụ triển khai
MVP cũ còn giả định kho `/var/lib/cyberlab/labs` trong quy trình cài mới; không
chạy quy trình cài mới/repair ấy để cập nhật VM đã chuyển kho này.
