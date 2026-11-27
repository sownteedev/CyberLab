# Nền tảng mục tiêu và kiểm thử bộ cài

CyberLab ưu tiên máy Linux dùng để học tập và thực hành. Danh sách này là lựa
chọn phạm vi sản phẩm, không phải thống kê thị phần hệ điều hành tại Việt Nam.
Kiểm chứng phải gắn với phiên bản và kiến trúc cụ thể, không chỉ tên distro.

## Thứ tự ưu tiên

| Nền tảng | Phạm vi hiện tại |
| --- | --- |
| Ubuntu 26.04 LTS, x86_64 | Mục tiêu cài mới chính; cần Quickshell native từ nguồn tương thích được quản trị viên chấp thuận. |
| Ubuntu 24.04 LTS / Linux Mint 22.x, x86_64 | Có fallback Qt/Quickshell riêng khi thiếu runtime native; Mint dùng adapter nền `noble` nhưng phải nghiệm thu desktop riêng. |
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
dùng `bash install.sh` mà không cần thêm nguồn. Nếu chưa có, phiên cài tương tác
đề xuất nguồn tương ứng và hỏi chấp thuận; không cần người dùng đoán cờ để chạy
lại. `--yes` không tự chấp thuận nguồn. Khi thay đổi đã được push lên
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
cài. Trên x86_64, khi chưa có runtime/candidate native, bộ cài chuẩn bị Qt
6.10.3 riêng và build Quickshell 0.3.2 bằng tài khoản thường. Không thêm PPA,
không thay Qt hệ thống; plugin X11/Wayland được kiểm tra dependency trước khi
chấp nhận runtime. Xem [luồng và dung lượng](README.md#runtime-gui-riêng).

Máy đã có Quickshell native giữ đường cũ. ARM64 không được dùng bundle x86_64;
các nền/kiến trúc khác chưa có fallback riêng sẽ báo thiếu runtime tương thích.

### Nguồn upstream và build thủ công

- [Hướng dẫn cài Quickshell 0.3.2](https://quickshell.org/docs/v0.3.2/guide/install-setup/)
  là điểm tham chiếu cho nguồn Ubuntu/Fedora/Arch; PPA Ubuntu là
  `ppa:avengemedia/danklinux`. Không suy ra mọi Ubuntu release đều có gói.
- [BUILD.md của bản 0.3.2](https://github.com/quickshell-mirror/quickshell/blob/v0.3.2/BUILD.md)
  yêu cầu Qt >=6.6, private headers tương ứng và rebuild khi Qt đổi ABI.
  Vì vậy build Quickshell không tự giải quyết thiếu phiên bản Qt tương thích.
- Nếu quản trị viên tự build/cài đúng hướng dẫn upstream, launcher nhận ELF
  native `qs` hoặc `quickshell` trong `/usr/bin` và `/usr/local/bin`. Binary và
  đường dẫn phải thuộc root, không cho group/other ghi. Không chạy wrapper từ
  `PATH`, AppImage mới hoặc binary trong home như một runtime native tin cậy.
- `bash install.sh --check` kiểm tra phiên bản và probe Qt/QML. Không sửa
  package manager hay nâng Qt để ép probe đạt; cài thủ công phải tự quản lý
  việc rebuild khi Qt của máy thay đổi.

### Arch và Fedora

Arch dùng gói stable trong repository đang bật. Fedora có lựa chọn COPR riêng
đã khai báo trong bộ cài; không dùng nguồn Ubuntu cho Fedora hoặc đoán phiên
bản nền của distro dẫn xuất. Không tắt SELinux để vượt lỗi cài dịch vụ.

### Kali rolling: APT yêu cầu gỡ thư viện cũ

Khi kế hoạch APT có `libpyside6-py3-6.10`/`libshiboken6-py3-6.10` bị gỡ để
thay bằng bản ABI khác, bộ cài giữ chốt `--no-remove`. Đây không phải lỗi tải
CyberLab; các dependency của máy cần được quản trị riêng. Không bỏ chốt gỡ gói,
không trộn repository Ubuntu vào Kali và không tự chạy nâng cấp toàn hệ điều hành.

Bộ cài chạy thêm một lần **mô phỏng**, không cài đặt, để hiển thị gói bị thay.
Kiểm tra nguồn APT, cập nhật chỉ mục bằng `sudo apt-get update`, rồi xem trước
`apt-get -s full-upgrade`. Người quản trị cần đọc kế hoạch và quyết định nâng
cấp Kali riêng; sau khi hệ thống nhất quán, chạy lại bộ cài CyberLab.
`--allow-dependency-upgrades` không cho phép gỡ gói và không giải quyết một
chuyển đổi ABI có gỡ thư viện cũ. Lượt sửa này có test mô phỏng tình huống trong
ảnh, chưa xác minh cài thật trên máy Kali của người dùng.

## Dependency và khả năng sử dụng

- **Bắt buộc:** Python >=3.12, Quickshell >=0.3.1, Qt/QML native hoặc riêng phù hợp,
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

### Runtime riêng trên Ubuntu 24.04 x86_64

- Cài mới từ snapshot source local trên Ubuntu **24.04.5** VM sạch đạt;
  không thêm nguồn APT Quickshell, không thay Qt hệ thống.
- CLI, daemon, danh mục/Session rỗng và probe QML từ wheel cài thật đạt.
  Studio tải được trên **Xvfb/X11** và **Weston headless/Wayland**; đã chụp
  giao diện thư viện kết nối daemon. Đây không phải nghiệm thu GPU/desktop thật.
- Runtime sau bỏ thư viện phát triển tĩnh còn khoảng **177 MiB**. Source/SDK
  tạm được dọn; thư mục/file cài đặt thuộc root và không cho group/other ghi.
- `install.sh --update` đạt, không đổi runtime riêng. Gây lỗi có chủ đích ở
  bước xác minh sau cài: rollback phục hồi metadata/cấu hình, giữ nguyên hash
  runtime; CLI/daemon/QML tiếp tục hoạt động. Lượt này dùng thư viện rỗng,
  không chứng minh riêng khả năng phục hồi dữ liệu bài/checkpoint có sẵn.
- Đã sửa lỗi thiếu `libxcb-shape0` mà offscreen không phát hiện; kiểm tra
  dependency plugin X11/Wayland được thêm trước khi chấp nhận runtime.
  Đã sửa quyền parent với `umask 077`, thử lại bằng root và user thường trong VM.
- 35 suite hồi quy Python đạt, trong đó có 19 kiểm thử runtime riêng. Kiểm thử
  timeout dọn process group lặp 20 lần đạt sau sửa race đọc `/proc` trong test.
- Giới hạn: chưa thử Mint/ARM64/desktop GPU thật, chưa chạy lại Session Docker
  và GUI node trong đợt này, chưa chạy curl từ GitHub với code chưa push.
  Qt/Quickshell riêng không tự được nâng bởi `cyberlab update`.

VM dùng NAT userspace, SSH loopback và dữ liệu thử riêng. Không đổi bản cài,
catalog hay quyền Docker trên máy phát triển. Một lượt kiểm tra bổ sung bị
gián đoạn do host khởi động lại; đã chạy lại cài mới/update/rollback trên VM
khác. Hash cloud image đối chiếu manifest HTTPS, chưa kiểm chứng chữ ký độc lập.

### Các lượt kiểm tra nguồn native trước đó

Lượt kiểm tra nguồn native trước khi thêm runtime riêng (26/11/2026):

- 38 kiểm thử installer đạt, gồm chấp thuận/từ chối nguồn trên PTY, giới hạn
  chỉ mục, nền/kiến trúc, binary native do quản trị viên cài và quyền đường dẫn.
  34 suite Python hồi quy liên quan cũng đạt (suite installer nằm trong số này).
- VM Ubuntu 24.04 sạch dừng trước sudo/thay package vì chỉ mục `noble/amd64`
  không có gói. Không tạo nguồn APT hoặc runtime/kho CyberLab. **Đây là kiểm
  chứng dừng an toàn, không phải cài thành công trên Ubuntu 24.04.**
- VM Ubuntu 26.04 sạch cài thành công từ snapshot source local với nguồn đã
  chấp thuận; CLI/System D-Bus, daemon, Docker và probe Qt/QML đóng gói đạt.
  Giao dịch nâng dependency được chấp thuận chỉ trong VM dùng một lần.
- Chưa thử desktop tương tác/GUI node, chưa tạo Session Docker trong lượt này;
  Xpra vẫn không có trong kho VM. Chưa thử lại Debian/Fedora/openSUSE sạch với
  patch này và chưa kiểm chứng lệnh curl từ GitHub sau khi phát hành.

VM dùng NAT userspace và SSH loopback, không mount dữ liệu host. Image distro
được đối chiếu SHA-256 từ manifest HTTPS, chưa xác minh chữ ký image độc lập.
Các VM, disk tạm và khóa SSH của lượt thử đã được dọn; không cập nhật host.

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
## Thiết kế runtime GUI riêng

Mục tiêu: giữ một lệnh cài và kiến trúc hiện tại, không thay Qt hệ thống.
Ưu tiên runtime native đang tương thích; fallback riêng trước mắt dành cho
Ubuntu 24.04/Mint 22 x86_64. Các nền khác vẫn đi qua adapter native cho tới
khi có bằng chứng nghiệm thu runtime riêng tương ứng.

- [x] Ghim Qt/Quickshell và checksum; tải HTTPS, build không đặc quyền trong
  `/var/tmp`, kiểm tra đường dẫn và dung lượng, dọn source sau khi hoàn tất.
- [x] Cài runtime riêng vào `/usr/lib/cyberlab/gui-runtime`, cô lập thư viện,
  plugin/QML; không đổi biến môi trường toàn hệ thống.
- [x] Tích hợp cài mới, `--deps-only`, kiểm tra, launcher và cập nhật hiện có;
  không thay runtime đang dùng hoặc ghi đè bản cài khi chưa kiểm tra an toàn.
- [x] Test âm tính và hồi quy; chạy cài mới trên Ubuntu 24.04 VM sạch,
  probe QML đóng gói, kiểm tra đường native không hồi quy; ghi giới hạn.

Quyết định triển khai: chưa có kho artifact CyberLab được phát hành, vì vậy
tải Qt SDK dựng sẵn từ Qt và build Quickshell đã ghim trên máy đích. Không
build toàn bộ Qt. Đây là bước đầu có thể kiểm chứng, chưa phải runtime
CyberLab dựng sẵn để tải một lần. Giữ các thông báo giấy phép upstream.

Quickshell được build phần cần cho Studio (core, IO, socket, Qt Quick), không
build các dịch vụ tray/PipeWire/PAM và extension shell không được app dùng.
Các cờ Quickshell `WAYLAND=OFF`, `X11=OFF` tắt extension riêng của shell,
không tắt plugin Qt `xcb`/`wayland`; Studio vẫn dùng cửa sổ Qt thông thường.
Runtime này không dùng làm shell desktop thay thế Quickshell hệ thống.
