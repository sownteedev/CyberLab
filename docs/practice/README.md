# Thực hành và lưu tiến độ

Session là một lần thực hành, tách khỏi mẫu bài trong thư viện. Tệp người học
tạo và phần mềm cài trong node không tự cập nhật ngược vào bài của tác giả.

## 1. Bắt đầu bài

1. Chọn bài và đọc hướng dẫn.
2. Trả lời Quiz chuẩn bị nếu bài có yêu cầu; xem đáp án, rồi chọn vào thực hành.
3. Nhập tham số nếu bài có khai báo.
4. Chờ chuẩn bị phần mềm và tạo máy. Terminal chỉ mở sau khi máy sẵn sàng.

Trạng thái `PREPARING` không có nghĩa ứng dụng bị treo: lần đầu có thể phải
tải image/package. Khi lỗi, giữ thông tin lỗi và trạng thái Session để xử lý,
không nhấn bắt đầu liên tục để tạo nhiều phiên.

```bash
cyberlab labs
cyberlab start LAB_ID --no-terminals
cyberlab sessions
cyberlab status SESSION_ID
```

`LAB_ID`, `SESSION_ID` và các tên viết hoa trong hướng dẫn là chỗ cần thay
bằng giá trị thật. CLI cũng chịu kiểm tra Quiz, quyền và chính sách như Studio.

## 2. Kết nối terminal và GUI

Terminal là shell trong node, không phải terminal quản trị host:

```bash
cyberlab terminal SESSION_ID NODE_ID --slot 0
```

Mỗi slot là một shell riêng dùng chung filesystem của node. Đóng/detach
terminal không đồng nghĩa dừng cả Session. Stop/reset vô hiệu hóa kết nối cũ.

Tùy chọn ứng dụng terminal nằm trong cài đặt cá nhân. CyberLab phát hiện
adapter native được hỗ trợ, không thực thi command host tùy ý do bài cung cấp.
Nếu không có desktop, CLI giữ Session và hướng dẫn kết nối thủ công. Lỗi mở
cửa sổ không được tự gọi StartLab lần nữa hoặc xóa phiên vừa tạo.

GUI ưu tiên native X11/XWayland khi hợp lệ, Xpra là fallback. Ứng dụng vẫn
cần được cài trong node; bật hỗ trợ GUI không tự chạy Firefox/Wireshark.
Nếu fallback bị ngắt, dùng thao tác kết nối lại mà không tạo lại Session.
Chi tiết điều kiện và rủi ro ở [hiển thị GUI](display-security.md).

## 3. Lưu, tạm dừng, tiếp tục và reset

| Thao tác | Kết quả | Điều cần nhớ |
| --- | --- | --- |
| **Lưu** (`save`) | Tạo/thay checkpoint, phiên vẫn chạy | Không bảo đảm chụp nhất quán khi ứng dụng vẫn ghi tệp |
| **Tạm dừng** (`suspend`) | Lưu trước rồi dọn tài nguyên chạy | Lưu thất bại thì không tự dừng |
| **Tiếp tục** (`resume`) | Tạo lại máy từ cấu hình và checkpoint đã lưu | Không lấy mẫu mới nhất trong thư viện để thay thế |
| **Dừng** (`stop`) | Dọn tài nguyên chạy, giữ checkpoint đã có | Thay đổi sau lần lưu cuối không được tự lưu |
| **Làm lại** (`reset`) | Xóa checkpoint, tạo lại từ mẫu Session đã chụp | Không phải tiếp tục; dữ liệu thực hành bị mất |
| **Xóa bản lưu** (`discard`) | Xóa checkpoint của phiên được chọn | Không xóa mẫu bài hoặc dữ liệu của phiên đang chạy |

```bash
cyberlab save SESSION_ID
cyberlab suspend SESSION_ID
cyberlab resume SESSION_ID --no-terminals
cyberlab discard SESSION_ID --yes
```

Studio phải phân biệt **đã tạm dừng** với **đã dừng, có bản lưu**. Bản lưu cũ
không chứng minh thay đổi gần nhất đã được lưu. Chỉ báo thành công sau khi
daemon xác nhận đúng Session, trạng thái và checkpoint cần thiết.

## 4. Checkpoint giữ những gì?

| Môi trường | Được lưu | Không được lưu |
| --- | --- | --- |
| Node hạn chế | Workspace và dữ liệu bài trong giới hạn | Thay đổi tùy ý ngoài workspace |
| Ubuntu workstation được cho phép | Workspace và filesystem hệ thống qua checkpoint image riêng | Bộ nhớ tiến trình, kết nối mạng; `/tmp` và `/run` vẫn tạm thời |

Tạm dừng là lưu rồi tạo lại, không phải đóng băng máy ảo. Dừng ghi tệp và chờ
cài package xong trước khi lưu. Checkpoint có giới hạn dung lượng/số lượng;
hết quota phải báo lỗi, không tự bỏ tiến độ người khác.

Database thực hành ở `/var/lib/cyberlab/authoring/practice.sqlite3`, riêng với
bản nháp. Bản lưu giữ cấu hình/asset đã chụp, không phụ thuộc bài trong thư
viện còn nguyên. Bản lưu hỏng hoặc thiếu asset phải được giữ để chẩn đoán,
không âm thầm thay bằng bài mới hoặc reset.

Sau khi daemon khởi động lại, phiên có bản lưu được khôi phục thành trạng thái
dừng/tạm dừng phù hợp; người dùng chủ động tiếp tục. Không hứa giữ phần chưa
lưu của container sau khi dịch vụ khởi động lại.

## 5. Tệp, báo cáo và bài nộp

Cây asset của tác giả không phải trình duyệt trực tiếp mọi tệp sinh trong
container. Dùng terminal để làm việc với dữ liệu runtime. Chức năng nhập tệp
Session, nếu được dùng qua CLI, chỉ thêm dữ liệu cho lần thực hành đó; không
thay đổi mẫu bài hoặc tự trở thành asset tác giả.

Checkwork tạo báo cáo theo snapshot mới. **Nộp và kết thúc** là xuất gói bằng
chứng rồi dừng theo xác nhận, không tự tải bài lên server. Chỉ các artifact
được khai báo đi vào gói nộp, không phải toàn bộ checkpoint/image.
Xem [đánh giá và nộp bài](../assessment/README.md).

## 6. Khi có lỗi

- Chuẩn bị lâu: kiểm tra trạng thái và lỗi tải/phần mềm; không đổi package host
  hoặc xóa image tùy ý khi một phiên khác đang dùng.
- Terminal không hiện: thử kết nối thủ công; phân biệt lỗi mở cửa sổ với lỗi máy lab.
- Không kết nối được GUI: đọc backend/fallback, không dùng `xhost +` để bỏ bảo vệ.
- Dừng/dọn chưa xong: giữ Session để kiểm tra, không xóa tài nguyên Docker khác.
- Lưu lỗi: giữ phiên đang chạy và nội dung hiện có; không reset để thử sửa lỗi lưu.

**Đọc tiếp:** [Máy và mạng](../authoring/machines.md) ·
[Checkwork](../assessment/README.md) · [Bảo trì ứng dụng](../installation/README.md).
