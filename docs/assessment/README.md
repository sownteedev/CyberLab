# Quiz, Checkwork và nộp bài

CyberLab dùng Quiz để ôn kiến thức, Checkwork để tự kiểm tra thực hành.
Đây không phải hệ thống thi bảo mật hay chấm bằng server độc lập.

## 1. Phân biệt các khái niệm

| Thành phần | Vai trò | Ví dụ |
| --- | --- | --- |
| **Quiz** | Câu hỏi lý thuyết trước hoặc trong bài | Chọn ý nghĩa của gói ICMP |
| **Result** | Thu thập giá trị hoặc kiểm tra trực tiếp bằng chứng | Đọc một trường trong `answer.txt` |
| **Goal** | Đánh giá/tổng hợp các Result | Giá trị thu được bằng đáp án mong đợi |
| **Checkwork** | Chụp dữ liệu mới và chạy các tiêu chí khai báo | Báo đạt, sai, lỗi hoặc chỉ thu thập |
| **Artifact** | Tệp/bằng chứng tác giả yêu cầu trong bài nộp | Báo cáo hoặc PCAP của người học |
| **Report** | Kết quả một lần kiểm tra, có danh tính riêng | Dùng để xem lại hoặc xuất bằng chứng |

Không phải bài nào cũng cần Goal. Result kiểu kiểm tra trực tiếp có thể trả
`PASS`/`FAIL`. Result chỉ trích xuất trả `COLLECTED`; phải thêm tiêu chí so sánh
nếu muốn kết luận đúng/sai. Thu thập được tệp không đồng nghĩa hoàn thành bài.

## 2. Quiz

Tác giả có thể tạo nhóm câu hỏi, phần mở đầu, trắc nghiệm và đúng/sai. Nhóm
`pre_start` được trả lời trước khi bắt đầu; các nhóm khác không tự chặn thực
hành. Nhóm mới trong editor mặc định là chuẩn bị trước bài, nhưng mở bài cũ
không đổi cài đặt nhóm đã có.

Luồng người học:

1. Mở Quiz và trả lời câu hỏi áp dụng cho mình.
2. Gửi câu trả lời để lưu và xem đáp án/giải thích.
3. Chọn **Vào thực hành** sau khi phần chuẩn bị đã hoàn tất.

**Không yêu cầu trả lời đúng hết.** `completed` và `pre_start_completed` khác
`passed`. Câu chưa trả lời hoặc bị bỏ qua theo điều kiện không lộ đáp án chỉ
vì mở Quiz. Đóng/hủy cửa sổ không tự bắt đầu bài.

Quiz có tối đa 8 nhóm; câu có `prerequisite` chỉ tham chiếu câu trước đó trong
cùng nhóm. Nếu câu prerequisite đã đúng, câu phụ thuộc được bỏ qua theo thiết
kế ôn tập. Preface riêng lẻ không tạo điều kiện chặn Start.

### Lưu và gắn với phiên bản bài

Câu trả lời thuộc từng UID và digest chính xác của bài. Sửa asset/definition
có thể làm lần chuẩn bị cũ không còn phù hợp, kể cả giữ nguyên số phiên bản.
Khi Start, đáp án chuẩn bị được sao vào Session; chỉnh hoặc xóa đáp án ở thư
viện sau đó không sửa bản sao này. Resume dùng bản Session đã lưu, không đổi
thành Quiz của bài mới trong catalog.

```bash
cyberlab lab-quiz LAB_ID
cyberlab lab-quiz LAB_ID --digest REVIEWED_DIGEST --answer question-id=0
cyberlab quiz SESSION_ID --answer question-id=1
cyberlab quiz-result SESSION_ID
cyberlab delete-lab-quiz LAB_ID --yes
```

Chỉ số đáp án CLI/API bắt đầu từ 0. Digest lấy từ lần đọc, không tự đoán.
ID lạ, đáp án trùng/sai kiểu, option ngoài phạm vi hoặc digest cũ bị từ chối
mà không ghi đè lần trả lời hợp lệ trước đó. Engine kiểm tra cổng chuẩn bị,
không chỉ nút Start của UI.

## 3. Checkwork

```bash
cyberlab checkwork SESSION_ID
cyberlab reports SESSION_ID
cyberlab report REPORT_ID
```

Mỗi lần phải dùng bằng chứng của lần chụp hiện tại. Không dùng snapshot cũ để
chấm khi lần thu thập mới lỗi. File thiếu khác lỗi quyền, timeout hoặc lỗi
thu thập; báo cáo không được đổi các lỗi hệ thống thành một lần đạt.

| Trạng thái | Ý nghĩa |
| --- | --- |
| `PASS` | Điều kiện kiểm tra đạt |
| `FAIL` | Bằng chứng không đạt điều kiện hoặc thiếu bằng chứng cần thiết |
| `ERROR` | Thu thập/đánh giá không hoàn tất hợp lệ |
| `COLLECTED` | Có dữ liệu, nhưng chưa có kết luận đạt từ phép thu thập này |
| `NO_CRITERIA` | Không có tiêu chí chấm được áp dụng |

Result/Goal, kiểu dữ liệu, giới hạn regex và phần khác Labtainer nằm trong
[tham chiếu Result–Goal](results-goals.md). Bài không có tiêu chí không được
hiển thị như đã vượt qua một bài kiểm tra thực chất.

## 4. Xuất báo cáo và nộp rồi kết thúc

```bash
cyberlab export-submission REPORT_ID NEW_OUTPUT.zip
cyberlab submit SESSION_ID NEW_OUTPUT.zip
cyberlab review-submissions FILE.zip
```

Đây là **gói bằng chứng**, khác gói mẫu bài `.cyberlab`. Không chứa toàn bộ
image hệ thống, checkpoint hoặc mọi tệp ngoài artifact được khai báo.
Tên đích phải mới; không ghi đè tệp hoặc symlink đã có.

Luồng nộp và kết thúc gồm ba bước:

1. Daemon chụp workspace, cố định Quiz, tạo checkpoint và báo cáo. Thu thập
   lỗi hoặc thiếu artifact bắt buộc thì không dừng phiên hay thay checkpoint một phần.
2. CLI xuất đúng báo cáo đó ra tệp mới, hoàn tất ghi bền vững trước khi yêu cầu dừng.
3. Daemon kiểm tra lại owner, đời Session, báo cáo, Quiz và nội dung/quyền tệp;
   chỉ hoàn tất với ticket chuẩn bị vẫn còn hiệu lực.

Làm sai Goal không cấm nộp. Khi Checkwork bị tắt, vẫn có thể thu artifact theo
khai báo với báo cáo `NO_CRITERIA`, không lộ các tiêu chí nội bộ.

Nếu ghi tệp thất bại, không gửi yêu cầu dừng. Nếu dừng thất bại sau khi tệp đã
ghi, giữ checkpoint/tệp và dùng lệnh phục hồi được CLI in ra sau khi xác nhận
tệp thực sự đã lưu:

```bash
cyberlab finish-submission SESSION_ID REPORT_ID --yes
```

Ticket cũ không được dừng một đời Session mới. Daemon restart làm mất ticket
hoàn tất; cần tiếp tục bản lưu rồi chuẩn bị bài nộp mới. Báo cáo thường từ
Checkwork không tự trở thành ticket dừng phiên.

Không có giao dịch nguyên tử xuyên filesystem người dùng và mọi container.
Ngừng sửa tệp/chạy tiến trình ghi nền trước khi nộp; kiểm tra lần hai giúp
phát hiện thay đổi nhưng không chứng minh chưa có ghi sau lần đọc cuối cùng.

## 5. Thiết kế tiêu chí cho tác giả

- Chọn tệp/bằng chứng người học thật sự tạo, không dùng tệp seed có sẵn làm
  bằng chứng hoàn thành nếu chưa có biến đổi cần kiểm tra.
- Thử tối thiểu bốn trường hợp: chưa làm, làm sai, làm đúng và lỗi thu thập.
- Dùng Goal khi cần so sánh/tổng hợp; không thêm nhiều Result chỉ để nhiều dấu tick.
- Tách lỗi cấu hình tiêu chí khỏi lỗi người học; giải thích đủ để sửa nhưng
  không trả nguyên expected value qua metadata công khai.
- Xác minh trên runtime thật nếu tiêu chí phụ thuộc mạng, GUI, phần mềm hoặc
  quyền tệp. MemoryRuntime không chứng minh thao tác đó chạy được trong Docker.
