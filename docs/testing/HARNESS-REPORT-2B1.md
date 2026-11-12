# FlowDrop — báo cáo sửa harness, Giai đoạn 2B.1

Ngày báo cáo: **12/11/2026, Asia/Saigon**. Repository `Melbournejr/FlowDrop_IOS`. Nhánh `test/fix-regression-harness`, base [`c04affa26441440434d821fe9ff3c6fb4ddf2a07`](https://github.com/Melbournejr/FlowDrop_IOS/commit/c04affa26441440434d821fe9ff3c6fb4ddf2a07).

## 1. Kết luận và điều kiện bắt đầu

**[API] PR #4 đã merge** vào main, merge commit `c04affa26441440434d821fe9ff3c6fb4ddf2a07`. Đã clone main mới nhất tại thời điểm bắt đầu, kiểm tra remote SHA trùng trước khi tạo nhánh mới, đọc `AGENTS.md`, `docs/REGRESSION-PLAN.md` và `docs/baselines/native-1.13.0/IMPORT-REPORT.md`. Không ghi đè nhánh có sẵn, không sửa PR #1.

**[TEST] REG-001: exit 1 trước → exit 0 sau.** Cả 101 file/host và luồng 384 MiB + 17 byte hai chiều đã chạy, đúng SHA-256, lưu đĩa và đúng ngân sách RSS. Các yêu cầu không có quyền vẫn bị từ chối. Có 16/16 test mới cho helper đạt.

**[TEST] Toàn bộ 12 lệnh unit/integration hiện có mà Linux/JVM hỗ trợ đã chạy trước và sau:** trước 9 đạt / 3 lỗi; sau 10 đạt / 2 lỗi. **Không phải toàn bộ suite xanh.** Hai lỗi HTTP/Android-host do font bị loại từ baseline 2A vẫn giữ nguyên. Không xóa/bỏ qua test, giảm kích thước, nới assertion hoặc sửa production để làm xanh.

## 2. Lỗi trước khi sửa và cách tái hiện

### REG-001 — compiler nhận một đường dẫn ghép sai

- Nguồn gốc: `tests/large-transfer-integration.mjs:12` tại base commit trên; Node 24, Java có module compiler, JAR org.json đã pin. Chạy `node tests/large-transfer-integration.mjs` từ root checkout, cấu hình JAR như [hướng dẫn](REGRESSION-HARNESS.md).
- Mong đợi: `RequestSecurity.java`, `TransferServer.java`, `CodeLookup.java` và `HostHarness.java` là bốn argument source riêng.
- Thực tế: hai source đầu bị đưa vào một `path.join`, compiler báo `RequestSecurity.java/android/src/.../TransferServer.java` không tồn tại; compiler exit 2, script exit 1. Chưa tới bước truyền file.
- Script tạo scratch trước compile, chưa vào `try/finally`, nên còn `flowdrop-large-*` sau lỗi. Runner chỉ dọn scratch thuộc run của chính nó sau khi đã ghi bằng chứng. Xem [log trước](harness-2b1-logs/before/large-transfer.log) và `temporary_entries_after_test` trong results.

### Capability cũ không còn đúng với native mode

**[SRC]** Sau khi qua compile, bản cũ tạo session không gửi local capability và đọc desktop settings chưa xác thực. Với protocol 1.13 hiện có, Node native cần `X-Desktop-Token` từ `FLOWDROP_READY`, JVM Android cần `X-Local-Token` từ pipe local. Các guard production giữ nguyên; test được cập nhật cách lấy và truyền token, không bật đường tạo session không xác thực.

### Runner phụ thuộc CWD/path tuyệt đối và cleanup trước preflight

**[TEST]** Bản gốc của `android-discovery-state.mjs`, lấy nguyên byte bằng `git show` từ base, chạy ở CWD khác thất bại exit 1 (`tests/nsd-stubs` không tồn tại tại CWD). Bản sửa cùng bài test đạt exit 0 khi JAR/scratch có khoảng trắng, cả cấu hình explicit JAR và override build-tools cũ. [Log đối chiếu](harness-2b1-logs/portability/results.json). Nguồn production và assertion discovery không đổi.

## 3. File và hành vi harness thay đổi

Mười file test hiện có được sửa setup/path/capability/report/cleanup; thêm helper và unit tests:

- `tests/android-discovery-state.mjs`
- `tests/android-host-integration.mjs`
- `tests/android-native-client.mjs`
- `tests/features-1.10.test.mjs`
- `tests/folder-receive.test.mjs`
- `tests/http-integration.mjs`
- `tests/lan-discovery-integration.mjs`
- `tests/large-transfer-integration.mjs`
- `tests/peer-integration.mjs`
- `tests/security-integration.mjs`
- `tests/helpers/harness.mjs`
- `tests/harness.test.mjs`

- `tests/helpers/harness.mjs`: đường dẫn repository từ URL module, pin JAR cũ, tách argument Java, unique scratch/classes, compile timeout, private startup record theo dòng/UTF-8, helper local request không theo redirect, child shutdown có giới hạn và report directory tùy chọn. Không tự tải tool hoặc chạy installer.
- `large-transfer`: lấy đúng hai loại local token từ pipe; không lấy capability bằng GET HTTP không xác thực. Thêm các nhánh 403 cho token thiếu/sai/sai header; config không lộ token; settings/receive native bị chặn khi không có quyền. Vẫn dùng upload token cho PUT/complete/revoke.
- `peer-integration`: Node chạy native mode và lấy pipe token; nguyên các ca offer/consent/progress/code/Android ↔ Android/failed receive/goodbye.
- Các harness JVM/HTTP/folder dùng cùng setup và cleanup kể cả compile/startup lỗi. JSON report có thể giữ ngoài scratch bằng `FLOWDROP_TEST_REPORT_DIR`; không ghi report/class vào một path `/workspace` chung. Không thay file Java production hay Java fixture.
- `tests/harness.test.mjs`: 16 ca, gồm missing/wrong JAR, path regression, fragmented startup, missing/wrong credential, executable lỗi, child không chịu thoát, redirect không lộ capability và cleanup/report. HTTP unit là fixture; các nhánh 403 production được chạy ở REG-001/security.

Tài liệu mới: `docs/testing/REGRESSION-HARNESS.md`, báo cáo này và tập text log/JSON `docs/testing/harness-2b1-logs/`. Không sửa tài liệu baseline hoặc manifest import để che sự khác biệt test đã được duyệt ở giai đoạn này.

## 4. Môi trường và cách thu bằng chứng

- Linux, Node `v24.19.0`, Java `openjdk version "21.0.12.1" 2026-08-18`, Python 3.12.14. Không phải Windows runtime đóng gói 24.22.2.
- JAR org.json:json:20240303, SHA-256 `3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed`; tái dùng bản cache đã kiểm hash. Không thêm JAR vào Git, không cập nhật dependency. `npm ci` đúng lock, 8 package; cache mặc định read-only nên dùng cache riêng dưới workspace.
- Có khoảng 19,3 GiB đĩa trống; cgroup RAM 8 GiB, CPU quota 2 core. Chỉ chạy tuần tự các ca >4 GiB sau preflight còn ít nhất 18 GiB trống và RAM >=2 GiB. Timeout mỗi lệnh lưu trong results (600s features, 900s folder, 1500s native client); không có timeout ở hai lượt tổng.
- Lượt trước: 12/11/2026 11:35:39 +0700 → 12/11/2026 11:38:24 +0700. Lượt sau: 12/11/2026 13:57:22 +0700 → 12/11/2026 14:01:08 +0700.
- Mỗi lệnh thu stdout/stderr, exit code, thời lượng, timeout và scratch còn lại; chạy tiếp sau lỗi để phủ đủ danh sách. Runner điều phối cục bộ exit 0 chỉ là hoàn tất thu log, **không** có nghĩa các lệnh con đều đạt; [comparison.json](harness-2b1-logs/comparison.json) ghi `overall_all_green: false`.
- Log text đã loại giá trị capability/UUID runtime; không chứa keystore, private key hoặc environment dump. Log output được giữ; không lưu `.class`, JAR, file thử >4 GiB, installer hoặc report chứa token.

## 5. Kết quả trước/sau — exit code thực tế

| Lệnh | Trước: exit / thời gian | Sau: exit / thời gian | Log |
| --- | --- | --- | --- |
| `npm test` | 0 / 0.615s | 0 / 0.708s | [trước](harness-2b1-logs/before/unit.log) · [sau](harness-2b1-logs/after/unit.log) |
| `node tests/http-integration.mjs` | 1 / 0.351s | 1 / 0.358s | [trước](harness-2b1-logs/before/http.log) · [sau](harness-2b1-logs/after/http.log) |
| `node tests/discovery-integration.mjs` | 0 / 2.786s | 0 / 2.796s | [trước](harness-2b1-logs/before/discovery.log) · [sau](harness-2b1-logs/after/discovery.log) |
| `node tests/peer-integration.mjs` | 0 / 11.704s | 0 / 12.237s | [trước](harness-2b1-logs/before/peer.log) · [sau](harness-2b1-logs/after/peer.log) |
| `node tests/lan-discovery-integration.mjs` | 0 / 17.044s | 0 / 15.027s | [trước](harness-2b1-logs/before/lan-discovery.log) · [sau](harness-2b1-logs/after/lan-discovery.log) |
| `node tests/android-host-integration.mjs` | 1 / 2.501s | 1 / 2.744s | [trước](harness-2b1-logs/before/android-host.log) · [sau](harness-2b1-logs/after/android-host.log) |
| `node tests/android-discovery-state.mjs` | 0 / 1.948s | 0 / 1.783s | [trước](harness-2b1-logs/before/android-discovery.log) · [sau](harness-2b1-logs/after/android-discovery.log) |
| `node tests/security-integration.mjs` | 0 / 12.38s | 0 / 12.211s | [trước](harness-2b1-logs/before/security.log) · [sau](harness-2b1-logs/after/security.log) |
| `node tests/large-transfer-integration.mjs` | 1 / 0.264s | 0 / 19.767s | [trước](harness-2b1-logs/before/large-transfer.log) · [sau](harness-2b1-logs/after/large-transfer.log) |
| `node --test tests/features-1.10.test.mjs` | 0 / 46.186s | 0 / 54.522s | [trước](harness-2b1-logs/before/features.log) · [sau](harness-2b1-logs/after/features.log) |
| `node --test tests/folder-receive.test.mjs` | 0 / 49.3s | 0 / 78.432s | [trước](harness-2b1-logs/before/folders.log) · [sau](harness-2b1-logs/after/folders.log) |
| `node tests/android-native-client.mjs` | 0 / 20.251s | 0 / 24.905s | [trước](harness-2b1-logs/before/native-client.log) · [sau](harness-2b1-logs/after/native-client.log) |

Test mới: `node --test tests/harness.test.mjs` — exit **0**, **16/16 đạt**, 0 skipped, 0.559s. [Log](harness-2b1-logs/after/harness-unit.log).

Unit ban đầu `npm test`: 10/10 cả hai lượt; `features`: 4/4 cả hai lượt; `folder-receive`: 5/5 cả hai lượt, **đã gồm ca >4 GiB**. Không có suite trước đó đạt chuyển thành lỗi trong lượt tổng sau. Thời gian chênh lệch không được coi là benchmark hiệu năng; không đặt mục tiêu nhanh hơn để làm giảm kiểm thử.

REG-001 sau sửa: **402653201 byte**, SHA-256 `4bdcb708f8ca8ffe5e86325e3621e6cc501da14e3285ec680fb417c8bae95a0f`, peak RSS Node **141332480** byte, Java **122003456** byte, đều dưới 300 MiB. Không cho phép thiếu phép đo RSS tự được tính là đạt; hiện yêu cầu Linux `/proc`. [Report trong console](harness-2b1-logs/after/large-transfer.log).

`native-client` giữ ca 101 file, Node 384 MiB + 17 byte và JVM Android `2^32 + 131089` byte, kiểm SHA-256/64-bit progress/cancel/revoke/source changed. Fixture Node này vẫn là web host như trước; boundary native Windows có các test khác, không dùng fixture web để khẳng định Win32 đã thử.

### Các lượt phụ và lỗi môi trường/observer

- Focused REG-001 trước lượt tổng sau: exit 0; [stdout](harness-2b1-logs/auxiliary/reg001.stdout.log), [stderr](harness-2b1-logs/auxiliary/reg001.stderr.log).
- Một lượt unit mới chạy trong sandbox mặc định bị timeout 90s; probe riêng báo loopback `EPERM`. Wrapper Python exit 1, không có completed Node exit/log; các process thử thuộc task được dừng. Không tính lượt này là PASS. Chạy có quyền mạng sau đó đạt 15/15 ở phiên helper sớm; bản cuối thêm redirect và đạt 16/16 trong lượt tổng sau. [Log sớm](harness-2b1-logs/auxiliary/harness-unit-network.log), [ghi chú setup](harness-2b1-logs/auxiliary/setup-notes.json).
- Diagnostic đầu exit 1 vì observer giả định Node sẽ in stderr ENOENT. Đọc lại source cho thấy nhánh headers-already-sent chỉ đóng socket. Diagnostic sửa **chỉ observer ngoài repository**, exit 0: file font ENOENT, CSS 200, font response không hoàn thành/`UND_ERR_SOCKET`, config vẫn 200. Giữ [log lỗi observer](harness-2b1-logs/auxiliary/missing-font-attempt1.log) và [log đối chiếu](harness-2b1-logs/auxiliary/missing-font-attempt2.log); không sửa app.

## 6. Hai lỗi còn đỏ và những bài chưa thể chạy

1. **HTTP Node — vẫn exit 1:** request font không hoàn tất, `UND_ERR_SOCKET`. Font `BeVietnamPro-Regular.ttf` không có trên cây baseline, được loại rõ trong Giai đoạn 2A. Đã xác nhận bằng diagnostic đọc file và request riêng; không thay font hoặc xử lý lỗi production.
2. **Android host JVM — vẫn exit 1:** assertion font `/assets/fonts/BeVietnamPro-Regular.ttf`, actual 500/expected 200. Giữ assertion. Những kiểm tra nằm sau assertion này trong riêng file đó chưa được chạy tới; không báo toàn bộ Android-host integration đạt.
3. Windows C++ UI/shell + fixture peer: không có Windows/Wine/MinGW hoặc payload ứng dụng. Không build/cài hoặc sửa fixture Windows trong nhiệm vụ này; `windows-peer-fixture.mjs` vẫn còn path workspace cũ cần nhiệm vụ OS riêng.
4. Android OS/instrumentation/Gallery/MediaStore/foreground: không adb/emulator/device và không build/ký/cài APK. Engine JVM/stub đã chạy không thay cho OS.
5. Physical Wi-Fi, ma trận binary 1.12/1.13, install/update/downgrade OS chưa chạy; iOS không chạy vì ngoài phạm vi.

Đề xuất **PR riêng** cho chính sách resource/asset hash-pinned và lỗi request khi thiếu asset, nếu chủ dự án duyệt; không giải quyết binary hoặc signing trong PR harness. Đây là lỗi/giới hạn baseline đã có trước, không phải bằng chứng APK/EXE đã phát hành bị hỏng.

## 7. Bảo vệ source và rủi ro còn lại

**[CHECK]** [source-integrity.json](harness-2b1-logs/source-integrity.json) ghi base và SHA-256 của 12 file harness ứng viên. 152 file main được đối chiếu: chỉ 10 file test cũ đổi, 142 file khác giữ nguyên byte; gồm toàn bộ production Windows/Android/Node, iOS, `.github`, signing identities, package/lock, AGENTS và tài liệu import. Thân test features/folder giữ nguyên sau khi chỉ đổi tên executable Python; core assertion của HTTP/Android-host/security/peer/LAN được đối chiếu nguyên byte ngoài bootstrap/report/cleanup. `git diff --check` exit 0.

Không xóa test, không `.skip`, không giảm số file/kích thước hoặc ngưỡng RSS. Các fixture ký RSA vẫn là key thử sinh trong RAM như trước, không đổi APK identity/cert/key/pin. PR #1 không bị sửa, không thêm CI/workflow, không chạy publisher, không build/ký/cài app hoặc tạo Release.

Rủi ro còn lại: suite chưa xanh do hai lỗi asset; Linux engine chưa chứng minh OS/mixed-version; discovery còn dùng network/cổng multicast chung và không thích hợp chạy đồng thời trên cùng namespace; SIGKILL ngoài process không thể chạy finally và runner vẫn cần cleanup process group; RSS hiện phụ thuộc Linux; các prerequisite Node/JAR/Python vẫn phải provision ngoài repo. Thời lượng ZIP64 có dao động, chưa có benchmark hoặc release gate.

## 8. Rollback và bước tiếp theo

PR để Draft, không merge. Mọi thay đổi test/helper/docs/log được đặt trong một commit độc lập; trước khi merge có thể đóng PR mà main/ứng dụng không đổi. Nếu đã merge sau review, tạo PR revert commit sửa harness (hoặc merge commit tương ứng), chạy lại nhóm test phù hợp và giữ log. Không uninstall/downgrade ứng dụng, xóa dữ liệu nhận hoặc đụng key/Release/tag để rollback một thay đổi test.

Chủ dự án cần quyết định cách xử lý hai lỗi asset trong nhiệm vụ riêng, kế hoạch runner OS/mixed-version và CI gate sau khi trạng thái đỏ được giải thích/xử lý đúng. Không tự xử lý PR #1 hoặc chuyển publisher sang tự động phát hành. Không gọi PR này là đã hoàn tất regression trên Windows/Android thật.
