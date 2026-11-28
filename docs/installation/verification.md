# Đối chiếu bản cài với máy phát triển

Tài liệu này phân biệt những gì đã kiểm tra trên máy Arch phát triển với những
gì chỉ được kiểm tra cách ly. Không dùng nó để kết luận mọi distro đều đã được
nghiệm thu.

## Máy Arch phát triển

- Daemon `cyberlabd.service` đang hoạt động qua System D-Bus.
- `cyberlab info` có Docker runtime, authoring, machine setup, Checkwork,
  Quiz, package preparation, lưu/tiếp tục Session và import/export gói bài.
- `cyberlab draft info` có `busybox:1.37.0` và
  `cyberlab/ubuntu:24.04-1`; Ubuntu được đánh dấu workstation.
- `cyberlab gui-status` xác nhận native XWayland; Xpra được kiểm tra riêng như
  đường dự phòng.
- Người dùng có terminal native; daemon vẫn là thành phần duy nhất được phép
  thao tác Docker.
- Không dùng quyền thành viên nhóm `docker` cho tài khoản desktop.

## Kiểm tra bản cài và bộ cài

- Cấu hình cài mới sinh ra cả BusyBox và Ubuntu workstation; Ubuntu dùng recipe
  cố định, image được kiểm tra label, user, thư mục làm việc và lệnh khởi động.
- Image hợp lệ được tái sử dụng; image cùng tên nhưng khác recipe không bị ghi
  đè. Tải/build/xác minh lỗi thì không đổi chính sách daemon.
- Máy đã cài chỉ có BusyBox dùng `bash install.sh --prepare-ubuntu`. Lệnh này
  dùng khóa installer và maintenance, kiểm tra Session của tất cả tài khoản,
  giữ catalog và phục hồi cấu hình khi xác minh thất bại.
- Xpra trên Debian/Ubuntu được kiểm tra thêm GTK3, cầu nối Cairo, rencodeplus
  và Pillow; thiếu thành phần vẽ thì không báo GUI fallback là sẵn sàng.
- Wheel đã build được kiểm tra tài nguyên QML, manifest, icon và smoke probe;
  kiểm thử thật Docker trên VM sạch vẫn là bước nghiệm thu riêng.

## Giới hạn

- Máy Arch hiện tại không chứng minh bộ cài chạy được trên Kali, Fedora,
  Debian hoặc Ubuntu khác phiên bản.
- Chưa tự chạy Docker thật trên VM mới trong lượt rà soát này vì không được
  thay đổi máy thử hoặc dữ liệu thực hành của người dùng.
- Cài đặt từ GitHub chỉ được coi là bản mới sau khi các thay đổi này được push
  lên `master` và thử lại bằng lệnh bootstrap trên máy sạch.
