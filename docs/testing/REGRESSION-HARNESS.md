# Chạy bộ kiểm thử FlowDrop trên runner sạch

Giai đoạn 2B.1 chỉ sửa harness. Kết quả thực thi, lỗi còn lại, log và rollback nằm trong [báo cáo](HARNESS-REPORT-2B1.md). Không có workflow, dependency ứng dụng, giao thức hoặc mã production nào được sửa để chạy test.

## 1. Công cụ và dữ liệu thử

- Node 24 và `npm ci` theo nguyên `package-lock.json`; không dùng `npm update` hoặc cài dependency mới để làm test xanh.
- Java có module `jdk.compiler`: kiểm tra bằng `java -m jdk.compiler/com.sun.tools.javac.Main -version`. Lượt này dùng Java 21; không cần executable `javac` riêng. Giữ các cờ source/target 8 của harness cũ.
- Python 3 cho các fixture ZIP độc lập. `FLOWDROP_TEST_PYTHON` cho phép chỉ định executable; mặc định `python3`.
- JAR kiểm thử **org.json:json:20240303**, đúng bản đã dùng ở Giai đoạn 1. SHA-256: `3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed`.
- Quyền mở socket loopback; các bài discovery cần multicast/broadcast và một IPv4 LAN. JVM/stub không thay thế Windows UI, Android OS hoặc Wi-Fi của điện thoại thật.

JAR và class output ở ngoài Git. Harness không tự tải JAR, không dùng keystore hoặc dữ liệu Downloads của người dùng. Thiếu JAR hoặc sai checksum là lỗi preflight, không tự thay phiên bản.

Ví dụ chuẩn bị trên Linux từ root checkout:

```bash
export FLOWDROP_TEST_TOOLS="$(mktemp -d "${TMPDIR:-/tmp}/flowdrop-test-tools.XXXXXX")"
export FLOWDROP_TEST_JSON_JAR="$FLOWDROP_TEST_TOOLS/json-20240303.jar"
curl -fL https://repo.maven.apache.org/maven2/org/json/json/20240303/json-20240303.jar \
  -o "$FLOWDROP_TEST_JSON_JAR"
printf '%s  %s\n' \
  3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed \
  "$FLOWDROP_TEST_JSON_JAR" | sha256sum --check -
npm ci --ignore-scripts --no-audit --no-fund --cache "$FLOWDROP_TEST_TOOLS/npm-cache"
export FLOWDROP_TEST_TMPDIR="$FLOWDROP_TEST_TOOLS/tmp"
export FLOWDROP_TEST_REPORT_DIR="$FLOWDROP_TEST_TOOLS/reports"
mkdir -p "$FLOWDROP_TEST_TMPDIR" "$FLOWDROP_TEST_REPORT_DIR"
```

Giữ thư mục run cho đến khi đã lưu log/báo cáo cần thiết. Chỉ xóa thư mục công cụ/thử do chính run đó tạo; không dùng lệnh cleanup trên Downloads, dữ liệu ứng dụng, khóa hoặc checkout khác.

## 2. Biến môi trường của harness

| Biến | Hành vi |
| --- | --- |
| `FLOWDROP_TEST_JSON_JAR` | Đường dẫn JAR ưu tiên; được đối chiếu SHA-256 trước compile |
| `FLOWDROP_BUILD_TOOLS` | Giữ tương thích cấu hình cũ: nếu không có biến trên, đọc `<tools>/downloads/json-test.jar`; không dùng làm thư mục class/report chung nữa |
| Không đặt hai biến JAR | Tìm `<os.tmpdir()>/flowdrop-test-tools/downloads/json-test.jar`; báo thiếu có hướng dẫn nếu chưa provision |
| `FLOWDROP_TEST_TMPDIR` | Parent scratch do người chạy chọn; mặc định `os.tmpdir()`. Mỗi harness luôn tạo thư mục con ngẫu nhiên riêng |
| `FLOWDROP_TEST_REPORT_DIR` | Nơi giữ JSON/text report. Nếu không đặt, report ở scratch và bị dọn cùng run; console và assertion vẫn chạy đầy đủ |
| `FLOWDROP_TEST_JAVA` | Executable Java cho test; mặc định `java` |
| `FLOWDROP_TEST_PYTHON` | Executable Python cho fixture; mặc định `python3` |

Class Java và state/received nằm trong scratch của từng harness. Nguồn compile và working directory của process con tính từ URL của helper trong repository, không từ `process.cwd()`. Có thể gọi entrypoint bằng đường dẫn tuyệt đối từ CWD khác; `npm test` vẫn phải chạy ở root package hoặc dùng `npm --prefix`.

Khi chạy nhiều job song song, cấp report directory riêng cho từng job/test. Các bài discovery dùng cổng multicast chung và vẫn nên chạy tuần tự hoặc trên network namespace riêng; chuẩn hóa scratch không loại bỏ xung đột mạng.

## 3. Các lệnh kiểm tra

Nhóm không có file trên 4 GiB, chạy từ root repository:

```bash
npm test
node --test tests/harness.test.mjs
node tests/http-integration.mjs
node tests/discovery-integration.mjs
node tests/peer-integration.mjs
node tests/lan-discovery-integration.mjs
node tests/android-host-integration.mjs
node tests/android-discovery-state.mjs
node tests/security-integration.mjs
node tests/large-transfer-integration.mjs
```

`large-transfer` giữ nguyên 101 file/host, file **384 MiB + 17 byte**, đối chiếu SHA-256 hai chiều, lưu vào đĩa và ngân sách **300 MiB peak RSS/host**. Hiện phép đo RSS cần Linux `/proc`; thiếu phép đo phải fail rõ, không coi `null < budget` là đạt.

`harness.test.mjs` kiểm tra đường dẫn Java tách riêng (REG-001), đường dẫn có khoảng trắng, workspace độc lập, preflight lỗi, startup bị chia chunk, capability/địa chỉ sai, child lỗi/không thoát, giới hạn gửi token và report đã loại capability. HTTP trong unit này là fixture; kiểm tra từ chối ở production host nằm trong `large-transfer` và `security`.

Ba lệnh sau có ít nhất một ca trên 4 GiB. Chỉ chạy sau khi xác nhận tài nguyên và đặt wall timeout:

```bash
timeout --kill-after=5s 600s node --test tests/features-1.10.test.mjs
timeout --kill-after=5s 900s node --test tests/folder-receive.test.mjs
timeout --kill-after=5s 1500s node tests/android-native-client.mjs
```

Các timeout trên là công cụ GNU/Linux, không phải timeout mới trong giao thức. Trong đợt này runner xác nhận ít nhất **18 GiB đĩa trống**, giới hạn RAM ít nhất **2 GiB**, chạy tuần tự; thực tế lúc bắt đầu có khoảng 19,3 GiB trống, cgroup RAM 8 GiB và CPU quota 2 core. Mỗi lệnh được kiểm tra lại đĩa trước chạy. Không bỏ ca >4 GiB rồi báo cả file test đã đạt.

Giữ nguyên các assertion asset trong `http-integration` và `android-host-integration`: main sau nhập baseline thiếu font nhị phân nên hai lệnh hiện vẫn thất bại. Không xóa assertion, tự tải font hoặc sửa production trong nhiệm vụ harness này. Những lệnh sau trong danh sách vẫn phải chạy; không dùng một chuỗi `&&` khiến lỗi asset chặn các nhóm còn lại.

## 4. Capability và cleanup

- Windows native lấy token từ bản ghi `FLOWDROP_READY` trên pipe của process con; Android lấy `localToken` từ pipe JVM test host. Không bootstrap capability qua API HTTP không xác thực.
- Tạo session dùng đúng `X-Desktop-Token` hoặc `X-Local-Token`. PUT/complete/revoke vẫn dùng upload token theo giao thức cũ.
- Lượt REG-001 xác nhận thiếu token, token sai và token ở nhầm header đều bị 403; config không lộ token. Settings/receive native cũng phải từ chối thiếu/sai token trước nhánh có quyền.
- `localFetch` của harness chỉ gửi đến loopback của chính host đã nhận trên pipe, từ chối đường dẫn sang origin khác và không tự theo redirect. Đây là guard của test helper, không sửa client production.
- `peer-integration` chạy Node ở native mode và dùng pipe token cho thao tác desktop. `android-native-client` vẫn là fixture Java upload vào Node web host như trước; ranh giới Windows native được kiểm tra bằng REG-001 và security, không suy từ fixture web rằng đã kiểm thử Win32.
- Compile nằm trong vùng cleanup; thiếu JAR/compile lỗi/startup lỗi đều dọn scratch. Process được SIGTERM trước, có SIGKILL sau grace period và giới hạn chờ; không chờ vô hạn vào event `exit` của executable chưa spawn được hoặc process đã thoát.
- Với SIGKILL từ bên ngoài, code JavaScript không thể chạy `finally`; runner phải dọn process group và scratch của chính nó. Log timeout phải là fail/not completed, không PASS.

## 5. Phạm vi chưa được bao phủ

Windows C++ UI/shell và fixture `windows-peer-fixture.mjs` cần Windows/Wine cùng payload; Android instrumentation cần emulator/device và test APK. Không chạy hoặc sửa các fixture đó trong đợt này; đường dẫn workspace cũ ở fixture Windows vẫn được ghi nhận cho nhiệm vụ OS riêng. iOS ngoài phạm vi. Không có coverage OS/mixed-version mới chỉ vì các engine test chạy trên Linux.

Không thay publisher, không tạo workflow CI hoặc phát hành. Bước tiếp theo là review kết quả còn đỏ và chuẩn bị nhiệm vụ CI riêng; không biến suite hiện tại thành gate “tất cả xanh” bằng cách loại test.
