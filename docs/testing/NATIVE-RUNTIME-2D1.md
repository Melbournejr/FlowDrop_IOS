# Chạy Native Runtime Verification

Dùng Draft PR từ baseline9171e7f, thêm `ci-native-runtime`, `ci-native-build`, `ci-zip64`. Workflow runtime tự build artifact của đúng source/run và chạy windows-2025/Android35/Android29. Không cần production secrets; không dispatch publisher. Đọc Native Runtime Verification summary và từng matrix, không coi SKIPPED do chưa opt-in là runtimePASS.

Chạy unit/harness trên local:

```bash
python3 -m unittest discover -s tests/ci -p 'test_*.py' -v
```

Đây là unit/mock, không OS proof. Các runtime entrypoints chỉ chấp nhận môi trường GitHub-hosted đúng nền tảng, app profile trống và emulator riêng. Không chạy trên máy đang có FlowDrop production. Linux thiếu KVM không thể thay bằng JVM/Wine; dùng GitHub runner hoặc xin môi trường thử riêng trong nhiệm vụ tiếp theo.

Artifact build có SHA256SUMS và producer manifest; app/test dùng cùng certificate TEST ONLY, không cài đè production. Runtime evidence artifact gồm test-matrix.json, results.json, commands.json, per-step logs, screenshot đầu phiên khi có, evidence-manifest.json và SHA256SUMS. Không lưu state/capabilities/keystore/adbkey/userdata. Giữ7ngày.

Nếu thất bại, đọc case status, command exit/timeout và sanitized log. Test Android phải có INSTRUMENTATION_CODE:-1 và result.passed=true; adb process exit0 đơn độc không đủ. Phân biệt emulator/KVM/desktop blocker, harness stale selectors và production failures. Không skip/assertion giảm/đổi pin để làm xanh. Giữ raw evidence ngoài Git, chỉ đưa bản đã screen/checksum vào PR.
