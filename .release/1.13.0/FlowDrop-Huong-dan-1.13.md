# FlowDrop 1.13 — Windows và Android native

## Cài đè và gửi trực tiếp

1. Cài `FlowDrop-Setup-1.13.0-Windows-x64.exe` trên Windows 10/11 x64 và `FlowDrop-1.13.0-Android.apk` trên Android 10 trở lên. Cài đè, không gỡ bản cũ. APK versionCode 14 giữ nguyên package và khóa ký.
2. Mở FlowDrop trên các thiết bị cùng Wi-Fi. Android tự bật chia sẻ và tự quét cả điện thoại lẫn máy tính. Windows có cột **Thiết bị gần bạn**. Chọn thiết bị → chọn file → **Gửi đến…**. Thiết bị nhận xác nhận trước khi lưu.
3. Xem **Phiên truyền** trên cả hai máy để theo dõi byte đã nhận, số file, tốc độ và kết quả. Chỉ báo hoàn tất khi các file đã lưu đủ; file đứt giữa chừng không xuất hiện dưới tên cuối.

Windows có nút **Cho phép Wi-Fi**. Lần đầu, Windows có thể yêu cầu quyền quản trị để thêm quy tắc Firewall cho runtime Node đi kèm. Quy tắc chỉ nhận kết nối từ mạng nội bộ, không tắt Firewall. Nếu hủy, bấm nút này để thử lại. Không cần mở cổng router. VPN, Wi-Fi khách/AP isolation hoặc chính sách mạng vẫn có thể ngăn các thiết bị liên lạc.

## Nhận bằng mã

Máy gửi chọn file → **Tạo mã**. Máy nhận mở **Nhận file**, nhập mã 8 ký tự, có thể dán dạng `ABCD EFGH` hoặc `ABCD-EFGH`. Bản 1.11 tìm máy đang giữ mã trong các thiết bị FlowDrop được phát hiện qua Wi-Fi, thay vì chỉ tra trên máy đã chọn. Android có nút **Nhận bằng mã 8 ký tự** ngay ở màn hình thiết bị; không cần kết nối thủ công trước.

Giữ FlowDrop mở trên máy gửi. Mã có hiệu lực 24 giờ nếu chưa thu hồi. Mã dùng trong mạng nội bộ, không tra cứu qua Internet. Khi trùng mã trên nhiều máy, chọn đúng máy gửi rồi nhận lại. Tự lưu theo mã có thể bật/tắt trong cài đặt; yêu cầu gửi trực tiếp luôn cần xác nhận.

## Gửi cả thư mục, tự tạo lại ở máy nhận

- Windows: **Thư mục…** → chọn thư mục → **Gửi đến…** hoặc **Tạo mã**.
- Android: **Chọn thư mục để gửi** → cấp quyền đọc trong trình chọn Android → **Gửi**.

Khi cả hai máy dùng 1.11 trở lên, máy nhận tự tạo thư mục đúng tên gốc ngay trong thư mục nhận. Ví dụ gửi `Dự án/` có `bản vẽ/a.pdf` và `ảnh/b.jpg` thì nhận được `FlowDrop/Dự án/bản vẽ/a.pdf` và `FlowDrop/Dự án/ảnh/b.jpg`. Tên file, thư mục con, thư mục rỗng và nội dung được giữ. Không cần giải nén thủ công.

Windows tạo trong thư mục nhận đã chọn. Android giữ toàn bộ thư mục trong `Download/FlowDrop/<Tên thư mục>`, kể cả ảnh/video bên trong; ảnh/video gửi lẻ vẫn vào Album FlowDrop. Nếu có sẵn thư mục cùng tên, tạo `Tên thư mục (1)`, `(2)`…; các tên file bên trong giữ nguyên, không trộn hay ghi đè dữ liệu cũ.

Gói được đóng gói và kiểm tra nội bộ, đọc/ghi theo luồng. Chỉ các gói do thao tác **chọn thư mục** đánh dấu mới được khôi phục thành thư mục; ZIP gửi như file thông thường vẫn giữ nguyên ZIP. Máy nhận 1.10 trở xuống sẽ lưu ZIP để bạn giải nén, nên cập nhật cả hai phía.

Cần đủ chỗ cho gói tạm, dữ liệu chia sẻ và thư mục khôi phục. File lớn hơn 4 GiB cần hệ thống file phù hợp. Không đặt hạn mức sản phẩm 10 file, 50 MiB/file hoặc 200 MiB/lượt. Metadata chia sẻ có giới hạn kỹ thuật 8 MiB. Windows báo lỗi nếu tên trong gói không được hệ thống file Windows hỗ trợ, thay vì âm thầm đổi tên.

## Mở thư mục trên Windows

Bấm **Mở thư mục** sẽ tạo thư mục nhận nếu chưa có và gọi Windows Shell để mở cửa sổ Explorer bình thường. Hỗ trợ đường dẫn có khoảng trắng và tiếng Việt. Nếu Windows từ chối, ứng dụng hiển thị lỗi thay vì bỏ qua. Thư mục nhận mặc định là Downloads/FlowDrop; có thể đổi bằng **Thay đổi…**.

## Nơi lưu

| Thiết bị / Loại file | Nơi lưu |
| --- | --- |
| Windows | Mặc định Downloads/FlowDrop; đổi bằng **Thay đổi…**, xem bằng **Mở thư mục**. |
| Android — ảnh/video | Album FlowDrop, đường dẫn DCIM/FlowDrop. |
| Android — ZIP/tài liệu/nhạc/loại khác | Download/FlowDrop. |

File trùng tên được giữ riêng. Thu hồi hoặc hết hạn mã không xóa bản đã lưu. Lịch sử Android nằm trên điện thoại đó. EXE và APK có giao diện native, không cần trình duyệt hoặc WebView. APK nhỏ vì dùng widget và API hệ thống Android, không đóng gói một runtime trình duyệt.

## Cập nhật tự động

Kênh chính thức: `https://github.com/Melbournejr/FlowDrop_IOS/releases/latest/download/latest.json`.

- Bản 1.10 đã có bộ cập nhật và có thể nhận 1.11 qua kênh GitHub. Bản 1.9 trở xuống cần cài đè thủ công một lần.
- Windows tự kiểm tra lúc mở và mỗi 6 giờ nếu bật **Tự động kiểm tra cập nhật**. Bấm **Cập nhật** để kiểm tra thủ công: chưa có bản mới sẽ hiện hộp thoại **Chưa có phiên bản mới**; nếu có sẽ hỏi **Cập nhật ngay / Để sau**. Chỉ tải sau khi chọn Cập nhật ngay. Nếu đang truyền/đóng gói, chờ phiên kết thúc rồi mới tải/cài đè và mở lại. Cài đặt, tên thiết bị và thư mục nhận được giữ. Lỗi mạng/chữ ký được báo riêng, không báo nhầm là đang dùng bản mới nhất.
- Android mặc định kiểm tra định kỳ qua Wi-Fi/mạng không tính phí (lịch do Android điều phối), tải vào bộ nhớ riêng, kiểm tra chữ ký manifest, SHA-256, package, versionCode và khóa ký APK. **Cài đặt → Kiểm tra / cài bản mới** để dùng thủ công. Cần cho phép FlowDrop cài ứng dụng từ nguồn này khi hệ thống yêu cầu. Android 12+ có thể cho ứng dụng tự cập nhật chính nó qua PackageInstaller khi đủ điều kiện; nếu hệ thống yêu cầu xác nhận, chạm thông báo và xác nhận. Android 10/11 thường cần xác nhận cài. FlowDrop chờ các phiên truyền kết thúc trước khi bắt đầu cài.
- Kho công khai chưa đủ: chủ dự án phải đăng release chứa bộ cài và `latest.json` đã ký. Nếu chưa đăng, mục kiểm tra báo chưa truy cập được kênh cập nhật; gửi file vẫn hoạt động.
- Không tự hạ phiên bản. Bộ cài sai hash/chữ ký hoặc thiếu dữ liệu bị từ chối. Không đưa mật khẩu, token GitHub hay token truy cập trang tải vào ứng dụng.

## Bản phát hành và khóa cập nhật

Bản phát hành chính thức: https://github.com/Melbournejr/FlowDrop_IOS/releases/latest. EXE, APK và `latest.json` đã ký cần là các asset riêng. Các bản sau tăng version/versionCode, giữ đúng khóa cập nhật và khóa APK gốc. Không chia sẻ các khóa riêng.


## Kiểm chứng và giới hạn

Bản 1.11 đã chạy kiểm tra HTTP/JVM hai chiều, discovery UDP/TCP ba engine, mã tra trên nhiều máy, mã sai/thu hồi/trùng, thông báo tiến độ và gián đoạn, ZIP Unicode/thư mục rỗng/ZIP64 hơn 4 GiB và đối chiếu CRC bằng Python, chữ ký manifest Java/Node và bộ cài sai hash/thiếu dữ liệu. DeviceDiscovery được kiểm tra bằng Android API stubs cho đổi Wi-Fi, callback đến muộn, timeout, nhiều IPv4 và TXT fallback. Giao diện Windows đã chạy trong Wine. Các kiểm tra tự động này không thay thế việc thử trên điện thoại Android 16 và Wi-Fi thật của bạn; cài cập nhật nền của hệ điều hành chưa được kiểm chứng trên máy thật.

Lệnh: `npm test`, `npm run test:network`, `npm run test:android-host`, `npm run test:android-discovery`, `npm run test:features`. Dựng bằng `python scripts/build-installers.py` với Android SDK 35/JDK 21, MinGW-w64 GCC 14, NSIS 3.11 và Node Windows x64 24.15.0. Cần khóa ký APK gốc; script từ chối tạo khóa thay thế.

EXE chưa có chứng thư ký mã nhà phát hành; APK dùng khóa riêng của dự án. Nếu điện thoại báo lỗi mạng khi kiểm tra APK, kết nối Internet ổn định rồi thử lại. Truyền file hiện dùng HTTP trong LAN, chưa mã hóa đầu cuối; dùng mạng tin cậy.

## Đổi tên thiết bị

Windows: bấm **Đổi tên** cạnh dòng Máy này. Android: **Cài đặt → Đổi tên thiết bị**. Tên dài tối đa 50 ký tự, hỗ trợ tiếng Việt và emoji. Lưu tên để các máy cùng Wi-Fi thấy tên mới sau vài giây. Không đổi ID thiết bị, không dừng phiên truyền, tên được giữ sau khi mở lại.

## Gửi nhanh từ Explorer

Sau khi cài bản Windows 1.12, chọn một hoặc nhiều file → chuột phải → **Send to / Gửi tới → FlowDrop**. Trên Windows 11, chọn **Show more options / Hiển thị thêm tùy chọn** trước. FlowDrop mở và thêm file vào danh sách; chọn thiết bị nhận rồi bấm Gửi. Nếu đã mở, file được thêm vào cùng cửa sổ, giữ các file đã chọn và loại file trùng đường dẫn. Có thể gửi thư mục bằng cách này; thư mục được chuẩn bị để giữ tên/cấu trúc ở máy nhận. Nếu đang truyền, file mới chờ vào danh sách sau khi phiên hiện tại kết thúc. Menu thuộc tài khoản Windows đang cài ứng dụng; gỡ cài đặt sẽ xóa lối tắt Send to.


## Chia sẻ file từ Thư viện hoặc trình quản lý file Android

Chọn một hay nhiều ảnh, video hoặc tài liệu → Chia sẻ → FlowDrop. Trong FlowDrop, chọn thiết bị nhận, kiểm tra danh sách rồi bấm Gửi. Ứng dụng giữ tên/nội dung và loại file bị chọn trùng. Nếu FlowDrop đang mở, danh sách được đưa vào cùng ứng dụng. Chỉ dùng quyền đọc do ứng dụng nguồn cấp; không cần cấp quyền truy cập toàn bộ bộ nhớ. Link/văn bản hoặc đường dẫn file hệ thống không được tự tải/mở.

## Bảo mật bản 1.13

Khóa quyền API được giữ riêng cho cửa sổ Windows và bộ gửi Android; thiết bị khác trong Wi-Fi và website khác không được tự tạo phiên ghi file. Dữ liệu/tên file, mã nhận và trạng thái phiên được kiểm tra trước khi dùng. Gói thư mục được kiểm tra đường dẫn, CRC và dung lượng trống trước khi khôi phục. Windows dùng Node 24.22.2 LTS đã kiểm tra checksum; khóa ký cập nhật và APK giữ nguyên để cài đè.

Lưu ý: dữ liệu file trong LAN vẫn dùng HTTP, chưa mã hóa đường truyền. Tên thiết bị không phải chứng thực danh tính. Chỉ dùng mạng tin cậy cho dữ liệu nhạy cảm. Xem SECURITY.md trong gói mã nguồn để biết phạm vi và giới hạn của bản nâng cấp.
