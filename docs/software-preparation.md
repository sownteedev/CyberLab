# Phần mềm đi kèm máy Lab

## Mở danh sách APT và Firefox Mozilla (2026-11-21)

Phạm vi đã thống nhất: giữ container và schema phần mềm; không thêm máy ảo,
nguồn APT tùy ý, Snap runtime hoặc quyền container. Tiếp tục sửa trong checkout
hiện tại để giữ các thay đổi đang có, không tạo nhánh hay di chuyển dữ liệu.

- [x] Metadata/cache: giữ mọi tên gói Ubuntu, ghi rõ gói bị giới hạn; lấy Firefox
  thật từ chỉ mục Mozilla với kiểm tra SHA256, tách nguồn và lỗi tải từng nguồn.
- [x] Giao diện: nguồn gói rõ ràng, gói chưa hỗ trợ vẫn hiện cùng lý do; Firefox
  Mozilla dùng lại công thức đã duyệt, không thay đổi lựa chọn trong bài cũ.
- [x] Kiểm thử: metadata, cache cũ/mất mạng, chọn và bỏ chọn, hai nguồn Firefox,
  luồng chuẩn bị phần mềm; tải chỉ mục thật nhưng không dùng catalog thật làm thử.

Kiểm chứng đợt này: 32 test package-search, 20 software, 26 auto-software;
QML software 32, notifications 35, editor 150 đều đạt. Editor cho phép riêng
cảnh báo khởi tạo WorkerScript Qt đã biết. Qmllint hai component thay đổi và
git diff --check đạt. Chỉ mục amd64 thật trả 88.814 tên gói Ubuntu và Firefox
Mozilla; cache tạm giữ đúng nguồn và lý do giới hạn. Arm64 được kiểm tra bằng
fixture, chưa tải chỉ mục thật. Ảnh kiểm tra nằm tại
`/tmp/cyberlab-full-apt-ui-green/firefox-sources.png`.

Chưa cài thử gói thật trong Docker ở đợt này; test luồng chuẩn bị dùng môi trường
cách ly. Chưa triển khai bản cài: phiên công cụ có NoNewPrivs=1, không thể nâng
quyền. Không đóng Studio hoặc tác động nội dung đang sửa để vượt giới hạn này.

## Luồng sử dụng

Trong trình soạn bài, chọn máy Ubuntu rồi mở thẻ **Phần mềm**:

- Ô tìm kiếm luôn hiện; tìm theo một phần tên hoặc mô tả công dụng.
- Kết quả là các hàng tên/mô tả ngắn với dấu chọn; không còn nút dài hay ô nhập
  APT thủ công. Gói đã chọn vẫn hiện khi đổi từ khóa.
- GUI mặc định bật cho máy Ubuntu mới; không còn công tắc GUI.
  Firefox/Wireshark vẫn dùng công thức cài riêng.
- Giữ nút **Cài phần mềm**, với chú thích **Cài sẵn để khởi động nhanh hơn.**
  Nút này chuẩn bị trước môi trường riêng của máy Lab, không cài lên máy chủ.
  Đây là lựa chọn, không phải điều kiện để lưu bản nháp hoặc lưu vào thư viện.
- **Lưu vào thư viện/Cập nhật bài** chỉ kiểm tra cấu hình rồi yêu cầu xác nhận;
  không tự chạy thử máy hoặc tải/cài phần mềm. Kiểm tra môi trường chạy là
  thao tác riêng khi người dùng yêu cầu.
- Khi chạy bài, daemon tự chuẩn bị image riêng cho các máy Lab; không cài lên host.
  Việc chuẩn bị chạy ngầm, không hiện tiến trình hoặc cửa sổ cài đặt. Chỉ mở
  terminal sau khi mọi máy đã sẵn sàng. Nếu thất bại, hiện lỗi qua popup.
  Trong lúc chờ vẫn xem được các phiên và dừng bài. Không mở terminal khi bị
  hủy hoặc cài thất bại; môi trường đã cài được tái sử dụng cho lần sau.

Bản nháp/bài cũ không bị sửa chỉ vì mở trình soạn. Khi chọn phần mềm
trên máy Ubuntu cũ, Studio bật GUI, giữ các gói đã chọn và
chuẩn bị lại nếu image trước đó chưa có GUI. Máy mới lấy giới hạn tài nguyên
GUI từ catalog của daemon; đây là giới hạn, không phải lượng RAM cấp sẵn.
GUI không miễn phí: gói nền cần dung lượng/thời gian cài và kết nối hiển thị
có thể chạy tiến trình nền. Không tự mở Firefox hoặc ứng dụng của người học.
Lưu vào thư viện chỉ lưu khai báo, không yêu cầu image đã được chuẩn bị.
Lần chạy đầu cần mạng để tải gói; những lần sau tái sử dụng image đã xác minh.
Nếu image bị xóa, CyberLab chuẩn bị lại từ khai báo khi chạy. Image được gắn
vào Session, không tự sửa bài đã lưu hoặc bản nháp. Bản lưu hệ thống đã có
phần mềm vẫn được khôi phục nguyên trạng, không cài đè khi tiếp tục bài.

Trong lúc cài, Session ở PREPARING; API vẫn cho xem trạng thái và dừng bài.
Không tạo máy thực hành cho tới khi mọi phần mềm đã sẵn sàng. Giữ giới hạn
hai tác vụ chuẩn bị, một tác vụ mỗi người dùng; dùng lại cache theo công thức
và base image. Tự chuẩn bị giới hạn hai giờ, mỗi container cài tối đa 20 phút.
Các API chuẩn bị thủ công vẫn giữ cho CLI/tương thích, nhưng không nằm trong
luồng Studio thông thường.

Image môi trường là bất biến và được tái sử dụng khi fingerprint phần mềm cùng
image Ubuntu cơ sở giống nhau. Bài và bản nháp giữ image đúng cấu hình hiện tại
ngay cả khi chỉ lưu danh sách gói, chưa ghi mã image. Vì vậy dừng rồi mở lại
không phải cài lại phần mềm. Khi đổi cấu hình, image cũ được dọn nếu không còn
bài, bản nháp, phiên đang chạy hoặc checkpoint cần đến.
Lịch sử cài thất bại và kết quả của bản nháp cũ không giữ image vô thời hạn.
Kết quả sẵn sàng cho đúng phiên bản bản nháp vẫn được giữ để áp dụng.
Image vừa chuẩn bị được giữ xuyên suốt việc chuẩn bị nhiều máy và bàn giao
cho phiên thực hành. Dọn image không chạy đồng thời với thao tác tạo image,
không chờ tác vụ cài đang chạy khi người dùng dừng phiên.
Daemon cũng dọn image mồ côi khi khởi động và trước khi chuẩn bị image mới.
Việc dọn chỉ nhắm image có nhãn CyberLab; không dùng `docker system prune` và
không xóa image đang được sử dụng.

Lưu bài làm ghi checkpoint hệ thống và mã image phần mềm vào cấu hình đã lưu.
Chỉ thay checkpoint cũ khi bản mới lưu thành công; lỗi lưu không dừng máy hay
xóa bản lưu trước. Tiếp tục khôi phục checkpoint, còn làm lại từ đầu bỏ bản lưu
và tạo container sạch trên image phần mềm đã chuẩn bị, không cài lại nếu cấu
hình không đổi. Nếu không xác minh được các tham chiếu, bỏ qua dọn image thay
vì xóa liều; lỗi dọn lúc khởi động daemon không chặn toàn bộ ứng dụng.

Tìm kiếm dùng lệnh CLI draft software-search: kiểm tra GetAuthoringInfo qua
D-Bus, sau đó tra metadata trong tiến trình người dùng. Không thêm API mạng
vào daemon. Chỉ mục Ubuntu 24.04 được đọc theo kiến trúc amd64
hoặc arm64, từ main/universe/restricted/multiverse của noble, updates và security.
Tìm tên/mô tả, kèm từ khóa tiếng Việt phổ biến; tối đa 40 kết quả mỗi truy vấn.
Mở phần mềm sẽ tải danh sách từ chỉ mục; truy vấn rỗng hiển thị 40 gói đầu
theo tên. Không trộn danh sách gợi ý hoặc đổi tên gói thành tên lệnh/ứng dụng:
`iputils-ping`, `python3`, `openssh-client` giữ nguyên tên và mô tả của Ubuntu.
Wireshark chỉ xuất hiện nếu có trong chỉ mục và vẫn dùng công thức đã duyệt
để giữ quyền bắt gói. Các gói Snap/chuyển tiếp sang Snap và gói bị chính sách
chặn vẫn hiện nhưng không thể chọn, kèm lý do ngắn. Firefox có hai hàng nguồn
riêng: Ubuntu APT (chuyển sang Snap, chưa hỗ trợ) và Mozilla APT (chọn được,
dùng công thức Firefox đã duyệt). Hàng Mozilla chỉ xuất hiện khi có metadata
Firefox thật, không thêm danh sách ứng dụng đặt sẵn. Lựa chọn Firefox hoặc gói
cũ trong bài đã lưu vẫn được giữ và có thể bỏ. Không hỗ trợ kho bên ngoài tùy ý.
Khi mất kết nối, chỉ dùng metadata đã lưu; không thay bằng danh sách đặt sẵn.
Đây là metadata để chọn gói, không phải cam kết mọi gói chạy được trong Lab.
APT khi cài vẫn kiểm tra nguồn/chữ ký theo công thức đã duyệt.

Downloader chỉ dùng các URL HTTPS cố định, kiểm SHA256/size từ
Release; Ubuntu dùng đường by-hash, Mozilla dùng chỉ mục Packages theo kiến trúc.
Không tuyên bố xác thực chữ ký Release bằng GPG ở
bước tìm kiếm. Có giới hạn tải, bộ giải nén, thời gian, số lượng gói; một lần
nạp dùng bộ đệm riêng từng người dùng trong 6 giờ. File cache 0600 dưới
XDG_CACHE_HOME/cyberlab/package-search (mặc định ~/.cache); ghi thay thế nguyên
tử, không theo symlink. Khóa file giữ một worker tải nền, tránh tải trùng giữa
các cửa sổ. Cache phiên bản 2 buộc tải lại chỉ mục cũ vốn đã lọc mất gói.
Lỗi tải giữ cache và lựa chọn hiện tại. Lỗi riêng kho Mozilla không chặn kết quả
Ubuntu; giữ metadata Mozilla đã kiểm tra trước đó nếu có, báo popup và cho thử lại.
Không gửi từ khóa người dùng tới kho; tìm kiếm được thực hiện trên chỉ mục.

Daemon vẫn chỉ cho AF_UNIX. Tiến trình metadata chạy với tài khoản desktop,
không chạy root, không cài APT hoặc dùng Docker. Chỉ tải metadata từ kho cố định;
không gửi từ khóa người dùng đi. Mọi chuẩn bị/cài phần mềm vẫn qua daemon và
công thức image đã duyệt. Không sửa catalog hay bản nháp để thử tìm kiếm.

## Quyền và giới hạn

Wireshark được cấp quyền bắt gói tối thiểu trong network namespace của máy
Lab. CyberLab không cấp `privileged`, Docker socket, host network hoặc mount
màn hình host. Phạm vi lưu lượng còn phụ thuộc mạng, routing và firewall của
Lab.

Firefox dùng nguồn APT Mozilla đã xác minh chữ ký, không dùng Snap trong image
chuẩn bị. Gói bổ sung chỉ là tên gói, không nhận lệnh shell, URL, Dockerfile
hoặc đường dẫn gói.

Nếu Xpra không kết nối được, Session vẫn giữ nguyên và terminal vẫn dùng được;
dùng **Kết nối lại GUI** sau khi sửa dependency host. Không cài lại image tự
động trong lúc thực hành.

Máy Ubuntu khai báo GUI có giới hạn 512 tác vụ (tiến trình và luồng) và
256 MiB shared memory; Ubuntu không khai báo GUI vẫn giữ 256 tác vụ. Giới hạn
RAM/CPU trong cấu hình máy vẫn được giữ nguyên. Thay đổi giới hạn runtime chỉ
áp dụng khi container được tạo lại sau khi lưu và dừng phiên, không sửa nóng
phiên đang học. Firefox vẫn chạy với sandbox mặc định, không dùng
`--no-sandbox` hoặc mở toàn bộ quyền container.

Kênh GUI dùng Docker exec **không TTY**, giải mã riêng phần đóng khung stdout
của Docker trước khi chuyển dữ liệu Xpra qua API daemon. Đây không phải phiên
terminal tương tác: byte nhị phân trùng Ctrl+P/Ctrl+Q không được coi là lệnh
detach. Terminal học tập vẫn giữ TTY bình thường.

Kênh GUI hết hạn, đã thoát, gặp EOF hoặc lỗi đọc/ghi được giải phóng để có thể
kết nối lại; kênh đang sống không bị thay thế. Dọn kết nối không dừng Session
hay đóng các terminal cá nhân.

## Nhập bài sang máy khác

Gói `.cyberlab` chỉ lưu khai báo phần mềm và công thức, không nhúng image lớn.
Máy nhận phải chuẩn bị lại môi trường trước khi chạy bài. CyberLab không tự
thực thi lệnh trong ZIP nhập vào.

## Kiểm chứng bản sửa GUI (2026-11-04)

`tools/check_software_runtime.py --uid UID --display DISPLAY` đã đạt trên
Arch/Niri với XWayland, Xpra host 6.4.4 và Xpra guest 3.1.5, dùng catalog,
bản nháp, profile Firefox và Session tạm riêng. Kiểm tra gồm truyền đủ các
byte nhị phân qua Docker không TTY, bắt/lọc ICMP giữa hai máy Lab bằng tài
khoản thường, Firefox headless không tắt sandbox, hai cửa sổ Firefox/Wireshark
hiển thị, resize, ngắt/kết nối lại GUI, nhập liệu trang thử và vòng đời
save/stop/resume/suspend/reset/phiên mới. Các tài nguyên thử đã được dọn.

Script GUI nhận diện cửa sổ bằng tiêu đề fixture riêng thay vì tên lớp
Firefox cố định; đợi tiêu đề phản ánh thao tác nhập thay vì kiểm tra ngay.
Profile Firefox thử nằm trong home của container để không làm đầy tmpfs
`/tmp`; chỉ profile tạm này tắt màn hình chào và tải dữ liệu telemetry.
Không sửa profile của người dùng hoặc cấu hình Firefox trong image công bố.
Khi kiểm tra cửa sổ thất bại, script giữ ảnh riêng các cửa sổ fixture dưới
`/var/tmp/cyberlab-gui-diagnostic-*` để chẩn đoán.

Đây là nghiệm thu trên máy hiện tại, không phải cam kết hiệu năng trên mọi
DE/WM. Thao tác gõ tự động được gửi vào màn hình của container; tương tác
bàn phím/chuột thực tế từ host vẫn cần người dùng nghiệm thu.
