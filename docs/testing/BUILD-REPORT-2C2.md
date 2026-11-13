# FlowDrop — Native build verification 2C.2

Ngày lập: **13/11/2026**. Phạm vi: build **TEST ONLY**, không phát hành.

**Các điều kiện build bắt buộc đạt PASS tại mốc bằng chứng `a2292ef7aff2fd49d7053e23f5e0c52a300a37ff`.** Local và GitHub thực build APK app, instrumentation, Windows EXE; verifier độc lập và toàn bộ Native Regression/ZIP64/Coverage đạt. [Draft PR #9](https://github.com/Melbournejr/FlowDrop_IOS/pull/9) giữ Draft. Bản báo cáo này đóng bằng chứng của mốc đã chạy; sau commit tài liệu sẽ kiểm lại cả hai workflow trên head bàn giao cuối và ghi URL/head/status cuối trong PR body. OS smoke/runtime và production signing equivalence vẫn **NOT VERIFIED**.

## 1. Điều kiện, base và head

- PR [#8](https://github.com/Melbournejr/FlowDrop_IOS/pull/8) đã merge lúc `2026-11-13T04:05:58Z`; main/base **`c502c2f8793839e7f10289bf051df06dd1c466a0`**. Nhánh riêng `build/native-verification-2c2`, được kiểm chưa tồn tại trước khi tạo. Không push main.
- Ruleset `protectMain` ID **27172303**, **active**, target `~DEFAULT_BRANCH`, strict required check **Coverage / explicit verification status**, integration15368, không bypass actors. Chỉ đọc; không sửa settings.
- PR #1 vẫn open, head `2ccf9248ed6de184a200a950e1d37dd1e5b11741`; 11 file security/iOS/ruleset riêng, không trùng đường dẫn thay đổi nhiệm vụ. Không sửa/merge PR #1.
- Đã đọc AGENTS root (không có AGENTS con), audit/architecture/protocol/features/release/regression/baseline/import/harness/asset/CI/build2C1/rights, restoration manifest, ba script build-control, tests/ci, runtime.json, security/README và workflow hiện có.
- [Snapshot bảo toàn](../build/NATIVE-SOURCE-BASELINE-2C2.json): 262/265 file base được kiểm SHA-256 trước mỗi build; ba file còn lại là build-control được phép sửa tối thiểu. Không có app source production, iOS, UI/font/icon, package/dependency/lock, version/public pin hoặc workflow cũ nào đổi byte. Kiểm public key inventory thực exit0; Android cert/RSA update/Ed25519 project fingerprints giữ nguyên. Diff-check source/test/workflow/docs điều khiển exit0; raw evidence log/metadata ký giữ byte gốc nên có whitespace do công cụ, không normalize chữ ký hoặc giả log.
- Local build sử dụng snapshot working tree trên base nêu trên, **chưa phải build một commit Git hoàn chỉnh**. `artifact-manifest.json` ghi checkout SHA và uncommitted paths thực tế. Mốc GitHub đã chạy: **head `a2292ef7aff2fd49d7053e23f5e0c52a300a37ff`**, checkout merge `8d812c53eb8d35b362f3cdee6663301fbae6c773`, uncommitted paths rỗng; không nhầm merge SHA với PR head. Commit đóng evidence tài liệu tạo head mới; kết quả kiểm lại head cuối nằm trong PR body để tránh vòng lặp tự ghi SHA của chính commit.

## 2. Phạm vi file

Thêm workflow độc lập `.github/workflows/native-build-verification.yml`; provisioning/ownership/log/artifact verifiers trong `scripts/native_build_ci/`; unit regression `tests/ci/test_native_build_pipeline.py`; toolchain/source/action pin manifests, public provenance và hướng dẫn ở `docs/build/`; báo cáo/manifest/SHA/log ở `docs/testing/`.

Chỉ sửa ba file có sẵn: `scripts/build-installers.py`, `scripts/build-native-test-apk.py`, `scripts/native_build_support.py`. Không xóa file. Diff/inventory đầy đủ được xuất trong `build-2c2-logs/changed-files.txt` tại mỗi commit evidence; thay đổi tài liệu sau đó được Git PR diff thể hiện. Không sửa `.github/workflows/native-regression.yml`, composite action, publisher hoặc iOS workflow.

## 3. Toolchain, URL, checksum và provenance

[Lock đầy đủ](../build/NATIVE-TOOLCHAIN-LOCK-2C2.json) ghi 25 archive cụ thể, byte, SHA-256, URL, license, pin và nhóm tải; [hướng dẫn](../build/README-2C2.md) giải thích chain và cách chạy. Không commit toolchain binary.

| Thành phần | Pin | Quan sát thực chạy local |
|---|---|---|
| Android platform | 35, revision2/ext13; platform-35_r02.zip | Layout android-35, android.jar được dùng bởi aapt2/javac |
| Android build tools | 35.0.0; build-tools_r35_linux.zip | aapt2 2.19-11948202; D8 8.6.2-dev (abaab469…); apksigner0.9; zipalign exit0 |
| Java | Temurin21.0.13+9 | 21.0.13+9-LTS; javac module từ chính JDK này |
| Windows compiler | Debian MinGW-w64 POSIX x64 GCC14.2.0-19+27+b1 | driver `-dumpfullversion` = `14-posix`; target x86_64-w64-mingw32; không gọi output này là literal14.2.0 |
| Binutils/windres | 2.44-3+12+b1 | GNU windres2.44 |
| NSIS | 3.11-1 | v3.11-1, compiler thực exit0 |
| Windows Node | 24.22.2, giữ runtime.json | archive/executable SHA khớp pin |
| Linux Node đóng gói npm | 24.22.2 | v24.22.2 |
| 7zip kiểm NSIS | 25.01+dfsg-1~deb13u2 | 25.01; binary lib/7zip riêng, không dùng wrapper /usr/bin của host |
| Python | CI3.12.16 | local3.12.14; GitHub3.12.16 |
| nlohmann/npm | vendored3.11.3; 8 dependency theo lock | source header/package-lock giữ byte; npm ci exit0; payload versions khớp |

Bằng chứng độc lập: Debian ba chữ ký InRelease → hash Packages.xz → hash từng .deb; Node signed SHASUMS + signer trong README tag; Adoptium publishedSHA256 + detachedPGP + release asset digest. Mỗi provisioning kiểm lại chữ ký và metadata records trước khi giải nén/chạy. Google metadata HTTPS công bố **SHA-1/size**; SHA-256 được ghi sau đối chiếu, **không được gọi là SHA-256 do Google ký**. Public keys chỉ của nhà phân phối, không phải production app keys.

Các license: SDK license/NOTICE chính thức; JDK GPL2 Classpath exception; Debian package copyright đi kèm (GCC runtime exceptions, Binutils GPL, NSIS/7zip theo notice từng package); Node LICENSE được đóng gói; nlohmann header/license, OFL và icon nguyên bản. Icon có quyền đã được chủ dự án xác nhận ở [tài liệu rights](../assets/FLOWDROP-ICON-RIGHTS.md), không gán license bên thứ ba. Không phân phối SDK/compiler/JDK cùng app artifact.

## 4. Môi trường, cô lập và bảo vệ bí mật

Linux x86_64, glibc2.41, RAM hiệu dụng8GiB; root sạch riêng cho Android, Windows và verifier. Preflight ≥8GiB free/2GiB RAM cho build; không dùng cache toolchain/keystore cũ của dự án. Archive tải mới từ nguồn pin, chmod0444; bản giải nén làm việc riêng nhận chmod của builder Android.

Checkout được snapshot từ Git inventory vào owned work-root/source sau kiểm262 hash. Không copy .git, artifact, dependency cache hoặc signing file. Path/ZIP/TAR kiểm traversal, absolute paths, symlink/special/encrypted/duplicate entries trước giải nén. Debian internal links được relocate có ràng buộc; không ghi qua link.

Java/compiler/SDK/NSIS/7zip là path trong tool root đã xác thực; PATH điều khiển và loại biến injection. Node Linux gọi npm-cli tuyệt đối; npm ci dùng lock nguyên bản, ignore-scripts, registry HTTPS, cache mới và npmrc trống riêng. Không dùng dữ liệu người dùng.

Keystore **mới, thử nghiệm**, ngoài checkout, thư mục0700/umask077, alias flowdrop, RSA3072, SHA256withRSA, hiệu lực3ngày. Password ngẫu nhiên chỉ trong bộ nhớ/env child; argv chỉ có tên env, không password. Child compiler không nhận signing env. Đối chiếu DER SHA công khai khác pin production, app/test ký cùng cert. Khóa xóa trong finally trước export, không Git/cache/artifact/GITHUB_ENV; không đọc/yêu cầu key/password production.

Mỗi tool có timeout/exit code thực; outer Journal có process-group termination. Output cũ/classes/dex được dọn trước build có ownership/path guard. Export chỉ installer TEST ONLY đã verify, JSON/hash/log đã lọc; quét marker private key/PAT/password thử trước upload. Cleanup chỉ child allowlist trong root có marker; không delete dữ liệu người dùng.

## 5. Lệnh build thực chạy và exit code

Trong snapshot riêng, runner đã gọi:

```text
python3 scripts/build-installers.py --only android          exit 0
python3 scripts/build-native-test-apk.py                     exit 0
python3 scripts/build-installers.py --only windows          exit 0
```

Wrapper lệnh đầy đủ, path, timeout, duration, raw child returncode và SHA từng log nằm tại `build-2c2-logs/{android-verified,windows-verified}/commands.json`; chi tiết compile/sign tại `builder-steps.jsonl`. Đây là **thực chạy local**, không phải mock hoặc log mô phỏng.

| Bước thực | Số lệnh | Exit |
|---|---:|---|
| App aapt2 compile/link, javac, D8, zipalign, sign, signature verify, alignment verify | 9 | tất cả0 |
| Instrumentation aapt2 link, javac, D8, zipalign, sign + verifier ngoài script | 5 + verifier | tất cả0 |
| windres, g++-posix, makensis | 3 | tất cả0 |
| npm ci khóa package-lock | 1 | 0 |
| app/test apksigner, zipalign, badging, compiled XML | 8 | tất cả0 |
| NSIS list/extract | 2 | tất cả0 |
| Verifier workspace độc lập kiểm lại cả hai export | 1 wrapper, nhiều tool | 0 |

Bytecode kiểm **69 app classes và12 instrumentation classes**, major52 (Java8). Không đổi compiler flags, D8/min29, package, version, resource, source, protocol hay signing scheme.

## 6. Android artifact thực

| Artifact local | Byte | SHA-256 |
|---|---:|---|
| FlowDrop-1.13.0-Android-TEST-ONLY.apk | 279316 | 9cd01fdef70602772a4c3c39cd45ba394236255ebc9801eb921e9a94d29b0871 |
| FlowDrop-1.13.0-Android-Instrumentation-TEST-ONLY.apk | 33171 | 6fee09b102f64240be3e9c9a47113d88198fe4c2abad4dcb49be8f97bce59bd2 |

Test certificate SHA256 **`94fa0d5499f964dd901726008553b3d4eead89b231189b7cb6424b3a99e1c534`**, chung app/instrumentation, khác production **`65cbed4feb375d2c3c2eb94e668bd7aaee7ce5b24f436887873a6fa11719f97f`**. Fingerprint/byte/hash sẽ thay giữa run do key tạm, không dùng bảng local này để gán fingerprint cho CI.

Công cụ thực kiểm: app package **app.flowdrop.mobile**, versionName1.13.0, versionCode14, min29/target35, đúng11 permissions baseline; test package app.flowdrop.mobile.test và bốn instrumentation declarations, SDK29/35. Test manifest gốc không khai versionName/versionCode; không tự thêm. Manifest binary, DEX header/SHA1/Adler32, ZIP CRC, resource/font/OFL inventory đầy đủ. Không keystore, password/private key hoặc test payload không cần thiết trong APK app. Instrumentation chỉ ở APK riêng.

## 7. Windows artifact thực

`FlowDrop-Setup-1.13.0-Windows-x64-TEST-ONLY.exe`: **24527415 byte**, SHA256 **`ab861a3f9eba4aebfca6563be4aba65a3a668337718e54671a8b24f2e0be3630`**.

Native FlowDrop.exe từ C++ hiện có: **PE AMD64/x64, Windows GUI subsystem2**, version1.13.0.0, không Authenticode. Sáu ảnh PNG icon/RT_GROUP_ICON và manifest nhúng đối chiếu nguyên byte nguồn. **NSIS bootstrap là I386/x86 theo baseline**, không được nhầm với app x64 được cài.

Node Windows archive SHA `ca1bff5d8ead13c9f2ea404a176db46bd430704d5b5113734049fa365e7799e2`; node.exe SHA **`1c331340fa6cac5e4294725959070a143fa0507195a78ad77eed7943f719aac9`**. npm payload8 package đúng lock; web/worker/font/OFL,15 LAN/discovery/security/update/folder scripts, startup/stop/LAN scripts, licenses và hướng dẫn đầy đủ.

7zip thực list/extract: **128 payload files** (gồm bản dereference .bin link npm nội bộ) khớp SHA với payload mới. Ba NSIS wizard/plugin files khớp distribution đã xác thực; từ chối file thừa. Không secret/cache/toolchain/classes/objects/keystore. Giữ byte NSIS/source nên đường dẫn install/data, SendTo, single-instance, startup/shutdown, uninstall/update không đổi theo source; **chưa xác minh hành vi OS thực**.

## 8. So sánh Release1.13.0

Tải lại APK/EXE chính thức chỉ làm đối chứng read-only, đối chiếu byte/SHA theo RELEASE-PROCESS; không thực thi/cài và không dùng làm output build. [Kết quả thực](build-2c2-logs/release-reference-comparison.json).

- APK reference đúng279316byte/hash42b6b774…; cert production khớp pin. Compiled identity, permissions/SDK và ZIP inventory path của APK thử khớp; **mọi entry trừ META-INF/FLOWDROP.RSA giữ SHA**, gồm DEX và manifest/resource/font. APK signing block ngoài ZIP cũng không được coi là giống production.
- EXE reference đúng24521113byte/hash576c3aeb…; bootstrapI386/appAMD64 GUI2; node.exe đúng pin. Các entry chung chỉ khác **FlowDrop.exe** (build mới) và **node_modules/.package-lock.json** (metadata npm ci sinh lại); package-lock nguồn và dependency versions không đổi.
- Production installer chứa thêm ba file mẫu **shell-smoke/*.txt** (tên Unicode được ghi JSON), không có trong source baseline/payload sạch. Không nhập/chỉnh Release để xử lý. Build thử không mang theo dữ liệu mẫu đó. Đây là inventory difference phải ghi nhận, không báo payload bit-identical.

| Mức tương đương | Kết luận |
|---|---|
| Source equivalence | PASS cho262 protected base files;3 build-control sửa có kiểm soát |
| Build success | PASS local và GitHub Android/test/Windows, exit0 |
| Artifact structural equivalence | PASS cho identity/SDK/permission/resource/PE/runtime; có inventory differences công bố phía trên |
| Runtime equivalence | NOT VERIFIED; Linux/JVM không thay Android/Windows OS |
| Production signing equivalence | NOT VERIFIED; cố ý dùng cert thử khác, không đụng production key |
| Reproducible binary | NOT VERIFIED; không tuyên bố SHA APK/EXE giống production |

## 9. Regression và CI

**Unit/mock:** 40/40 Python CI unit đã thực chạy exit0 (26 cũ +14 mới), bảo vệ stale APK/classes, path/link/cleanup, key purpose/prod pin, Java path, download checksum, badging, multi-signer, artifact tamper/secret và child exit. Các mock/fixture không được coi là build thật.

Workflow mới chỉ PR opt-in ci-native-build/workflow_dispatch, contents:read, fullSHA Actions, không production secrets/publisher/release. Năm job và timeout16–25phút, artifact retention7ngày, separate logs/cleanup và summary fail nếu mandatory job không success. Fork không có đường cấp repository write/production secrets. [Hướng dẫn chạy/lỗi](../build/README-2C2.md).

**GitHub Actions thực chạy trên Draft PR**, nhãn ci-native-build + ci-zip64, head **a2292ef7aff2fd49d7053e23f5e0c52a300a37ff**:

| Workflow/job | Run/job | Kết quả thực |
|---|---|---|
| Native Build Verification | [run #4](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43384264087) | **5/5 success** |
| Toolchain | [131748978917](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43384264087/job/131748978917) | 25 authenticated archives, version probes, cleanup success |
| Android app + instrumentation | [131749211738](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43384264087/job/131749211738) | build14 tool calls + signature/alignment/manifest verification, tất cảexit0 |
| Windows | [131749211765](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43384264087/job/131749211765) | npmci + windres/g++/NSIS + extract, tất cảexit0; payload128 file |
| Independent artifact verification | [131749689101](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43384264087/job/131749689101) | same-run downloads + fresh tools, APK/PE/payload checks PASS |
| Build verification summary | [131749897191](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43384264087/job/131749897191) | mandatory job outputs đều PASS, job success |
| Native regression | [run #13](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43384264145) | **5/5 success** |
| Fast | [131748985687](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43384264145/job/131748985687) | ci-unit40/40 + asset integrity + npm unit + harness,4 command exit0 |
| Integration | [131749124470](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43384264145/job/131749124470) | HTTP/Android-host/discovery/peer/LAN/Android-discovery/security,7 command exit0 |
| 101 files /384MiB+17 | [131749124648](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43384264145/job/131749124648) | large-transfer exit0 |
| ZIP64 >4GiB | [131749124592](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43384264145/job/131749124592) | features/folders/native-client,3 command exit0, không skip |
| Coverage / explicit verification status | [131749684828](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43384264145/job/131749684828) | **PASS**, ZIP64 được yêu cầu và thực chạy |

Đã đọc cả10 job logs/API; tải **7 archive** (hai build, independent và bốn regression) bằng kết nối GitHub hợp lệ, đối chiếu API digest trước ZIP path/type/CRC và SHA từng file. Không lấy exit của collector thay test. Có `results.json`/per-case logs/cert/inventory/commands trong [evidence GitHub](build-2c2-logs/github-a2292ef/); không lưu environment dump. Upload và cleanup đều success. Hai log đã lọc Coverage/summary chỉ lưu trạng thái công khai, không giả stdout test.

Regression giữ **13 command Node/JVM gốc +2 guard =15 command**, 101file,384MiB+17,RSS300MiB/host, assertions/timeouts/SHA nguyên. ZIP64 preflight thực ~91.5GB free/16.76GB RAM, vượt18GiB/2GiB yêu cầu. Features4/4 và folders5/5, skipped0; native-client truyền file **4295098385byte** ở Android JVM host. Đây là engine/JVM test, không phải Android OS. Coverage workflow cũ có câu installer NOT VERIFIED vì scope cũ không build; kết quả build mới được chứng minh riêng, không sửa workflow cũ.

Artifact CI ở run4 (không nhầm với local hoặc run sau):

| Artifact | Byte | SHA-256 |
|---|---:|---|
| APK app | 279316 | d5c45a4cc8c78baa15b48987b2fd7dac5c0226ec795144c305b738679939dbca |
| APK instrumentation | 33171 | 6fa7dd1905829585a850a2152223257ec38f464b81fad218dabd966f1b1f3bc5 |
| Windows NSIS | 24528373 | 55cd76c50316d6fbe22754ffb1038c073cfb5a05a67735d2e272a9a1b9021a28 |

Cert thử CI **c5ddb26b6c6679ed9c4c8b24d0e420268306f7b6619f6052c8ed619916ba0343**, app/test cùng cert; app69/test12 Java8 classes. [Android archive](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43384264087/artifacts/14017748408) SHA8570604f…, [Windows archive](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43384264087/artifacts/14017807537) SHAa78f9bc0…; manifest đầy đủ hash/byte/artifactID. Cùng128 payload path local/CI, chỉ FlowDrop.exe khác byte; runtime/dependency/script/font giữ byte. Mỗi run có manifest/fingerprint riêng; artifact giữ7ngày đến20/11/2026.

Run #2 build trước opt-in chỉ summary success với các build SKIPPED, **không** được tính build PASS. Run #3 build và #11/#12 regression bị concurrency hủy khi thêm label; **không** tính PASS. Không dispatch publisher, không build từ binary release.

**Local Node/JVM:** setup mới đã exit0 (Node24.19.0,JDK21.0.12.1,Python3.12.14,pinnedorg.json,8 lockednpm). Gate chưa được dùng làm bằng chứng PASS ở lần ghi này. Local ZIP64 chưa chạy lại vì còn ~12GiB free, thấp hơn preflight18GiB của runner; không hạ ngưỡng. Toàn bộ CI phải chạy trên runner riêng đủ tài nguyên.

## 10. OS smoke

**NOT VERIFIED.** Môi trường local Linux không có /dev/kvm, Android emulator/adb hoặc Windows VM/Wine phù hợp. Không cài lên máy/điện thoại production. Chuyển cài APK/launch/crash/four instrumentations/permissions và Windows silent install/launch/process/backend/single-instance/SendTo/uninstall sang2D trong emulator/hostedWindows riêng. Không dùng unit/JVM/Linux làm kết quả OS.

## 11. Lỗi build-control phát hiện và sửa

| Lỗi/điều kiện tái hiện | Trước | Sửa tối thiểu / sau |
|---|---|---|
| Build app thất bại sau output cũ | unit giữ staleAPK, FAIL | xóa đúng target trước compiler; unitPASS |
| Rebuild instrumentation sau classes cũ | unit vẫn giữ Old.class, FAIL | fresh owned classes/dex/root; unitPASS |
| Verification nhận keystore sai thư mục | unit không từ chối, FAIL | purpose/test-root/cert-pin guard; unitPASS |
| Java qua PATH không kiểm soát | unit chọn java tương đối, FAIL | pinned absoluteJDK; unitPASS |
| TAR hardlink compiler mất execute mode | actual provision PermissionDenied; unit0600 vs0755 FAIL | bảo toàn executable bit của authenticated member; fresh provision/buildPASS |
| G++ driver dumpfullversion format | provision mong14.2.0, nhận14-posix | phân biệt packagepin14.2.0 và driverobserved14-posix; không thay compiler |
| aapt2 badging35 dùng minSdkVersion | verifier BLOCKED sau buildexit0 | parser hỗ trợ tên minSdkVersion và sdkVersion cũ; unit+APK thựcPASS |
| Debian7z wrapper dùng absolutehost path | nsis-list exit127 sau buildexit0 | gọi authenticated lib/7zip/7z; actualextractPASS |

Giữ log thất bại và unit trước/sau; không sửa production để ép build/test xanh. Không thay dependency/resource/key/version; không skip/assertion giảm. Lượt failed provision/build-verifier không được tính PASS.

## 12. Rủi ro và giới hạn

- **P0:** không phát hiện mới trong phạm vi; không có kết luận hệ thống hết lỗ hổng hoặc production private key an toàn ngoài Git.
- **P1:** chưa OS smoke/runtime/production signing/update lifecycle. APK thử cùng package/version nhưng cert khác không được cài đè production; key thử bị hủy. Password cũ trong SourceZIP công khai là rủi ro lịch sử, không có bằng chứng mới private key lộ; không tự rotate.
- **P2:** Google chỉ công bố SHA1/size qua HTTPS; Debian mirror/index có thể retire/đổi và lock sẽ BLOCKED. Cần nhiệm vụ review refresh manifest, không silent upgrade. Production NSIS còn3samplefiles; cân nhắc PR release-hygiene riêng. Compiler/JDK pin mới không chứng minh binary reproducibility.
- **P3:** artifact tạm7ngày, checksum/cert thay mỗi run; tải/giữ evidence công khai khi cần. Metadata npm phụ thuộc phiên bản npm đi kèm Node pin; lock ứng dụng giữ nguyên.

## 13. Rollback và Giai đoạn2D

Rollback bằng **PR revert các commit2C.2** (tắt workflow build mới bằng revert file), giữ protectMain/required checks; không push/reset main, không xóa Release/tag/feed, không đụng key/data/app production. Native Regression/iOS/publisher cũ vẫn nguyên byte. Không có production deployment cần rollback ở giai đoạn này.

2D: emulator/device thử sạch, chạy bốn instrumentation, Windows hostedVM với guard không có FlowDrop/data sẵn; kiểm install/GUI/backend/single-instance/SendTo/uninstall bảo toàn data; test LAN Android↔Windows/Android↔Android; update test-signed feed riêng và public pin policy trong nhiệm vụ được duyệt. Không dùng key/feed production.

Quyết định chủ dự án: duyệt Draft PR; chọn môi trường OS2D; quy trình bảo quản/migration signing credential lịch sử nếu cần; lịch review lock khi distribution retire package. Không cần cung cấp production secrets để nghiệm thu build thử này.

[Artifact manifest](BUILD-ARTIFACT-MANIFEST-2C2.json) · [Log checksums](BUILD-LOG-SHA256SUMS-2C2.txt) · [Log folder](build-2c2-logs/). Báo cáo ghi mốc evidence đã chạy; CI/head bàn giao cuối được kiểm lại và ghi trong PR body sau commit tài liệu. PR giữ Draft; **không merge/publish/nâng version/đổi production key**.
