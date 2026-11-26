# Tham chiếu Result–Goal

Checkwork hiện dựa trên snapshot workspace có giới hạn. CyberLab tiếp nhận
một phần mô hình Result–Goal của Labtainer, không tự ghi lại mọi lần chạy
command, stdin/stdout hay log hệ thống.

## 1. Kiểm tra trực tiếp và thu thập

| Nhóm | Toán tử |
| --- | --- |
| Tồn tại / nội dung | `exists`, `contains`, `equals`, `line_contains`, `regex` |
| Kích thước / số lượng | `size_less_than`, `size_equals`, `line_count_equals`, `string_count_equals` |
| Hash | `sha256_equals`, `md5_equals` |
| Trường dữ liệu | `field_equals` |
| Thu thập | `collect`, `extract` tương thích bài cũ |

`collect` trích giá trị đơn trả `value` cùng trạng thái `COLLECTED`; expected
đặt ở Goal riêng. Hai field boolean `contains` và `file_regex` vẫn có kết
quả `PASS`/`FAIL`. `extract` không chấp nhận trường `expected`.

## 2. Chọn dòng và trường

Ví dụ kiểm tra trường thứ hai trên dòng bắt đầu bằng `VALUE`:

```yaml
operator: field_equals
field_type: token
field_id: 2
line_type: starts_with
line_id: VALUE
expected: "42"
```

- Kiểu trường: `token`, `parens`, `quotes`, `slash`, `group`.
- Trường thông thường đánh số từ 1, có thể dùng `ALL` hoặc `LAST` khi hỗ trợ.
  `ALL` trả dòng được chọn, không phải danh sách trường.
- Regex `group` đánh số từ 0 và cần `line_type: regex`.
- Chọn dòng: `line`, `starts_with`, `contains`, `regex`, `previous_starts_with`.
  Số dòng bắt đầu từ 1.
- `previous_starts_with` chọn dòng trước **kết quả đầu tiên**. Nếu kết quả
  đầu nằm ở dòng 1, không tìm kết quả sau để thay thế.
- Thiếu dòng/trường là `FAIL`; cấu hình/regex sai hoặc timeout là `ERROR`.

Quote extraction giữ cả chuỗi rỗng và dấu nháy đơn hợp lệ. Không dùng giá trị
trích ra để tự mở đường dẫn chưa được khai báo.

## 3. Các field của `collect`

Hỗ trợ `token`, `parens`, `quotes`, `slash`, `group`, `search`, `line_count`,
`checksum`, `size`, `time_delim`, `contains`, `file_regex`, `string_count`,
`command_count`, `param`; `none` lấy toàn bộ nội dung.

| Field đặc biệt | Ràng buộc |
| --- | --- |
| `checksum` | MD5 phục vụ tương thích bài, không phải cơ chế bảo mật |
| `search` | Chỉ tập định dạng `{}`, `{:d}`, `{:f}`, `{:w}`, `{:S}`, `{:s}`, `{:x}`; không nhận biểu thức Python tùy ý |
| `time_delim` | Đọc tên capture workspace đã khai báo như `program.stdout.YYYYMMDDhhmmss` |
| `param` | Đọc capture có `PROGRAM_ARGUMENTS (...)`, không tự ghi lệnh terminal |

`timestamp_type` gồm `file`, `log_ts`, `log_range` cho các field hỗ trợ.
Log phải có timestamp ISO-8601 kèm múi giờ. Timeline giới hạn 128 instance và
16 KiB; lưu/hiển thị được không đồng nghĩa đã hỗ trợ Goal thời gian.

## 4. Goal

| Loại | Khai báo và hành vi |
| --- | --- |
| `group` | Danh sách `results` không rỗng, kết hợp `all` hoặc `any` |
| `compare` | Một `result` so với **một trong** `expected` hoặc `other` |
| `count` | `count_greater` đếm Result đạt trong snapshot hiện tại |
| `boolean` | Biểu thức logic có giới hạn trên Result/Goal trước đó, không dùng `eval` |

Toán tử so sánh chuỗi: `string_equal`, `string_diff`, `string_contains`,
`string_start`, `string_end`. Số nguyên: `integer_equal`, `integer_greater`,
`integer_less`. `hash_equal` nhận MD5 32 ký tự hex hoặc SHA-256 64 ký tự hex.

Số nguyên là thập phân có dấu 64-bit, không phải số thực, boolean hoặc hex.
Giá trị mong đợi do tác giả nhập sai bị từ chối; bằng chứng người học không
phải số làm tiêu chí sai, không tự cắt phần thập phân.

```yaml
assessment:
  results:
    - id: answer
      node: client
      path: answer.txt
      operator: extract
      field_type: token
      field_id: 2
      line_type: starts_with
      line_id: port
  goals:
    - id: correct-port
      type: compare
      operator: integer_equal
      result: answer
      expected: "42"
```

Dependency của `compare` lấy từ toán hạng. Nếu còn danh sách `results` legacy,
nó phải khớp đúng dependency, không thêm `mode`/`threshold` không liên quan.
So sánh có thể dùng giá trị đã thu dù phép kiểm tra riêng của Result đó sai.

`count_greater` không coi lỗi là đạt: đủ số Result biết chắc đạt thì `PASS`;
kể cả tất cả kết quả chưa biết đạt vẫn không vượt ngưỡng thì `FAIL`; còn lại
là `ERROR`. Đây không phải đếm sự kiện có timestamp như Labtainer.
Boolean dùng logic ba giá trị để giữ trạng thái chưa xác định khi phù hợp.

## 5. Giới hạn và bảo vệ

- Chỉ đọc bằng chứng workspace đã khai báo; không chấp nhận symlink/tệp đặc biệt.
- Văn bản tối đa 64 KiB. Regex chạy worker riêng, không trong tiến trình daemon;
  giới hạn một giây mỗi phép và ngân sách báo cáo năm giây cho regex.
- Chọn dòng thường không khởi tạo worker regex. Worker trả JSON có giới hạn,
  không cắt chuỗi tùy ý thành JSON hỏng.
- UI xem trước giá trị tối đa 512 ký tự/bốn dòng; báo cáo giữ giá trị theo
  giới hạn dữ liệu, không lấy preview làm bằng chứng thay thế.
- Metadata công khai bỏ expected và selector riêng. Đây là tránh rò rỉ qua API,
  không đảm bảo bí mật trước quản trị viên máy hoặc người phân tích gói xuất.

Chưa có tương đương đầy đủ cho `matchany`, `matchlast`, `matchacross`,
`time_before`, `time_during`, đếm instance sự kiện và logic timeline. `execute`,
`pregrade.sh`, host log và hook đặc quyền tùy ý không thuộc chính sách chấm.

**Kiểm thử liên quan:** `tools/tests/unit/check_result_collection.py`,
`tools/tests/unit/check_assessment_quiz.py`, `tools/tests/unit/check_checkwork_regression.py` và các suite UI
được liệt kê trong [hướng dẫn phát triển](../development/README.md).
