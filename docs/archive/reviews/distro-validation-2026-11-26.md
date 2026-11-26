# Kiểm chứng bộ cài theo distro — 26/11/2026

> **Tài liệu lịch sử.** Trạng thái và lệnh bên dưới thuộc lần ghi nhận này,
> không thay thế [hướng dẫn hiện hành](../../README.md).

## Phạm vi

Ưu tiên Ubuntu LTS, Linux Mint và Debian; giữ adapter Arch/Fedora. Không đổi
framework, không tải Qt riêng, không tự thêm repository ngoài cờ chấp thuận.
Các VM dưới đây là tài nguyên dùng một lần của lượt thử, không phải máy hoặc
bài của người dùng. Không cập nhật hệ thống host, commit hoặc push source.

Mã thử gồm các thay đổi local chưa push. Các lệnh VM có
`--yes --allow-dependency-upgrades` là chấp thuận rõ ràng trên **VM thử riêng**;
không đưa các cờ này vào lệnh mặc định dành cho máy sử dụng hằng ngày.

## Các sửa đổi

| Lỗi/thiếu sót | Tái hiện | Thay đổi |
| --- | --- | --- |
| Thiếu `pkexec` trên desktop tối giản | Dependency không đảm bảo helper mà cửa sổ update yêu cầu | Chọn gói native theo distro; giữ helper đã có, cảnh báo khi check/update gặp thiếu helper |
| PPA `noble` không có Quickshell | Đọc chỉ mục amd64 trực tiếp; Linux Mint 22.x cùng nền Ubuntu này | Không đề xuất/bật nguồn đã biết thiếu gói; giải thích Ubuntu 24.04/Mint 22.x, không trộn Qt khác phiên bản |
| Xpra chặn cả cài đặt | Ubuntu 26.04.1 VM: APT không có candidate `xpra` | Xpra trở thành dependency dự phòng có điều kiện; không che giấu giới hạn GUI nếu cả native và fallback đều không dùng được |
| APT cloud sạch chưa có chỉ mục | Debian 13 VM: `gnupg` không có candidate ở bước chuẩn bị nguồn | Refresh trước khi giải dependency của công cụ repository; dùng `--error-on=any` |
| Mirror OBS sai dữ liệu | Metadata yêu cầu 1.574.188 byte; mirror trả 1.573.472 byte và SHA-256 khác | Nguồn Debian 13 dùng máy chủ gốc OBS trả đúng hash; giữ nguyên fingerprint/kiểm tra APT, không ghi đè source khác nội dung |
| Debian tách Docker CLI | Cài `docker.io` với `--no-install-recommends` nhưng thiếu `/usr/bin/docker` | Thêm `docker-cli` khi distro có gói riêng; cho phép hoàn thiện đúng provider Debian, vẫn từ chối Docker CE trộn lẫn, Podman hoặc binary custom |

Đã thêm `tools/tests/unit/check_installer_distros.py`. Các lỗi được ghi nhận bằng kiểm thử
thất bại trước sửa; suite cuối có 21 test, một số test gồm nhiều distro/subcase.
`check_desktops.py` được điều chỉnh để kiểm tra việc chọn gói Xpra có điều kiện.

## Môi trường thật

VM chạy QEMU/KVM x86_64, NAT userspace, SSH chỉ mở trên loopback host; source
được chép vào `/var/tmp` guest, không có mount home/Docker socket của host.
Image tải từ distro và đối chiếu checksum tải qua HTTPS; không tuyên bố đã
kiểm tra chữ ký image độc lập. Tài khoản thử `learner`, UID 1000, không thuộc
nhóm Docker.

### Ubuntu 26.04.1 LTS

- Cài native Quickshell 0.3.2 từ PPA đã chấp thuận, Qt 6.10.2 và Docker 29.1.3.
- Lần đầu dừng ở Xpra thiếu candidate; sửa rồi chạy lại trên VM đó. Không mô tả
  đây là một lần cài thành công ngay từ đầu với bản script cuối.
- Cài runtime/daemon/D-Bus thành công; kiểm tra QML từ runtime đóng gói offscreen đạt.
- Thư viện ban đầu rỗng; tạo, lưu, kiểm tra và publish bài BusyBox hai node qua
  CLI/System D-Bus; start/reset/stop đều đạt.
- Kiểm tra TCP bằng `nc` và DNS hostname giữa hai node bằng UID 65534 đạt.
  Một phép thử đầu dùng BusyBox `ping` thất bại do quyền raw socket; đổi phép
  thử sang TCP để kiểm tra mạng, **không thay quyền container hoặc coi ping đã đạt**.
- Tài khoản thường không đọc được `/var/lib/cyberlab/labs` và không ghi được
  Docker socket; không thêm tài khoản vào nhóm Docker.
- `install.sh --update` thành công, giữ bài và cấu hình. Khi có Session đang
  chạy, update bị từ chối, Session còn RUNNING và receipt không đổi.
- Tiêm lỗi riêng trong callback xác minh sau thay runtime: updater trả lỗi và
  phục hồi; daemon, API, receipt, cấu hình và bài vẫn còn. Source tiêm lỗi trong
  guest được phục hồi trong `finally`, không đưa thay đổi đó vào repo.
- Xpra không có trong kho đang dùng: native GUI chưa được thử trên desktop
  tương tác và không tuyên bố có fallback Xpra ở guest này.

### Debian 13

- VM đầu tái hiện các lỗi APT rỗng, mirror OBS và Docker CLI tách gói. Sau sửa,
  cài runtime/daemon và kiểm tra QML đóng gói thành công.
- Source APT cũ do lần thử tạo ra được lưu riêng trong guest trước khi kiểm
  tra endpoint mới; bộ cài không tự ghi đè nó.
- Chạy thêm một VM từ image sạch mới với **bản sửa cuối**, không có Git/Docker/
  Quickshell trước khi bắt đầu. Cài thành công ngay lần đầu với bản sửa cuối.
- VM sạch nhận diện Debian 13.8 (`trixie`). Tạo/lưu/publish bài hai node,
  start/reset/stop, TCP không root và phân giải hostname đều đạt. Tài khoản
  thường không đọc được kho riêng hoặc ghi vào Docker socket.
- Update bị chặn khi Session đang chạy; sau khi dừng, `install.sh --update`
  thành công. Tiêm lỗi sau thay runtime rồi rollback thật cũng đạt: giữ
  daemon/API, receipt, cấu hình và bài.
- Launcher từ chối đúng khi không có desktop. Sau khi cài **Xvfb chỉ trong
  guest để thử**, chạy `xvfb-run -a env QT_QUICK_BACKEND=software cyberlab-studio`
  đạt `Configuration Loaded` từ runtime đã cài. Giới hạn chạy 20 giây kết thúc
  bằng mã 124 theo chủ đích; không coi mã này là launcher thoát thành công.
  Đây là smoke tải ứng dụng, không phải kiểm thử thao tác GUI/GPU thực tế.
- Còn cảnh báo QML `Backend.qml:291: Unable to assign QJSValue to QVariantHash`.
  Không chặn tải Studio trong phép thử này, nhưng luồng môi trường Process/UI
  chưa được xác minh đầy đủ; không đánh dấu GUI hoàn toàn sạch lỗi.

### Các nền tảng khác

- Arch host: `install.sh --plan` đạt, không thay đổi package/service.
- Ubuntu 24.04/Mint 22.x: kiểm tra metadata và fixture; chưa cung cấp đường cài
  tự động đầy đủ hoặc thử desktop Mint thật.
- Fedora/openSUSE: regression adapter cách ly; không có VM mới chứng minh
  cài đặt/SELinux/desktop trong lượt này.
- Không thử ARM, Windows, macOS hoặc WSL.

## Kiểm thử hồi quy

| Suite | Số test đạt |
| --- | ---: |
| `check_installer_distros.py` | 21 |
| `check_system_update.py` | 19 |
| `check_upgrade_runtime.py` | 31 |
| `check_update_ui.py` | 21 |
| `check_terminal_apps.py` | 28 |
| `check_desktops.py` | 74 |
| `check_native_display.py` | 33 |
| **Tổng** | **227** |

Cú pháp `install.sh` và toàn bộ `tools/install/*.sh` được kiểm tra bằng
`bash -n`. Các test Python chạy bằng runtime hiện có nhưng không cài/sửa nó.
Test rollback ở trên là VM thật, tách biệt với các test mock trong bảng.
`check_qml_manifest.py` đạt thêm 1 test; chạy lại 21 test distro và kiểm tra
cú pháp/diff cuối lượt đều đạt.

## Bằng chứng và giới hạn bàn giao

Log cục bộ: `/var/tmp/cyberlab-distro-20261126-_1841url/`.
Các tệp chính: `ubuntu-install.log`, `ubuntu-install-fixed.log`,
`ubuntu-lifecycle.log`, `ubuntu-acceptance-fixed.log`, `ubuntu-update.log`,
`ubuntu-rollback.log`, `ubuntu-final-state.log`, `debian-install.log`,
`debian-install-fixed.log`, `debian-install-origin.log`,
`debian-install-complete.log`, `debian-fresh-install.log`,
`debian-fresh-lifecycle.log`, `debian-fresh-acceptance.log`,
`debian-fresh-rollback.log`, `debian-fresh-studio.log`,
`debian-fresh-update.log`, `debian-fresh-final-state.log` và các
`final-check_*.log`. Giữ cả log lỗi ban đầu, không thay bằng log xanh.

Trong log lifecycle, CLI đạt rồi launcher từ chối headless; phép thử Xvfb nằm
ở log Studio riêng. Trong log update, cập nhật đã thành công nhưng lệnh đọc
receipt tiếp theo dùng nhầm đường dẫn `/etc/cyberlab/install-receipt.json`;
receipt đúng `/usr/lib/cyberlab/installation.json` được thu lại trong final-state.
Không giấu mã lỗi của cả hai lệnh ghép này.

Đã dừng cả ba VM và xóa riêng disk, khóa SSH, seed, source archive, helper venv
của lượt thử; giữ log chẩn đoán (`cleanup.log`). Không dọn backup hoặc dữ liệu
thật của host. Chưa triển khai bản sửa lên máy người dùng hoặc GitHub.

Không có acceptance GUI tương tác/hiệu năng, nhập mật khẩu qua polkit agent,
GUI node X11/XWayland/Xpra, mọi dạng phần mềm hoặc mọi distro. Nguồn gói có thể
thay đổi sau ngày kiểm tra; cài được trong VM không phải bảo đảm vĩnh viễn.
