# Studio và hệ thống giao diện

Studio là client desktop Quickshell/QML. Nó dùng CLI không đặc quyền để gọi
daemon, không tự truy cập Docker hoặc kho bài riêng.

## 1. Tổ chức mã nguồn

```text
ui/
├── launcher.py          # Entry point của bản cài
└── studio/
    ├── shell.qml        # Ghép cửa sổ và các service
    ├── qmldir           # Đăng ký kiểu QML công khai
    ├── app/             # Cửa sổ, điều hướng, bảo vệ nội dung chưa lưu
    ├── components/      # Control dùng chung, cây tệp, editor, Markdown
    ├── services/        # CLI transport, workflow, tùy chọn cá nhân
    ├── models/          # Biến đổi dữ liệu bằng JavaScript
    ├── theme/           # Token màu, typography, spacing, shape, motion
    ├── views/           # Thư viện, thực hành, tạo bài, cài đặt
    ├── assets/          # Font, icon và nhận diện đóng gói
    └── testing/         # Harness cách ly, không dùng dữ liệu thật
```

Đây là một module QML với `qmldir` ánh xạ tới file con, không tạo một Theme
singleton mới cho mỗi màn. Component/JS/icon dùng đường dẫn tương đối đúng
vị trí; wheel phải chứa đủ tài nguyên lồng nhau.

## 2. Trách nhiệm giao diện

| Thành phần | Quy tắc |
| --- | --- |
| `Backend.qml` | Chạy CLI nghiệp vụ bằng argv rõ ràng, xử lý yêu cầu và lỗi |
| Service | Điều phối workflow, trạng thái chờ và callback |
| Model | Chuyển đổi/kiểm tra dữ liệu để hiển thị; không thay quyền daemon |
| View | Hiển thị và phát ý định người dùng, không tự thực hiện đặc quyền |
| Window / navigation | Chỉ đổi route sau khi vượt guard nội dung chưa lưu |
| Updater riêng | Luồng quản trị độc lập, giữ cửa sổ hoạt động khi thay runtime |

Mỗi callback cần gắn với đối tượng và đời yêu cầu đang chọn. Đổi bài, đổi
Session hoặc đóng dialog phải vô hiệu hóa phản hồi cũ; không lấy focus hoặc
ghi đè input vì một request trước đó vừa xong.

## 3. Quy ước UX

- Thư viện: nhóm tìm kiếm/bộ lọc, chủ đề và độ khó rõ; không trộn metadata
  tác giả nội bộ vào màn người học.
- Soạn bài: ưu tiên diện tích editor, cây chỉ có asset tác giả; lưu/bỏ sửa
  có xác nhận và xử lý lỗi không làm mất nội dung.
- Thực hành: trạng thái máy/phiên quyết định hành động; không báo thành công
  chỉ vì tiến trình CLI vừa được khởi chạy.
- Thông báo lỗi qua popup tiếng Việt, không mở nhiều popup cho cùng lỗi đang
  hiển thị. Tác vụ nền tự động không được liên tục giành focus.
- Dialog/menu có Escape/Enter, thứ tự focus và trả focus về control mở nó;
  không cuộn ngang chỉ vì hover sát mép dropdown.
- Hướng dẫn ngắn ở nơi cần quyết định; chi tiết kỹ thuật để trong tài liệu,
  không thành banner hoặc đoạn giải thích lặp trên mỗi màn.

## 4. Theme và tài nguyên

[`Theme.qml`](../../ui/studio/theme/Theme.qml) là nguồn token dùng chung.
Duy trì sáng/tối, zoom, chữ tiếng Việt dài và cửa sổ nhỏ; trạng thái chọn,
lỗi, disabled, focus phải phân biệt được, không chỉ dựa vào màu.

Giữ font đóng gói, không tải font khi chạy. Animation phục vụ phản hồi trạng
thái, không trì hoãn nghiệp vụ hoặc làm dịch nội dung editor/terminal.
Không suy ra đạt Material 3 tuyệt đối chỉ vì bật Qt Material style.

Icon ứng dụng tại
[`cyberlab-studio.svg`](../../ui/studio/assets/branding/cyberlab-studio.svg)
dùng đầy đủ màu, tách khỏi icon điều khiển có tint. Wheel chứa bản QML và
bản `share/cyberlab/` cho desktop entry; đường dẫn icon không phụ thuộc phiên
bản Python. Shortcut cá nhân có thể che shortcut hệ thống, nên cần phân biệt
khi kiểm tra icon/launcher sau cập nhật.

## 5. Kiểm chứng thay đổi UI

1. Kiểm tra đăng ký `qmldir`, import, đường dẫn asset và package-data.
2. Chạy suite liên quan với fixture/offscreen, kiểm tra warning thực tế.
3. Chạy từ wheel mới để phát hiện thiếu resource hoặc tệp cũ trong build cache.
4. Nghiệm thu tương tác thật riêng; ảnh chụp không chứng minh animation mượt.

UI từ source vẫn có thể dùng daemon thật nếu chạy launcher phát triển bình
thường. Chỉ harness cách ly mới là thử không đụng dữ liệu thật. Hướng dẫn và
lệnh kiểm tra nằm ở [phát triển](../development/README.md).
