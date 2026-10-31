# FlowDrop 1.10 — Windows và Android native

## Cài đè và gửi trực tiếp

1. Cài `FlowDrop-Setup-1.10.0-Windows-x64.exe` trên Windows 10/11 x64 và `FlowDrop-1.10.0-Android.apk` trên Android 10 trở lên. Cài đè, không gỡ bản cũ. APK versionCode 11 giữ nguyên package và khóa ký.
2. Mở FlowDrop trên các thiết bị cùng Wi-Fi. Android tự bật chia sẻ và tự quét cả điện thoại lẫn máy tính. Windows có cột **Thiết bị gần bạn**. Chọn thiết bị → chọn file → **Gửi đến…**. Thiết bị nhận xác nhận trước khi lưu.
3. Xem **Phiên truyền** trên cả hai máy để theo dõi byte đã nhận, số file, tốc độ và kết quả. Chỉ báo hoàn tất khi các file đã lưu đủ; file đứt giữa chừng không xuất hiện dưới tên cuối.

Windows có nút **Cho phép Wi-Fi**. Lần đầu, Windows có thể yêu cầu quyền quản trị để thêm quy tắc Firewall cho runtime Node đi kèm. Quy tắc chỉ nhận kết nối từ mạng nội bộ, không tắt Firewall. Nếu hủy, bấm nút này để thử lại. Không cần mở cổng router. VPN, Wi-Fi khách/AP isolation hoặc chính sách mạng vẫn có thể ngăn các thiết bị liên lạc.

## Nhận bằng mã

Máy gửi chọn file → **Tạo mã**. Máy nhận mở **Nhận file**, nhập mã 8 ký tự, có thể dán dạng `ABCD EFGH` hoặc `ABCD-EFGH`. Bản 1.10 tìm máy đang giữ mã trong các thiết bị FlowDrop được phát hiện qua Wi-Fi, thay vì chỉ tra trên máy đã chọn. Android có nút **Nhận bằng mã 8 ký tự** ngay ở màn hình thiết bị; không cần kết nối thủ công trước.

Giữ FlowDrop mở trên máy gửi. Mã có hiệu lực 24 giờ nếu chưa thu hồi. Mã dùng trong mạng nội bộ, không tra cứu qua Internet. Khi trùng mã trên nhiều máy, chọn đúng máy gửi rồi nhận lại. Tự lưu theo mã có thể bật/tắt trong cài đặt; yêu cầu gửi trực tiếp luôn cần xác nhận.

## Gửi cả thư mục

- Windows: **Thư mục…** → chọn một hoặc nhiều thư mục → chờ đóng gói → **Gửi đến…** hoặc **Tạo mã**.
- Android: **Chọn thư mục · Gửi ZIP** → cấp quyền đọc thư mục trong trình chọn của Android → **Gửi**.

Thư mục được gửi dưới dạng `.zip`, giữ cây thư mục, tên tiếng Việt và thư mục rỗng. Máy nhận lưu file ZIP; giải nén bằng công cụ của hệ điều hành để lấy thư mục. Windows không đi theo liên kết/symlink. Android chỉ đọc cây thư mục được cấp quyền; trình chọn hệ thống có thể không cho chọn gốc bộ nhớ, Download, Android/data hoặc Android/obb.

Đóng gói và truyền đều đọc theo luồng. Cần đủ chỗ cho ZIP tạm và bản chia sẻ ở máy gửi, bản lưu ở máy nhận. ZIP64 hỗ trợ file lớn hơn 4 GiB; hệ thống file nhận cũng cần hỗ trợ kích thước này. Không đặt hạn mức sản phẩm 10 file, 50 MiB/file hoặc 200 MiB/lượt. Thông tin tên file/metadata có giới hạn kỹ thuật 8 MiB.

## Nơi lưu

| Thiết bị / Loại file | Nơi lưu |
| --- | --- |
| Windows | Mặc định Downloads/FlowDrop; đổi bằng **Thay đổi…**, xem bằng **Mở thư mục**. |
| Android — ảnh/video | Album FlowDrop, đường dẫn DCIM/FlowDrop. |
| Android — ZIP/tài liệu/nhạc/loại khác | Download/FlowDrop. |

File trùng tên được giữ riêng. Thu hồi hoặc hết hạn mã không xóa bản đã lưu. Lịch sử Android nằm trên điện thoại đó. EXE và APK có giao diện native, không cần trình duyệt hoặc WebView. APK nhỏ vì dùng widget và API hệ thống Android, không đóng gói một runtime trình duyệt.

## Cập nhật tự động

Kênh chính thức: `https://github.com/Melbournejr/FlowDrop_IOS/releases/latest/download/latest.json`.

- Cần cài 1.10 thủ công một lần để có bộ cập nhật. Bản 1.9 không có tính năng này.
- Windows kiểm tra lúc mở và mỗi 6 giờ. Mặc định tự tải, kiểm tra chữ ký RSA của manifest và SHA-256 của EXE, sau đó cài khi không có phiên truyền/đóng gói đang chạy và mở lại ứng dụng. Có checkbox để tắt và nút **Cập nhật** để kiểm tra/cài thủ công. Dữ liệu và thư mục nhận được giữ.
- Android mặc định kiểm tra định kỳ qua Wi-Fi/mạng không tính phí (lịch do Android điều phối), tải vào bộ nhớ riêng, kiểm tra chữ ký manifest, SHA-256, package, versionCode và khóa ký APK. **Cài đặt → Kiểm tra / cài bản mới** để dùng thủ công. Cần cho phép FlowDrop cài ứng dụng từ nguồn này khi hệ thống yêu cầu. Android 12+ có thể cho ứng dụng tự cập nhật chính nó qua PackageInstaller khi đủ điều kiện; nếu hệ thống yêu cầu xác nhận, chạm thông báo và xác nhận. Android 10/11 thường cần xác nhận cài. FlowDrop chờ các phiên truyền kết thúc trước khi bắt đầu cài.
- Kho công khai chưa đủ: chủ dự án phải đăng release chứa bộ cài và `latest.json` đã ký. Nếu chưa đăng, mục kiểm tra báo chưa truy cập được kênh cập nhật; gửi file vẫn hoạt động.
- Không tự hạ phiên bản. Bộ cài sai hash/chữ ký hoặc thiếu dữ liệu bị từ chối. Không đưa mật khẩu, token GitHub hay token truy cập trang tải vào ứng dụng.

## Đăng bản 1.10 đầu tiên lên GitHub

Giải nén `FlowDrop-GitHub-Release-1.10.0.zip`. Mở https://github.com/Melbournejr/FlowDrop_IOS/releases/new, tạo tag `v1.10.0`, tiêu đề `FlowDrop 1.10.0`, rồi kéo các file EXE, APK và `latest.json` **bên trong** gói vào phần đính kèm. Có thể thêm SHA256SUMS và ghi chú. Chọn **Publish release**, giữ là release chính thức/latest, không đánh dấu prerelease. Không chỉ đính kèm cả ZIP: ứng dụng cần tải được `latest.json` theo tên riêng.

Gói này đã ký đúng URL của tag `v1.10.0`; giữ nguyên tên file và tag. Các máy đang dùng 1.10 sẽ nhận ra mình đã ở bản mới nhất. Các lần phát hành sau phải tăng phiên bản/versionCode và ký lại bằng đúng khóa cập nhật cùng khóa APK gốc.

Để tạo manifest cho bản sau: build bộ cài rồi chạy `node scripts/make-release.mjs --key /duong-dan-rieng/update-signing-private.pem`. Không công khai khóa RSA cập nhật hoặc keystore APK; mất khóa sẽ không phát hành tiếp được các bản cập nhật tương thích. Mã nguồn ZIP không chứa hai khóa này.

## Kiểm chứng và giới hạn

Bản 1.10 đã chạy kiểm tra HTTP/JVM hai chiều, discovery UDP/TCP ba engine, mã tra trên nhiều máy, mã sai/thu hồi/trùng, thông báo tiến độ và gián đoạn, ZIP Unicode/thư mục rỗng/ZIP64 hơn 4 GiB và đối chiếu CRC bằng Python, chữ ký manifest Java/Node và bộ cài sai hash/thiếu dữ liệu. DeviceDiscovery được kiểm tra bằng Android API stubs cho đổi Wi-Fi, callback đến muộn, timeout, nhiều IPv4 và TXT fallback. Giao diện Windows đã chạy trong Wine. Các kiểm tra tự động này không thay thế việc thử trên điện thoại Android 16 và Wi-Fi thật của bạn; cài cập nhật nền của hệ điều hành chưa được kiểm chứng trên máy thật.

Lệnh: `npm test`, `npm run test:network`, `npm run test:android-host`, `npm run test:android-discovery`, `npm run test:features`. Dựng bằng `python scripts/build-installers.py` với Android SDK 35/JDK 21, MinGW-w64 GCC 14, NSIS 3.11 và Node Windows x64 24.15.0. Cần khóa ký APK gốc; script từ chối tạo khóa thay thế.

EXE chưa có chứng thư ký mã nhà phát hành; APK dùng khóa riêng của dự án. Nếu điện thoại báo lỗi mạng khi kiểm tra APK, kết nối Internet ổn định rồi thử lại. Truyền file hiện dùng HTTP trong LAN, chưa mã hóa đầu cuối; dùng mạng tin cậy.
