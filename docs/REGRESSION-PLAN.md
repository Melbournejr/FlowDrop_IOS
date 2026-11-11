# Kế hoạch regression và tự động hóa

Tài liệu đề xuất cho giai đoạn sau, chưa tạo test mới, chưa sửa test/workflow và chưa cập nhật dependency. Baseline là [Source ZIP 1.13.0][Z] đã kiểm tra hash. Không chạy các lệnh build/publish để thực hiện kế hoạch trong giai đoạn 1.

## 1. Kết quả thực sự đã chạy trong kiểm toán

Môi trường: Linux, Node `v24.19.0`, JDK 21; không phải runtime Windows đóng gói 24.22.2. Dùng đúng bản dependency đang có, đối chiếu mọi package version với `package-lock.json` của ZIP; không cài/đổi dependency. JVM dùng JAR `org.json` ngoài repo, SHA-256 `3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed`.

| Lệnh thực thi trên nguồn ZIP | Kết quả | Phạm vi và giới hạn |
| --- | --- | --- |
| `npm test` | exit 0; 10/10 test đạt | Worker/storage/name/metadata/capability/update-choice; không có UI thật |
| `node tests/android-host-integration.mjs` | exit 0 | Production Java HTTP host + request từ Node; fixed/chunked, 1 MiB, file rỗng, UTF-8, revoke/expiry, upload dở |
| `node tests/security-integration.mjs` | exit 0 | Node native mode và JVM host: local capability, remote-write, config không lộ capability, Origin/Host/CL-TE/duplicate Host, deadline header Android |
| `node --test --test-isolation=none --test-name-pattern='Windows and Android verify the same signed release' tests/features-1.10.test.mjs` | exit 0; 1 test được chọn đạt | Fixture chữ ký Node/Java, HTTPS/hash/truncation và update busy; không chạy 3 test còn lại trong file |
| `node --test --test-isolation=none --test-skip-pattern='above 4 GiB' tests/folder-receive.test.mjs` | exit 0; 4 test được chọn đạt | Cây/tên/root trùng, Java deflate → Node, path/CRC/download lỗi, kích thước giả vượt đĩa. Ca ZIP64 >4 GiB không chạy |
| `node tests/large-transfer-integration.mjs` | **exit 1** ở bước compile | Ghép sai path Java tại dòng 12; chưa tới truyền 101 file/384 MiB. Không coi là test large đạt |
| Verifier `verifyRelease` với manifest phát hành thật, hash bộ cài, `apksigner verify`, `node security/verify-key-inventory.mjs` | Đạt | Chỉ đọc/xác minh, không ký lại hoặc tạo installer; chi tiết [RELEASE-PROCESS.md](RELEASE-PROCESS.md) |

Tổng các ca unit/fixture/folder được chọn đạt là 15, cộng hai script integration đạt; có một script preflight large thất bại. Không gọi đây là toàn bộ regression suite đã xanh. Log nằm trong workspace kiểm toán, không được đưa thêm vào PR tài liệu.

## 2. Bộ test đã có và khả năng tái sử dụng

| Nhóm | File trong ZIP | Đánh giá |
| --- | --- | --- |
| Unit | `tests/transfer.test.mjs`, `desktop-storage.test.mjs`, `device-name.test.mjs`, `update-choice.test.mjs`, `security.test.mjs` | Dùng ngay cho fast gate sau khi nguồn native có cây mã được duyệt |
| HTTP | `http-integration.mjs`, `android-host-integration.mjs`, `HostHarness.java` | Có kiểm tra production handlers; Java host không phải Android OS |
| Peer/phiên | `peer-integration.mjs`, `PeerHostHarness.java`, `windows-peer-fixture.mjs` | Có consent, progress, receive bằng mã, mất kết nối và completed; cần chạy lại trước khi coi tương thích đã chứng minh |
| Discovery | `discovery-integration.mjs`, `lan-discovery-integration.mjs`, `android-discovery-state.mjs`, `NsdDiscoveryHarness.java`, `nsd-stubs/` | Có mDNS/UDP và stub network state; stub không thay thế multicast lock/Wi-Fi của điện thoại thật |
| Thư mục | `features-1.10.test.mjs`, `folder-receive.test.mjs`, `FolderPackageHarness.java` | Đã tái sử dụng phần nhỏ; phần >4 GiB cần runner/disk riêng |
| File lớn/client native | `large-transfer-integration.mjs`, `android-native-client.mjs`, `NativeClientHarness.java`, `NativeHostHarness.java` | Harness large hiện có lỗi xác nhận; native-client dự kiến dùng >4 GiB, đợt này chưa chạy |
| API security | `security-integration.mjs`, `RequestSecurity`, các ca unit | Đã chạy các guard hiện có; chưa tương đương pentest đầy đủ |
| UI Windows | `windows-native-smoke.cpp`, `windows-shell-smoke.cpp` | Báo cáo Wine có sẵn; không có workflow build/run này trên main |
| Android OS/UI | `tests/android-native-smoke/NativeSmoke.java`, `NativeShareSmoke.java`, `NativeServiceSmoke.java`, `NativeFolderSmoke.java`, provider/sender UID riêng | Cần APK instrumentation riêng và emulator/device; không build/cài trong giai đoạn này |

Một số script hardcode `/workspace/flowdrop-build` và ghi report/cache tại đó, dù script khác hỗ trợ `FLOWDROP_BUILD_TOOLS`. Trước tự động hóa cần PR nhỏ để tham số hóa test paths và pin/provision JAR/toolchain; chưa triển khai trong PR này.

## 3. Lỗi harness cần tái hiện trước tiên

**REG-001 — large preflight**, đã tái hiện. Điều kiện: giải nén ZIP, Node 24/JDK 21, có JAR test. Chạy `node tests/large-transfer-integration.mjs` với `FLOWDROP_BUILD_TOOLS` trỏ thư mục test riêng có `downloads/json-test.jar`.

- Mong đợi: compiler nhận hai source Java riêng rồi mới chạy truyền file.
- Thực tế: dòng 12 gọi một `path.join` chứa cả `RequestSecurity.java` và `TransferServer.java`, compiler báo `RequestSecurity.java/android/src/.../TransferServer.java` không tồn tại; exit 1.
- Sau khi sửa harness ở PR được duyệt, phải kiểm tra thêm request tạo session dòng 22 và lấy desktop settings dòng 40: script hiện không chuyển local capability mới của native mode. Đây là vấn đề nhìn thấy từ nguồn, chưa chạy qua vì lỗi compile xảy ra trước.
- Không bỏ capability trong sản phẩm để chiều theo harness. Chỉ sau khi preflight đạt mới chạy lại 101 file, 384 MiB và đối chiếu SHA-256/RSS. Kết quả fail hiện tại không xác định hành vi file lớn của binary đã phát hành.

## 4. Ma trận thiết bị và phiên bản cần xây

| Receiver / sender | 1.13 ↔ 1.13 | 1.12 → 1.13 | 1.13 → 1.12 |
| --- | --- | --- | --- |
| Windows ↔ Android | Engine + UI thật hai chiều | Cần kiểm tra | Cần kiểm tra |
| Android A ↔ Android B | Hai máy/UID/nhãn riêng, kiểm tra cả A→B và B→A | Cần kiểm tra | Cần kiểm tra |

Mỗi ô áp dụng cho gửi trực tiếp và nhận bằng mã; không suy từ `version` trong fixture rằng đã chạy binary 1.12. Tầng engine chạy Node/JVM trên cùng runner giúp phát hiện lỗi contract; tầng OS cần Windows x64 và Android thật/emulator. Đề xuất Windows 10/11 và Android API 29/35/36 làm các nhóm cần chủ dự án chốt, chưa là lời hứa hỗ trợ đã thử.

## 5. Danh sách regression đề xuất

| ID | Mức/feature | Cách tái hiện và oracle |
| --- | --- | --- |
| RG-01 | P1; F02/F11 | Mở W+A+B cùng LAN, hai Android trùng tên; tất cả thấy hai peer còn lại, không thấy self; đổi tên/restart vẫn đúng ID |
| RG-02 | P1; F02 | Đổi Wi-Fi, bật VPN/Ethernet, mDNS mất, chỉ UDP còn; peer mới xuất hiện và peer cũ hết hạn. AP isolation phải báo lỗi có thể hiểu, không giả completed |
| RG-03 | P1; F03/F07 | Gửi trực tiếp từng chiều; trước consent không lưu, Reject không truyền; quan sát progress tăng, completed chỉ sau receiver commit đầy đủ |
| RG-04 | P1; F04 | Mã viết thường/có khoảng trắng, sai, chưa ready, hết hạn, revoke, hai peer cùng mã; chọn peer khi mơ hồ; metadata trả sai code bị từ chối |
| RG-05 | P1; F05/F08 | File 0/1 byte, Unicode, tên dài, tên trùng, 101/1.000 file; SHA-256 độc lập từng file và bảo toàn file cũ. Test sát 8 MiB metadata thay vì thêm quota sản phẩm |
| RG-06 | P1; F05 | 384 MiB, qua mốc 4 GiB, truyền lâu với byte count 64-bit; hash streaming, tiến độ không lùi, RSS đo riêng theo process, không nạp cả file vào RAM |
| RG-07 | P1; F06 | Thư mục lồng/rỗng/file rỗng/Unicode, root trùng, deflate/ZIP64; giữ cây/tên/nội dung; ZIP thường không tự giải nén |
| RG-08 | P1; F06/F17 | Traversal, absolute/drive path, symlink, path trùng, CRC sai, ZIP khai báo petabyte, thiếu đĩa; không thoát root, không công bố folder lỗi, cleanup staging |
| RG-09 | P1; F07/F08 | Ngắt TCP/mất Wi-Fi/kill sender hoặc receiver ở upload, download, unpack; failed/connection error đúng, không completed giả; file đã commit trước đó được giữ |
| RG-10 | P1; F08 | Nguồn thay size/mtime, body ngắn/dài, chunked hỏng, hết dung lượng giữa chừng; không file nhận dở công khai; thử lại không ghi đè file cũ |
| RG-11 | P1; F17 | Thiếu/sai token, token local từ remote, origin null/cross-site, Host giả/trùng, absolute target, CL+TE, chunk header lỗi, slow header; API từ chối đúng và socket được thu hồi |
| RG-12 | P1; F14/F15 | Node + Java verify cùng payload; sửa payload/signature/hash/size, HTTP redirect, APK khác cert/package/version, file bị đổi sau download; mọi nhánh sai đều bị từ chối |
| RG-13 | P1; F15/F16 | Current/available/manual/auto, Later, consent cũ, transfer đang busy, install fail/restart; không Windows download trước chấp thuận, không cài giữa phiên; Android xử lý pending user action |
| RG-14 | P2; F09/F12 | Windows đổi thư mục/mở Explorer, Send To cold/warm/multi, drag/drop, Unicode, single instance, settings qua restart |
| RG-15 | P1; F10/F13 | Android Gallery/File Manager → Share, UID khác; content URI grant/dedup/cold/warm, không tự gửi; media lẻ vào album, folder nguyên cây vào Download |
| RG-16 | P1; F18 | Nâng cấp có settings/receipt/history/file đã lưu; so sánh trước/sau; thử rollback trên thiết bị thử theo kế hoạch riêng, không uninstall máy người dùng |

Các con số kích thước/RSS là ca kiểm tra hoặc tiêu chí cần đo/chốt, không phải giới hạn sản phẩm mới. Fixture cố định/random có seed, checksum độc lập, đồng hồ điều khiển được và network fault injection cần thiết kế để test ổn định.

## 6. Tổ chức tự động hóa sau khi được duyệt

1. **Fast gate:** unit + contract/metadata + update fixtures, tách fixture khỏi mạng ngoài; chạy trên dependency lock hiện có.
2. **Engine gate:** Node host + production JVM engines, HTTP/security/discovery/folder nhỏ; cấp cổng động và dữ liệu riêng, có timeout và cleanup kể cả preflight fail.
3. **OS gate:** Windows UI và Android emulator instrumentation, lưu log đã loại token; ma trận physical smoke trước phát hành.
4. **Scheduled/large gate:** >4 GiB/soak/disconnect/restart với đủ đĩa, không chạy trong mọi PR tài liệu. Công bố rõ test bị loại và thời lượng/RSS.
5. **Release verification:** chỉ sau phê duyệt phát hành; verify source/artifact SHA, RSA, APK identity, runtime pin, install/update và rollback plan. Test không tự publish.

Chưa viết workflow mới. PR #1 đang đề xuất Actions/Swift CodeQL và policy check; không có coverage native Android/C++ chỉ vì PR đó xanh. Cần quyết định đưa nguồn native vào cây mã chính trước khi bổ sung CI tương ứng. Không tự bật lại bốn workflow publisher đang disabled.

## 7. Điều kiện kết thúc một PR sửa lỗi sau này

PR phải có repro, test fail trước/đạt sau, feature Fxx/RGxx, diff nhỏ, đánh giá giao thức/hai nền tảng, rủi ro và revert. Test chưa chạy không được đổi thành passed; lỗi môi trường/harness ghi riêng. Chặn merge nếu mất dữ liệu, đổi signing identity, completed giả, cài update sai hash/chữ ký hoặc chưa có quyết định tương thích cần thiết.

[Z]: https://github.com/Melbournejr/FlowDrop_IOS/releases/download/v1.13.0/FlowDrop-Source-1.13.zip
