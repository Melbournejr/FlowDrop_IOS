# Native Build Verification 2C.2

Luồng build **TEST ONLY**, độc lập Native regression và publisher. Không sản xuất bản cập nhật. Giữ package/version 1.13.0 và mọi source production; Android dùng khóa thử tạm, không thể cập nhật đè production.

## Thực thi trên GitHub

- Draft PR vào `main`: thêm label **`ci-native-build`**. Thêm **`ci-zip64`** để workflow Native regression riêng chạy toàn bộ ca >4 GiB.
- Workflow mới: `.github/workflows/native-build-verification.yml`, tên **Native Build Verification**. `workflow_dispatch` có thể dùng khi file đã có trên ref được GitHub cho phép; không dispatch publisher.
- Năm job: toolchain → Android và Windows độc lập → xác minh artifact tải lại → summary luôn chạy. Draft PR được chạy bằng label; không cần chuyển Ready.
- Chỉ `contents: read`; checkout không giữ credential. Không `pull_request_target`, production secret, GITHUB_ENV, signing cache, release/tag/push-main trigger hoặc quyền ghi repository. Fork có cùng giới hạn; job cần phê duyệt chạy fork theo thiết lập GitHub vẫn phải tôn trọng.
- GitHub Actions full SHA/version được đối chiếu tag và chữ ký commit trong `ACTIONS-PINS-2C2.json`.

Artifact Android chứa APK app, instrumentation, manifest, SHA256SUMS và log đã lọc. Artifact Windows chứa NSIS EXE, manifest, SHA256SUMS và log đã lọc. Chỉ upload installer sau build + structural verification PASS. Job xác minh độc lập tải đúng artifact của chính run/attempt, yêu cầu digest-mismatch=error, kiểm lại từng SHA, apksigner, zipalign, compiled manifest, PE, icon, dependency và toàn bộ payload. Evidence thất bại được lọc riêng trước upload. Retention **7 ngày**. Không đưa artifact vào Releases/feed/publisher.

## Chạy trên Linux x86_64 riêng

Cần Python 3.12, glibc ≥2.38, `/usr/bin/curl`, `gpg`, `dpkg-deb`, ít nhất 8 GiB đĩa trống và 2 GiB RAM. CI ghim Python 3.12.16; các toolchain được tải theo lock, không lấy compiler/JDK tùy ý từ PATH.

```bash
python3 -m scripts.native_build_ci.toolchain --group all --work-root /tmp/flowdrop-2c2-tools --cache-root /tmp/flowdrop-2c2-tools/download-cache
python3 -m scripts.native_build_ci.runner --role android --work-root /tmp/flowdrop-2c2-android --cache-root /tmp/flowdrop-2c2-android/download-cache
python3 -m scripts.native_build_ci.runner --role windows --work-root /tmp/flowdrop-2c2-windows --cache-root /tmp/flowdrop-2c2-windows/download-cache
python3 -m scripts.native_build_ci.artifacts --work-root /tmp/flowdrop-2c2-verify --cache-root /tmp/flowdrop-2c2-verify/download-cache --android /tmp/flowdrop-2c2-android/export --windows /tmp/flowdrop-2c2-windows/export
python3 -m unittest discover -s tests/ci -p 'test_*.py' -v
```

Mỗi lệnh cần root mới, trống; không tái sử dụng root lỗi hoặc chọn thư mục dữ liệu cá nhân. Marker xác nhận ownership; cleanup từ chối escape/symlink. Cache chứa archive đã kiểm hash, không được chứa khóa. Chỉ chạy tool từ bản giải nén riêng; archive được chmod 0444. `finish logs` xuất evidence; `finish cleanup` chỉ xóa các child allowlist của root có marker. Không sửa HOME/CODEX_HOME. Không dùng thư mục keystore hiện có.

Runner gọi đúng builder gốc:

```text
python3 scripts/build-installers.py --only android
python3 scripts/build-native-test-apk.py
python3 scripts/build-installers.py --only windows
```

Tất cả chạy trong `work-root/source`, khác checkout Git. Password ngẫu nhiên chỉ tồn tại trong bộ nhớ/env child ký; `keytool -storepass:env` / apksigner `env:`. Khóa alias `flowdrop`, RSA3072, hiệu lực 3 ngày, xóa trong finally và cleanup; chỉ public fingerprint được ghi. App/instrumentation có cùng cert thử, khác production pin. Không cài APK thử lên máy có production.

## Nguồn và giấy phép

`NATIVE-TOOLCHAIN-LOCK-2C2.json` lưu pin, quan sát thực tế, URL, size, SHA-256, license và nhóm tải. Không commit toolchain binary.

- Debian GCC14.2 POSIX x64/Binutils2.44/NSIS3.11/7zip25.01: ba chữ ký `InRelease` → SHA-256 Packages.xz → SHA-256 từng `.deb`. Mỗi provisioning kiểm lại chain. Index mirror đổi so với pin thì BLOCKED; không chọn bản mới âm thầm. Lock/metadata cần nhiệm vụ cập nhật có review khi mirror retire package. Copyright cụ thể nằm trong `/usr/share/doc/*/copyright` của package được xác thực; toolchain chỉ chạy trong CI, không phát tán trong installer.
- Android platform35 r02/build-tools35.0.0: snapshot metadata HTTPS chính thức Google có SHA-1/size công bố. SHA-256 lock được ghi sau khi khớp giá trị công bố; **không phải SHA-256 do Google ký độc lập**. License SDK trong metadata và NOTICE của archive; không đưa SDK vào Git/artifact.
- Node24.22.2: signed SHASUMS256, signer khớp README upstream tag; Windows archive/executable khớp runtime.json baseline. Node LICENSE được đóng gói.
- Temurin21.0.13+9: published SHA-256 + detached PGP signature đã kiểm; GPL2 Classpath exception và notice đi kèm JDK. Java bytecode vẫn 8, min29/target35.
- nlohmann3.11.3, OFL font và icon giữ byte gốc. Quyền icon đã được chủ dự án xác nhận tại `docs/assets/FLOWDROP-ICON-RIGHTS.md`; không gán license bên thứ ba cho icon.

Metadata/chữ ký/key công khai trong `provenance/` là bằng chứng nguồn phân phối, không phải production signing material. Debian index ~9.7 MB tải lúc chạy, không commit. Không nhận checksum tự tính là nguồn xác thực độc lập.

## Khi có lỗi

Đọc `build-results.json`, `toolchain.json`, `commands.json`, `builder-steps.jsonl` và log theo step. Exit code child được giữ nguyên; log collector không thay thế trạng thái test. FAIL/BLOCKED/SKIPPED/NOT VERIFIED không được báo PASS. Summary thất bại nếu bất kỳ build/verification bắt buộc không success.

Phân loại toolchain/provisioning/build-control/dependency/resource/signing/source/environment. Chỉ sửa provisioning/build-control trong phạm vi; nếu production source lỗi, dừng nhánh lỗi và đề xuất PR riêng. Không giảm assertion, đổi dependency/SDK/compiler, đổi pin hoặc lấy binary release làm output.

Build thành công và cấu trúc đúng chưa chứng minh runtime tương đương. Emulator/Windows VM, GUI, single-instance, backend và uninstall là kiểm thử OS riêng của 2D nếu chưa thực chạy. Không dùng JVM/mock/Linux thay OS test.
