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

## Windows OS execution đã xác minh lần đầu

Run43552367620 / head `f20e71494445fdfd2b579630cfc1c564528dfabf`: cài TEST ONLY bằng NSIS exit0 trên Windows Server2025 Datacenter10.0.26100 x64, kiểm128 file payload/Node pin, chạy FlowDrop.exe và Node child thật, liveHTTP1.13/windows, HWND visible/interactive session2, single-instance/SendTo/shortcut/registry. Truyền6 file thuộc2code độc lập gồm rỗng/Unicode/1MiB+17; SHA trùng, collision tạo `(1)` giữ file gốc. Revoke/abortTCP/invalid403/400/stop-backend/restart/preserve/uninstall đều thực chạy. **19/21 nhóm PASS,2 nhóm FAIL, không nghiệm thu đầy đủ.**

W15 old native helper exit1: “Native file picker did not select files”. Chưa đủ bằng chứng phân loại lỗi app hay UI driver; giữ nguyên assertion/FAIL và bổ sung quan sát OS dialog controls trong harness mới, không điều khiển/che kết quả. W16 shell helper loader exit3221225785 (`0xC0000139` ENTRYPOINT_NOT_FOUND), không có test stdout. StaticPE thực chứng import COMCTL32 TaskDialogIndirect trong helper nhưng thiếu manifest activationCommonControlsV6; app có manifestV6 và chạy được. Chỉ link resource manifest baseline vào test helper, kiểm resource bytes trong PE, không sửa app hoặc test source/assertions. Sẽ thực chạy lại để xác nhận nguyên nhân.

Android vẫn trước boot do policyAPT `mirror+file:/etc/apt/apt-mirrors.txt` thay URL trực tiếp. Signed index thực tải archiveUbuntu Noble và candidate1:16.1+dfsg1-2ubuntu10.1. Harness xác minh system mirror file/root ownership, chỉ official Ubuntu archive regional URLs, từ chối host/path giả; không bỏ APT signature checks. Local unit52/52 exit0 trước thay đổi observer.

## Sửa provisioning và UI driver có bằng chứng

Head `740dd001e120b06c88a2d18982ae5da1a01fd4bf`, run43568850232: host library provisioning thực cài libpulse0 `1:16.1+dfsg1-2ubuntu10.1` từ signedAPT/official mirrors. adb37.0.1 và emulator37.2.13 actual probes exit0. AVD create exit1: package path invalid; chưa cài/chạy APK.

Tái hiện local bằng đúng archive đã kiểm SHA, không boot emulator: flat `cmdline-tools/bin` làm avdmanager suy ra saiSDK root; chuyển đúng `cmdline-tools/19.0/bin` nhận image nhưng báo thiếu package emulator mặc dù binary có. Đăng ký `package.xml` từ official metadata snapshot đã kiểmSHA (giữ type/revision/license/dependencies, bỏ field remote-download/channel), avdmanager create35 thực exit0. Không sửa image, không thay phiên bản, không dùng việc tạo AVD làm bằng chứng Android runtime. Harness mới áp dụng layout/registration này trong work root, metadata có receiptSHA, từ chối ghi đè.

Windows lượt này đã sửa loader: shell helper chạy vào assertion thay vì0xC0000139. Hai helper vẫn FAIL ở UI input: native picker không chọn file; shell báo config chưa có tên mới dù native UI báo lưu. OS dialog observations cho thấy control tạo theo nhiều đợt, filename edit1148 vẫn rỗng. Sửa driver trong bản sao test disposable: chờ dialog/primarybutton visible+enabled, nhập và kiểm text readback, invoke button BM_CLICK thật; giữ mọi fixture/assertion/timeout gốc, không chọc biến chọn file hoặc đổi app. Original440 file vẫn nguyên; ghi SHA nguồn gốc/nguồn test compile riêng. Unit chống source drift và giữ literal/assertion; hai bản sao C++ compile với manifest thực exit0, **không phải OS PASS**. Chờ rerun native.

Python unit hiện55/55 local, exit0; không thay/skip test cũ.

Log nhập Git được lọc bí mật và chuẩn hóa trailing whitespace/newline; checksum trong báo cáo áp dụng byte sau chuẩn hóa. ZIP evidence gốc và manifest hash của producer được kiểm độc lập trước bước này, không gọi bản đã lọc là raw log nguyên byte.

## Emulator boot thực và cross-process UI input

Run43570158444 / head `e253d3805be5f1bfafdbff472429627ee7e507e5`: cả API35(Android15, fingerprint Android/sdk_phone64_x86_64/emu64x:15/AE3A.240806.019/12368160:userdebug/test-keys) và API29(Android10, Android/sdk_phone_x86_64/generic_x86_64:10/QSR1.210820.001/7663313:userdebug/test-keys) boot x86_64/KVM thật thành công. A01/A02/A03 PASS. A04 dừng NameError do import `verify_export` bị thiếu, trước install APK; giữ FAIL/NOT VERIFIED cho các bước sau. Sửa đúng import và thêm unit static symbol-table guard, không cài thêm dependency lint hoặc sửa production.

Đã lọc thêm ephemeralADB **public** key khỏi boot log (không có private key); privateADBkey chưa từng export. Đặt ANDROID_EMULATOR_HOME/XDG_RUNTIME_DIR vào owned work root để prefs/cache/JWT runtime của emulator cũng được cô lập.

Windows vẫn19/21: các readback mới cho thấy thao tác setter của helper không thay actual edit text, không phải tên đã nhập rồi mất qua backend. Microsoft Win32 docs xác nhận SetWindowText không dùng đổi control của process khác; cần gửi WM_SETTEXT trực tiếp (blob/path/excerpt trong win32-settext-provenance.json). Driver test-only mới dùng SendMessageTimeout(WM_SETTEXT) có kiểm return/GetLastError/readback cho filename, receive code và rename; giữ mọi assertion cũ. Console diagnostic native chuyển sang UTF-8 để không trộn wide/narrow stdout gây mất dòng PASS, không đổi UI app. Chưa gọi đây là Windows PASS cho tới rerun.

Local unit57/57 exit0; actual NativeBuild43570158448 và fullNativeRegression43570158449/Coverage PASS tại head trên; vẫn cần lặp lại trên head cuối. Android oldselector chưa chạy, adaptation vẫn tắt.

## Instrumentation thực đã chạy / sửa lỗi harness tiếp theo

Run43571092761 / head `2fd451dd609cec594d31248d3fb7ad0c7dbaeabf`: Android35/29 đều xác minh APK thực, testcertificate chung `466f72e2a023d9c21ee582b8736890c543988ad188e291a8d5eaf0fb4cc39023` khác production, cài app+test thành công. Các runner gốc NativeServiceSmoke/NativeFolderSmoke/NativeShareSmoke đều PASS ở cả hai API: real Send/ReceiveService, MediaStore bytes/routing/pending/history, folders/collision/emptydirs, Share Intent separate senderUID/grants/consent/exactbytes. Permission dialog deny+grant thật API35 PASS; API29 policy PASS. **Mỗi API10/16 nhóm PASS,6 FAIL; không nghiệm thu.**

NativeSmoke gốc thực timeout120s với “Native connect screen not ready” do literal nút cũ. Nay mới bật adaptation hai literal trong bản sao test; không đổi UI/assertion/gốc Git. A06 lấy `dumpsys window windows` không chứa header mCurrentFocus trên hai API dù surfaceMainActivity visible; đổi sang full dumpsys window và chờ focused app thật, vẫn assertion không chấp nhận Splash. A08/A14 tunneledHTTP dùng Host là ephemeral host-side port bị production allowedHost chặn đúng; harness phải preserve Host `127.0.0.1:5173` trong ADB TCP tunnel. Unit HTTP fixture xác nhận host đúng200/host sai403, không tắt/bớt bảo vệ app.

A13 crash và A15 phát hiện đúng crash. Stack trên cả API chỉ vào helper NativeRuntimeSmoke.click→widget gọi runOnMainSync từ main thread. Sửa helper để tìm view trước dispatch rồi click một lần trên main; không sửa production/không loại crash khỏi evidence. Test mới đối chiếu collision theo file ID và displayName MediaStore thực (production history ghi tên đích đã thêm hậu tố), đồng thời giữ stem/extension, distinctURI, first-name exact, IS_PENDING0 và mọi SHA. Java8 helper compile thực exit0.

Windows20/21 PASS; SendTo/rename shell helper nay PASS. Native helper đã qua picker/upload/receive/folderarchive/updateprefs, còn FAIL nhậnfolder vì fixture `Con` trùng Windows reservedCON. Source folder-receive.mjs chặn rõ CON theo thiết kế, không được nới regex. Chỉ đổi5 đường dẫn fixture trong bản sao sang `Con hợp lệ`, giữ structure/Unicode/emptydirs/collision/assertion; thêm probe live Windows gửi ZIP có Con và bắt buộc400/fullmessage/no-leftovers để kiểm bảo vệ vẫn hoạt động. Windows naming docs/blob được lưu. Mọi childapp do helper khởi động cũng nhận test-env disable-updates, không chạm update feed.

Unit mới có socket fixture nên lần local sandbox mặc định exit1 PermissionError bind loopback; chạy lại nguyên58 test với network sandbox permission hỗ trợ loopback đạt58/58 exit0, không skip. Đây là unit/harness, không OS proof. NativeBuild43571092705 và fullRegression43571092770 PASS ở head trên; sẽ rerun ở head mới.

## Mốc Windows21/21 và Android15/16

Run43572621465 / head `afc3a3b679524c99f86b8d8d9eb93c5268fa1254`: Windows runtime **21/21 PASS**, bao gồm hai C++ helper, native realfile/folderpicker, exact folder structure/names/emptydirs/collision và Explorer window visible. Live reserved-name ZIP probe trả đúng400 “Windows không hỗ trợ tên: Con”, không để file lại; không sửa guard app. Uninstall xác nhận0ownedapp/backendprocess còn lại và dữ liệu synthetic ngoài installation giữSHA.

Cả hai Android **15/16 nhóm PASS**: bốn old instrumentation đầy đủ đã thực chạy thành công sau test-onlyselectorfix; Activityfocus/screenshot/liveADBHTTP/force-stop/restart/no-crash cũng PASS. Chỉ A13 mới còn FAIL ở “Picker cancel did not return to app”; các subcase A13 phía sau chưa chạy nên không gọi toàn bộ transfer/fault smoke bổ sung PASS.

Sửa input helper mới: tạo BACK/HOME KeyEvent với down/event uptime hiện hành, virtual keyboard source/flags rõ ràng và bắt buộc cả hai inject trảtrue; cặp sự kiện cũ không thiết lập time/source và không kiểm return. Giữ45s chờ actual appreturn, không thay bằng direct Activity launch để bỏ qua cancel. launch cũng phải thấy active accessibility window thuộcMainActivity cả khi mở lại từ nền. Java8 helper compile exit0; Android runtime kết quả chờ rerun.

NativeBuild43572621478 và fullRegression43572621491/Coverage PASS tại mốc trên; sẽ xác minh lại head cuối.
