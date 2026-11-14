# FlowDrop Phase 2D.1 — Native Runtime Verification

Ngày báo cáo: 14/11/2026 (Asia/Saigon). PR bàn giao: [Draft #10](https://github.com/Melbournejr/FlowDrop_IOS/pull/10).

**Mốc bằng chứng đã kiểm: 53/53 nhóm runtime và 20/20 subcheck native bổ sung PASS; Native Build Verification và Native Regression đầy đủ, gồm ZIP64, PASS.** Đây là kiểm thử trên Windows Server 2025 và Android Emulator 35/29, không phải chứng nhận thiết bị vật lý hoặc ký production.

## Commit và cách đối chiếu HEAD cuối

- Main/base và merge PR #9: `9171e7f1ffbc0143d6e11374e3f6c847853341fe`.
- Nhánh riêng: `test/native-runtime-verification-2d1`; không push main hoặc force push.
- Snapshot bằng chứng được nhập Git: head `78c049cc0a9bfba47d0bd8b4cab4f5657cb80ddf`.
- Checkout GitHub PR merge revision của snapshot: `b94d50fa27880b04bbaed6b194c4c0ed4646c7c8`. Đây là checkout chung của builder/runtime, khác SHA head được review; không nhầm hai giá trị này.
- Sau snapshot, harness tăng điều kiện chờ Activity hết splash và ghi package đang foreground khi app ở nền. Python unit local 59/59, Java 8 compiler exit 0. Các điều kiện mới phải được chạy lại trên commit bàn giao.
- **HEAD bàn giao và các run cuối được ghi trong PR body sau khi commit báo cáo và chờ CI kết thúc.** Mỗi artifact runtime của run cuối chứa source/reviewed_head, checkout_commit, matrix, command exit và checksum của chính HEAD đó. Các JSON snapshot trong Git giữ nguyên SHA đã thực chạy ở trên, không được đổi nhãn thành HEAD mới. Quy trình này tránh vòng lặp đưa SHA của chính commit vào nội dung commit.

`protectMain` ruleset 27172303 được đọc lại: Active, áp dụng `~DEFAULT_BRANCH`, strict required `Coverage / explicit verification status` integration 15368; không sửa/bypass. PR #1 vẫn mở, head `2ccf9248ed6de184a200a950e1d37dd1e5b11741`, không sửa và không trùng workflow mới. PR #10 vẫn Draft, chưa merge.

## Kết quả thực thi và phạm vi bằng chứng

| Lớp kiểm chứng | Kết quả snapshot | Bằng chứng |
|---|---|---|
| Bảo toàn nguồn | 440 file baseline đúng SHA-256; không file cũ bị sửa | [Baseline](RUNTIME-SOURCE-BASELINE-2D1.json), kiểm trước build/runtime và trước commit |
| Unit/harness local | 59/59 exit 0; có HTTP fixture, không phải OS proof | [Log](runtime-2d1-logs/unit-final-proof.log) |
| Compile local | App/instrumentation, helper C++ và Java 8 đã compile; không suy ra OS runtime | Log điều tra và java-final-proof-compile.json |
| Build và structural CI | PASS, mọi child build/verify exit 0 | [Native Build run](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43573559041) |
| Windows OS | 21/21 nhóm PASS | [Runtime run](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43573559009), verified-78c049c/windows |
| Android API 35 | 16/16 nhóm, 4 runner cũ và 1 runner bổ sung PASS | verified-78c049c/android35 |
| Android API 29 | 16/16 nhóm, 4 runner cũ và 1 runner bổ sung PASS | verified-78c049c/android29 |
| Native regression | 15 command entries thực chạy exit 0, đủ 13 suite Node/JVM gốc và hai CI guards; Coverage PASS | [Regression run](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43573559007) |
| Thiết bị thật/OEM/Wi-Fi multicast/LAN vật lý liên nền tảng | NOT VERIFIED | Không dùng emulator/JVM để thay bằng chứng này |
| Production signing hoặc reproducible binary | NOT VERIFIED | Chỉ certificate thử nghiệm; không sử dụng production key |

[Ma trận](RUNTIME-TEST-MATRIX-2D1.json) giữ platform, OS/API, source/checkout, artifact SHA, precondition, method, expected/actual, exit nếu có, timing, evidence và status cho 53 nhóm. Thêm 20 subcheck từ hai runner NativeRuntimeSmoke; thời gian subcheck ghi rõ dùng chung duration instrumentation, không bịa timing riêng. [Manifest](RUNTIME-ARTIFACT-MANIFEST-2D1.json) ghi archive API digest/size/head, binary SHA/size và ánh xạ source/imported log hash. [SHA log](RUNTIME-LOG-SHA256SUMS-2D1.txt) áp dụng byte đã lọc và chuẩn hóa whitespace trong Git.

## Windows đã kiểm trên OS thật

Windows Server 2025 Datacenter, 10.0.26100, build 26100, x64; interactive session 2 thực đo được, HWND native visible. Không dùng Wine làm bằng chứng.

- Guard từ chối program/profile/shortcut/uninstall registry FlowDrop có sẵn trước cài.
- NSIS `/S` exit 0, đúng LocalAppData/Programs/FlowDrop; kiểm 128 file payload SHA, PE AMD64 GUI và Node runtime đúng pin.
- FlowDrop.exe và child Node thực chạy; desktop capability lấy nội bộ từ profile thử, không export token. HTTP config version 1.13.0, Windows/local đúng.
- Second invocation, Send To cold/warm IPC, dedup, Unicode path, relative-path rejection, native rename và identity qua restart đã chạy.
- Hai lượt transfer độc lập: file rỗng, UTF-8 nhỏ, pattern 1 MiB + 17 byte, tên Unicode/khoảng trắng. Sáu file đích có SHA chính xác; lượt hai sinh tên riêng và giữ nguyên file lượt một.
- Revoke, TCP disconnect giữa upload, partial file không public, thiếu/sai capability, invalid metadata đều đạt. ZIP có thành phần `Con` bị chặn đúng 400 và không để dữ liệu dở.
- Hai C++ smoke giữ assertion cũ: native file/folder picker, upload/download, automatic permanent receive, folder root collision, tên/cấu trúc/thư mục rỗng, update preference binding, và Explorer window visible.
- Dừng chỉ backend PID thuộc test, đóng app/backend, restart giữ device ID và SHA, NSIS uninstall thực tế. Kiểm không còn app/Node PID, shortcut và registry; marker AppData và sáu file đã nhận ngoài installation vẫn giữ SHA trước cleanup synthetic data.

## Android đã kiểm trên emulator thật

Emulator 37.2.13, hardware KVM thực, ABI x86_64:

| API | OS/fingerprint quan sát |
|---|---|
| 35 | Android 15; Android/sdk_phone64_x86_64/emu64x:15/AE3A.240806.019/12368160:userdebug/test-keys |
| 29 | Android 10; Android/sdk_phone_x86_64/generic_x86_64:10/QSR1.210820.001/7663313:userdebug/test-keys |

App và instrumentation cùng run, cùng test certificate `2760ec172c49ef423d17ac346e7216dddd2dc8b49c113ccdcae362db1c962672`, khác production pin. Cài sạch cả hai APK, app vẫn `app.flowdrop.mobile`, 1.13.0/code 14, min 29/target 35, đủ 11 permission gốc, font/resource/dex và signature/zipalign thực kiểm. App Java 8 bytecode gồm 69 class; không đổi manifest production.

Bốn runner gốc đều thực chạy trên cả API:

- NativeSmoke: native Activity/widgets, không embedded renderer, picker contract, Send/ReceiveService, MediaStore exact bytes, Album/Download, pending/history/revoke.
- NativeServiceSmoke: foreground host và service thật, saved bytes/routing/history/pending.
- NativeFolderSmoke: original folder name, nested/empty directories, names/bytes, collision và completion sau import.
- NativeShareSmoke: separate sender UID/provider, ACTION_SEND/MULTIPLE, URI grants, cold/warm Activity, dedup/MIME, từ chối URI nguy hiểm hoặc thiếu grant, không tự gửi, recipient consent và exact bytes.

Runner mới thực chạy đủ 10 subcheck mỗi API: backend native; foreground notification; system DocumentsUI mở/cancel; sáu file hai code độc lập với SHA/Unicode/trùng tên/URI riêng; hủy active HTTP; TCP abort không public partial; auth/invalid request; recipient rejection; backend sống khi HOME rồi mở lại; stop/restart giữ identity và sáu SHA. ADB force-stop/restart và uninstall hai package cũng thực chạy, logcat không crash/ANR ở run đạt.

API 35 deny/grant POST_NOTIFICATIONS đi qua dialog Android thật và kiểm permission state; API 29 xác nhận policy không yêu cầu runtime notification permission. HTTP qua ADB giữ Host của app để không làm yếu allowedHost. Picker contract bị ActivityMonitor chặn của runner cũ được phân biệt với system DocumentsUI thật ở runner mới.

Snapshot ảnh API 29 đã xem, là UI native thực. Snapshot đầu API 35 tại mốc trên còn splash dù Activity nhận focus; không dùng ảnh này chứng minh UI đã hết splash. Harness bàn giao bổ sung guard hết starting-window và screenshot sau compositor; ảnh và package-background mới phải đối chiếu trong artifact HEAD cuối. Không sửa/ghép ảnh hoặc thay UI production.

## Toolchain, authenticity và cô lập

Builder/provisioning/verification 2C.2 giữ nguyên byte, không nâng app dependency, không Gradle/AGP. JDK Temurin 21.0.13+9, SDK 35/build tools 35.0.0, aapt2 2.19-11948202, D8 8.6.2-dev, apksigner 0.9; MinGW-w64 POSIX x64/windres/NSIS theo lock đã duyệt. Compiler probe ghi đúng giá trị quan sát `14-posix`, không đổi nhãn thành kết quả đo numeric khác. Node Windows 24.22.2 với SHA exe `1c331340fa6cac5e4294725959070a143fa0507195a78ad77eed7943f719aac9`. Regression quan sát Node 24.22.2/Java 21.0.13/Python 3.12.16. Windows harness dùng Python 3.12.10 vì 3.12.16 không có distribution Windows tương ứng.

[Runtime lock](RUNTIME-TOOLCHAIN-LOCK-2D1.json): cmdline-tools 19.0, platform-tools 37.0.1, emulator 37.2.13 stable, AOSP default x86_64 API35r02/API29r08. Pin archive URL/build ID/version; so published SHA-1/size trong official HTTPS metadata rồi SHA-256 cố định. Google metadata không cung cấp independent signed SHA-256; không gọi hash tự tính là chứng thực nguồn độc lập. Metadata gốc và license được giữ nguyên. APT host libpulse0 quan sát 1:16.1+dfsg1-2ubuntu10.1, signed Ubuntu Noble index và root-owned official mirror list; candidate cố định vào install argv và version được log, không coi package index động là immutable archive pin.

- Work root/marker riêng, không dùng dữ liệu cá nhân hoặc production signing cache; kiểm paths/symlink/traversal trước cleanup/extract.
- System image có entry trên 512 MiB nên dùng extractor riêng 8 GiB/entry, 10 GiB/tổng; không giảm giới hạn extractor build cũ.
- Không giả SDK: command-line tools đặt đúng versioned layout, package.xml chỉ đăng ký exact authenticated package metadata/license/dependency, không thay image bytes.
- AVD, emulator prefs, XDG runtime, ADB keys và server port 5039 riêng; chỉ serial emulator-5554. KVM ACL chỉ cấp cho runner, không tắt firewall/SELinux/Defender.
- App/test APK ký cùng key tạm ngoài checkout, alias flowdrop; env-only password, không argv/GITHUB_ENV/cache/artifact, xóa trước export/finally. Không đọc production private key.
- Guard hash/provenance trước execute; no stale output. Windows mọi child app test disable automatic update; Android disable trong isolated test preferences, không động update feed.
- Workflow mới contents:read, full verified SHA Action pins, không pull_request_target/write/secrets/publisher/main-push/tag trigger. Log collector thành công không thay exit của test; summary yêu cầu từng required job và runtime status PASS. Opt-out ghi SKIPPED rõ ràng.
- Chỉ upload evidence đã screen, manifest/SHA; chỉ initial screenshot chưa có code. Mask capability/token/password/PAT/private-key material và ephemeral ADB public key. Không upload userdata/AVD/cache/keys/environment dump. Retention 7 ngày.

## Lỗi trước/sau và cách tái hiện

Mỗi lỗi có log trước sửa trong runtime-2d1-logs; kết quả sau sửa ở verified-78c049c hoặc HEAD cuối được nêu rõ. Không sửa production để ép test.

| ID | Tái hiện/kết quả trước | Sửa trong harness | Kết quả |
|---|---|---|---|
| H01 | Emulator version exit127 thiếu libpulse.so.0 | ldd với bundled libraries; signed APT official Ubuntu | emulator/KVM/boot thực PASS |
| H02 | setup-python 3.12.16 không có Windows2025 distribution | chỉ Windows dùng verified 3.12.10 | Windows runtime PASS |
| H03 | Windows autocrlf làm lệch protected SHA | Git command config autocrlf=false, không normalize hash sai | 440-file guard PASS |
| H04 | Flat cmdline-tools không nhận image; thiếu emulator registration | versioned layout/package.xml từ metadata đã hash | local avdmanager exit0; hai emulator boot PASS |
| H05 | A04 NameError verify_export | import đúng, unit symbol-table guard | APK verify/install PASS |
| H06 | C++ shell helper exit0xC0000139 trước main | RT_MANIFEST Common Controls v6, kiểm bytes PE | helper chạy và PASS |
| H07 | Cross-process edit vẫn rỗng/tên cũ | WM_SETTEXT trực tiếp, return/error/readback, actual button | picker/code/rename PASS |
| H08 | C++ fixture Con bị Windows reserved-name guard từ chối | chỉ copied fixture đổi Con hợp lệ; thêm negative live ZIP Con | folder positive và reserved-name rejection cùng PASS |
| H09 | NativeSmoke timeout120s ở literal UI cũ | hai selector trong compiled test copy, giữ assertion/UI gốc | bốn runner cũ PASS cả API |
| H10 | Host header dùng tunnel port bị 403 | preserve app Host qua ADB; HTTP fixture đúng200/sai403 | A08/A14 PASS |
| H11 | FATAL chỉ vào NativeRuntimeSmoke.click→widget→nested runOnMainSync | helper dispatch main một lần | no-crash gate và A13 PASS |
| H12 | Collision history phải ghi actual MediaStore destination name | map receipt file ID; kiểm first name/stem/extension/URI/displayName/pending/SHA | sáu SHA/unique URI PASS mỗi API |
| H13 | Picker BACK không quay lại app; inject chưa kiểm return/time/source | KeyEvent uptime/keyboard source, check cả down/up | picker cancel và full A13 PASS |
| H14 | Activity focus có thể còn splash overlay | gate visible surface và hết starting window; unit tái hiện | bổ sung ở commit bàn giao; xem CI HEAD cuối |
| H15 | BG evidence cần package foreground cụ thể | kiểm active package khác app trước backend probe, app active sau reopen | bổ sung ở commit bàn giao; xem CI HEAD cuối |

Bản gốc Windows/Android tests trong baseline vẫn nguyên byte. Helper copies ghi original/compiled source SHA, selector/driver/fixture adaptation; không tuyên bố test source byte-identical. Không xóa/skip hoặc giảm assertion, test size, RSS hay timeout cũ. First local HTTP fixture bị sandbox chặn loopback exit1; chạy lại nguyên suite với network permission đạt58, sau guard splash đạt59; cả log lỗi và log thực đạt được giữ, không biến môi trường lỗi thành PASS.

## Regression cũ được bảo toàn

Native Regression chạy fast, serial integration/discovery, stream và ZIP64; không đổi workflow cũ. 101 files, 384 MiB + 17 byte, RSS bounds, ZIP64 feature/folder/native-client trên 4 GiB, SHA/CRC và timeout cũ giữ nguyên. Resource preflight thực có trên 90 GB đĩa và khoảng16 GiB RAM cho ZIP64; cả ba bài nặng thực exit0, không bị skip.

Node/JVM HTTP/discovery/peer/security/large regressions là bằng chứng lớp riêng. Không gọi chúng là Android/Windows OS tests hoặc physical cross-platform LAN. Native runtime smoke dùng tải vừa để kiểm UI/lifecycle, không thay các bài trên4GiB bằng tải nhỏ.

## File và diff

Chỉ thêm workflow mới, harness/test và tài liệu/evidence. Không sửa/xóa bất kỳ file baseline nào: app Windows/Android/Node/shared, protocol, UI/assets, version, signing pins, lock/dependency, iOS và ba workflow cũ đều nguyên byte. Không thêm APK/EXE/keystore vào Git.

- .github/workflows/native-runtime-verification.yml.
- scripts/native_runtime_ci/: __init__.py, common.py, definitions.py, build.py, sdk.py, android.py, windows.py, http_probe.py, test_sources.py, finish.py.
- tests/android-runtime/NativeRuntimeSmoke.java; tests/ci/test_native_runtime_ci.py.
- docs/testing/RUNTIME-REPORT-2D1.md, RUNTIME-TEST-MATRIX-2D1.json, RUNTIME-ARTIFACT-MANIFEST-2D1.json, RUNTIME-LOG-SHA256SUMS-2D1.txt, RUNTIME-SOURCE-BASELINE-2D1.json, RUNTIME-TOOLCHAIN-LOCK-2D1.json, NATIVE-RUNTIME-2D1.md.
- runtime-2d1-provenance/: hai official metadata snapshots; runtime-2d1-logs/: historical before/after và authenticated CI snapshot. Exact paths/SHA của log nằm trong SHA256SUMS, full diff ở Files changed của PR.

## Rủi ro và điều chưa xác minh

| Mức | Nội dung/thực trạng | Quyết định hoặc việc tiếp theo |
|---|---|---|
| P0 | Không phát hiện mới trong phạm vi đã chạy; không phải bảo đảm không có lỗi | Giữ Draft để review độc lập |
| P1 | LAN HTTP plaintext là baseline hiện có; OS PASS không sửa rủi ro nghe lén LAN | Chỉ thiết kế đổi protocol khi được phê duyệt ở nhiệm vụ riêng |
| P2 | Windows Server2025 x64 và AOSP x86_64 không đại diện Win10/11 máy thật, Android16/OEM/ARM, Wi-Fi multicast hoặc pin nền | Chọn VM/điện thoại thử riêng cho Phase2D.2; chưa triển khai |
| P2 | Production signing/update-install end-to-end, Authenticode và reproducible binary chưa xác minh | Nhiệm vụ riêng nếu được giao; không dùng hoặc đổi production key ở đây |
| P3 | Google published checksum là SHA1/HTTPS; host package index/runner image có phần động | Giữ lock/provenance/observed versions, không tự đổi pin |
| P3 | Actions artifacts 7 ngày; Git logs đã lọc/whitespace-normalized khác raw bytes | Manifest giữ cả original/import hashes; tải evidence khi còn hạn |

## Rollback và bàn giao

PR vẫn Draft; chưa merge nên main/Release và máy production không bị thay đổi. Nếu chủ dự án sau này merge, rollback bằng PR revert commit merge của #10, giữ protectMain và required checks; không reset/force-push main hoặc xóa dữ liệu người dùng. Workspaces CI đã uninstall test app/installer và cleanup owned emulator/keys. Không yêu cầu người dùng gỡ production để thử.

Chủ dự án cần quyết định review/merge Draft PR, danh sách máy/OS/Wi-Fi riêng để kiểm tiếp và phạm vi signed-update/physical interoperability tương lai. Không cần production password hoặc key cho phần đã làm. Không tự triển khai Phase2D.2/3, tạo tag/Release, publish update feed hoặc nâng version.

[Hướng dẫn chạy/đọc CI](NATIVE-RUNTIME-2D1.md). Khi bàn giao, đối chiếu PR body: đúng HEAD cuối, đủ ba workflow PASS, Coverage PASS, runtime53/53 và các artifact mang đúng head. Nếu bất kỳ gate cuối chưa đạt thì chưa nghiệm thu đầy đủ, bất kể snapshot trước đã xanh.
