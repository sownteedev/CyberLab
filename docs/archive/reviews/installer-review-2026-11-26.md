# Rà soát bộ cài đa distro — 26/11/2026

> **Tài liệu lịch sử.** Trạng thái và lệnh bên dưới thuộc lần ghi nhận này,
> không thay thế [hướng dẫn hiện hành](../../README.md).

## Kết luận

Chưa đủ điều kiện tuyên bố cài được trên mọi distro. Bộ cài có bốn nhánh trình
quản lý gói, không phải bốn chứng nhận tương thích trên mọi phiên bản. Lượt này
chỉ kiểm tra mã nguồn, kiểm thử cách ly, metadata nguồn gói và kế hoạch cài;
không cài lại hệ thống, sửa dependency hay chạy máy ảo mới.

## Những điểm cần xử lý hoặc xác minh

1. **Ubuntu 24.04:** đã tải lại chỉ mục `noble/main/binary-amd64/Packages.gz`
   của PPA được cấu hình trong `tools/install/repositories.sh`; không có bản ghi
   `Package: quickshell`. Thêm PPA này không tự giải quyết thiếu Quickshell.
   Đây là kết luận về nguồn cụ thể, không khẳng định không tồn tại nguồn khác.
2. **Fedora:** `docs/installation/README.md` ghi nhận lần thử trước cài được dependency
   nhưng dịch vụ ứng dụng không khởi động. Chưa tái hiện trong VM mới ở lượt này;
   không suy đoán nguyên nhân hoặc coi kết quả test Python là đã giải quyết.
3. **Debian/openSUSE:** chưa có bằng chứng cài mới xuyên suốt trong lượt này.
   Chỉ mục OBS Debian 13 hiện có Quickshell 0.3.2 cho amd64 và arm64; điều này
   không chứng minh bộ giải dependency, dịch vụ và ứng dụng hoạt động đầy đủ.
4. **Cập nhật bằng giao diện:** `ui/update_window.py` yêu cầu `/usr/bin/pkexec`,
   nhưng danh sách dependency trực tiếp và preflight của installer không đảm
   bảo có chương trình này. Trên distro tách riêng pkexec, một desktop tối giản
   có thể cài ứng dụng nhưng không mở được cửa sổ cập nhật. CLI có thông báo
   chuyển sang `cyberlab update`; đây không phải lỗi của mọi bản cài. Cần kiểm
   tra cả authentication agent, không tự cài một desktop agent tùy ý.
5. **Giới hạn chủ đích:** yêu cầu Linux/systemd/System D-Bus, Python >=3.12,
   Quickshell >=0.3.1 và Docker hệ thống. Distro không có adapter, non-systemd,
   OSTree/immutable hoặc Podman thay Docker không thuộc luồng hỗ trợ này.

## Kết quả thực thi mới

| Kiểm tra | Kết quả |
| --- | --- |
| `bash -n` với `install.sh` và mọi `tools/install/*.sh` | Đạt |
| `check_system_update.py` | 19 đạt |
| `check_upgrade_runtime.py` | 31 đạt |
| `check_update_ui.py` | 21 đạt |
| `check_terminal_apps.py` | 28 đạt, có fixture cho bốn họ distro |
| `check_desktops.py` | 74 đạt |
| Tổng Python | **173 đạt** |
| `bash install.sh --check` trên máy Arch hiện tại | Exit 2: Python, terminal, Xpra và QML đạt; Docker API cần kiểm tra quản trị |
| Bootstrap GitHub chạy qua stdin với `--plan` | Exit 0 trên Arch hiện tại; không cài package/service |

GitHub `master` được kiểm tra ở commit
`3881f69a6711006d0fb960ed7924929e1bc65332`. Entry script tải theo commit này
được so sánh bằng byte với `install.sh` local trước khi chạy `bash -s -- --plan`.
Bootstrap tiếp tục tải snapshot từ GitHub; không lấy các sửa đổi chưa push.
Đây là kiểm tra luồng tải/kế hoạch trên máy đã có dependency, **không phải cài
mới bằng curl trên một máy sạch**.

Các endpoint metadata đã đọc (không thêm repository hoặc nhập khóa vào máy):

```text
https://api.github.com/repos/sownteedev/CyberLab/git/ref/heads/master
https://archlinux.org/packages/extra/x86_64/quickshell/json/
https://ppa.launchpadcontent.net/avengemedia/danklinux/ubuntu/dists/noble/main/binary-amd64/Packages.gz
https://download.opensuse.org/repositories/home:/AvengeMedia:/danklinux/Debian_13/Packages.gz
```

Log và bản sao metadata: `/tmp/cyberlab-installer-review-20261126/`.
Đây là dữ liệu chẩn đoán tạm, không phải artifact phát hành.

## Kiểm chứng còn thiếu trước khi công bố hỗ trợ

- Chọn rõ từng distro, phiên bản và kiến trúc CPU; cài trong VM sạch tương ứng.
- Xác minh daemon, D-Bus, quyền kho bài, mở Studio và tạo/chạy bài Docker thật.
- Kiểm tra cập nhật qua terminal và giao diện, xác thực, hủy thao tác và rollback.
- Điều tra lại lỗi dịch vụ Fedora bằng journal/audit của guest, không tắt SELinux.
- Xác minh dependency/nguồn Quickshell và pkexec trên từng nền tảng mục tiêu.

Phiên công cụ hiện tại có `NoNewPrivs=1`; không thử vượt giới hạn này. Không thay
đổi mã chạy của installer trong lượt rà soát; chỉ bổ sung báo cáo này.
