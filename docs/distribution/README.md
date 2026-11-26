# Chia sẻ và bảo vệ bài lab

## 1. Xuất và nhập bài CyberLab

Trong Studio, xuất bài thành một file `.cyberlab` để người khác nhập vào thư
viện. Không cần mã nhận bài, khóa theo máy hoặc mật khẩu để thực hành.

```bash
cyberlab export-lab LAB_ID NEW_OUTPUT.cyberlab
cyberlab import-lab INPUT.cyberlab --as NEW_LAB_ID --title "Tên bài"
```

File xuất phải là tên mới. Import kiểm tra gói, schema và chính sách trước
khi lưu; trùng ID thì dừng hoặc dùng ID mới được chỉ định, không ghi đè bài
có sẵn. Gói CyberLab hợp lệ đi thẳng vào thư viện, kể cả khi có mật khẩu sửa.

| Có trong gói | Không có trong gói |
| --- | --- |
| Khai báo bài, chủ đề, độ khó | Docker image đã tải/cài |
| Asset, hướng dẫn, script ban đầu | Checkpoint và tệp cá nhân khi thực hành |
| Quiz, Result–Goal, tham số | Bộ nhớ tiến trình, kết nối mạng |
| Verifier mật khẩu sửa nếu có | Mật khẩu nguyên văn hoặc credential desktop |

Máy nhận vẫn phải có môi trường được cho phép. Phần mềm có công thức chuẩn
bị có thể được cài khi bắt đầu; image tùy ý không tự xuất hiện vì đã nhập bài.

## 2. Mật khẩu sửa bảo vệ điều gì?

Mật khẩu chặn thao tác tác giả qua daemon: mở để sửa, đọc asset tác giả,
clone để chỉnh sửa và các thao tác bản nháp liên quan. Chỉ khóa nút UI là
không đủ. Grant mở khóa gắn với người dùng/tài nguyên/phiên bản, bị thu hồi
khi đổi mật khẩu và không được giữ qua daemon restart.

Nhập, thực hành và xuất lại bài đã xuất bản không yêu cầu mật khẩu; verifier
được giữ trong gói chia sẻ. Bản nháp chỉnh sửa cùng bài dùng bảo vệ liên quan;
clone độc lập có trạng thái bảo vệ riêng. Đổi mật khẩu có hiệu lực độc lập
với việc lưu hoặc bỏ thay đổi nội dung editor.

**Giới hạn cần hiểu rõ:**

- Gói v3 không phải ZIP đổi đuôi, nhưng cũng **không phải mã hóa**.
- Người biết định dạng có thể viết decoder, đọc/chỉnh gói và tính lại checksum.
- Quyền `0700`/`0600` của kho hệ thống ngăn tài khoản thường đọc trực tiếp,
  không chống root hoặc người có quyền quản trị máy.
- Tệp tác giả đưa vào node cho học viên sử dụng cố ý đọc được ở đó.
- Đây là kiểm soát chỉnh sửa trong ứng dụng, không phải DRM hoặc hệ thống
  chống gian lận khi thi. Không quảng bá là “chỉ CyberLab giải mã được”.

## 3. Nhập từ Labtainer

Đây là **chuyển đổi sang bản nháp**, khác import `.cyberlab`:

```bash
cyberlab inspect-labtainer SOURCE
cyberlab import-labtainer SOURCE --as NEW_LAB_ID --title "Tên bài"
```

SOURCE có thể là thư mục, ZIP, TAR hoặc TGZ. Inspection không tạo bài và không
chạy Dockerfile; đọc `can_import` trong kết quả, không lấy exit code 0 làm
bằng chứng tương thích. `runtime_ready` không được coi là đã đạt qua inspection.

Converter chỉ chuyển tập khai báo được hỗ trợ: máy/mạng, tệp home, một phần
tham số, Quiz và Result–Goal. Không tự thay criterion không hỗ trợ bằng kiểm
tra “tệp tồn tại”, không thêm image BusyBox hoặc lệnh ngủ để giả bài chạy được.
Các hook, quyền đặc biệt, capture/Goal thời gian và cấu hình không biểu diễn
được phải được báo để tác giả xem xét.

Sau nhập, chọn image/lệnh chạy, kiểm tra account/shell, hướng dẫn và tiêu chí
trước khi xuất bản. Bản nháp có báo cáo ở `assets/docs/labtainer-import.json`;
Dockerfile chỉ được ghi nhận thông tin, không được tự build hoặc thực thi.
Khả năng đọc cấu trúc không tương đương chạy nguyên bài Labtainer.

## 4. Quản lý thư viện

Mỗi máy có kho riêng do daemon quản lý. Xuất bản không tải lên server và
update ứng dụng không được viết lại bài. Kho cũ trong home chỉ được di chuyển
bằng [thao tác quản trị riêng](../installation/README.md).

Xóa bài cần xác nhận; mọi Session chưa `STOPPED` của bài đó, kể cả người dùng
khác hoặc phiên lỗi, đều có thể chặn xóa. Không tự dừng các phiên để xóa cho
xong. Xóa mẫu bài không phải lệnh dọn toàn bộ image hay bản nháp.
Nếu timeout, kiểm tra lại thư viện trước khi thử lại vì kết quả có thể chưa rõ.

**Tra cứu kỹ thuật:** [Định dạng gói v3](package-format.md) ·
[Schema](../../schemas/v1/lab.schema.json) · [Checkwork](../assessment/README.md).
