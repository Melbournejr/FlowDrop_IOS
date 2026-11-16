# FlowDrop 2D.2 — cross-platform verification

Ngày 16/11/2026 (Asia/Saigon). App baseline 1.13.0. **2D.2-B và toàn bộ Phase2D.2 chưa được nghiệm thu:** chưa có native Windows↔Android hai thiết bị hoặc LAN vật lý. Đây là PR công cụ/test/tài liệu 2D.2-A, tách ba lớp bằng chứng.

## Baseline và kiểm soát

- PR #10 đã merge đúng `f9b5a43c5eae93b169717a72d19f5a426d913094`; checkout main mới nhất trước tạo nhánh `test/cross-platform-e2e-2d2`. Không push main.
- AGENTS root và audit/architecture/features/protocol/release/regression/build2C.2/runtime2D.1, các artifact manifest, workflow và source test đã được đối chiếu. Không có AGENTS con. Báo cáo cũ giữ nguyên là lịch sử, không suy thành kết quả mới.
- `protectMain` ruleset27172303 Active, áp dụng main/~DEFAULT_BRANCH, strict required Coverage / explicit verification status. Chỉ đọc; không sửa/bypass. PR#1 còn mở head2ccf9248ed6de184a200a950e1d37dd1e5b11741; không sửa và workflow mới không trùng đường dẫn.
- Bảo toàn **790/790 file baseline** bằng SHA-256 và Git blob đối chiếu trực tiếp base commit; không chỉ tin manifest do PR mới tạo. App Windows/Android/Node/shared, protocol/API/UI/assets, version/package, signing/update pins, dependencies/lock, iOS, bốn workflow cũ và mọi test cũ giữ nguyên byte.
- Mọi thay đổi là bổ sung harness, workflow opt-in, portable owner toolkit và tài liệu/evidence. Không build/publish phiên bản mới; các build TEST ONLY do workflow cũ chạy lại theo nhiệm vụ, không dùng production keys.

## Ba lớp bằng chứng và topology

| Lớp | Phạm vi | Trạng thái trước CI |
|---|---|---|
| A | Node production engine + Java TransferServer trên JVM; HTTP loopback, bốn hướng engine, không native OS proof | Local smoke24case PASS, CI/full size NOT VERIFIED |
| A / toolkit | Generator/hash/compare/timing/report, safe path/cleanup/exit-code unit, Windows PowerShell wrapper | Linux local82unit PASS; Windows native script execution NOT VERIFIED trước CI |
| B / Windows↔Android | Hai native client trên OS khác nhau cần mạng riêng thật sự chung | BLOCKED: môi trường hiện tại Linux không KVM/Windows VM; hosted Windows/Linux jobs độc lập không có private LAN được cấu hình |
| B / Windows↔Windows, Android↔Android | Hai client native độc lập | NOT VERIFIED: chưa chạy hai thiết bị; chuyển hướng dẫn local |
| C / physical LAN | Owner Windows10/11 và điện thoại thật, multicast/router/NIC/Firewall/OEM | NOT VERIFIED |

Không tạo tunnel công cộng, expose transfer API ra Internet, tắt firewall hoặc coi các hosted runners cùng LAN. Không dùng Node/JVM làm native E2E. Cùng OS native hai emulator không tự được suy là Wi-Fi vật lý. Kết quả runtime một thiết bị 2D.1 được chạy lại riêng, không thay lớp B/C.

## Test mới và cách chạy

- `tests/cross-platform-protocol.mjs`: bốn hướng Node→Java, Java→Node, Node→Node, Java→Java. Mỗi lượt stage source, relay HTTP sang một host khác, complete, tải/hash đích và đối chiếu đủ bytes/name/SHA. Thu hồi hai session, cleanup group thuộc test. Không gửi local capability sang host khác; từng host dùng capability từ private readiness pipe đúng loại.
- Smoke gồm0/1024/1MiB và101file mỗi hướng. Full gồm thêm100MiB/1GiB/4GiB+17byte mỗi hướng:36case tổng (28data/batch +8negative/security). Test negative chặn thiếu/sai/sai-loại capability, Origin ngoại, metadata âm; ngắt upload chính xác lượng byte ghi vào socket25/50/75% mỗi engine, metadata/complete409, không công khai file dở. Không suy đây là disconnect Wi-Fi vật lý.
- Source/destination digest và sizes ghi từng file, batch101 đủ101hash; rate ghi rõ interval bao gồm staging/relay/disk/hash, MB/s decimal và Mbps. /proc đo peak RSS từng host và giữ <300MiB. Không đổi RSS/sizes/timeouts của test cũ.
- `scripts/cross_platform_ci/run.py`: source guard790, isolated work root, log filtering, actual child exit/timeout, own POSIX process group cho Node/JVM descendants, manifest/checksums, source-only toolkit ZIP. Không lấy exit log collection thay test exit. Timeout kill chỉ group do task tạo, không kill mọi Node/Java.
- Local chạy smoke: đặt FLOWDROP_TEST_JSON_JAR qua đối số `--jar` (org.json20240303 SHA3cf6cd…414ed), npm ci từ lock gốc; `python3 -m scripts.cross_platform_ci.run protocol --work-root <fresh-outside-checkout> --jar <verified.jar>`. Dùng `--full` chỉ khi đủ≥18GiB free/timeout45phút; local này còn khoảng6GiB nên chưa chạy full. Không giảm file để gọi full PASS.
- `python3 -m scripts.cross_platform_ci.run toolkit --work-root <fresh-outside-checkout>` chạy unit và CLI/bundle. Self-test copy filesystem được ghi rõ là copy, không native transfer. Windows runner thực chạy PowerShell wrapper và read-only network collector; Linux unit không thay bằng chứng Windows.

## Owner toolkit và kiểm vật lý

[Hướng dẫn](PHYSICAL-LAN-TEST-GUIDE.md), [checklist](../../tools/physical-lan/CHECKLIST.md), [script](../../tools/physical-lan/flowdrop_lan.py), [menu PowerShell](../../tools/physical-lan/Run-FlowDrop-LAN.ps1), [network collector](../../tools/physical-lan/Collect-FlowDrop-Network.ps1).

Không cài/gỡ/ghi đè ứng dụng production; không cần key/password. Tạo workspace mới,110file tổng hợp và empty/nested/Unicode/media fixtures, profile lớn opt-in/space guard/streaming thực. File manifest chỉ định rõ những path được đọc; chặn traversal/drive/reserved name/symlink/junction/hardlink, nguồn đổi khi hash, gộp đích hoặc name-map mất tiền tố run. Không tự quét/xóa Downloads/profile cá nhân. Không có cleanup tự động trên máy người dùng.

Start/stop trên cùng máy, clock consistency, không reset timing; file SHA/timing/copy local không đủ kết luận LAN. Report luôn phân biệt integrity PASS với physical/native NOT VERIFIED và operator checklist. ADB helper chỉ đọc hash/size/dir của đúng unique synthetic folder ở Download/FlowDrop và một serial chỉ định; không push/pull/install/logcat/profile/token. Android→Windows có SHA nguồn Android riêng trước gửi. Collector Windows chỉ đọc adapters/firewall, không đổi rule. Không xuất environment dump hoặc raw private logs.

## CI và evidence

Workflow mới `.github/workflows/cross-platform-e2e.yml`, opt-in `ci-cross-platform` hoặc workflow_dispatch, contents:read, actions full SHA từ verified pins2C.2, không secrets/write/cache/sign/publish/pull_request_target. Protocol full trên PR, explicit summary giữ B BLOCKED/C NOT VERIFIED dù A xanh. Toolkit Windows/Linux có negative/safety/CLI thực thi; artifact chỉ scripts/docs+SHA/provenance, retention7ngày.

PR sẽ gắn `ci-cross-platform`, `ci-native-build`, `ci-native-runtime`, `ci-zip64`; phải chờ **bốn workflow** tại HEAD cuối: mới + Native Build Verification + Native Runtime Verification + Native Regression/full ZIP64/Coverage. Kết quả CI hiện **NOT VERIFIED**, không dùng local smoke thay CI.

[Matrix](CROSS-PLATFORM-TEST-MATRIX-2D2.json) ghi sender/receiver/network/source/artifact SHA (null nếu không chạy binary), size/expected/actual/source và destination SHA/time/rate/evidence/status. [Manifest](CROSS-PLATFORM-ARTIFACT-MANIFEST-2D2.json) và [SHA logs](CROSS-PLATFORM-LOG-SHA256SUMS-2D2.txt) áp dụng file log đã lọc trong Git. Local preliminary logs có source engine từ base nhưng harness lúc đó là working tree mới chưa commit; không gọi nó là CI chạy tại base.

Sau khi có CI, nhập snapshot bằng chứng đúng head đã thực chạy; sau commit report, chạy lại bốn workflow và ghi HEAD/runs/artifact cuối vào PR body. Không đổi nhãn JSON snapshot cũ thành commit mới để tránh vòng lặp self-SHA. Artifact của run cuối là matrix/manifest gắn đúng HEAD cuối.

## Rủi ro và việc chưa kiểm

| Mức | Finding/phạm vi | Hướng xử lý riêng |
|---|---|---|
| P0 | Chưa phát hiện mới trong phạm vi test đã chạy; không là bảo đảm toàn sản phẩm | Reviewer độc lập, không merge tự động |
| P1 | HTTP/discovery LAN cleartext và tên tự khai báo là baseline hiện có | Phase3 thiết kế authenticated pairing/TLS chỉ sau phê duyệt protocol; chưa triển khai |
| P2 | Native Win↔Android/Win↔Win/Android↔Android hai thiết bị, physical multicast/NIC/router/OEM/Android16 chưa kiểm | Owner chạy guide/checklist, giữ từng case NOT VERIFIED/BLOCKED đúng lý do |
| P2 | Native1GiB/>4GiB, disk-full an toàn, expiry24h, cancel/disconnect native và repeated soak chưa có evidence | Fixture volume/thiết bị riêng, không làm đầy ổ cá nhân; test riêng sau khi có topology |
| P2 | APK cert rejection trong update install thực, production signed update và artifact-to-source equivalence của binary đang dùng chưa xác minh | Không cài wrong-cert lên production; tách nhiệm vụ signing/update validation |
| P3 | Manual stopwatch gồm thao tác người dùng; localhost RSS/rate không là Wi-Fi benchmark | Ghi đúng method, đo CPU/read/write/discovery riêng nếu có |
| P3 | Artifact7ngày; network collector có private IP; Google/host toolchain provenance theo giới hạn2C.2/2D.1 | Chỉ chia sẻ allowlisted evidence, che dữ liệu trước public và ghi hash bản che |

## Điều tra CI đầu và sửa toolkit

Tại head `ff75c81074ffce6c3bbed1083a04e46d390c3f58`, [workflow mới43857110781](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43857110781) thực chạy full engine36/36case PASS, Linux toolkit PASS; **Windows toolkit FAIL**, summary FAIL đúng thiết kế. Ba workflow cũ cùng head đạt PASS: Native Build43857110877, Native Runtime43857111028, Native Regression43857110805 (full ZIP64/Coverage). Đây không phải kết quả sau sửa toolkit.

| Lỗi | Tái hiện và trước sửa | Thay đổi nhỏ trong test tools | Kiểm sau sửa |
|---|---|---|---|
| T01 / P2 toolkit | Windows3.12.10 đọc source-manifest.json UTF-8 bằng locale cp1252: UnicodeDecodeError ở TOOLKIT-CLI, command exit1 | read_result dùng UTF-8-sig tường minh, bao gồm BOM PowerShell; không đổi app | Fixture UTF-8/BOM và local suite84 PASS; Windows CI phải chạy lại |
| T02 / P2 toolkit | Windows20unit có1error, stop ngay sau start cho interval0 với monotonic tick thô; guard đúng cách từ chối timing | perf_counter_ns độ phân giải cao/cùng clock giữa process trên Python được hỗ trợ; giữ chặn clock khác máy, interval≤0, drift>5s và stop/reset trùng | Unit tái hiện tick không đổi +84local PASS; Windows CI phải chạy lại |

Artifact trước sửa14221149484 được tải và kiểm GitHub archive SHA-256/size/CRC rồi đối chiếu evidence-manifest. Log unit, test matrix và commands đã lọc được giữ trong cross-platform-2d2-logs/first-ci; không commit raw Actions credential/setup log. Local sau sửa `python3 -m scripts.cross_platform_ci.run toolkit ...` exit0,84unit; không gọi nó là Windows OS proof. Native app không đổi.

Source hiện hỗ trợ consent/pull/receipt/folder/ZIP64 nhưng không có resume offset; không thêm yêu cầu resume hoặc gọi đây là regression.

## Rollback và bàn giao

Chỉ thêm file; close Draft PR thì main/production không thay đổi. Nếu chủ dự án sau này merge, revert bằng PR riêng giữ Ruleset/required checks và dữ liệu nhận; không reset/force-push main. Chỉ xóa synthetic workspace của task, không xóa người dùng. Không release/tag/update feed/version/key/iOS/PR#1.

Đề xuất Phase3: thu evidence 2D.2-B trên Win10/11 và hai Android khác OEM; ưu tiên hai chiều Win↔Android; phân loại lỗi tái hiện riêng trước sửa; quyết định thiết kế security/protocol riêng dựa kết quả. Không triển khai Phase3 trong PR này.
