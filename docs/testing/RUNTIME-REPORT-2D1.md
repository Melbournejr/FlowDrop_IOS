# FlowDrop Phase 2D.1 — Native Runtime Verification

Ngày: 14/11/2026. **Trạng thái: NOT VERIFIED — đang xây dựng và chạy pipeline; không phải nghiệm thu runtime.**

## Baseline và phạm vi

PR #9 đã merge đúng `9171e7f1ffbc0143d6e11374e3f6c847853341fe`, đồng thời là main mới nhất lúc bắt đầu. Nhánh riêng `test/native-runtime-verification-2d1`; remote được kiểm chưa tồn tại trước khi tạo. `protectMain`27172303 vẫn Active, áp dụng `~DEFAULT_BRANCH`, strict required `Coverage / explicit verification status` integration15368; không đổi settings/bypass. Chỉ PR #1 đang mở, head2ccf9248ed6de184a200a950e1d37dd1e5b11741; không sửa và không trùng workflow mới.

Đã đọc AGENTS (root duy nhất), các tài liệu audit/architecture/features/protocol/regression/release và toàn bộ báo cáo/manifest/README2C.2; byte khớp mốc đã review. [Baseline440 file](RUNTIME-SOURCE-BASELINE-2D1.json) được kiểm SHA trước build/runtime. Không sửa bất kỳ file baseline nào, không sửa production/iOS/pin/package/version/UI/dependency/oldworkflow.

## Phân biệt bằng chứng

- Build/structural verification2C.2 đã có bằng chứng lịch sử; không suy ra OS runtime.
- Unit49/49 thực chạy local exit0, gồm41 case cũ và8 guard mới; **không phải** Android/Windows OS proof.
- App/original instrumentation/extended instrumentation đã build bằng SDK35/JDK21 tại local; không chạy APK trên Android local, không chạy EXE bằng Wine.
- Windows runtime, Android API35/API29 emulator và các CI trên HEAD mới: **NOT VERIFIED tại lần ghi này**.
- Physical device, Wi-Fi multicast/OEM battery, cross-platform physical LAN, production signing: **NOT VERIFIED**, không thuộc tuyên bố runtime loopback.

## Thiết kế kiểm chứng

Workflow mới `.github/workflows/native-runtime-verification.yml`, opt-in `ci-native-runtime` hoặc workflow_dispatch, contents:read, fullSHA Action pins tái sử dụng pin đã xác minh2C.2. Không pull_request_target/secrets/write/release/publisher. Checkout revision cụ thể; kiểm ancestry baseline và440 hash.

Các build jobs mới tái sử dụng builder/provisioning2C.2 nguyên byte, tạo APK/EXE TEST ONLY từ chính checkout của runtime jobs. Android cùng app/test cert tạm khác production, aliasflowdrop, mật khẩu env-only, xóa key trước export/finally. Build app và instrumentation gốc vẫn được thực thi. APK instrumentation mở rộng thêm NativeRuntimeSmoke và giữ đủ bốn runner gốc/provider/activity; không đổi app manifest. Test manifest/source phát sinh trong owned build output, không ghi đè baseline trong Git. Metadata ghi SHA source test gốc/đã compile; không báo test-source tương đương byte khi có adaptation.

Windows compile hai test C++ có sẵn bằng chính compiler đã pin, consolePE x64 riêng, có manifest/hash/source provenance. Windows runtime nhận installer và helper của cùng run, kiểm checkoutSHA/inventory trước execution; không cài đè FlowDrop/data/shortcut/registry đã có. Chạy trên windows-2025 và ghi OS build thực, không giả định interactive desktop. Transfer loopback thực qua Node backend do FlowDrop.exe khởi động, dùng desktop capability đọc nội bộ từ state trong profile thử; không ghi token/state vào artifact. SHA file rỗng/nhỏ/nhiều/Unicode/trùng tên; abort/cancel/auth/stop/restart; uninstall/shortcuts/registry/data preservation. C++ smoke giữ mọi assertion, mặc định1MiB; không bật flag runtime>4GiB, vì regression lớn riêng vẫn chạy đủ.

Android dùng official Emulator37.2.13 stable, platform-tools37.0.1 stable, cmdline-tools19.0, AOSP default/x86_64 API35r02/API29r08, được tải/đối chiếu publishedSHA1/size trước ghiSHA256. Google không cung cấp chữ ký SHA256 độc lập cho các archive này; không gọi hash tự tính là independent source proof. [Lock](RUNTIME-TOOLCHAIN-LOCK-2D1.json) và metadata gốc lưu provenance; archive/image/SDK/AVD không commit hoặc upload. Không silent chọn latest/canary/beta; filename cmdline có `_latest` nhưng buildID13114758/version19/hash cố định.

Runtime dùng KVM thực, device ACL chỉ cho runner nếu cần, không đổi firewall/SELinux. AVD/Android-user/ADB keys/serverport/serial riêng, chỉ emulator-5554, không đụng điện thoại vật lý. Boot/getprop/ADB kiểm thật; thiếu KVM/boot/APK/provenance phải BLOCKED/FAIL. Cài APK sạch sau apksigner/zipalign/badging; chạy bốn instrumentation cũ và runner bổ sung serial. Parse cả process exit và INSTRUMENTATION_CODE/result: am instrument exit0 không tự là testPASS. Permission denial/grant dùng Android dialog thật qua native instrumentation/UiAutomation; API29 ghi policy không cần runtime POST_NOTIFICATIONS. Picker contract cũ dùng ActivityMonitor, được phân biệt với bài mở/cancel DocumentsUI thật mới. ReceiveService/MediaStore/SHA, notification/background/restart/force-stop/auth/abort được kiểm trên Android, không dùng JVM thay thế.

## Harness tồn tại và phát hiện tĩnh

- `tests/windows-native-smoke.cpp`: native HWND/backend/picker/upload/receive/folder/Explorer/updateprefs/close, optional large/peer flags không bật ở runtime smoke này.
- `tests/windows-shell-smoke.cpp`: realapp cold/warm SendTo, IPC/dedup/Unicode/rename/identity/auth/revoke/restart.
- NativeSmoke: Activity/no-renderer/picker-contract/services/MediaStore/history.
- NativeServiceSmoke: realservices và MediaStore.
- NativeFolderSmoke: folders/names/emptydirs/collision/realReceiveService.
- NativeShareSmoke: actual separate sender UID/provider/grants/share intents/warmreuse/consent/exact bytes.

**Đã thấy selector cũ trong NativeSmoke:** literal “Tạo phiên trên điện thoại này” không tồn tại trong MainActivity1.13; button ready hiện là “● Điện thoại đang hiển thị trong Wi-Fi”. Đây mới là bằng chứng source, chưa phải kết quả test. Lượt đầu phải chạy nguyên selector để ghi nhận lỗi thực. Nếu xác nhận lỗi harness, chỉ đổi hai literal selector trong bản sao test đã compile, giữ toàn bộ assertion và nguồn baseline; ghi SHA adaptation trong artifact. Không sửa UI hoặc skip bài để làm xanh.

## Coverage và trạng thái bắt buộc

[Ma trận](RUNTIME-TEST-MATRIX-2D1.json) có21 nhóm Windows và16 nhóm cho mỗi API, tổng53 nhóm bắt buộc; runner mới còn ghi các subcheck SHA/permission/picker/lifecycle. Mỗi case ghi platform, OS/API, source/checkout commit, artifactSHA, preconditions, method, expected/actual, exit nếu có, timing, evidence và status. Missing case NOT VERIFIED; FAIL/BLOCKED/NOT VERIFIED/SKIPPED không thànhPASS. Summary yêu cầu cả ba runtime và build jobs thành công; không dùng exit của log collector thay test.

Thêm `ci-native-build` và `ci-zip64` vào Draft PR để workflow2C.2 và Native Regression hiện có chạy riêng, đầy đủ101files/384MiB+17/RSS/ZIP64>4GiB. Không đổi kích thước/assertion/timeout/oldtests. Các workflow trước giữ nguyên.

## Evidence, bảo mật và cleanup

Log và JSON được lọc token/capability/password/code trước upload; không env dump, desktop-state, private key, adb key, cache, userdata hoặc image. Chỉ screenshot đầu phiên chưa tạo code, không sửa ảnh hay dùng ảnh giả. Export chuẩn bị sau screening toàn bộ, có manifest/SHA, uploader chỉ chạy khi screening success; retention7ngày. Root ownership/path guards từ chối outside/symlink/stale export. Windows không xóa profile có trước; chỉ cleanup synthetic profile có marker được tạo sau empty-profile guard. Android finally uninstall/stop scoped emulator/server; workflow always cleanup image/key/workspace.

## Rủi ro tạm thời và xử lý

- P0: chưa có phát hiện mới; không có tuyên bố production đã được kiểm toàn diện.
- P1: chưa OS runtime đầy đủ trên HEAD mới; mọi claim runtime còn NOT VERIFIED đến khi đọc evidence thật. Không cài test lên production.
- P2: selector cũ cần thực nghiệm; khả năng desktop/KVM/emulator/image provisioning phải quan sát thực. Nếu lỗi production thì giữFAIL, ghi tái hiện/ảnh hưởng và đề xuất PR riêng, không sửa production ở2D.1.
- P3: evidence tạm7ngày; report lưu mốc đã chạy, PR body ghi head/run cuối để tránh self-SHA recursion.

Rollback bằng PR revert các file harness/workflow/docs thêm của2D.1, giữ main/Ruleset, app/data/key/Release. Không merge, publish, nâng version hoặc triển khai2D.2/3. Khi có môi trường blocker, báo PARTIAL và đưa hướng dẫn Windows VM/emulator/thiết bị thử cụ thể thay vì báoPASS.

## CI lần đầu và sửa hạ tầng (chưa nghiệm thu runtime)

Draft PR #10; head đầu `97dccd7bb214f574d30727a6e889a561e6ceb73f`. Run [43551446591](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43551446591) đã build app/instrumentation/Windows/helper thành công từ source checkout sạch. Hai API xác nhận KVM read/write, khoảng94.85GB đĩa nhưng `emulator -version` exit127: thiếu `libpulse.so.0`. Chưa boot/install nên không suy ra lỗi sản phẩm. Archive evidence được đối chiếu digest/size GitHub, CRC/paths và manifest file SHA trước nhập log đã lọc.

Sửa provisioning trong harness mới: `ldd` chỉ chấp nhận missing `libpulse.so.0` đã quan sát, giới hạn Ubuntu24.04, APT signed index và official Noble origin, candidate version được cố định vào argv install và ghi observed dpkg version; unresolved library khác vẫn BLOCKED. Không thay SDK/emulator hoặc production. Host APT dependency không phải archive pin bất biến; report ghi version thực từ runner. Thêm negative/unit guard không tự cài package chưa review.

Job Windows dừng trước runtime: `actions/setup-python` không có3.12.16 Windows2025. Chỉ job Windows đổi sang3.12.10 có file win32-x64 được xác minh trong manifest chính thức actions/python-versions (blobSHA trong log provenance). Các job Linux/build cũ không đổi. Không gọi lỗi setup là lỗi app.

Unit sau sửa:51/51 thực chạy local, exit0; xem `unit-host-library-fix.log`. Test selector NativeSmoke vẫn chưa chạy trên Android, chưa bật adaptation. Các lần đầu/label event hủy bởi concurrency không được tính PASS. CI đầy đủ sẽ được kiểm lại trên head cuối.

Lượt tiếp theo [43551949371](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43551949371), head `b8db11fe32d5a689e8d17fc2f1d628e1de1981ff`: precondition/builds PASS; runtime vẫn dừng trước install. Phát hiện guard `ldd` gọi qemu trực tiếp thiếu đường dẫn thư viện bundled do launcher chính thức thiết lập; guard từ chối đúng chứ không cài bừa Qt/Android library. Sửa phép đo `ldd` với đúng hai directory Google đã đối chiếu SHA, chỉ áp dụng env riêng của probe, không đưa vào APT. Không thay emulator hoặc bỏ check missing library. Unit kiểm rằng APT không nhận LD_LIBRARY_PATH này.

Windows checkout mặc định chuyển LF→CRLF; protected-source dừng ở `.github/actions/native-test-setup/action.yml`, trước execution. Cấu hình `core.autocrlf=false` qua Git command environment riêng job để checkout đúng byte blob; không normalize hoặc chấp nhận hash sai. Baseline guard440 vẫn nguyên và bắt buộc. Đây là lỗi portability harness, không phải thay đổi source.
