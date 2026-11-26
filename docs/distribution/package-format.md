# Định dạng gói `.cyberlab`

Tài liệu dành cho phát triển codec. Quy trình người dùng và giới hạn bảo vệ
nằm ở [chia sẻ bài](README.md).

## 1. Phiên bản

Xuất mới dùng `cyberlab-lab/v3`; nhập vẫn nhận v1/v2 ZIP cũ. V3 là container
nhị phân riêng, không lồng ZIP/TAR, không dùng pickle và không chạy script
trong lúc giải mã. Tái xuất gói cũ tạo v3, không làm gói cũ tự có bảo vệ mới.

`create_package(definition, assets, lab, edit_protection=None)` và
`read_package(data)` giữ hợp đồng; reader trả `(definition, assets, manifest)`.
`PROTECTED_FORMAT` là định danh v2 legacy, không có nghĩa mọi gói được khóa
đều phải là v2. Khả năng nhập/xuất được công bố qua API capability.

## 2. Header và payload v3

Header dài 49 byte, số nguyên unsigned big-endian, định dạng
`struct.Struct(">8sBII32s")`:

| Offset | Số byte | Nội dung |
| --- | ---: | --- |
| 0 | 8 | Magic `CYBLAB\r\n` (`43 59 42 4c 41 42 0d 0a`) |
| 8 | 1 | Version `3` |
| 9 | 4 | Độ dài payload nén chính xác |
| 13 | 4 | Độ dài JSON giải nén chính xác |
| 17 | 32 | SHA-256 của payload nén |
| 49 | Theo khai báo | Một stream raw DEFLATE, không header zlib/gzip |

Không chấp nhận prefix, trailer, padding hoặc stream nối thêm. Envelope có
đúng ba khóa; ví dụ rút gọn definition/manifest:

```json
{"assets":{"assets/empty":null,"assets/readme.txt":"aGkK"},"definition":"...","manifest":{}}
```

- Thư mục là `null`, tệp rỗng là `""`, tệp khác dùng base64 chuẩn có padding.
- Asset chỉ trong `assets/`; thư mục gốc `assets` nếu có là `null`.
- JSON canonical: khóa sắp xếp, `ensure_ascii=True`, separator `,`/`:`, không
  số không hữu hạn. Từ chối khóa trùng ở mọi cấp và hình dạng/khóa thừa.
- Base64 không whitespace, padding và bit padding phải canonical.
- Manifest giữ format, danh tính Lab, image, kích thước/hash asset và digest
  nội dung. `lab.yaml` là tên logic, không phải thành viên ZIP trong v3.

## 3. Giới hạn kiểm tra độc lập

| Dữ liệu | Giới hạn |
| --- | ---: |
| Definition | 64 KiB |
| Một asset | 1 MiB |
| Tổng definition + asset giải mã | 2 MiB |
| Đường dẫn, gồm thư mục cha ngầm định | 128 |
| Manifest | 64 KiB |
| Toàn container | 4 MiB |

Envelope có trần riêng cho overhead base64/JSON; không làm tăng giới hạn nội
dung giải mã. Codec kiểm tra length/checksum trước inflation, chặn vượt trần
trong quá trình giải nén, yêu cầu kết thúc đúng stream/độ dài và không có input
thừa; sau đó mới kiểm tra path, asset, schema và manifest digest.

V1/v2 giữ giới hạn nội dung/đường dẫn, từ chối thành viên trùng, link/tệp đặc
biệt, mã hóa ZIP, kiểu nén không hỗ trợ, dữ liệu đầu/cuối thừa và digest sai.
Labtainer có giới hạn đầu vào riêng (32 MiB, 512 entry); kết quả chuyển đổi
vẫn phải đáp ứng giới hạn CyberLab chặt hơn, không nhận đặc quyền từ archive.

## 4. Bảo vệ chỉnh sửa và tính toàn vẹn

`manifest.edit_protection` chỉ chứa verifier version 1, thuật toán cố định
`scrypt-131072-8-1`, salt 16 byte và hash 32 byte dạng hex thường. Không nhận
tham số KDF tùy ý hoặc plaintext. V1 không mang verifier, v2 bắt buộc có,
v3 cho phép có hoặc không.

Checksum phát hiện hỏng dữ liệu, **không phải chữ ký chống sửa/giả mạo**.
Base64, nén và magic không cung cấp tính bí mật. Decoder không là ranh giới
phân quyền; daemon tiếp tục xác thực chính sách và ownership khi nhập.

## 5. Kiểm thử codec

`tools/tests/unit/check_exchange_v3.py` kiểm tra round-trip, binary/thư mục rỗng, verifier,
gói legacy, JSON/base64 sai, traversal, truncation, dữ liệu thừa và bomb nén.
Dùng fixture tạm; không lấy catalog thật để tạo gói thử hỏng.
Gói nộp bằng chứng `.zip` là loại dữ liệu khác, không áp wire format này.
