# CI kiểm thử Windows/Android qua Node và JVM

Workflow: [native-regression.yml](../../.github/workflows/native-regression.yml). Đây là CI kiểm thử engine/harness trên Linux; không build APK/EXE, ký, cài hoặc phát hành ứng dụng. Kết quả JVM/stub không chứng minh Windows UI, Android OS hoặc Wi-Fi trên thiết bị thật đã đạt.

## Kích hoạt và quyền

- Pull Request vào `main`: mở, cập nhật commit, mở lại, đổi sang ready, thêm/bỏ label. Draft PR cũng chạy. Không có trigger `push`, tag, Release hoặc `pull_request_target`.
- `workflow_dispatch`: mặc định không chạy nhóm trên 4 GiB; bật input boolean `run_zip64` khi cần. GitHub cần workflow có trên default branch trước khi cung cấp nút chạy thủ công.
- Chỉ `contents: read`; không có quyền ghi, publish, `id-token`, secrets hoặc keystore. Checkout không lưu credential. Composite setup không cấp quyền riêng.
- Concurrency theo PR/ref, tự hủy run cũ khi có run mới. Run bị hủy không phải PASS. Không có `continue-on-error`.
- Mọi Action bên ngoài được ghim bằng full commit SHA; nguồn release, commit và trạng thái chữ ký API nằm trong [CI-ACTION-PINS.json](CI-ACTION-PINS.json). Local composite cũng chỉ dùng Actions đã ghim. Không sửa workflow iOS/publisher hiện có hoặc PR #1.

## Runner sạch và dependency

Ubuntu **24.04**, Node **24**, Temurin Java **21** (có `jdk.compiler`), Python **3.12**; `bash`, `curl`, Git, `sha256sum`, socket loopback và multicast/broadcast IPv4. Workflow cài ba runtime bằng setup Actions; runner Python chỉ dùng thư viện chuẩn. Không cần Android SDK, Gradle, MinGW, Wine, emulator, NSIS, certificate hay key.

Setup tải đúng `org.json:json:20240303` từ Maven Central qua HTTPS, kiểm SHA-256 trước `npm ci` và trước chạy gate:

```text
https://repo.maven.apache.org/maven2/org/json/json/20240303/json-20240303.jar
3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed
```

Sai checksum dừng, không thay JAR hoặc bỏ kiểm tra. JAR/cache/class/test data ở vùng tạm, không đưa vào Git/artifact. `npm ci --ignore-scripts --no-audit --no-fund` dùng nguyên `package-lock.json`: `bonjour-service@1.3.0`, `yauzl@3.4.0` và sáu dependency gián tiếp đã khóa (`@leichtgewicht/ip-codec`, `dns-packet`, `fast-deep-equal`, `multicast-dns`, `pend`, `thunky`). Không nâng dependency hay sửa lockfile. Setup không chạy lifecycle script ứng dụng.

## Gate và phạm vi thực sự chạy

Các lệnh từ root repository, không lọc tên test, không bỏ case, không giảm assertion/kích thước. **13 lệnh cũ** cộng hai guard mới (runner unit và integrity tài nguyên).

| Gate | Lệnh | Timeout mỗi lệnh |
| --- | --- | ---: |
| Fast | `python3 -m unittest discover -s tests/ci -p 'test_*.py' -v` | 90s |
| Fast | `sha256sum --check docs/assets/FONT-RESTORATION-SHA256SUMS.txt` | 30s |
| Fast | `npm test` | 90s |
| Fast | `node --test tests/harness.test.mjs` | 90s |
| Integration | `node tests/http-integration.mjs` | 120s |
| Integration | `node tests/android-host-integration.mjs` | 120s |
| Integration | `node tests/discovery-integration.mjs` | 120s |
| Integration | `node tests/peer-integration.mjs` | 240s |
| Integration | `node tests/lan-discovery-integration.mjs` | 240s |
| Integration | `node tests/android-discovery-state.mjs` | 120s |
| Integration | `node tests/security-integration.mjs` | 120s |
| Stream | `node tests/large-transfer-integration.mjs` | 300s |
| ZIP64 | `node --test tests/features-1.10.test.mjs` | 600s |
| ZIP64 | `node --test tests/folder-receive.test.mjs` | 900s |
| ZIP64 | `node tests/android-native-client.mjs` | 1500s |

Fast chạy trước; ba job test còn lại chạy sau Fast trên các VM riêng. Bảy lệnh Integration chạy **tuần tự**, cùng một runner; discovery dùng cổng chung không chạy song song trong namespace đó. ZIP64 cũng chạy ba lệnh tuần tự. Coverage chờ mọi job và báo kết luận thực tế, không thay thế exit của test.

| Gate | Job timeout | Run step timeout | Preflight mỗi lệnh |
| --- | ---: | ---: | --- |
| Fast | 10 phút | 5 phút | Linux, RAM limit >=2 GiB, đĩa trống >=0,5 GiB |
| Integration | 25 phút | 20 phút | Như Fast, cần loopback/multicast/broadcast |
| Stream | 15 phút | 8 phút | Linux `/proc`, RAM >=2 GiB, đĩa >=2 GiB |
| ZIP64 | 65 phút | 55 phút | Linux, RAM >=2 GiB, đĩa >=18 GiB |
| Coverage | 5 phút | Không chạy test | Báo needs results và gate được yêu cầu |

Stream giữ nguyên **101 file**, **384 MiB + 17 byte**, SHA-256 hai chiều, lưu đĩa, giới hạn peak RSS **300 MiB/host**. ZIP64 giữ nguyên mọi ca **trên 4 GiB** trong cả ba file; không chỉ chọn ca nhỏ trong file rồi báo PASS.

Mọi PR tự chạy Fast, Integration, Stream. ZIP64 chỉ chạy khi có label **`ci-zip64`** hoặc manual input `run_zip64=true`. Người có quyền sửa label có thể bật trên Draft PR, không cần sửa source. Bỏ label để ngừng yêu cầu gate nặng ở các run sau. Nếu không bật, job ZIP64 là `skipped` và Coverage ghi **NOT VERIFIED**, không tuyên bố cả suite đã chạy. Khi đã yêu cầu mà ZIP64 thất bại/không chạy, Coverage thất bại. Thiếu tài nguyên trả exit **78**, ghi NOT VERIFIED và không chạy/giảm size test; cần cấp runner đủ tài nguyên trong nhiệm vụ riêng.

## Chạy cùng bộ điều phối ở máy Linux

Chuẩn bị công cụ kể trên, đứng ở root checkout. Dùng parent tạm riêng; ví dụ một gate:

```bash
FLOWDROP_CI_PARENT=$(mktemp -d /tmp/flowdrop-native-ci.XXXXXX)
python3 tests/ci/run.py setup --work-root "$FLOWDROP_CI_PARENT/integration"
python3 tests/ci/run.py integration --work-root "$FLOWDROP_CI_PARENT/integration"
python3 tests/ci/run.py cleanup --work-root "$FLOWDROP_CI_PARENT/integration"
```

Ghi lại exit của từng lệnh ngay khi chạy; không dùng exit của cleanup thay exit test. Có thể thay `integration` bằng `fast`, `stream`, `zip64`; mỗi gate dùng work root riêng. Chỉ chạy `zip64` sau kiểm tra tài nguyên/timeout. Vùng cũ có dữ liệu chưa thuộc CI bị từ chối; chọn vùng mới, không xóa dữ liệu người dùng để chạy lại.

## Exit code, log và cleanup

- Bộ điều phối tạo trạng thái NOT VERIFIED trước chạy; chỉ có child đã thực sự chạy và exit 0 mới PASS. Lỗi thường vẫn chạy tiếp các lệnh trong gate để ghi đủ kết quả; trả exit lỗi đầu tiên, không exit thành công của script thu log. `raw_returncode` và exit quy đổi đều có trong JSON; signal thành 128+signal, timeout thành **124**, không khởi động được executable thành **127**/NOT VERIFIED. Job/step timeout ngoài cùng của GitHub cũng là lỗi/cancel, không PASS.
- Mỗi lệnh có process group riêng; timeout TERM rồi KILL sau grace 2s. Sau lệnh kết thúc cũng dọn descendant còn lại. Scratch/class/received/report con được dọn sau từng test; bước `always()` dọn scratch/tools của gate. Chỉ dọn work root có marker sở hữu, từ chối symlink và giữ log. Với runner bị hủy/tắt cứng, không bảo đảm bước cuối chạy; GitHub-hosted VM là vùng tạm riêng.
- Chỉ ghi output test/setup vào file sau khi loại giá trị env nhạy cảm (TOKEN/SECRET/PASSWORD/CREDENTIAL/AUTH), trường token/capability JSON, header token, UUID runtime và mẫu GitHub token. Không dump env, không log raw startup pipe. Self-test dùng dữ liệu giả xác nhận việc loại token trước ghi log. Đây không phải cam kết sanitizer nhận ra mọi định dạng bí mật tương lai; không thêm logging credential mới.
- Artifact `FlowDrop-Native-{fast,integration,stream,zip64}-<run_id>-<attempt>` lưu **7 ngày**, có ở cả thành công/thất bại khi job bắt đầu được và upload chạy. Chỉ upload `logs/`: sanitized `.log`, `setup.json`, `results.json` hoặc `not-verified.json` nếu runner chưa tạo kết quả. Không upload tools/JAR/cache/receive/test data/keys. Jobs bị skip không có artifact; upload lỗi vẫn làm job lỗi, không bỏ qua.
- `results.json` ghi từng command, thực thi hay chưa, exit, timeout, thời gian và snapshot đĩa/RAM. `setup.json` và log version giúp phân biệt lỗi provision với lỗi test. Artifact hết hạn thì log không còn; giữ bằng chứng đã loại bí mật bên ngoài nếu cần lưu lâu hơn.

Trong Actions → run của **Native regression**, xem từng job và Step summary trước. Tải artifact tương ứng để đọc log, không dùng một ô xanh tổng hợp làm bằng chứng cho nhóm bị skip. DNS/TLS/JAR lỗi: kiểm URL/hash/toolchain, không tắt TLS/checksum. Multicast/timeout: đọc log và thử tái hiện cùng lệnh, không skip discovery. Disk/RAM lỗi: giữ NOT VERIFIED, cấp tài nguyên đúng mức. Assertion production lỗi: báo lỗi và đề xuất PR riêng, không sửa production để ép CI đạt.

## Coverage và rollback

Chưa có kiểm thử Windows C++/Explorer/Send to/UI/update installer, Android instrumentation/MediaStore/share UI/background hoặc mixed-version binary trên thiết bị thật. `windows-peer-fixture.mjs` là fixture OS riêng, không phải entrypoint độc lập trong 13 lệnh Node/JVM; thiếu Wine/payload nên chưa xác minh. iOS tạm dừng. Icon/signing/build inputs còn thiếu theo [báo cáo 2B.2](ASSET-REPORT-2B2.md) vẫn nằm ngoài nhiệm vụ này. Không coi CI engine xanh là release-ready.

Rollback bằng PR revert commit CI, review rồi merge thủ công. Tệp CI/test mới và tài liệu có thể gỡ độc lập; không cần cài/gỡ ứng dụng, đổi key, xóa file nhận hoặc sửa protocol. Chủ dự án quyết định riêng việc đưa check vào branch ruleset; PR này không đổi Settings, PR #1 hoặc publisher.
