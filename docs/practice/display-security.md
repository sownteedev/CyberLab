# Hiển thị GUI và ranh giới an toàn

Trang này dành cho chẩn đoán/quản trị GUI trong node. Studio tự nó là ứng dụng
desktop trên host; việc Studio mở được không chứng minh GUI của node đã kết nối.

## 1. Hai đường hiển thị

| Backend | Khi dùng | Ranh giới |
| --- | --- | --- |
| Native X11 / XWayland | Chế độ tự động, máy chủ hiển thị và cấp quyền vượt kiểm tra | Dùng display host; không tương đương display cách ly |
| Xpra | Native không đáp ứng hoặc chọn Xpra rõ ràng | Display của guest, truyền dữ liệu qua kênh được daemon quản lý |

`native-x11` là định danh backend cho cả Xorg và XWayland. XWayland cho ứng
dụng X11 chạy trên phiên Wayland; bản thân nó không phải cơ chế cô lập từng
ứng dụng lab khỏi các client khác trên display chung.

Không có Xpra trên host và native không hoạt động thì terminal vẫn có thể dùng,
nhưng GUI của node không có fallback khả dụng. Không giải quyết bằng cách cấp
`privileged`, mount toàn bộ socket màn hình hoặc tắt sandbox của trình duyệt.

## 2. Cấp quyền native

CyberLab xác minh danh tính server/socket, UID, thời điểm khởi tạo tiến trình
và cơ chế X11 SECURITY trước khi cấp quyền. Không chấp nhận một tiến trình
chỉ vì nó có tên `Xwayland`; không sao chép credential đăng nhập desktop để
chia sẻ chung cho các node.

Đường XWayland có listener riêng mode `0600` cho mỗi node trong vùng lease
của daemon. Worker mở endpoint đã xác minh với quyền tài khoản desktop,
kiểm tra UID guest và cookie riêng trước khi chuyển dữ liệu. Có giới hạn kết
nối, buffer, timeout và đóng descriptor khi lỗi. Đây là chuyển tiếp X11,
không phải mã hóa hình ảnh như Xpra.

Việc chuyển descriptor phục vụ buffer X11 không biến display chung thành
display cách ly. Chọn Xpra nếu yêu cầu thực hành cần ranh giới hiển thị tách
khỏi desktop host; không đánh đồng container với máy ảo chống mã độc.

## 3. Lỗi và kết nối lại

- Chuẩn bị hoặc probe guest thất bại có thể chọn Xpra trước khi dùng GUI.
- Native đang chạy bị mất kết nối không thể âm thầm chuyển cửa sổ ứng dụng
  đang tồn tại sang Xpra; cần xử lý kết nối lại theo trạng thái thực tế.
- Hết lease, EOF hoặc lỗi truyền phải giải phóng handle để thử lại; không
  thay kênh đang sống hoặc dừng Session chỉ để sửa cửa sổ.
- Stop/reset/fallback dọn worker và quyền riêng của node. Không thu hồi quyền
  hoặc đóng client không thuộc CyberLab.

Kênh Xpra dùng Docker exec không TTY, tách framing stdout trước khi chuyển
byte qua daemon. Chuỗi byte trùng phím detach không được xử lý như terminal.
Terminal tương tác vẫn dùng TTY theo luồng riêng.

## 4. Kiểm tra có kiểm soát

```bash
cyberlab gui-status
```

Trạng thái ready của host chỉ chứng minh các điều kiện host đã được kiểm tra,
không phải phép thử guest, tương tác chuột/phím hay phép đo độ trễ.

| Công cụ phát triển | Phạm vi |
| --- | --- |
| `tools/tests/unit/check_native_display.py` | Hồi quy chính sách và vòng đời, cách ly |
| `tools/tests/runtime/check_x11_security.py` | Kiểm tra cấp quyền trên display Xvfb dùng một lần |
| `tools/tests/runtime/check_xwayland.py` | Fixture XWayland; chế độ guest cần Docker/image phù hợp |
| `tools/tests/runtime/check_software_runtime.py` | Nghiệm thu phần mềm/GUI thật trong môi trường thử |

Đọc `--help` và [phân loại kiểm thử](../development/README.md) trước khi chạy.
Không dùng display/login thật làm fixture cho kiểm thử thu hồi quyền. Chỉ
đóng tiến trình và dọn tài nguyên do lượt thử tạo; không đổi quyền socket,
không chạy `xhost +`, không tự chuyển phiên X11/Wayland của người dùng.
