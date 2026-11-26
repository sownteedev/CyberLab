# Nền tảng mục tiêu và kiểm thử bộ cài

CyberLab ưu tiên máy Linux dùng để học tập và thực hành. Danh sách này là lựa
chọn phạm vi sản phẩm, không phải thống kê thị phần hệ điều hành tại Việt Nam.
Kiểm chứng phải gắn với phiên bản và kiến trúc cụ thể, không chỉ tên distro.

## Thứ tự ưu tiên

| Nền tảng | Phạm vi hiện tại |
| --- | --- |
| Ubuntu 26.04 LTS, x86_64 | Mục tiêu cài mới chính; cần Quickshell native từ nguồn tương thích được quản trị viên chấp thuận. |
| Ubuntu 24.04 LTS / Linux Mint 22.x | Ưu tiên về trải nghiệm và thông báo lỗi, nhưng chưa cung cấp đường cài tự động đầy đủ: nguồn PPA đã duyệt không có Quickshell cho nền `noble`. |
| Debian 13, x86_64 | Mục tiêu cài mới thứ hai; có lựa chọn nguồn Quickshell OBS đúng Debian 13. |
| Arch Linux | Giữ đường cài native từ repository đồng bộ; không thực hiện `pacman -Sy` hoặc tự nâng cả hệ thống. |
| Fedora | Giữ adapter và xử lý dependency; chưa coi là đã kiểm chứng cài mới trong lượt này. |
| openSUSE và các bản dẫn xuất khác | Không mở rộng phạm vi trong đợt này; có adapter không có nghĩa là đã kiểm thử desktop. |

Windows/macOS không cài trực tiếp bằng `install.sh`. Nếu dùng máy ảo Linux,
phải đáp ứng yêu cầu của Linux bên trong; WSL không nằm trong phạm vi chứng nhận
của đợt kiểm thử này. Không dùng script này cho NixOS, hệ không có systemd,
OSTree/immutable hoặc Podman thay Docker.

## Cài đặt theo nền tảng

### Ubuntu 26.04 LTS hoặc Debian 13

Từ checkout, xem nguồn bổ sung trước khi chấp thuận:

```bash
bash install.sh --plan --enable-quickshell-repo
bash install.sh --enable-quickshell-repo
```

Nếu đã có Quickshell native tương thích trong hệ thống/repository đang bật,
dùng `bash install.sh` mà không cần thêm nguồn. Khi thay đổi đã được push lên
`master`, người dùng không cần clone:

```bash
curl -fsSL https://raw.githubusercontent.com/sownteedev/CyberLab/master/install.sh \
  | bash -s -- --enable-quickshell-repo
```

Cờ này là chấp thuận nguồn bên thứ ba và khóa ký được chỉ rõ, không phải bỏ qua
kiểm tra chữ ký. Bộ cài vẫn xem xét giao dịch gói và hỏi xác nhận. Nếu cần nâng
dependency đã có, xem kế hoạch rồi mới dùng `--allow-dependency-upgrades`;
không mặc định thêm cờ này vào hướng dẫn cài máy sử dụng hằng ngày.

### Ubuntu 24.04 / Linux Mint 22.x

Không trộn gói Quickshell/Qt của Ubuntu 26.04 hoặc Debian vào hệ 24.04 để ép
cài. Với `UBUNTU_CODENAME=noble`, tùy chọn thêm PPA dừng sớm và giải thích đúng
nền Ubuntu, thay vì hướng dẫn lặp lại một nguồn không có gói.

Nếu máy đã được quản trị viên chuẩn bị Quickshell >=0.3.1 tương thích với Qt
native, vẫn có thể chạy kiểm tra môi trường; việc này không tự chứng nhận đầy
đủ hỗ trợ Mint/Ubuntu 24.04. Dự án chưa bổ sung Qt riêng, AppImage, build
Quickshell từ source hoặc nguồn chưa duyệt để che giấu giới hạn này.

### Arch và Fedora

Arch dùng gói stable trong repository đang bật. Fedora có lựa chọn COPR riêng
đã khai báo trong bộ cài; không dùng nguồn Ubuntu cho Fedora hoặc đoán phiên
bản nền của distro dẫn xuất. Không tắt SELinux để vượt lỗi cài dịch vụ.

## Dependency và khả năng sử dụng

- **Bắt buộc:** Python >=3.12, Quickshell >=0.3.1, Qt/QML native phù hợp,
  systemd, System D-Bus và Docker Engine hệ thống.
- **Terminal:** dùng terminal native đã có; chỉ đề xuất `xfce4-terminal` khi
  kiểm tra xác nhận chưa có terminal được hỗ trợ.
- **Cập nhật GUI:** cài gói cung cấp `pkexec` khi còn thiếu. Giữ nguyên helper
  đã có, không tự lựa chọn/thay thế authentication agent của desktop.
- **Xpra:** cài gói native nếu repository có. Nếu thiếu thì báo rõ chưa có
  fallback GUI nhưng không chặn Studio, terminal và native X11/XWayland.
  Không có Xpra và native không hoạt động thì không dùng được GUI của node.
- **APT sạch:** cập nhật chỉ mục trước khi tìm công cụ tải/kiểm tra khóa cho
  nguồn tùy chọn; dừng khi refresh lỗi, không cài theo metadata cũ âm thầm.

Các thay đổi này chỉ áp dụng khi cài dependency. `--check`, `--no-deps` và
`--update` không tự cài thêm gói OS hoặc chỉnh repository.

## Bằng chứng hỗ trợ

Lượt kiểm tra 26/11/2026 dùng VM x86_64 riêng với source local:

| Hệ thống | Đã xác minh | Chưa xác minh |
| --- | --- | --- |
| Ubuntu 26.04.1 | Cài sau sửa, CLI/D-Bus, mạng hai node, quyền, update và rollback | Desktop/GUI tương tác đầy đủ |
| Debian 13.8 | Cài sạch với bản sửa cuối, cùng các luồng trên, Studio tải qua Xvfb | Desktop thực, GPU và polkit agent |
| Arch/Fedora/openSUSE | Kiểm tra adapter cách ly; Arch có kiểm tra kế hoạch trên host | Cài mới toàn bộ trong lượt này |

Không suy từ kết quả này rằng link GitHub đã có source local, hoặc mọi gói và
desktop đều tương thích. Chi tiết lỗi, log, cảnh báo QML còn lại và giới hạn
được giữ trong [báo cáo kiểm thử](../archive/reviews/distro-validation-2026-11-26.md).

Nguồn Debian 13 đã chuyển sang máy chủ gốc OBS để tránh mirror sai hash.
Nếu máy từng bật URL cũ, quản trị viên phải xem xét thay nguồn; installer vẫn
không ghi đè file khác nội dung và update ứng dụng không sửa repository OS.
