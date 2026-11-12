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

**[API/log, đã thực chạy]** [Draft PR #7](https://github.com/Melbournejr/FlowDrop_IOS/pull/7) tạo sự kiện PR và [run #1](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43250684364). Sau khi thêm label `ci-zip64`, [run #2](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43250769922) được kích hoạt và **completed/success**. Run #1 bị **cancelled** do concurrency khi run mới bắt đầu; không tính là PASS.

Run #2 kiểm commit head **`e2855b8c5db2f0bec89144d57863bc34743079bb`** (PR merge checkout theo hành vi checkout mặc định). Đã đọc log của đủ năm job, đối chiếu conclusion/steps và các dòng PASS/exit thực do runner ghi; không suy từ một ô trạng thái tổng hợp.

| Job | Kết quả thực | Test/upload/cleanup |
| --- | --- | --- |
| [Fast](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43250769922/job/131295695641) | success | Đều success |
| [Integration](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43250769922/job/131295824688) | success | Đều success |
| [Stream](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43250769922/job/131295824906) | success | Đều success |
| [ZIP64](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43250769922/job/131295824488) | success | Đều success, không skip |
| [Coverage](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43250769922/job/131296534309) | success | Cả bốn gate cần đều success |

Mỗi job log xác nhận `Contents: read`. Ubuntu 24.04; setup Node 24, Java 21 và CPython **3.12.16** (patch khác môi trường Codex, giữ đúng dòng 3.12). Setup kiểm version/JAR/npm ci đều success. Các dòng log exit/thời gian thực:

| Suite | GitHub exit | Thời gian |
| --- | ---: | ---: |
| CI runner unit | 0 | 0,546s |
| Asset integrity | 0 | 0,003s |
| npm unit | 0 | 0,248s |
| Harness unit | 0 | 0,274s |
| HTTP | 0 | 1,597s |
| Android host | 0 | 4,478s |
| Discovery | 0 | 2,769s |
| Peer | 0 | 9,771s |
| LAN discovery | 0 | 16,289s |
| Android discovery | 0 | 1,333s |
| Security | 0 | 11,641s |
| Large transfer | 0 | 8,988s |
| Features | 0 | 13,843s |
| Folders | 0 | 25,172s |
| Native client | 0 | 15,792s |

**13/13 lệnh gốc và hai guard mới đều chạy đạt trên GitHub**, gồm đầy đủ ba file test ZIP64, không timeout. Đây là bằng chứng Node/JVM/Linux; không thêm coverage OS/thiết bị thật. Run mặc định không bật ZIP64 và nhánh manual chưa được nghiệm thu riêng ở GitHub; logic thông báo NOT VERIFIED đã kiểm từ source, preflight thiếu tài nguyên được unit test thực chạy. Không suy run #1 bị hủy thành bằng chứng cho kết quả default gate hoàn chỉnh.

Bốn artifact run #2 có trong API, upload steps success, digest API trùng digest upload job log; hết hạn **19/11/2026**:

| Artifact | Byte ZIP | SHA-256 từ API/upload |
| --- | ---: | --- |
| [fast](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43250769922/artifacts/13957738869) | 4915 | `eeddd5f5ac16312a1462393b603023e62433e3cbc18942b7c5222bc176c42028` |
| [integration](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43250769922/artifacts/13959565943) | 4694 | `04701ebb61302b65881e41c5fc16a209177d8a0b5dd22839fd09f16f7a4a5a19` |
| [stream](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43250769922/artifacts/13959098425) | 2485 | `9d6686a12b6cb8cb5167d332637d70babc8b2649b347397479c0a8a1cceb2203` |
| [zip64](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/43250769922/artifacts/13959640674) | 3532 | `1a9e16bb3056ee99cd3f4958222a1c401508fae65ab9a63d78f091eee15960e4` |

Đã xác nhận API tải artifact Fast trả file ZIP. Chưa giải nén/đối chiếu nội dung ZIP GitHub trong shell vì môi trường thực thi không còn khả dụng sau push; không tuyên bố đã kiểm tra từng member của archive GitHub. Quy trình chỉ upload logs đã sanitize, sanitizer có unit thực chạy ở cả local/GitHub; log local đã quét mẫu UUID/PAT trước commit. Việc kiểm archive byte độc lập còn là giới hạn bằng chứng, tách khỏi kết quả test/step thực chạy.

Commit cập nhật báo cáo này chỉ bổ sung bằng chứng, không đổi workflow/runner/source đã kiểm ở run #2. Push đồng bộ PR sẽ tạo run kế tiếp; trạng thái commit cuối được đối chiếu riêng trong PR trước bàn giao.

## Rủi ro, giới hạn và rollback

- Ubuntu hosted cần internet tới Actions/toolchains/npm/Maven và multicast nội bộ; upstream/toolchain patch có thể thay đổi dù dependency ứng dụng/JAR và mã Action đã ghim. Ghi version trong artifact; không âm thầm đổi pin để chữa lỗi.
- Nhóm >4 GiB không mặc định trên mọi PR; job Coverage ghi NOT VERIFIED nếu chưa chọn. Không thể tuyên bố đủ suite khi chỉ Fast/Integration/Stream đạt. Runner thiếu tài nguyên thất bại preflight, không giảm file.
- Logs chỉ giữ 7 ngày; sanitation có test nhưng không thể suy rằng mọi định dạng bí mật tương lai đều được nhận diện. Không cấp signing keys/production secrets cho CI này.
- Windows/Android OS, emulator/device, installer, mixed-version, Wi-Fi thực, icon/khóa ký còn thiếu và iOS: **NOT VERIFIED**, không giải quyết ở PR này.
- Rollback bằng PR revert commit CI; không đổi dữ liệu đã nhận, key, protocol hoặc bản 1.13.0 phát hành. Không sửa ruleset để tự yêu cầu check; chủ dự án review Draft, quyết định merge và branch protection riêng.
