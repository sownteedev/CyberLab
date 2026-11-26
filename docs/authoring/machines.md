# Máy, mạng và phần mềm

Trang này tập trung vào cấu hình máy trong bài. Quy trình tạo/lưu bài nằm ở
[hướng dẫn tác giả](README.md); vòng đời khi chạy ở [thực hành](../practice/README.md).

## 1. Chọn môi trường

| Môi trường | Cách sử dụng |
| --- | --- |
| Node hạn chế | Image được cho phép, tài khoản/shell có sẵn; quyền và hệ thống tệp bị giới hạn |
| Ubuntu workstation | Môi trường thực hành có phần mềm, GUI và setup tài khoản/tệp theo chính sách đã duyệt |

Không suy ra khả năng của image từ tên hiển thị. BusyBox không phải Ubuntu,
không mặc định có Bash, APT hoặc các quyền của Ubuntu workstation. Image phải
được daemon cho phép; khai báo một username không tự chứng minh account đó
đã tồn tại trong một image tùy ý.

`hostname` là hostname thật của container. Tên gọi giữa các node mặc định dựa
trên ID node trong mạng, không nhất thiết trùng hostname hiển thị.
UID/GID trong node khác UID người sở hữu Session trên host.

## 2. Tài khoản, nhóm và quyền tệp

Máy Ubuntu có khả năng `machine-setup-v1` cho phép cấu hình tài khoản chính,
nhóm/tài khoản bổ sung, sudo và tệp Home/System từ giao diện. Nút quản lý mở
hộp thoại tài khoản/nhóm; mật khẩu của tài khoản máy lab không phải mật khẩu
mở khóa chỉnh sửa bài.

- `node.user` mô tả tài khoản đăng nhập chính: tên, UID/GID, home và shell.
- `node.setup` mô tả thiết lập bổ sung đã kiểm soát. UID/GID bổ sung nằm trong
  vùng 3000–59999; runtime kiểm tra trùng với tài khoản trong image.
- Chế độ sudo gồm tắt, yêu cầu mật khẩu hoặc không yêu cầu mật khẩu, theo
  khả năng môi trường. Đây là quyền bên trong node, không phải trên host.
- Mật khẩu thiết lập đi qua luồng riêng, không đặt plaintext trong đối số
  tiến trình hoặc tùy chọn UI. Hash tài khoản Linux không dùng chung với
  verifier của khóa sửa bài.
- Tệp System có kiểm tra đường dẫn, owner/group và mode; không chấp nhận
  script root tùy ý như một cách thay thế khai báo setup.

Setup áp dụng trước lệnh khởi động trên máy mới; reset áp dụng lại từ mẫu.
Resume phục hồi bản lưu, không chạy setup để ghi đè trạng thái đang học.
Setup riêng của bài không được trộn vào software image dùng chung.

## 3. Mạng và Internet

Mỗi mạng là bridge riêng của Session; không dùng chung default bridge của
Docker và không tự công bố cổng host. Có hai cách khai báo địa chỉ:

| Kiểu | Tác giả thiết lập |
| --- | --- |
| Tự động | Chọn mạng cho node; để runtime cấp địa chỉ |
| Tĩnh | Subnet, gateway nếu cần và địa chỉ node thuộc đúng subnet |

Không nhập IP tĩnh cho mạng tự động, dùng địa chỉ gateway cho node hoặc tạo
địa chỉ trùng nhau. Hai Session dùng subnet tĩnh chồng lấn không có không gian
địa chỉ riêng để chạy song song; Session thứ hai bị từ chối, không tự đổi IP.

**Internet** là tùy chọn của từng mạng, không phải mạng phụ bí mật dành cho
cài package. Một node nối một mạng chỉ cần một interface cho cả giao tiếp lab
và outbound khi được bật. Hai interface chỉ hợp lý khi có hai kết nối mạng.

- `internet: false` tạo mạng nội bộ. Chuẩn bị phần mềm trước vẫn là quy trình
  riêng, không tự thêm egress vào mạng thực hành.
- `internet: true` cho phép outbound theo routing/firewall host, **không phải**
  bộ lọc chỉ cho APT hay chỉ cho Internet công cộng; LAN/host có thể vẫn reachable.
- Node nối đồng thời mạng offline và mạng có Internet vẫn có thể ra ngoài qua
  mạng thứ hai.
- Bài cũ bỏ trống trường này có quy tắc tương thích; không coi thiếu trường
  là luôn offline. Ubuntu đứng riêng không khai báo mạng có thể dùng egress
  tương thích; hãy khai báo và gắn mạng offline rõ ràng nếu cần cô lập.

DNS tùy chỉnh chỉ trỏ tới node được khai báo, có địa chỉ tĩnh và chia sẻ mạng
phù hợp. Node đó phải thực sự chạy DNS; nhập địa chỉ không tự cài dịch vụ.
Giữ nguyên phân giải tên nội bộ mặc định nếu không có yêu cầu đặc biệt.

## 4. Phần mềm

Trong thẻ **Phần mềm**, tìm tên/mô tả package rồi chọn. Danh sách Ubuntu là
metadata package, không phải danh sách command: ví dụ lệnh `ping` do package
cung cấp, không được biến thành tên gói giả. Một package xuất hiện trong
metadata chưa chắc dùng được trong container; UI phải giữ lý do giới hạn.

Nguồn metadata được cố định trong mã nguồn, xử lý bằng tài khoản thường và
cache riêng. Tìm kiếm không chạy APT/Docker với quyền root. Firefox Mozilla
là công thức riêng được duyệt; không có Snap runtime hoặc nguồn APT tùy ý
chỉ vì tên gói có trong Ubuntu.

| Thao tác | Điều xảy ra |
| --- | --- |
| Chọn package rồi lưu | Lưu khai báo phần mềm, không cài lên host |
| Nhấn **Cài phần mềm** | Chuẩn bị trước image cho lần khởi động nhanh hơn |
| Bắt đầu khi chưa cài trước | Session ở `PREPARING`; daemon chuẩn bị, rồi mới mở terminal |
| Tiếp tục bản lưu | Khôi phục trạng thái đã lưu; không cài đè phần mềm lên checkpoint |

Không mở terminal khi bị hủy hoặc chuẩn bị thất bại. Image đã xác minh được
tái sử dụng theo công thức và base image; nếu bị xóa thì có thể cần tải/cài lại.
Thay danh sách phần mềm không được làm mất tệp thực hành hoặc đưa tệp cá nhân
vào image dùng chung.

GUI mặc định bật cho máy Ubuntu mới, không có công tắc riêng ở thẻ phần mềm.
Điều này không tự mở ứng dụng và cũng không có nghĩa GUI không tốn tài nguyên:
package cần dung lượng, dịch vụ hiển thị có thể chạy nền. Firefox giữ sandbox;
Wireshark chỉ có quyền bắt gói cần thiết trong phạm vi mạng node.

## 5. Terminal

Một node có thể có nhiều terminal độc lập nhưng dùng chung hệ thống tệp/mạng.
`terminal_count` từ 1 đến 4, tổng tối đa 8 slot mỗi bài. Slot đánh số từ 0;
không tự mở cửa sổ không đồng nghĩa cấm kết nối thủ công.

Ứng dụng terminal trên host do tùy chọn cá nhân quyết định, không phải một
command shell tùy ý được nhúng vào bài. Konsole có thể nhóm tab; các adapter
khác có thể mở cửa sổ riêng. Xem [cách kết nối](../practice/README.md).

## 6. Tham số hóa

Chỉ dùng khi cần biến thể của cùng kịch bản; bài đơn giản không cần thêm mục
nâng cao này. Giá trị nhập được kiểm tra theo kiểu, enum và giới hạn trong schema.
Bỏ override dùng mặc định/phát sinh; chuỗi rỗng được nhập rõ ràng là giá trị khác.

| Phép biến đổi | Mục đích |
| --- | --- |
| `rand_replace` | Thay token bằng số trong khoảng/bước đã khai báo |
| `rand_replace_unique` | Biến thể thay số có ràng buộc duy nhất của phép toán |
| `hash_replace`, `hash_create` | Thay token hoặc tạo tệp từ giá trị hash tương thích bài tập |
| `clone_replace` | Biến đổi gắn với khai báo nhân bản được hỗ trợ |

Phép toán có thứ tự, phụ thuộc seed của Session và chỉ tác động vùng seed
được kiểm tra. Typed substitution không đánh giá đệ quy input người dùng.
Reset/resume giữ dữ liệu tham số đã giải cho Session thay vì tạo bài ngẫu
nhiên khác. MD5 trong bài tập không được dùng như bảo mật mật khẩu.

Có giới hạn số phép toán, độ dài token và tổng seed; sai đường dẫn, thiếu token
hoặc tăng kích thước vượt giới hạn bị từ chối trước khi chạy. Trường và giới hạn
chính xác nằm trong [schema](../../schemas/v1/lab.schema.json) và
[`parameter_operations.py`](../../engine/cyberlab/parameter_operations.py).
Không suy ra tương thích toàn bộ Labtainer từ việc có các toán tử này.
