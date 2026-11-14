# Chạy và đọc Native Runtime Verification

Trên Draft PR, thêm ba label ci-native-runtime, ci-native-build, ci-zip64. Workflow mới chạy trên pull_request vào main; không cần merge để có runtime. workflow_dispatch là lựa chọn khi workflow đã được GitHub đăng ký; không dùng publisher. Không đổi Ruleset/required checks hoặc cấp quyền ghi.

Đợi cả Native Runtime Verification, Native Build Verification và Native Regression hoàn tất tại đúng SHA head của PR. Trong regression phải có Coverage / explicit verification status PASS và Large / full ZIP64 above 4 GiB thực chạy. Summary opt-out ghi SKIPPED không phải runtime PASS.

Mở run → Artifacts ở cuối trang. Runtime có ba ZIP FlowDrop-2D1-Runtime-windows/35/29-run-attempt. Mỗi ZIP có results.json, test-matrix.json, commands.json (actual command/exit/timeout), per-step log, evidence-manifest.json và SHA256SUMS.txt. So SHA256SUMS sau giải nén; đối chiếu reviewed_head với SHA PR và checkout_commit với source manifest của same-run build. PR checkout có thể là virtual merge SHA, khác head review; điều đó được ghi rõ.

App/instrumentation phải lấy cùng build artifact Android của run, cùng test certificate; không trộn với APK của Native Build Verification run khác. TEST ONLY giữ package/version production nhưng certificate khác: không cài lên điện thoại đang có bản production. Windows guard cũng từ chối máy/profile có FlowDrop. Retention artifact 7 ngày; manifest/log snapshot đã lọc được lưu trong Git.

Runtime entrypoints chỉ chấp nhận fresh GitHub-hosted VM, không chạy trên workstation của chủ dự án hoặc giả môi trường bằng cách đặt biến GITHUB_*. Chỉ emulator-5554/ADB server5039 do job tạo. Thiếu KVM/desktop/resource phải BLOCKED/NOT VERIFIED đúng thực trạng; JVM, Wine và cross-compilation không thay OS proof.

Local unit/harness:

    python3 -m unittest discover -s tests/ci -p 'test_*.py' -v

Suite có HTTP loopback fixture, cần sandbox hỗ trợ socket. Nếu bị chặn bind phải ghi lỗi và chạy nguyên suite trong môi trường có quyền mạng; không skip. Local unit/mock và Java/C++ compile không được gọi là Android/Windows runtime. Runtime builder tái sử dụng 2C.2 và chỉ compiled test copies dùng reviewed selector/driver/fixture adaptation; bản Git gốc và production source không đổi.

Khi lỗi, đọc case status và child exit trước log collector. Android chỉ PASS khi am instrument có process0, terminal INSTRUMENTATION_CODE:-1 và result.passed=true. stdout của adb exit0 khi instrumentation fail vẫn phải FAIL. Dữ liệu transfer tổng hợp cần SHA đúng, URI/file riêng khi collision, no partial publication, auth denial, lifecycle và cleanup đúng. Không giảm test/assertion/size/timeout/pin.

Chỉ export logs/screenshots allowlisted đã screen, không desktop-state/capability/password/key/keystore/AVD/userdata/cache hoặc environment dump. Screenshot ban đầu trước code; đợi Activity hiện và splash biến mất. Không đưa ảnh sau transfer chứa code vào Git/artifact.

Các báo cáo JSON/MD trong Git ghi snapshot head đã thực kiểm, không gắn nhãn lại cho commit khác. Sau commit báo cáo phải chạy CI lại; PR body được cập nhật sau cùng với SHA head thật, URL ba run và artifact của head đó. Artifact run cuối là bằng chứng source-bound chính xác cho commit bàn giao, tránh self-SHA recursion trong file báo cáo.

Thiết bị thật/Android16/OEM/ARM/Win10/11/Wi-Fi multicast và cross-platform LAN vật lý, production signing/update-install không nằm trong claim emulator/server. Chỉ đề xuất kiểm tiếp, không triển khai Phase2D.2/3 trong PR này. Giữ Draft; không merge, publish hoặc nâng version.
