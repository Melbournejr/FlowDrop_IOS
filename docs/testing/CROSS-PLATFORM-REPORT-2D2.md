# FlowDrop 2D.2 — cross-platform verification

Ngày 16/11/2026 (Asia/Saigon). App baseline1.13.0. [Draft PR#11](https://github.com/Melbournejr/FlowDrop_IOS/pull/11).

**Mốc 2D.2-A đã đạt:** full engine36/36case, HTTPhelper5/5, Python84/84, portable Windows21/21, toolkit CLI/bundle và bốn workflow thực PASS. **2D.2-B và toàn bộ Phase2D.2 chưa được nghiệm thu:** chưa có native Windows↔Android hai thiết bị hoặc LAN vật lý. Không dùng kết quả protocol/emulator thay bằng chứng này.

Snapshot kiểm chứng trong Git là head `c057f6dbbbd4d9da4e9fe4da63e173204691aefc`, GitHub merge checkout `fa74266e3658332681214fb04f02ee758d6a5d63`, đúng cùng checkout của các producer/verifier/runtime. Sau commit báo cáo và guard ADB canonical cuối, phải chạy lại đủ bốn workflow tại HEAD bàn giao; **HEAD/runs/artifact cuối được cập nhật trong PR body**, không đổi nhãn JSON snapshot thành commit mới. CI cuối chưa đạt thì chưa nghiệm thu 2D.2-A, bất kể snapshot này đã xanh.

## Baseline và kiểm soát

- PR #10 đã merge đúng `f9b5a43c5eae93b169717a72d19f5a426d913094`; checkout main mới nhất trước tạo nhánh `test/cross-platform-e2e-2d2`. Không push main.
- AGENTS root và audit/architecture/features/protocol/release/regression/build2C.2/runtime2D.1, các artifact manifest, workflow và source test đã được đối chiếu. Không có AGENTS con. Báo cáo cũ giữ nguyên là lịch sử, không suy thành kết quả mới.
- `protectMain` ruleset27172303 Active, áp dụng main/~DEFAULT_BRANCH, strict required Coverage / explicit verification status. Chỉ đọc; không sửa/bypass. PR#1 còn mở head2ccf9248ed6de184a200a950e1d37dd1e5b11741; không sửa và workflow mới không trùng đường dẫn.
- Bảo toàn **790/790 file baseline** bằng SHA-256 và Git blob đối chiếu trực tiếp base commit; không chỉ tin manifest do PR mới tạo. App Windows/Android/Node/shared, protocol/API/UI/assets, version/package, signing/update pins, dependencies/lock, iOS, bốn workflow cũ và mọi test cũ giữ nguyên byte.
- Mọi thay đổi là bổ sung harness, workflow opt-in, portable owner toolkit và tài liệu/evidence. Không build/publish phiên bản mới; các build TEST ONLY do workflow cũ chạy lại theo nhiệm vụ, không dùng production keys.

## Ba lớp bằng chứng và topology

| Lớp | Phạm vi | Kết quả snapshot đã thực chạy |
|---|---|---|
| A | Node production engine + Java TransferServer trên JVM; HTTP loopback, bốn hướng engine, không native OS proof | Full36/36case +HTTPhelper5 PASS, child exit0 |
| A / toolkit | Generator/hash/compare/timing/report, safe path/cleanup/exit-code unit, Windows PowerShell wrapper | Linux84unit PASS; Windows21unit +PowerShell/CLI/collector/bundle thực PASS |
| Native build/runtime regression cũ | Windows Server2025 và emulator35/29 từng thiết bị; build APK/EXE, signature/zipalign/PE/payload | Build PASS; runtime53/53 nhóm PASS, không phải hai native client trao đổi qua LAN |
| Native Regression cũ | Fast/integration/stream/fullZIP64/Coverage;13suite Node/JVM gốc +2guards |15command thực exit0, không skip, Coverage PASS |
| B / Windows↔Android | Hai native client trên OS khác nhau cần mạng riêng thật sự chung | BLOCKED: môi trường hiện tại Linux không KVM/Windows VM; hosted Windows/Linux jobs độc lập không có private LAN được cấu hình |
| B / Windows↔Windows, Android↔Android | Hai client native độc lập | NOT VERIFIED: chưa chạy hai thiết bị; chuyển hướng dẫn local |
| C / physical LAN | Owner Windows10/11 và điện thoại thật, multicast/router/NIC/Firewall/OEM | NOT VERIFIED |

Không tạo tunnel công cộng, expose transfer API ra Internet, tắt firewall hoặc coi các hosted runners cùng LAN. Không dùng Node/JVM làm native E2E. Cùng OS native hai emulator không tự được suy là Wi-Fi vật lý. Kết quả runtime một thiết bị 2D.1 được chạy lại riêng, không thay lớp B/C.

## Test mới và cách chạy

- `tests/cross-platform-protocol.mjs`: bốn hướng Node→Java, Java→Node, Node→Node, Java→Java. Mỗi lượt stage source, relay HTTP sang một host khác, complete, tải/hash đích và đối chiếu đủ bytes/name/SHA. Client mới của test dùng node:http HTTP/1.1, không thay transport ứng dụng. Thu hồi hai session, cleanup group thuộc test. Không gửi local capability sang host khác; từng host dùng capability từ private readiness pipe đúng loại. Checkpoint trước/sau từng case giữ kết quả chưa hoàn tất khi child lỗi.
- Smoke gồm0/1024/1MiB và101file mỗi hướng. Full gồm thêm100MiB/1GiB/4GiB+17byte mỗi hướng:36case tổng (28data/batch +8negative/security). Test negative chặn thiếu/sai/sai-loại capability, Origin ngoại, metadata âm; ngắt upload chính xác lượng byte ghi vào socket25/50/75% mỗi engine, metadata/complete409, không công khai file dở. Không suy đây là disconnect Wi-Fi vật lý.
- Source/destination digest và sizes ghi từng file, batch101 đủ101hash; rate ghi rõ interval bao gồm staging/relay/disk/hash, MB/s decimal và Mbps. /proc đo peak RSS từng host và giữ <300MiB. Không đổi RSS/sizes/timeouts của test cũ.
- `scripts/cross_platform_ci/run.py`: source guard790, isolated work root, log filtering, actual child exit/timeout, own POSIX process group cho Node/JVM descendants, manifest/checksums, source-only toolkit ZIP. Không lấy exit log collection thay test exit. Timeout kill chỉ group do task tạo, không kill mọi Node/Java.
- Local chạy smoke: đặt FLOWDROP_TEST_JSON_JAR qua đối số `--jar` (org.json20240303 SHA3cf6cd…414ed), npm ci từ lock gốc; `python3 -m scripts.cross_platform_ci.run protocol --work-root <fresh-outside-checkout> --jar <verified.jar>`. Dùng `--full` chỉ khi đủ≥18GiB free/timeout45phút; local này còn khoảng6GiB nên full được chạy trên CI, không chạy local. Không giảm file để gọi full PASS.
- `python3 -m scripts.cross_platform_ci.run toolkit --work-root <fresh-outside-checkout>` chạy unit và CLI/bundle. Self-test copy filesystem được ghi rõ là copy, không native transfer. Windows runner thực chạy PowerShell wrapper và read-only network collector; Linux unit không thay bằng chứng Windows.

## Owner toolkit và kiểm vật lý

[Hướng dẫn](PHYSICAL-LAN-TEST-GUIDE.md), [checklist](../../tools/physical-lan/CHECKLIST.md), [script](../../tools/physical-lan/flowdrop_lan.py), [menu PowerShell](../../tools/physical-lan/Run-FlowDrop-LAN.ps1), [network collector](../../tools/physical-lan/Collect-FlowDrop-Network.ps1).

Không cài/gỡ/ghi đè ứng dụng production; không cần key/password. Tạo workspace mới,110file tổng hợp và empty/nested/Unicode/media fixtures, profile lớn opt-in/space guard/streaming thực. File manifest chỉ định rõ những path được đọc; chặn traversal/drive/reserved name/symlink/junction/hardlink, nguồn đổi khi hash, gộp đích hoặc name-map mất tiền tố run. Không tự quét/xóa Downloads/profile cá nhân. Không có cleanup tự động trên máy người dùng.

Start/stop trên cùng máy, clock consistency, không reset timing; file SHA/timing/copy local không đủ kết luận LAN. Report luôn phân biệt integrity PASS với physical/native NOT VERIFIED và operator checklist. ADB helper chỉ đọc hash/size/dir của đúng unique synthetic folder ở Download/FlowDrop và một serial chỉ định; không push/pull/install/logcat/profile/token. Android→Windows có SHA nguồn Android riêng trước gửi. Collector Windows chỉ đọc adapters/firewall, không đổi rule. Không xuất environment dump hoặc raw private logs.

## CI và evidence

Workflow mới `.github/workflows/cross-platform-e2e.yml`, opt-in `ci-cross-platform` hoặc workflow_dispatch, contents:read, actions full SHA từ verified pins2C.2, không secrets/write/cache/sign/publish/pull_request_target. Protocol full trên PR, explicit summary giữ B BLOCKED/C NOT VERIFIED dù A xanh. Toolkit Windows/Linux có negative/safety/CLI thực thi; artifact chỉ scripts/docs+SHA/provenance, retention7ngày.

PR đã gắn `ci-cross-platform`, `ci-native-build`, `ci-native-runtime`, `ci-zip64`. Tại snapshot, đã đọc đủ **21/21 job success**, tải/kiểm12archive (API head/digest/size, ZIP path/CRC), producer evidence manifest và source binding:

| Workflow thực chạy | Kết quả |
|---|---|
| [Cross-platform E2E43859327396](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43859327396) |4/4job PASS;36enginecase,5HTTPhelper,84PythonLinux,21Windows và toolkit source ZIP |
| [Native Build43859327383](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43859327383) |5/5job PASS; verifier độc lập cùng checkout, source/fingerprint/SDK/PE/runtime giữ baseline |
| [Native Runtime43859327498](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43859327498) |7/7job PASS; Windows21, Android35/2916mỗiAPI, instrumentation thật |
| [Native Regression43859327444](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43859327444) |5/5job PASS;15command,101file/384MiB+17/ba bàiZIP64>4GiB/Coverage |

Toolkit snapshot [artifact14221648361](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43859327396/artifacts/14221648361), nestedZIP SHA `f21af8b33f9f7f214886cf7965a31dbca71b105e7d75f0e4bbe8f4b9a17b4d66`. Đã đối chiếu đủ năm file trong ZIP với Git blob tại snapshot; không APK/EXE/secret/cache. Handoff dùng **artifact HEAD cuối** trong PR body, sau đổi hướng dẫn ADB canonical.

[Matrix](CROSS-PLATFORM-TEST-MATRIX-2D2.json) ghi sender/receiver/network/source/artifact SHA (null nếu không chạy binary), size/expected/actual/source và destination SHA/time/rate/evidence/status. [Manifest](CROSS-PLATFORM-ARTIFACT-MANIFEST-2D2.json) và [SHA logs](CROSS-PLATFORM-LOG-SHA256SUMS-2D2.txt) áp dụng file log đã lọc trong Git. Local preliminary logs có source engine từ base nhưng harness lúc đó là working tree mới chưa commit; không gọi nó là CI chạy tại base.

Matrix có36case engine đã chạy, bốn native-pair chưa chạy và124case vật lý chưa chạy, tổng164; single-device native regressions và15legacy commands được tách riêng. PeakRSS actual của bốn engine đều<300MiB; throughput chỉ là interval staging/relay/disk/hash loopback, không Wi-Fi. CPU model/read-write throughput/discovery latency trên hardware vật lý **NOT VERIFIED**. JSON snapshot giữ source/original/imported SHA, không giả timing hoặc digest cho case chưa chạy.

Sau khi có CI, nhập snapshot bằng chứng đúng head đã thực chạy; sau commit report, chạy lại bốn workflow và ghi HEAD/runs/artifact cuối vào PR body. Không đổi nhãn JSON snapshot cũ thành commit mới để tránh vòng lặp self-SHA. Artifact của run cuối là matrix/manifest gắn đúng HEAD cuối.

## File bổ sung

Chỉ thêm `.github/workflows/cross-platform-e2e.yml`, `scripts/cross_platform_ci/`, `tests/cross-platform-protocol.mjs`, `tests/helpers/protocol-http.mjs`, `tests/protocol-http.test.mjs`, hai file unit mới trong `tests/ci/`, `tools/physical-lan/`, năm tài liệu/JSON/SHA yêu cầu +SOURCE-BASELINE và `cross-platform-2d2-logs/`. Full path của log nằm trong SHA256SUMS; source byte hashes của790file baseline đối chiếu trực tiếp immutable Git commit. Không thêm binary toolkit/installers vào Git. Native guard440 và build guard262 cũ giữ nguyên; source guard790 của phase này bổ sung riêng, không đổi nhãn các guard cũ.

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
| P2 / chưa xác định ảnh hưởng sản phẩm | Node24.22.2 bundled Undici HTTP parser phát sinh unhandled assertion trong **client của test mới**, ở lần full matrix thứ hai. Node production cũng có dùng fetch nhưng chưa tái hiện lỗi này trong native app | Giữ log/raw exit, không sửa hoặc nâng dependency production; Phase3 tái hiện riêng bằng native binary trước khi kết luận/sửa |

## Điều tra CI đầu và sửa toolkit

Tại head `ff75c81074ffce6c3bbed1083a04e46d390c3f58`, [workflow mới43857110781](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43857110781) thực chạy full engine36/36case PASS, Linux toolkit PASS; **Windows toolkit FAIL**, summary FAIL đúng thiết kế. Ba workflow cũ cùng head đạt PASS: Native Build43857110877, Native Runtime43857111028, Native Regression43857110805 (full ZIP64/Coverage). Đây không phải kết quả sau sửa toolkit.

| Lỗi | Tái hiện và trước sửa | Thay đổi nhỏ trong test tools | Kiểm sau sửa |
|---|---|---|---|
| T01 / P2 toolkit | Windows3.12.10 đọc source-manifest.json UTF-8 bằng locale cp1252: UnicodeDecodeError ở TOOLKIT-CLI, command exit1 | read_result dùng UTF-8-sig tường minh, bao gồm BOM PowerShell; không đổi app | Fixture UTF-8/BOM và local suite84 PASS; Windows CI43858014802 thực PASS21unit +CLI/bundle |
| T02 / P2 toolkit | Windows20unit có1error, stop ngay sau start cho interval0 với monotonic tick thô; guard đúng cách từ chối timing | perf_counter_ns độ phân giải cao/cùng clock giữa process trên Python được hỗ trợ; giữ chặn clock khác máy, interval≤0, drift>5s và stop/reset trùng | Unit tái hiện tick không đổi +84local PASS; Windows CI43858014802 thực PASS21unit +CLI/bundle |
| T03 / P2 harness/client, ảnh hưởng app chưa xác minh | Full protocol lần đầu36PASS; lần hai Node24.22.2 exit1 ở Undici Parser.finish assert(!this.paused), không hoàn tất matrix. Summary FAIL, không khai PASS hoặc tự retry | Chỉ client mới của test chuyển sang node:http HTTP/1.1, giữ loopback/origin/capability, Content-Length/streaming/SHA và toàn bộ sizes/assertions; thêm checkpoint từng case +5HTTPhelperunit thực socket (truncated body/redirect/size bound/capability/stream) | Local helper5/5 và smoke24/24 thực PASS; full36CI phải chạy lại. Production source và dependency nguyên byte |

Artifact trước sửa14221149484 được tải và kiểm GitHub archive SHA-256/size/CRC rồi đối chiếu evidence-manifest. Log unit, test matrix và commands đã lọc được giữ trong cross-platform-2d2-logs/first-ci; không commit raw Actions credential/setup log. Local sau sửa `python3 -m scripts.cross_platform_ci.run toolkit ...` exit0,84unit; không gọi nó là Windows OS proof. Native app không đổi.

Tại head4d64bcd4910fd310aa8a5b24608e1d1e1cb3b2d1, artifact14222835565 giữ protocol child raw_returncode1/timeoutfalse, client parser stack và mandatory FAIL. Từng case của lần abrupt exit chưa có checkpoint nên không xác định được size/direction gây assertion từ log đó; không bịa kết quả. Chưa gọi đây là lỗi production đã tái hiện. Thay transport **của harness** không thay client/server ứng dụng; mọi regression cũ vẫn phải chạy nguyên bản.

Sau T03 tại snapshot c057f6d: HTTPhelper5/5 +full36/36 thực PASS, không retry hoặc giảm sizes/assertion. Guard ADB cuối chỉ nhận `/storage/emulated/0/...` canonical; `/sdcard` vốn là system alias/symlink bị từ chối sớm để không tự mâu thuẫn với no-link checks. Unit negative giữ alias ngoài allowlist; kiểm SHA trên điện thoại vật lý vẫn NOT VERIFIED.

Source hiện hỗ trợ consent/pull/receipt/folder/ZIP64 nhưng không có resume offset; không thêm yêu cầu resume hoặc gọi đây là regression.

## Rollback và bàn giao

Chỉ thêm file; close Draft PR thì main/production không thay đổi. Nếu chủ dự án sau này merge, revert bằng PR riêng giữ Ruleset/required checks và dữ liệu nhận; không reset/force-push main. Chỉ xóa synthetic workspace của task, không xóa người dùng. Không release/tag/update feed/version/key/iOS/PR#1.

Đề xuất Phase3: thu evidence 2D.2-B trên Win10/11 và hai Android khác OEM; ưu tiên hai chiều Win↔Android; phân loại lỗi tái hiện riêng trước sửa; quyết định thiết kế security/protocol riêng dựa kết quả. Không triển khai Phase3 trong PR này.
