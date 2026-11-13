# FlowDrop — kiểm toán và khôi phục hệ thống build, Giai đoạn 2C.1

Ngày quan sát: **13/11/2026, Asia/Saigon**. Nhánh `build/restore-native-toolchain`.
Base main [`893443d50c4eb02c8cd5537c1f0c42d37ede551d`](https://github.com/Melbournejr/FlowDrop_IOS/commit/893443d50c4eb02c8cd5537c1f0c42d37ede551d).

## 1. Kết quả và ranh giới bằng chứng

- **[API/Git] PR #7 đã merge**, workflow `native-regression.yml`, composite setup và runner Node/JVM có trên main. Đã clone main mới nhất, đọc AGENTS và đủ 12 tài liệu kiểm toán/harness/CI hiện có trước thay đổi. Tạo nhánh mới, không ghi đè nhánh có sẵn.
- **[API] Ruleset `protectMain` ID 27172303 active**, áp dụng `~DEFAULT_BRANCH`, bảo vệ deletion/non-fast-forward, yêu cầu PR và status check **Coverage / explicit verification status** (integration 15368), strict status checks; không có bypass actors. Chỉ đọc Settings. Không sửa/vô hiệu hóa/bypass Ruleset, không push main hoặc thử bypass để xác minh.
- **[SRC/CHECK] Khôi phục hai script từ đúng Source ZIP 1.13.0 và bỏ mật khẩu hardcode.** Thêm helper secret/process và 15 unit tests dùng dữ liệu giả. Giữ alias `flowdrop`, compile/packaging arguments, package, version, public certificate và update pins.
- **[OWNER/CHECK] Khôi phục đúng icon gốc** sau xác nhận quyền và cho phép rõ của chủ dự án; giữ byte/hash. Không suy giấy phép bên thứ ba, không sửa UI. [Hồ sơ quyền icon](../assets/FLOWDROP-ICON-RIGHTS.md).
- **[TEST] Local: 13/13 lệnh Node/JVM cũ và hai guard CI đạt**, gồm ZIP64 đầy đủ; sau bổ sung kiểm thử build-control, **26/26 Python CI unit** đạt (11 cũ + 15 mới). Kết quả chi tiết ở mục 7. Kết quả GitHub phải được quan sát riêng, không suy từ local.
- **Chưa build, ký hoặc cài APK/EXE trong 2C.1.** Chỉ chạy version probes, `--help`, static checks, unit/mock và regression Node/JVM. Không dùng/đọc nội dung keystore production, sinh khóa, sửa chứng thư/RSA pin, nâng version, sửa iOS, dependency, workflow phát hành hoặc PR #1. Không publish/merge.

`[SRC]`: đọc source; `[CHECK]`: đối chiếu hash/AST/Git; `[TEST]`: thực chạy; `[API]`: metadata/run GitHub; `[OWNER]`: xác nhận của chủ dự án; `NOT VERIFIED`: chưa thực thi/chưa đủ bằng chứng. Không coi version probe, mock hoặc CI engine xanh là build thành công.

## 2. Nguồn chuẩn và phạm vi khôi phục

Tải mới **không gửi thông tin đăng nhập** từ [custom Source ZIP chính thức](https://github.com/Melbournejr/FlowDrop_IOS/releases/download/v1.13.0/FlowDrop-Source-1.13.zip): **611206 byte**, SHA-256 **`d1fea853ad992c0b8febf8efa1cc988ef52bc2ca8e6b798eb440f2c7a243a962`**. Khớp RELEASE-PROCESS và manifest/exclusions 2A. Không dùng ZIP tự sinh của tag hoặc migration local chưa được review.

Trước ghi file: kiểm đủ 141 path/type, root, traversal/absolute/drive/ADS/backslash/control/reserved names, Unicode/case collisions, symlink/special/reparse, compression/encryption/size limits và file/parent conflict. Đọc mọi member để kiểm CRC/local header, đối chiếu size/SHA của đủ 141 baseline record. Không `extractall`, không ghi đè cây iOS. Bản script gốc chứa mật khẩu chỉ ở vùng audit ngoài Git, không stage/archive/upload nó.

| Member gốc dưới `FlowDrop/` | Byte gốc | SHA-256 gốc | Khôi phục |
| --- | ---: | --- | --- |
| `scripts/build-installers.py` | 5711 | `d39fa1ab2e5a77193631011d18a8fd501dc330fee3f3a6a7058f8e57967a6a42` | Sửa điều khiển build/credentials như mục 4 |
| `scripts/build-native-test-apk.py` | 1736 | `c7e5e0f32bb30144899b1ad4f84d4355b5d4aec77a93c962d90ffd2e2412c677` | Sửa điều khiển build/credentials như mục 4 |
| `desktop/windows/FlowDrop.ico` | 19820 | `cce4d31a79b6350c73daa884e9493d6ebc70746ac8e7471c924e0ad1b767650e` | Nguyên byte, không sửa |

[Manifest khôi phục](../assets/NATIVE-BUILD-RESTORATION-1.13.0-2C1.json) ghi hash bản script sau sửa và hash gốc, icon và xác nhận không build/dùng khóa production. Giữ nguyên exclusions/manifest lịch sử 2A; script sau loại mật khẩu không được mô tả là nguyên byte ZIP.

**[CHECK] AST đối chiếu 12 lệnh tool của installer và 5 lệnh instrumentation:** sau tách đúng cụm keystore/alias/password ra helper, mọi argument còn lại giữ nguyên và đúng thứ tự. Không thay target/min API, Java bytecode, D8 flags, link flags, v1/v2/v3 signing flags của app, runtime hash, payload files hoặc NSIS behavior. Alias mới đối chiếu bằng unit test với `flowdrop` gốc. [Bằng chứng](build-2c1-logs/audit-checks.json).

## 3. Quy trình build thực tế

### Android

`build-installers.py --only android`: aapt2 compile vector/resources → aapt2 link manifest với platform 35 → compiler module JDK tạo Java 8 bytecode (`-source 8 -target 8`, UTF-8, bootclasspath core-lambda stubs + android.jar) → D8 `--release --min-api 29` → ZIP resources/classes.dex/fonts/OFL → zipalign 4 byte → apksigner cùng alias/key được cấp bên ngoài → verify verbose/print-certs, zipalign check, aapt2 badging. Manifest giữ `app.flowdrop.mobile`, **1.13.0 / versionCode 14**, min 29/target 35. Không có Gradle/AGP project trong baseline, không thêm Gradle hay đổi cấu trúc app.

`build-native-test-apk.py`: cần **classes app đã compile** tại `android/build/classes`; link manifest `app.flowdrop.mobile.test`, compile nguồn instrumentation, D8 tham chiếu app classes, ZIP/zipalign/sign test APK. Để Android chấp nhận instrumentation, app và test APK cần cùng certificate của lượt thử. Đây là test package riêng, không được bundle vào installer app.

### Windows

`build-installers.py --only windows`: copy web/worker/node_modules, đúng danh sách Node scripts và VBS/PowerShell → windres (manifest/icon/version/dialog resources) → MinGW g++ POSIX **x64**, C++17, static runtime, Unicode GUI, các thư viện WinHTTP/comctl32/OLE/UUID/Shell/uxtheme/GDI/user/advapi → copy vendored JSON/MIT notice, package metadata, INSTALL guide → copy Node Windows runtime và LICENSE sau executable SHA check → NSIS LZMA tạo installer theo user.

Không đổi `%LOCALAPPDATA%\\Programs\\FlowDrop`, data path, Send To, single-instance, update/shutdown hoặc uninstall behavior. EXE 1.13.0 được báo cáo trước đây chưa có Authenticode; nhiệm vụ này không thêm certificate Windows hoặc thay RSA update signature.

### Các công cụ không phải native compiler

`npm run build` chạy **download-site packaging**, cần `releases/<version>/manifest.json` và payload đã có; `build:worker` tạo hosted prototype, còn cần `.openai/hosting.json`. Chúng không build APK/EXE. `make-release.mjs` nhận installer có sẵn và ký update manifest RSA; publisher nhánh automation kiểm/upload payload prebuilt. Không gọi các lệnh đó, không bổ sung đầu vào hosting, không bật/sửa publisher.

## 4. Cơ chế secret và điều khiển build sau khôi phục

| Biến | Vai trò |
| --- | --- |
| `FLOWDROP_BUILD_TOOLS` | CLI yêu cầu thư mục toolchain tuyệt đối, có sẵn; không tự tải/cài tool |
| `FLOWDROP_ANDROID_KEYSTORE` | File keystore bên ngoài checkout, đường dẫn tuyệt đối, có sẵn, không symlink |
| `FLOWDROP_ANDROID_STORE_PASSWORD` | Mật khẩu store do môi trường an toàn cấp; bắt buộc khi build Android |
| `FLOWDROP_ANDROID_KEY_PASSWORD` | Mật khẩu key do môi trường an toàn cấp; bắt buộc khi build Android |

Không có mật khẩu/default keystore fallback, không tự keygen/re-sign baseline. Alias công khai **`flowdrop`** giữ cố định, không dùng alias mới để chữa thiếu key. Password env phải khác rỗng và không NUL/newline. `apksigner` nhận **`env:FLOWDROP_ANDROID_STORE_PASSWORD` / `env:FLOWDROP_ANDROID_KEY_PASSWORD`**; giá trị không xuất hiện trong argv. Không ghi file `.env`, `GITHUB_ENV`, mật khẩu hoặc key vào Git, output/artifact. Env là kênh nạp secret, không tự cung cấp một kho khóa; việc cấp/quyền/thu hồi thuộc secret manager và chủ dự án.

Helper chỉ truyền ba biến signing cho **hai lệnh apksigner sign**. Compiler/zipalign/verify không nhận chúng. Chỉ log tên tool; stdout/stderr được capture, loại giá trị nhạy cảm trước ghi; nonzero báo tool/exit code, timeout/spawn error không in raw command/output. Có timeout 900s/tool. Không in environment dump. Mock kiểm tra cả nhánh tool lỗi vô tình echo credential. Sanitizer là bảo vệ bổ sung cho output tool, không phải lời hứa nhận ra mọi secret tương lai.

App kiểm cấu hình ký trước khi tạo output/dọn `android/build`; instrumentation kiểm cấu hình và app classes trước khi tạo workspace. Import hai module và `--help` không build, ký hoặc tạo directory. Windows-only không yêu cầu Android secrets. Các vùng `android/build`, `artifacts`, `<tools>/windows-payload`, `<tools>/native-instrumentation` vẫn là vùng build có thể bị ghi/dọn theo builder: **2C.2 phải dùng checkout/tool work root thử riêng**, không trỏ vào dữ liệu người dùng hoặc payload đang cần giữ. Không coi directory có sẵn là sandbox tự động.

Giữ certificate/public pins nguyên bản. Trước bất kỳ ký production tương lai, chủ dự án phải đối chiếu certificate SHA-256 với **`65cbed4feb375d2c3c2eb94e668bd7aaee7ce5b24f436887873a6fa11719f97f`**. Sai/mất identity thì dừng để quyết định; không sinh key thay thế hoặc sửa pin. Helper không xác lập trust cho một keystore chỉ từ tên file/alias; 2C.1 không mở khóa thực để kiểm định identity. RSA DER pin giữ **`10edffbf006bbd6e6a8fe5e8ab5859a44f62bdcd03aa3d339a158cbf4685c4b1`**; `verify-key-inventory.mjs` thực chạy exit 0 với public material.

## 5. Mật khẩu trong Source ZIP công khai và quyền icon

**[SRC/CHECK]** Hai script gốc có literal mật khẩu trong lệnh ký (installer dòng 35, test APK dòng 16 tại bản ZIP). URL public tải được không có credential; mật khẩu đó phải được coi là đã công khai. Không lặp giá trị, không commit script gốc hoặc tạo hash riêng của mật khẩu. Sửa Git hiện tại không xóa bản ZIP/lịch sử/bản sao đã tải.

**Phân biệt:** quét đủ 141 member không thấy tên file keystore/JKS/P12/PFX/private-key hoặc private-key PEM theo mẫu đã dùng. Không có bằng chứng private key production được phân phối trong chính ZIP này. Mật khẩu công khai làm tăng rủi ro nếu ai đó lấy được keystore, nhưng tự nó không phải private key và không chứng minh APK identity đã bị chiếm. Kiểm tra này không bao phủ mọi encoding bí mật, toàn bộ Git history, tài khoản, artifact/log cũ hoặc hệ thống ngoài repository.

**Chủ dự án cần xử lý ngoài PR nếu còn dùng mật khẩu cũ:** kiểm tra quyền/bản sao keystore, đổi store/key password mà giữ đúng private key/certificate, đối chiếu fingerprint trước/sau. `security/README.md` đã mô tả migration lịch sử; 2C.1 không đọc keystore để xác nhận trạng thái mật khẩu hiện tại và không tự làm migration. Chỉ khi có bằng chứng key lộ mới cần quy trình xử lý identity được duyệt riêng. Không tự rotate cert/RSA, sửa asset/tag hoặc xóa Release.

**[OWNER/CHECK] Icon:** trước xác nhận, repository/ZIP không có bằng chứng giấy phép riêng cho ICO; sáu PNG 16/32/48/64/128/256 không có text-license chunk. Đã tạm dừng phần phụ thuộc icon và hỏi chủ dự án. Chủ dự án sau đó xác nhận quyền lưu/sử dụng/sửa/phân phối cùng phần mềm và **cho phép nhập nguyên icon từ ZIP**. Đã ghi nguyên xác nhận trong [FLOWDROP-ICON-RIGHTS.md](../assets/FLOWDROP-ICON-RIGHTS.md), hash khớp. Đây là xác nhận của chủ dự án, không phải giấy phép OFL/MIT suy từ font/dependency hay kiểm chứng pháp lý độc lập. Không còn chờ quyết định nhập chính icon ở PR này.

## 6. Toolchain, dependency và đầu vào còn thiếu

Các đường dẫn dưới `<tools>` là layout **script gốc yêu cầu**. Chưa có installer/provisioner hash-pinned cho toàn bộ toolchain trong Git. Version probe hiện tại chỉ quan sát cache local, không chứng minh nó là đúng bộ compiler từng tạo binary Release 1.13.0.

| Thành phần | Đầu vào/phiên bản xác minh | Trạng thái 2C.1 |
| --- | --- | --- |
| Python | Thư viện chuẩn Python 3; local 3.12.14 | Có; helper không thêm pip dependency |
| JDK/compiler | Local OpenJDK 21.0.12.1, `jdk.compiler/com.sun.tools.javac.Main`; Java 8 output flags | Probes exit 0; không cần executable javac riêng |
| Android platform | `<tools>/sdk/platforms/android-35/android.jar`; metadata API 35, Android 15, revision 2, extension 13 | Có local; chưa provision trên GitHub runner |
| Android build-tools | `<tools>/sdk/build-tools/android-15`; metadata 35.0.0, directory là tên layout cũ | Có local; không mặc định directory name là package SDK chuẩn |
| aapt2 | Version probe `2.19-11948202` | Exit 0 |
| D8 | `lib/d8.jar`, `8.6.2-dev`, build `abaab469b5ebd4dd2bb91ba0ed6f45277faae4ca` | Exit 0; chưa pin/provision nguyên bộ này trên CI |
| zipalign / core-lambda | Binary `zipalign`, `core-lambda-stubs.jar` cùng build-tools | Builder cần; chưa chạy align/compile APK |
| apksigner | `lib/apksigner.jar`, version probe 0.9 | Exit 0; không ký APK |
| MinGW-w64 POSIX | `<tools>/mingw/usr/bin/x86_64-w64-mingw32-{gcc,g++}-posix`, headers/CRT/libs/sysroot | Local g++ banner GCC `14-posix`, exit 0; không compile C++ |
| windres | Cùng tool root; Binutils 2.44 | Exit 0; không compile resources |
| NSIS | `<tools>/nsis/usr/bin/makensis`, share/nsis include/plugins; local `v3.11-1` | Exit 0 version probe; không package EXE |
| Windows Node | **24.22.2** theo `desktop/windows/runtime.json`, license và node.exe | Local node.exe SHA khớp pin `1c331340fa6cac5e4294725959070a143fa0507195a78ad77eed7943f719aac9`; không chạy PE |
| Node archive | URL/hash trong runtime.json; archive SHA `ca1bff5d8ead13c9f2ea404a176db46bd430704d5b5113734049fa365e7799e2` | Không tải lại archive ở 2C.1; script giữ executable check |
| npm | `npm ci --ignore-scripts` đúng package-lock: bonjour-service 1.3.0, yauzl 3.4.0, sáu dependency gián tiếp | Không nâng dependency/lock; local regression dùng Node 24.19.0, khác runtime Windows được pin |
| JSON C++ | Vendored nlohmann 3.11.3, MIT/copyright trong header | Giữ nguyên byte, builder giữ copy notice/source |
| Font/icon/resources | Ba TTF/OFL đã có từ 2B.2; manifest/vector; icon gốc khôi phục có xác nhận quyền | Không thay assets khác hoặc UI |
| Test-only org.json | 20240303, SHA `3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed` | Dành cho JVM regression, không phải dependency APK mới |

[Log version/metadata](build-2c1-logs/toolchain-observed.json). Có công cụ local không đồng nghĩa runner GitHub sạch đã có SDK/MinGW/NSIS/Windows runtime. **Còn thiếu để tuyên bố build từ GitHub tái lập:** provisioning/provenance/checksum đủ bộ compiler/SDK/sysroot, môi trường build thử tách biệt, khóa tạm và cấu hình ký thử được cấp riêng, kiểm APK/PE/package sau build, máy Windows/Android thử và bằng chứng build/install/smoke thực. Không tạo/cấp secret GitHub ở 2C.1. Hosting config/release payload vắng mặt thuộc công cụ site cũ, không cần thêm để sửa native builder.

## 7. Kiểm thử, log và exit code thực

Lượt local đầy đủ: **13/11/2026 09:38:57–09:41:32 +0700**. Mỗi gate chạy setup → test → cleanup; cả 12 phase exit 0. Linux, Node 24.19.0, JDK 21.0.12.1, Python 3.12.14. ZIP64 kiểm trước mỗi lệnh: ít nhất 18 GiB đĩa/2 GiB RAM; snapshot đầy đủ trong [JSON](build-2c1-logs/local-results.json). Không giảm size/timeout/assertion, không lọc case. Giữ 101 file, 384 MiB +17 byte, RSS 300 MiB/host, đầy đủ ba suite có ca >4 GiB.

| Suite local | Exit | Giây |
| --- | ---: | ---: |
| CI runner unit ban đầu (11 test) | 0 | 0,370 |
| Asset integrity | 0 | 0,007 |
| npm unit | 0 | 0,449 |
| Harness unit | 0 | 0,463 |
| HTTP | 0 | 1,714 |
| Android host JVM | 0 | 2,136 |
| Discovery | 0 | 3,187 |
| Peer | 0 | 11,482 |
| LAN discovery | 0 | 17,064 |
| Android discovery | 0 | 1,960 |
| Security | 0 | 12,056 |
| Large transfer | 0 | 14,079 |
| Features đủ ZIP64 | 0 | 24,467 |
| Folder đủ ZIP64 | 0 | 37,790 |
| Native client đủ >4 GiB | 0 | 22,064 |

[Log đầy đủ local](build-2c1-logs/local-regression.log) đã qua sanitizer CI. Sau thêm 15 build-control tests, lệnh `python3 -m unittest discover -s tests/ci -p 'test_*.py' -v` thực chạy **26/26**, exit **0**; [log](build-2c1-logs/build-ci-units.log). Fixture chỉ là file text không phải keystore, credential giả và subprocess mock; không gọi SDK compile/sign. Kiểm tra import không spawn/mkdir, config thiếu bị từ chối trước cleanup, alias/env arguments, log/error redaction, credential chỉ tới sign, Windows-only và icon hash. Các tool-command comparison, `--help` hai script và public inventory exit 0: [audit-checks.json](build-2c1-logs/audit-checks.json).

Một lời gọi bổ sung `local-regression-after` bị người dùng ngắt trước khi có execution ledger; không có completed exit để báo PASS cho lời gọi đó. Kết quả local kể trên là lượt thực sự có log/exit; nghiệm thu sau sửa dùng đầy đủ CI của PR như mục 8, không dùng exit script thu log thay test exit.

Checksum năm file bằng chứng: [BUILD-LOG-SHA256SUMS-2C1.txt](BUILD-LOG-SHA256SUMS-2C1.txt). Log không chứa bản script gốc có mật khẩu, key, installer, env dump hoặc file truyền thử; không commit JAR/cache/classes. Quét mẫu có giới hạn, không tuyên bố scanner nhận ra mọi secret.

## 8. Tương thích Native Regression CI và nghiệm thu PR

Workflow/composite/runner cũ giữ nguyên. Python unit discovery sẵn có tự lấy thêm `test_build_security.py`; không cần cấp secrets/SDK hoặc thay workflow để chạy mock. Các gate Node/JVM không gọi script build thực; assets icon chỉ được kiểm hash. Không thay 13 lệnh cũ, assertions, protocol hoặc dependency để làm xanh.

**NOT VERIFIED tại commit chuẩn bị PR:** phải mở Draft PR, thêm `ci-zip64`, quan sát đủ Fast/Integration/Stream/ZIP64 và **Coverage / explicit verification status** trên GitHub. Phần này sẽ cập nhật sau khi đọc run/job/log/artifact thực. Không coi unit/mock/local xanh là CI GitHub xanh hoặc APK/EXE build được.

## 9. Kế hoạch Giai đoạn 2C.2 — chưa thực hiện

1. Chủ dự án duyệt build thử riêng: source commit cụ thể, provisioning đủ toolchain gốc/hash/provenance và điều kiện giấy phép phân phối liên quan; không tự nâng SDK/Node/dependency hay chuyển Gradle. Thiết kế build workflow riêng chỉ khi nhiệm vụ 2C.2 cho phép, không sửa publisher hiện tại hoặc Ruleset.
2. Dùng checkout, `<tools>` work root và VM/emulator **thử riêng**, không có app/data người dùng hoặc production secrets. Cấp toolchain đọc-only từ cache có hash; vùng payload/classes/output riêng có cleanup. Không dùng build root đang chứa payload/keystore cũ. `npm ci` đúng lock, kiểm fonts/OFL/icon/runtime pins trước build.
3. Tạo **keystore tạm cho test** ngoài Git trong nhiệm vụ được duyệt; không tạo/thay production key. App và instrumentation cùng test certificate/alias `flowdrop`; kiểm fingerprint test khác production pin, lưu chỉ fingerprint công khai. Nạp password qua secret environment, không ghi giá trị vào shell history, YAML, argv hoặc log. Không có nhánh fallback sang keystore production.
4. Chạy Android builder và instrumentation với cấu hình thử; verify signature/zipalign/badging/package/version/API, inventory ZIP không có key. APK test không phải bản cập nhật production, không cài đè bản thật; dùng emulator/thiết bị trống. Giữ APK identity/version nguồn và updater pins; nếu cần đổi chúng thì dừng xin nhiệm vụ riêng.
5. Build Windows x64 từ cùng source/icon/runtime pin, kiểm PE/installer/payload/license và metadata version. Thử Windows sandbox: startup/single instance/Explorer/Send To/discovery/transfer. Không thêm Authenticode hoặc chạy installer trên máy người dùng.
6. Chạy đầy đủ Native Regression + ma trận Windows ↔ Android, Android ↔ Android, code/folder/ZIP64/disconnect/data smoke. Android instrumentation/Gallery/MediaStore và Windows UI cần OS thật/emulator; Linux engine không thay thế. Updater phải tiếp tục từ chối APK sai cert/hash; không sửa pin để nhận gói test.
7. Chỉ giữ log/manifest/hash đã loại bí mật và artifact thử có nhãn rõ, thời hạn ngắn; không upload keystore/password hoặc gói thử vào Release/feed. Xóa khóa tạm theo kế hoạch run. Báo build command/exit/toolchain/hash và kết quả install thực; bất kỳ cert/hash/resource không khớp đều dừng, không tự thay key hoặc bỏ kiểm tra.

Không có build/installer/instrumentation-device/OS/mixed-version, reproducible-binary hoặc publish mới được chứng minh bởi 2C.1. Chỉ sau chạy thực ở 2C.2 mới có thể kết luận build thử thành công.

## 10. Diff, rủi ro còn lại và rollback

**[CHECK] 251 file đã có ở base main giữ nguyên byte**: toàn bộ production Android/Windows/Node, UI/protocol, versions, dependency/lock, iOS, public identities, workflows, AGENTS và tài liệu lịch sử. Chỉ thêm:

1. `scripts/build-installers.py`
2. `scripts/build-native-test-apk.py`
3. `scripts/native_build_support.py`
4. `desktop/windows/FlowDrop.ico`
5. `tests/ci/test_build_security.py`
6. `docs/assets/FLOWDROP-ICON-RIGHTS.md`
7. `docs/assets/NATIVE-BUILD-RESTORATION-1.13.0-2C1.json`
8. `docs/testing/BUILD-REPORT-2C1.md`
9. `docs/testing/BUILD-LOG-SHA256SUMS-2C1.txt`
10. `docs/testing/build-2c1-logs/audit-checks.json`
11. `docs/testing/build-2c1-logs/build-ci-units.log`
12. `docs/testing/build-2c1-logs/local-regression.log`
13. `docs/testing/build-2c1-logs/local-results.json`
14. `docs/testing/build-2c1-logs/toolchain-observed.json`

- **P1:** mật khẩu trong ZIP public là exposure lịch sử; trạng thái keystore/password ngoài Git chưa kiểm. Chủ dự án xử lý bảo quản/migration cùng identity; không có bằng chứng private key lộ trong ZIP.
- **P1:** build chưa thực chạy/tái lập trên GitHub; SDK/MinGW/NSIS/provisioning/hash và test signing/OS còn cần 2C.2. Helper không tự tin cậy keystore qua tên/alias; production signing cần fingerprint gate được duyệt.
- **P2:** toolchain được quan sát ngoài Git, một số version metadata/layout chưa là pin phân phối; timeouts và build work root cần nghiệm thu khi build thực. Builder vẫn dọn vùng build, phải dùng vùng thử riêng.
- **P2:** archive/log CI giữ theo retention, sanitizer kiểm theo mẫu; chưa là kiểm toán toàn bộ history/keys/OS. Icon rights đã có xác nhận chủ dự án, không gán giấy phép bên thứ ba.

Rollback bằng **PR revert commit khôi phục build/resources/test/docs**, review và chạy CI theo Ruleset. Không reset/force-push main, gỡ app, xóa dữ liệu file nhận/settings/history, đổi key/cert hoặc xóa Release/tag. Revert sẽ làm thiếu lại script/icon cho build; ứng dụng 1.13.0 đã phát hành không bị thay đổi ở PR này. Giữ Draft, chủ dự án quyết định merge; không tự merge/publish hoặc kích hoạt publisher.
