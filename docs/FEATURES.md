# Danh mục tính năng cần bảo vệ

Baseline: FlowDrop Windows/Android 1.13.0, Android versionCode 14. Đường dẫn **Z:** thuộc [Source ZIP 1.13.0][Z], chưa nằm trực tiếp trên `main`. **[SRC]** đọc nguồn; **[TEST]** chạy trong kiểm toán này; **[DOC]** báo cáo/tài liệu có sẵn; **[?]** chưa xác minh. Một test JVM hoặc unit không xác nhận toàn bộ hành vi UI/OS.

| ID | Tính năng/bất biến | Bằng chứng và phần đã kiểm tra | Việc còn cần làm |
| --- | --- | --- | --- |
| F01 | UI native Windows và Android; desktop quản lý một instance | [SRC] `Z:desktop/windows/FlowDrop.cpp:323–360,435–443,583–585`; `android/.../MainActivity.java`, `FlowArtwork.java` | [?] Chạy lại UI trên Windows thật và điện thoại thật |
| F02 | Tự phát hiện peer cùng Wi-Fi, không nhập IP; tên trùng vẫn phân biệt theo ID | [SRC] `scripts/discovery.mjs`, `lan-discovery.mjs`, `DeviceDiscovery.java`, `LanDiscovery.java`, `WifiNetwork.java`; [DOC] release report nói đã thử engine và emulator | [?] Mạng thật nhiều NIC/VPN, đổi Wi-Fi, hai Android khác hãng; đợt này chưa chạy discovery suite |
| F03 | Windows → Android, Android → Windows, Android → Android với bên nhận chấp nhận | [SRC] `PeerOffers`, `TransferServer`, `TransferClient`, `ReceiveService`; [DOC] `tests/peer-integration.mjs` và release report có ma trận engine | [TEST] Host JVM phục vụ request từ Node và API security đạt; [?] toàn bộ ba luồng native end-to-end chưa chạy lại |
| F04 | Nhận bằng mã 8 ký tự, expiry 24 giờ và thu hồi | [SRC] `worker/index.js`, `CodeLookup.java`, `scripts/code-lookup.mjs`; [TEST] unit và host JVM kiểm tra complete/revoke/expiry | [?] UI tra mã qua nhiều thiết bị thật, mã mơ hồ và peer rời mạng |
| F05 | File rỗng, Unicode và nhiều file; không thêm quota sản phẩm tùy ý | [SRC][TEST] unit/host JVM giữ byte và tên, nhận file rỗng; metadata vẫn có giới hạn 8 MiB và số nguyên an toàn | [?] 101/1.000 file, video lớn, tải dài; harness large hiện lỗi trước bước truyền |
| F06 | Gửi thư mục, phục hồi đúng cây và root; giữ thư mục/file rỗng, không trộn vào root cũ | [SRC][TEST] `FolderJobs`, `folder-zip`, `folder-receive`, `FolderArchive`, `FolderPackage`, `FolderReceive`; 4 test nhỏ đạt | [?] ZIP64 >4 GiB và MediaStore trên máy thật chưa chạy lại |
| F07 | Hiển thị phiên đang chờ/đang truyền/kết quả; completed do receiver xác nhận lưu đủ | [SRC] `PeerOffers:6–82`, `TransferServer:40–127`, `ReceiveService:25–31,49–98`; [DOC] peer integration kiểm tra tiến độ và lỗi | [?] UI cả hai phía khi mất mạng, restart hoặc app bị OS dừng |
| F08 | File nhận dở không thành file hoàn tất; không ghi đè; giữ file trước đã lưu khi file sau lỗi | [SRC][TEST] `desktop-storage.mjs`, `local-bucket.mjs`, `ReceiveService`, các test storage/host/folder | [?] Fault injection hết đĩa, kill process và MediaStore cleanup trên Android thật |
| F09 | Windows tự lưu, chọn thư mục nhận, mở Explorer, lưu settings | [SRC] `DesktopStorage`, API desktop, C++ `openDirectory:555`; [TEST] engine storage/settings đạt; [DOC] báo cáo Wine cho một phần UI | [?] Explorer, quyền thư mục và ổ mạng trên Windows thật |
| F10 | Android phân loại file lẻ vào album hoặc Download; folder giữ nguyên cây trong Download | [SRC] `ReceiveFiles.java:9–27`, `ReceiveService.java:69–98`, `FolderReceive.java`; [DOC] báo cáo MediaStore/emulator | [?] Gallery/Download trên nhiều OEM; kiểm tra tên trùng và Android 10/15/16 |
| F11 | Đổi tên thiết bị, lưu tên và quảng bá lại | [SRC] `DeviceName`, `DeviceLabel`, C++/MainActivity; [TEST] unit kiểm tra tên Unicode, validation và lưu trạng thái | [?] Peer cập nhật tên trên mạng thật, tránh tạo peer ma |
| F12 | Windows Send To cho một/nhiều file, drag/drop và chuyển file vào instance đang mở | [SRC] `installer.nsi:52`, `FlowDrop.cpp:435–443,583–585`; [DOC] `windows-shell-smoke.cpp`, release report Wine | [?] Explorer Windows thật, cold/warm app, tên dài, UNC, danh sách nhiều file |
| F13 | Android xuất hiện trong Share sheet, một/nhiều file, content grant, không tự gửi trước khi chọn đích | [SRC] manifest SEND/SEND_MULTIPLE, `SharedFiles`, `MainActivity`, `SendService`; [DOC] report Android 16 emulator, sender UID khác | [?] Gallery/File Manager của máy thật; revoked/missing URI grant và cold/warm intent |
| F14 | Update feed HTTPS, chữ ký RSA, SHA-256, kiểm tra APK identity | [SRC][TEST] manifest thật và hash bộ cài khớp; fixture Node/Java từ chối giả mạo/HTTP/size lỗi; `UpdateManifest`/`AppUpdates` | [?] PackageInstaller và Windows installer end-to-end trên thiết bị thật |
| F15 | Windows kiểm tra tự động/thủ công, báo current/available, Later không tải, chờ phiên truyền trước cài | [SRC][TEST] `DesktopUpdater`, update-choice unit và fixture test đạt; UI C++ xử lý state | [?] Hộp thoại và restart sau cài trên Windows thật |
| F16 | Android update job/cache, kiểm tra busy, xử lý quyền cài và xác nhận OS | [SRC] `AppUpdates`, `UpdateJobService`, `UpdateInstallReceiver`; chỉ khẳng định hành vi có điều kiện | [?] Không có bằng chứng silent update trên mọi OS/OEM; phải thử foreground/background và reboot |
| F17 | Capability nội bộ, chặn remote write, origin/Host/framing xấu | [SRC][TEST] `RequestSecurity`, Node native API và host JVM; security integration đạt cả hai engine | [?] Quét sâu toàn bộ API, soak/resource exhaustion và kiểm thử mạng không tin cậy |
| F18 | Lịch sử/receipt/phiên và các file đã nhận không mất sau nâng cấp | [SRC] Android `TransferHistory`, receipt/preferences; Windows receipt/settings, session engine giữ trong RAM | [?] Migration và rollback dữ liệu chưa được chứng minh; không hứa session Windows persist qua restart |

`android/...` trong bảng là `android/src/app/flowdrop/mobile/`. Kế hoạch test chi tiết và thứ tự ưu tiên ở [REGRESSION-PLAN.md](REGRESSION-PLAN.md).

## Các giới hạn không được mô tả thành tính năng

- [SRC] LAN dùng HTTP, chưa có end-to-end encryption, TLS hay pairing mật mã. Device name/offerKey không phải danh tính tin cậy.
- [SRC] Không thấy resume offset cho file đang dở; chỉ có retry/poll và receipt cho file đã lưu xong.
- [SRC] Tên không hợp lệ có thể bị làm sạch/từ chối; bảo vệ dữ liệu không đồng nghĩa giữ nguyên mọi tên mà Windows không hỗ trợ.
- [SRC] APK dùng chứng thư dự án; EXE kiểm tra không có bảng chứng thư Authenticode. Ed25519 project key không thay chữ ký cập nhật RSA.
- [DOC] Các kiểm thử Wine/emulator và báo cáo npm audit lịch sử không thay thế kết quả thiết bị thật hoặc quét dependency mới.
- [?] Windows ↔ Windows, relay Internet, QR pairing, antivirus, đồng bộ nền và iOS production chưa được xác lập là tính năng được kiểm chứng của baseline này. Không thêm cam kết cho các mục đó.

## Khi sửa một tính năng

Ghi ID Fxx bị tác động, ví dụ tái hiện và các test tương ứng vào PR. Không xóa/bỏ qua tính năng để làm test đạt. Thay đổi tên route, token, MIME folder, kiểu số, trạng thái completed, khóa ký, installer identity hoặc cấu trúc lưu dữ liệu đều cần xem xét khả năng phá tương thích.

[Z]: https://github.com/Melbournejr/FlowDrop_IOS/releases/download/v1.13.0/FlowDrop-Source-1.13.zip
