# FlowDrop — CI kiểm thử tự động, Giai đoạn 2B.3

Ngày quan sát: **12/11/2026**. Nhánh `ci/native-regression`, base main [`3797b8bbcad50eb47109cb3b92a70112a21327b3`](https://github.com/Melbournejr/FlowDrop_IOS/commit/3797b8bbcad50eb47109cb3b92a70112a21327b3).

## Kiểm toán trước thay đổi

**[API/Git]** PR #6 đã merge ở commit base trên; remote main được đối chiếu trước tạo nhánh mới, không ghi đè nhánh. Đã đọc AGENTS, REGRESSION-PLAN, REGRESSION-HARNESS và ASSET-REPORT-2B2. Nguồn Windows/Android/Node, test và ba font baseline đã có trên main.

**[API/source]** PR #1 vẫn mở, head `security/github-hardening-2026-11-11` / `2ccf9248ed6de184a200a950e1d37dd1e5b11741`. Đã đối chiếu danh sách 11 file và policy `audit_workflows.py`, workflow security-checks/CodeQL/CODEOWNERS của PR đó. Không trùng đường dẫn thay đổi; CI mới có tên/concurrency riêng, contents chỉ read, full-SHA Actions, checkout không giữ credential và không dùng pull_request_target. Chạy hàm policy của PR #1 đối với workflow mới: không có lỗi. Không sửa hoặc merge PR #1; workflow iOS/publisher hiện tại giữ nguyên. Đây là kiểm tra tương thích policy mới, không xác nhận toàn bộ policy/Settings hiện tại đã triển khai.

**[Yêu cầu]** Chủ dự án đã giải quyết mâu thuẫn quyền bằng lựa chọn **chỉ `contents: read`, không quyền ghi**. Workflow tuân theo lựa chọn đó.

## Thay đổi

- Workflow test riêng: PR vào main và manual; Fast, Integration tuần tự discovery, Stream 101 file/384 MiB và ZIP64 opt-in. Coverage ghi NOT VERIFIED rõ khi ZIP64 chưa chạy.
- Composite cài Node 24/Temurin 21/Python 3.12; JAR 20240303 kiểm checksum, `npm ci` giữ lock và tắt lifecycle scripts. Không cần khóa thật hoặc build installer.
- Runner Python giữ exit child, timeout/process group, resource preflight, log đã loại token và cleanup vùng thử thuộc sở hữu. 11 unit tests riêng chống false PASS, sai hash, timeout và cleanup không an toàn. Guard tài nguyên dùng manifest font sẵn có.
- [Hướng dẫn CI](NATIVE-CI.md) và [bằng chứng ghim Actions](CI-ACTION-PINS.json). Tất cả SHA lấy từ release/tag chính thức, resolve tới commit và API chữ ký verified; metadata cả năm Action dùng Node 24.

Không sửa logic production, protocol, UI/asset, signing/cert/key, iOS, dependency/lock, test/helper cũ hoặc workflow cũ. Không xóa/skip test, giảm assertion hoặc file size. Không build APK/EXE, publish, merge hay kích hoạt publisher.

**[Git/check]** Đối chiếu byte đủ **244 file** sẵn có với base: tất cả giữ nguyên. Chỉ thêm bảy file: workflow, composite setup, hai Python runner/unit, pin provenance và hai tài liệu CI. Không có binary, cache, fixture data, JAR hoặc log raw được stage. Quét mẫu private-key/PAT ở file mới và UUID/PAT trong log đã sanitize: không có finding; đây là kiểm tra mẫu, không phải chứng nhận không tồn tại mọi loại bí mật.

## Kiểm thử thực chạy trong Codex

Linux; Node **v24.19.0**, Java **21.0.12.1**, Python **3.12.14**. Mỗi gate chạy cả setup → test → cleanup, mỗi phase exit **0**. JAR hash `3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed`. Trước các ca ZIP64 có khoảng **19,28 GiB** trống, cgroup RAM **8 GiB**, vượt preflight 18 GiB/2 GiB. Không thay size/timeout gốc để đạt.

| Gate | Suite | Exit thực | Thời gian lệnh |
| --- | --- | ---: | ---: |
| Fast | CI runner unit (11 test) | 0 | 0,391s |
| Fast | Asset integrity (TTF/OFL/manifest) | 0 | 0,007s |
| Fast | npm unit | 0 | 0,610s |
| Fast | Harness unit | 0 | 0,385s |
| Integration | HTTP | 0 | 1,708s |
| Integration | Android host JVM | 0 | 3,003s |
| Integration | Discovery | 0 | 2,913s |
| Integration | Peer | 0 | 11,898s |
| Integration | LAN discovery | 0 | 18,434s |
| Integration | Android discovery | 0 | 2,372s |
| Integration | Security | 0 | 12,663s |
| Stream | Large transfer | 0 | 15,307s |
| ZIP64 | Features (đủ file test) | 0 | 22,064s |
| ZIP64 | Folders (đủ file test) | 0 | 35,089s |
| ZIP64 | Android native client JVM | 0 | 22,711s |

**[TEST] 13/13 lệnh Node/JVM cũ đạt**, cộng hai guard mới đạt. Không có suite cũ bị sửa; so với 13/13 ở báo cáo 2B.2 không có lệnh chuyển sang lỗi trong lượt này. Các assertion cố tình lỗi trong unit fixture của runner không phải lỗi sản phẩm: unit xác nhận trả exit 7/124/127/78 đúng, không giả PASS.

**[CHECK]** actionlint **1.7.12**, binary tải từ release chính thức và kiểm checksum trước chạy; `actionlint -shellcheck= .github/workflows/native-regression.yml`: exit **0**. Không có ShellCheck cài sẵn nên static check này không bao gồm ShellCheck. Policy workflow PR #1: exit 0, không lỗi. Kiểm tra static không được coi là bằng chứng Actions đã chạy.

## GitHub Actions

**NOT VERIFIED tại commit chuẩn bị PR:** chưa có run của workflow mới. Phải tạo Draft PR, xác nhận sự kiện PR thực sự tạo run, bật label `ci-zip64` cho đợt nghiệm thu, rồi đối chiếu job/step/log/artifact và exit từng suite. Phần này sẽ cập nhật bằng run URL/kết quả thực tế sau quan sát; không coi kết quả Codex là kết quả runner GitHub.

## Rủi ro, giới hạn và rollback

- Ubuntu hosted cần internet tới Actions/toolchains/npm/Maven và multicast nội bộ; upstream/toolchain patch có thể thay đổi dù dependency ứng dụng/JAR và mã Action đã ghim. Ghi version trong artifact; không âm thầm đổi pin để chữa lỗi.
- Nhóm >4 GiB không mặc định trên mọi PR; job Coverage ghi NOT VERIFIED nếu chưa chọn. Không thể tuyên bố đủ suite khi chỉ Fast/Integration/Stream đạt. Runner thiếu tài nguyên thất bại preflight, không giảm file.
- Logs chỉ giữ 7 ngày; sanitation có test nhưng không thể suy rằng mọi định dạng bí mật tương lai đều được nhận diện. Không cấp signing keys/production secrets cho CI này.
- Windows/Android OS, emulator/device, installer, mixed-version, Wi-Fi thực, icon/khóa ký còn thiếu và iOS: **NOT VERIFIED**, không giải quyết ở PR này.
- Rollback bằng PR revert commit CI; không đổi dữ liệu đã nhận, key, protocol hoặc bản 1.13.0 phát hành. Không sửa ruleset để tự yêu cầu check; chủ dự án review Draft, quyết định merge và branch protection riêng.
