# Chuẩn bị image và cài Studio cho OVA offline

Tài liệu lịch sử: các công cụ MVP/OVA/cài AppImage đã được chuyển ra ngoài
repository để lưu trữ. Cài đặt Linux hiện tại dùng `bash install.sh` và hướng
dẫn `install-mvp.md`. Không chạy lại các lệnh sửa bundle cũ trên hệ thống mới.

Các lệnh quản trị bên dưới chỉ dành cho người chuẩn bị máy ảo. Coding agent
không tự chạy chúng. Công cụ không cấp Docker socket cho học sinh và không
ghi lại catalog production. Không chạy quy trình `deploy_mvp.py repair` cũ
trên VM đã chuyển catalog sang home.

## 1. Tách Lab, image và source

Một Lab trong `CyberLab-labs` có `lab.yaml`, `assets/<node>/`, `assets/docs/` và
tuỳ chọn `image-source/<node>/Dockerfile` cùng `rootfs/`. Image đã build nằm
trong Docker local storage, không nằm dưới `assets/`. Mạng được khai báo trong
`lab.yaml`; không có bản cấu hình mạng thứ hai. Start không build hoặc pull image.

Image phải chuẩn bị sẵn account, UID/GID, home, shell và công cụ bootstrap theo
runtime policy. Filesystem gốc chỉ đọc, home là tmpfs rỗng có giới hạn và noexec.
Không đặt file bài vào home lúc build rồi mong chúng còn hiện trong Session:
hãy dùng `assets/<node>/` để seed home. File hệ thống đặt trong `rootfs/etc/`,
chương trình được duyệt đặt trong `rootfs/usr/local/bin/`. `COPY rootfs/ /`
mới đưa chúng vào image; tên thư mục không tự có tác dụng.

`lab.yaml` phải có `command` tường minh chạy lâu dài hoặc dịch vụ tương thích
với user không đặc quyền. Runtime không dùng ENTRYPOINT của image. Dockerfile
build thành công không chứng minh Lab chạy được; validation vẫn báo
`runtime_verified: false`.

## 2. Chuẩn bị gói image, không đụng Docker

Làm trên thư mục Lab nguồn riêng hoặc đọc một bài có sẵn. Không chỉnh catalog
thật nếu chưa được người dùng duyệt nội dung thay đổi.

```sh
cd /home/student/CyberLab
.venv/bin/python -I tools/prepare_lab_images.py plan \
  /path/to/reviewed-lab-source dist/images/my-lab
```

Lệnh tạo `manifest.json` và tar context riêng cho các node có recipe. Đầu ra
phải là thư mục mới ngoài Lab nguồn và ngoài `CyberLab-labs`. Node không có
recipe được ghi nhận là cần một image đã preload. Cùng một image không được
có hai recipe khác nhau. Mỗi context tối đa 32 MiB và 512 mục; gói tối đa
128 MiB, không nhận link, file đặc biệt, file ẩn hoặc đường dẫn đi ngược thư mục.

Recipe được giới hạn một FROM có tag cụ thể, không `latest`; cho phép RUN,
COPY, USER, WORKDIR, ENV, CMD, LABEL, EXPOSE. COPY chỉ nhận `rootfs/ /` (hoặc
mảng JSON tương đương). Không nhận frontend directive, heredoc, ARG, ADD,
ONBUILD, VOLUME, multi-stage hoặc RUN mount/entitlement. Đây là phạm vi công cụ
MVP, không phải toàn bộ cú pháp Dockerfile.

Người quản trị phải đọc Dockerfile và toàn bộ rootfs trước khi dùng checksum.
Checksum chỉ phát hiện thay đổi sau khi duyệt, **không xác thực tác giả hoặc
chứng minh recipe an toàn**. RUN vẫn là mã thực thi của người chuẩn bị image.

## 3. Build rõ ràng bằng tài khoản quản trị

Base image phải có sẵn trong Docker local. Công cụ không tự tải base bị thiếu,
không push, không ghi allowlist và không ghi catalog:

```sh
sudo /usr/bin/python3 -I tools/prepare_lab_images.py build \
  dist/images/my-lab --reviewed-sha256 SHA256_DA_DUYET
```

Công cụ giữ context được kiểm tra trong thư mục root-private ở `/var/tmp`,
kiểm tra base image ID và chạy builder `default` với `--load --pull=false
--network=none`. Cần Docker cùng Buildx đã cài. `--network=none` giới hạn mạng
của bước RUN; không phải một cam kết tắt mọi truy cập mạng của Docker/BuildKit.
Thời điểm chuẩn bị image có thể cần cài dependency riêng; hoạt động của app
trong OVA sau khi preload mới là phạm vi bắt buộc offline.

Không ghi đè tag đầu ra đã tồn tại: chọn version tag mới. Nếu có lỗi, giữ staging
để kiểm tra; một image từ bước trước có thể đã được tạo. Không xóa/prune hàng
loạt để thử lại. `inventory.json` chứa image ID đã build/preload; chưa có Lab
hay Session nào được chạy bởi công cụ này.

Sau khi xem xét image và phù hợp runtime policy, quản trị viên bổ sung đúng
reference vào `allowed_images` qua quy trình cập nhật cấu hình có chủ đích,
giữ nguyên catalog và UID. Việc này cần quyền quản trị riêng, không phải quyền
authoring của học sinh. Kết thúc Session trước mọi lần restart daemon.

## 4. Studio trong gói cài chính

Wheel CyberLab chứa package `cyberlab_studio` gồm launcher và QML/JS. Lệnh
`cyberlab-studio` dùng interpreter của chính môi trường đã cài để gọi CLI.
Nó không tìm `.venv` trong source, không đọc Lab trực tiếp và không gọi Docker.
Launcher production loại bỏ các biến môi trường demo/smoke.

Build wheel mới bằng quy trình packaging, rồi quản trị viên dùng
`tools/upgrade_runtime.py` và checksum wheel như trước. Không cập nhật khi còn
Session active. Sau đó cài Quickshell đã tải trước và launcher hệ thống:

```sh
sudo /usr/bin/python3 -I tools/install_studio_runtime.py \
  /home/student/.local/share/cyberlab/quickshell-0.3.1.AppImage
```

Installer chỉ nhận bản AppImage có checksum đã pin trong repository; không
tải Internet. Nó kiểm tra package QML đã cài, giữ backup, rồi cài:

- `/usr/lib/cyberlab/quickshell.AppImage`
- `/usr/local/bin/cyberlab-studio`
- `/usr/share/applications/cyberlab-studio.desktop`

Không restart daemon hay thay đổi cấu hình, catalog, Docker image. Cài nhiều
file không phải giao dịch toàn bộ: nếu lỗi giữa chừng, giữ backup và xem xét
trước khi chạy lại. Launcher chạy bằng user desktop, không dùng sudo.

Đổi shortcut phát triển cũ sang bản chính, chạy bằng **student**:

```sh
/usr/bin/python3 -I tools/install_quickshell.py --production-shortcuts
```

Lệnh này chỉ thay các shortcut CyberLab trong home, giữ bản cũ tại
`~/.local/state/cyberlab/shortcuts-*`, không tải Quickshell. Không xóa source
để ép shortcut đổi đường dẫn. Có thể dùng `/usr/local/bin/cyberlab-studio`
để bỏ qua shortcut phát triển cũ trong PATH.

## 5. Phân phối nhỏ bằng OVA

Trước khi export, quản trị viên tạo manifest chỉ đọc để ghi nhận đúng catalog,
wheel, image ID và AppImage đã có. Dùng Python của runtime đã cài mới, không
cấp Docker socket cho student. Chạy từ thư mục gốc repository hoặc bundle
cập nhật đã được duyệt (nơi có `tools/prepare_ova_release.py`); tool sử dụng
engine của runtime đã cài, không tự lấy engine mới từ mã nguồn:

```sh
sudo /usr/lib/cyberlab/venv/bin/python -I tools/prepare_ova_release.py \
  /home/student/CyberLab-labs \
  /tmp/cyberlab-release-wheel/cyberlab_engine-0.9.0-py3-none-any.whl \
  /tmp/cyberlab-release-manifest --check-docker
```

Nếu bundle wheel nằm ở đường dẫn khác, thay bằng đường dẫn thật. Lệnh yêu cầu
catalog trùng `daemon.toml`, xác nhận mỗi image được allowlist và tồn tại local
khi dùng `--check-docker`, từ chối nếu còn resource CyberLab, kiểm tra Lab definition,
file seed/tài liệu và ghi checksum. Bỏ cờ này chỉ tạo inventory chưa kiểm tra image,
không được coi là bản đã sẵn sàng offline. Nó không copy,
đổi quyền, xóa hoặc sửa `CyberLab-labs`; không dừng Session và không gọi VMware.
Manifest là bằng chứng chuẩn bị, chưa phải OVA.

Giữ runtime, system config, catalog, Docker images và Quickshell trong ổ đĩa
VM. Không cần Docker Hub, GitHub hay imodule để người nhận chạy bài. Source
có thể giữ để trình bày nhưng không còn là dependency của app đã cài đúng.
Không tự chèn các fixture/demo vào catalog khi nâng cấp.

Tạo bản sao release của VM trước khi dọn credentials/cache và export. Việc
chạy nghiệm thu thủ công, export OVA, rồi import vào VMware khác vẫn là bước
riêng cần người dùng thực hiện/duyệt; công cụ mới không chứng minh các bước đó
đã hoàn tất. Unit test và smoke test không tự được chạy trong quy trình này.

Khi lập manifest OVA với `--check-docker`, mọi image trong allowlist đều phải
có trên máy, kể cả image chưa được bài nào sử dụng nhưng có thể được chọn khi
tạo Lab mới. Manifest `images` ghi toàn bộ allowlist; `catalog_image_references`
ghi riêng tập image đang được catalog dùng. Công cụ không tự pull image còn thiếu.

## 6. Bundle cập nhật offline

`tools/package_offline_release.py` gom wheelhouse đã chuẩn bị, AppImage đúng
checksum, launcher, tài liệu và công cụ quản trị. Nó không tải dependency,
không cài đặt, không lấy bài từ catalog và không mang Docker image theo. Đây
là gói cập nhật **VM đã được provision**, không thay thế file OVA hoặc bộ cài
Ubuntu/Docker/systemd trên máy trắng.

Chuẩn bị wheelhouse bằng pip ở giai đoạn development (có thể cần Internet).
Nên pin phiên bản dependency từ môi trường đã duyệt. Giữ cả wheel CyberLab và
các dependency chuyển tiếp, đúng Python 3.12 và kiến trúc VM. Sau đó chạy:

```sh
/usr/bin/python3 -I tools/package_offline_release.py build \
  /path/to/wheelhouse \
  /home/student/.local/share/cyberlab/quickshell-0.3.1.AppImage \
  /path/to/new-offline-bundle
```

Bundle giữ `requirements.lock` có version/hash của từng wheel và manifest
checksum cho tất cả file. Lưu hash manifest riêng sau khi duyệt. Trước khi
dùng gói trên VM, kiểm tra từ bản tool tin cậy:

```sh
/usr/bin/python3 -I tools/package_offline_release.py check \
  /path/to/new-offline-bundle --sha256 SHA256_MANIFEST_DA_DUYET
```

Checksum không xác thực nguồn phát hành; không chạy script quản trị từ gói
không tin cậy. `check` kiểm tra tính nguyên vẹn, không chạy test và không chứng
minh đủ dependency hoặc runtime đúng. Manifest ghi dependency metadata để người
chuẩn bị kiểm tra, còn việc phân giải phụ thuộc phải được thực hiện lúc tạo
wheelhouse. Các wheel không bao gồm dependency hệ điều hành/driver desktop.

Sau kiểm tra, dùng `tools/upgrade_runtime.py` trong bundle với wheel và checksum
của wheel đó như quy trình hiện có; sau đó cài Studio từ `quickshell.AppImage`
cũng trong bundle. Không tự chạy `pip install` dưới quyền root vào môi trường
đang phục vụ Session để bỏ qua backup và guard của updater.
