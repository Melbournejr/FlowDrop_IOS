# FlowDrop — kiểm toán baseline và bảo vệ mã nguồn, giai đoạn 1

Ngày quan sát: **11/11/2026, Asia/Saigon**. Repository: [Melbournejr/FlowDrop_IOS][REPO]. Phiên bản sản phẩm được kiểm toán: **Windows/Android 1.13.0**. iOS đang tạm dừng theo yêu cầu chủ dự án.

Phạm vi thay đổi của PR này chỉ là `AGENTS.md` và sáu tài liệu trong `docs/`. Không sửa ứng dụng, test, workflow, dependency, cấu hình ký, APK/EXE hoặc Release; không merge và không phát hành. Kết quả phản ánh các snapshot dưới đây, không chứng nhận những thay đổi phát sinh sau thời điểm kiểm toán.

## 1. Kết luận chính

1. **[SRC][TEST] Có nguồn Windows/Android 1.13.0 kiểm chứng được:** custom asset [FlowDrop-Source-1.13.zip][ZIP] và bản ZIP trong payload nhánh automation. SHA-256 khớp; 141 file ZIP khớp byte với commit local đóng gói `19435e5…`. **Nguồn native chưa nằm trực tiếp trên main.**
2. **[SRC][TEST] Kênh update hiện có kiểm tra mật mã:** manifest thật verify bằng RSA, hash APK/EXE khớp, chứng thư APK khớp fingerprint công khai. Điều này chưa chứng minh binary có thể build tái lập hoặc mọi cập nhật/cài đè đã chạy trên OS thật.
3. **[TEST] Fast checks thực sự chạy:** 10 unit + 1 fixture update Node/Java + 4 folder nhỏ đạt; hai script host/security integration đạt. **Large preflight thất bại** ở compile, chưa có kết quả truyền file lớn mới.
4. **[SRC][TEST] PR #1 không được coi là đã hoàn tất:** còn mở; policy/Actions check đạt trong các run lịch sử nhưng Swift CodeQL bị hủy. Một probe offline cho thấy policy regex bỏ lọt cú pháp YAML flow. Không sửa, merge hoặc trùng lặp file của PR #1 trong giai đoạn này.
5. **[SRC] Các ranh giới quan trọng còn tồn tại:** LAN HTTP chưa mã hóa/pairing; main chưa được bảo vệ theo metadata đã đọc; publisher phân phối bộ cài chuẩn bị sẵn; rollback qua downgrade không tự động khả dụng.

Chưa xác nhận phát hiện P0 đang xảy ra. Danh sách P1/P2 và điều kiện dừng phát hành không đồng nghĩa tuyên bố sản phẩm an toàn toàn diện.

## 2. Quy ước bằng chứng

| Nhãn | Ý nghĩa | Không được suy diễn thành |
| --- | --- | --- |
| **[SRC]** | Đã đọc file tại commit/ZIP cụ thể | Đã chạy đúng hành vi đó trên thiết bị thật |
| **[TEST]** | Đã chạy phép kiểm/đối chiếu hoặc đọc kết quả API/run được chỉ rõ | Toàn bộ suite xanh, OS khác cũng đạt, hoặc không còn lỗ hổng |
| **[DOC]** | Báo cáo/tài liệu có sẵn ghi một kết quả | Kiểm thử mới hoặc bằng chứng độc lập của kiểm toán này |
| **[?]** | Chưa truy cập/chưa chạy/chưa đủ bằng chứng | Không tồn tại chức năng hoặc chắc chắn đang lỗi |

Trong tài liệu, **Z:** là đường dẫn tương đối bên trong `FlowDrop/` của custom Source ZIP. Đường dẫn đó thường không tồn tại trên `main`; cần tải/giải nén ZIP để đọc. Bằng chứng GitHub có permalink theo SHA; trạng thái Settings/Actions là quan sát API tại thời điểm kiểm toán.

## 3. Snapshot đã kiểm tra

| Nhánh | HEAD đã quan sát | File ở HEAD | Nguồn native trực tiếp |
| --- | --- | ---: | --- |
| `main` | `2e7708d79e76315f2c8db152b0fa11712e07c037` | 31 | Không; iOS và public keys |
| `automation/flowdrop-release-1.10.0` | `452f99af26c6b08dcb98e8012ed3cec539e58d60` | 36 | Không; Source ZIP trong `.release/1.10.0/` |
| `automation/flowdrop-release-1.11.0` | `f85626028742748abb8a70a06c089b5b125df58e` | 36 | Không; Source ZIP trong `.release/1.11.0/` |
| `automation/flowdrop-release-1.12.0` | `7be0978d32b84645879d3b7a4b32563ae1e0f683` | 36 | Không; Source ZIP trong `.release/1.12.0/` |
| `automation/flowdrop-release-1.13.0` | `c425078e0de9e70c86c2d3345b2caca7241d0494` | 36 | Không; Source ZIP trong `.release/1.13.0/` |
| `security/github-hardening-2026-11-11` | `2ccf9248ed6de184a200a950e1d37dd1e5b11741` | 33 | Không; PR #1 |
| `security/public-signing-identities-2026-11-11` | `a841e182d47a2d0ead41a740c63a86063b8d0094` | 31 | Không; public-key change đã vào main qua PR #2 |

**[TEST]** Đã clone các ref, lập inventory cây file, đọc workflows/publisher trên bốn automation branch, đối chiếu tags và danh sách Release. Không chỉ kiểm tra tên nhánh. Các Source ZIP 1.10/1.11/1.12/1.13 lần lượt có 120/126/131/141 file; kiểm tra sâu chức năng tập trung ZIP 1.13, so sánh danh sách thay đổi ZIP 1.12→1.13, không tuyên bố đã review ngữ nghĩa mọi dòng vendor hoặc mọi phiên bản cũ.

**Nguồn local và trạng thái chưa commit:** checkout native có HEAD `19435e5dbc3c039446804f3aa7145df6bfc5e13f`; các sửa `.gitignore`, README/package/build/signing scripts và các file key-management mới từ lượt trước chưa commit. Đợt này không đưa chúng vào nhánh audit hay thay đổi chúng. `FlowDrop-Kiem-chung-1.13.json` ghi sourceCommit `7847c97…`; ZIP đã kiểm khớp tập 141 file ở commit đóng gói `19435e5…`, chưa phải bằng chứng build reproducible.

**Baseline ZIP:** 611206 byte; SHA-256 `d1fea853ad992c0b8febf8efa1cc988ef52bc2ca8e6b798eb440f2c7a243a962`. Kiểm tra download GitHub, bản payload Git và bản local cho cùng digest. APK/EXE/manifest/danh sách đủ 7 asset có trong [RELEASE-PROCESS.md](RELEASE-PROCESS.md).

## 4. Kiến trúc và phát hành đã xác minh

**[SRC]** Windows là UI Win32/C++ và Node host cục bộ, Android là Activity/Service Java và HTTP engine native. File truyền trực tiếp qua LAN; discovery dùng NSD/mDNS và UDP, sender stage dữ liệu ở chính host rồi receiver pull sau consent. Thư mục là ZIP/ZIP64 có MIME riêng; metadata/token/state là hợp đồng chung. Xem [ARCHITECTURE.md](ARCHITECTURE.md) và [PROTOCOL.md](PROTOCOL.md).

**[SRC]** Công cụ build APK/EXE nằm trong Source ZIP, dùng SDK/JDK/MinGW/NSIS/Node và khóa ngoài checkout. Workflow publisher 1.13 **không compile hoặc chạy regression ứng dụng**; nó verify và upload payload prebuilt trong `.release`. `main` chỉ có workflow iOS thủ công. Bốn workflow publisher hiện disabled; kiểm toán giữ nguyên.

**[SRC][TEST]** RSA-SHA256/HTTPS/SHA-256 update và APK identity tồn tại, các bản public RSA key khớp nhau. APK đã verify signature, fingerprint `65cbed4feb375d2c3c2eb94e668bd7aaee7ce5b24f436887873a6fa11719f97f`. EXE kiểm PE Certificate Table là 0/0, chưa có Authenticode. Không đổi khóa hoặc ký lại gì để kiểm tra.

## 5. PR #1 — nội dung và nguy cơ chồng chéo

[PR #1][PR1] còn `open`, không phải Draft, chưa merged. HEAD `2ccf9248ed6de184a200a950e1d37dd1e5b11741`; API ghi base SHA `ae85b16d9bf4d2f5d365d694b489af9234194099`, mergeable nhưng trạng thái check `unstable`. Không dùng “mergeable” làm phê duyệt merge.

11 file PR #1 chạm tới:

```text
.github/CODEOWNERS
.github/SECURITY-SETUP.md
.github/dependabot.yml
.github/scripts/audit_workflows.py
.github/scripts/test_security_policy.py
.github/security/main-ruleset.json
.github/workflows/codeql.yml
.github/workflows/flowdrop-ios.yml
.github/workflows/security-checks.yml
.gitignore
SECURITY.md
```

PR đề xuất ghim Actions, bỏ credential persist, CodeQL Actions/Swift, Dependabot, regex policy, CODEOWNERS và hướng dẫn Settings. Những thứ đó chưa nằm trên main chỉ vì PR đã mở. Mẫu ruleset JSON không tự bảo vệ nhánh. CODEOWNERS không tự thực thi review khi chưa có branch rule.

| Bằng chứng lịch sử đọc lại từ API | Trạng thái |
| --- | --- |
| [Run policy 42947874524][RUNPOLICY], job Workflow safety | success |
| [Run CodeQL 42947874605][RUNQL], job Actions | success |
| Cùng run, job Swift | cancelled; cả workflow cancelled |
| [Run publisher 1.13 42913925358][RUNRELEASE] | success; chỉ publisher |

**[TEST] Probe offline PR #1:** nạp đúng `audit_workflows.py` ở HEAD trên, gọi hàm với YAML chứa `on: [pull_request_target]` và step `- {uses: actions/checkout@v6}`, vẫn có block quyền root read. Hàm trả `[]`, bỏ lọt cả trigger và ref không pin. Mẫu chỉ ở RAM, không commit hoặc chạy workflow. Đây là giới hạn của regex check, cần review/test riêng trước khi coi nó là security gate; không sửa nó trong giai đoạn 1.

CodeQL đề xuất chỉ Actions/Swift, không quét nguồn Java/C++ của ứng dụng chính chưa có trên main. Workflow Swift còn build iOS, cần chủ dự án quyết định vì iOS đang tạm dừng.

**Chống trùng:** bảy file của PR audit không trùng bất kỳ path nào trong PR #1; không sao chép workflow, script, SECURITY.md, CODEOWNERS hoặc ruleset. Không đóng, rebase, merge hay thay Draft status của PR #1. Các thay đổi ở nó cần nhiệm vụ riêng và cập nhật lại các nhận định phụ thuộc snapshot khi được merge.

## 6. Kết quả kiểm thử của đợt này

Chi tiết lệnh, môi trường và bài bị loại ở [REGRESSION-PLAN.md](REGRESSION-PLAN.md).

| Kiểm tra | Kết quả |
| --- | --- |
| Unit baseline đúng ZIP | 10/10 đạt, exit 0 |
| Android production host JVM | Đạt, exit 0, khoảng 2,76 giây |
| API security Node native mode + JVM | Đạt, exit 0, khoảng 12,42 giây |
| Update fixture Node/Java, chọn một test | 1 test đạt, exit 0; các test khác trong file không chạy |
| Folder suite loại ca >4 GiB | 4 test đạt, exit 0; ca >4 GiB không chạy |
| Large harness | **Fail**, exit 1, khoảng 0,24 giây; không truyền file lớn |
| Hash 7 release assets, manifest RSA thật, public pins, APK signature, key inventory | Đạt, chỉ đọc/xác minh |
| Probe regex PR #1 | Xác nhận bỏ lọt mẫu YAML flow; không thay đổi workflow |

Không chạy lại Windows UI/Wine, APK instrumentation, physical Wi-Fi, mọi luồng mixed-version, kiểm thử >4 GiB, install/update/downgrade OS, iOS/Xcode hoặc build tái lập. Báo cáo `FlowDrop-Kiem-chung-1.13.json` nói các kiểm tra trước đó đã đạt; các mục chưa chạy lại chỉ mang nhãn **[DOC]**.

## 7. Rủi ro và mức độ

P0: nguy cơ mất dữ liệu/khóa, phát hành sai identity hoặc cập nhật không tin cậy cần dừng ngay nếu có bằng chứng. P1: rủi ro đáng kể cho bảo mật, kiểm soát nguồn hoặc regression cần xử lý trước nâng cấp liên quan. P2: hạn chế vận hành/tài liệu/coverage cần xếp lịch. Mức độ không phải kết luận đã có khai thác.

**P0 đã xác nhận: chưa có trong phạm vi kiểm toán.** Chưa đủ bằng chứng để kết luận không thể có P0 ở phần chưa kiểm tra. Dừng phát hành nếu cert/key/hash sai, mất dữ liệu hoặc completed giả được tái hiện; không sửa bằng cách bỏ validation.

| ID | Mức | Phát hiện, bằng chứng | Hệ quả và hướng xử lý cần duyệt |
| --- | --- | --- | --- |
| A01 | P1 | [SRC][TEST] Native source chỉ ở ZIP/payload; main thiếu cây Android/Windows; publisher upload prebuilt, không compile/test | Khó review và gắn binary với source commit. Duyệt PR import baseline chuẩn, sau đó thiết kế build/test gates; không làm ở giai đoạn này |
| A02 | P1 | [SRC][TEST engine HTTP] LAN plaintext, discovery ID/offerKey chưa phải pairing mật mã; metadata không có digest file được xác thực | Người trong mạng có thể quan sát/tấn công luồng. Cần thiết kế trust/pairing/TLS và migration protocol được duyệt; giữ cảnh báo giới hạn hiện tại |
| A03 | P1 | [TEST] `tests/large-transfer-integration.mjs:12` ghép nhầm path Java và fail trước truyền; [SRC] dòng 22/40 chưa theo capability native | Không thể dùng suite này chứng minh file lớn của 1.13 đạt. Tạo PR sửa harness + repro/expectation riêng; không giảm bảo vệ ứng dụng |
| A04 | P1 | [TEST metadata] Các branch được liệt kê đều `protected:false`; `GET rulesets` trả `[]` | Quy tắc chỉ trong AGENTS không ngăn push/merge tại server. Chủ dự án cần duyệt Settings/required review/checks, nhưng không đổi Settings trong đợt này |
| A05 | P1 | [SRC][TEST probe] Regex policy PR #1 bỏ lọt cú pháp YAML hợp lệ; Swift CodeQL bị hủy và chưa có native coverage | Có thể hiểu nhầm security gate đã đầy đủ. Review PR #1 riêng, bổ sung ca cú pháp/parser và phạm vi nền tảng theo quyết định; không merge tự động |
| A06 | P1 | [SRC] Build ký APK của ZIP dùng mật khẩu cố định; local migration key-management đang chưa commit | Không được lẫn source release với cấu hình mới. Kiểm tra lưu khóa/quyền/khôi phục trong nhiệm vụ riêng, giữ cert và RSA pin; không phát tán mật khẩu |
| A07 | P1 | [SRC][?] Updater/Android chống downgrade; chưa có test rollback dữ liệu/OS thật | “Cài bản cũ” chưa phải kế hoạch rollback bảo toàn dữ liệu. Duyệt phương án snapshot + thử migration và forward rollback khi cần |
| A08 | P2 | [SRC] Workflow main còn checkout/upload tag động; publisher dùng checkout@v5 và root contents:write | Rủi ro chuỗi cung ứng/quyền. Đối chiếu PR #1 trước mọi sửa; không pin/chỉnh workflow thêm trong PR audit |
| A09 | P2 | [SRC] README main chỉ mô tả iOS 1.0.2/chưa build dù có run success; README ZIP ghi 1.11/Node 24.15.0 trong khi runtime pin là 24.22.2 | Dễ chạy sai hướng dẫn hoặc nhận diện sai baseline. Tài liệu mới ghi bằng chứng đúng; cập nhật README cũ ở nhiệm vụ riêng |
| A10 | P2 | [SRC][?] Test có đường dẫn tools tuyệt đối, JAR/toolchain ngoài repo; coverage OS hiện dựa báo cáo Wine/emulator | Chạy trên runner mới có thể không tái lập; cần tham số hóa/provision/pin công cụ và máy thật trước release gate |
| A11 | P2 | [TEST PE][SRC] EXE chưa có Authenticode | Người dùng có thể gặp cảnh báo publisher/SmartScreen. Quyết định chứng thư ký mã và quy trình riêng; RSA manifest vẫn phải giữ |

## 8. Bí mật và giới hạn truy cập

**[TEST]** Quét offline có giới hạn trên 78 text blobs reachable và bốn Source ZIP thấy không có file keystore/private-key/PAT theo các mẫu đã dùng. Không in giá trị nhạy cảm. Đây không phải GitHub secret scanning, không phủ mọi loại secret, unreachable objects, CI logs/artifacts hay toàn bộ advisory database. Không kết luận lịch sử chắc chắn không có bí mật.

**[?]** API đọc chi tiết main protection, workflow token defaults và CodeQL default setup trả 403 `Resource not accessible by integration`. Không kiểm tra được đầy đủ các Settings đó; không suy trạng thái secret scanning/push protection, release immutability hoặc tài khoản 2FA từ mục Secrets trống. Tài khoản có quyền admin không tự cấp các scope đó cho integration. Không tạo token mới hoặc đổi cài đặt để vượt giới hạn kiểm toán.

## 9. Quyết định cần chủ dự án chốt

1. Chọn nguồn native chính thức: import đúng ZIP 1.13 lên nhánh/PR riêng, cách giữ lịch sử và gắn source commit vào release. Không dùng tự động Source code ZIP của tag thay custom Source ZIP.
2. Tiếp tục, thu hẹp hay chia PR #1; iOS đã tạm dừng thì có tiếp tục Swift workflow/CodeQL hay không. Native coverage chỉ có thể thiết kế sau khi có nguồn đúng vị trí.
3. Duyệt sửa harness large và chuẩn hóa test tools ở giai đoạn sau; chốt Windows/Android phiên bản nào và thiết bị thật nào là release gate.
4. Chốt mô hình tin cậy LAN, nhu cầu TLS/pairing và kế hoạch tương thích; đây là thay đổi protocol, không thực hiện như một bản vá ngầm.
5. Chốt việc hoàn thiện/kiểm tra migration quản lý khóa đang có ở local, quyền truy cập và khôi phục; cert APK và RSA updater phải giữ nguyên. Không mặc định đưa khóa lên GitHub Actions.
6. Chốt rollback giữ dữ liệu, chính sách forward rollback/versionCode và tiêu chí trước phát hành; chưa có bằng chứng an toàn cho downgrade OS thật.
7. Chốt branch protection/review, xử lý publisher đang disabled, chính sách phát hành có người duyệt và nhu cầu Authenticode. Không có hành động tự bật workflow/merge/publish từ PR này.

## 10. Bảy file được bổ sung

1. `AGENTS.md` — phạm vi, protocol/signing freeze, repro/test, nhánh/PR, cấm tự merge/phát hành.
2. `docs/ARCHITECTURE.md` — cây nguồn thực tế và luồng runtime/build.
3. `docs/PROTOCOL.md` — discovery, API/token/schema/session/folder/update contract đã đọc.
4. `docs/FEATURES.md` — F01–F18, bằng chứng và phần chưa kiểm chứng.
5. `docs/REGRESSION-PLAN.md` — kết quả hiện có, repro harness và RG-01–RG-16, kế hoạch tự động hóa.
6. `docs/RELEASE-PROCESS.md` — hash asset, pipeline prebuilt/signing và rollback có giới hạn.
7. `docs/AUDIT-REPORT.md` — snapshot, PR #1, rủi ro, giới hạn và quyết định.

Không thêm CI/test executable hoặc copy native code vào main. Draft PR để chủ dự án xem; chưa merge. Khi hoàn tất, đối chiếu diff allowlist, public refs/assets/workflow trạng thái và PR #1 với snapshot; thay đổi ngoài phạm vi hoặc hoạt động đồng thời phải được ghi rõ, không ghi đè.

[REPO]: https://github.com/Melbournejr/FlowDrop_IOS
[ZIP]: https://github.com/Melbournejr/FlowDrop_IOS/releases/download/v1.13.0/FlowDrop-Source-1.13.zip
[PR1]: https://github.com/Melbournejr/FlowDrop_IOS/pull/1
[RUNPOLICY]: https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/42947874524
[RUNQL]: https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/42947874605
[RUNRELEASE]: https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/42913925358
