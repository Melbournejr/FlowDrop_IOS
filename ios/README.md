# FlowDrop cho iPhone và iPad — mã nguồn bản phát triển 1.0.1

Đây là ứng dụng SwiftUI native, cửa sổ riêng, không dùng trình duyệt hoặc WebView. Một dự án dùng chung cho iPhone và iPad chạy iOS/iPadOS 16 trở lên.

**Trạng thái:** mã nguồn và workflow đã được chuẩn bị trong môi trường Linux. Chưa có lần build Xcode thành công, IPA, chữ ký Apple hay kiểm thử trên iPhone/iPad thật. Workflow sẽ biên dịch và kiểm thử trên máy macOS của GitHub; cần có kết quả xanh trước khi tải IPA. Bản iOS đang phát triển, chưa phải bản phát hành ổn định.

## Cập nhật từ gói 1.0 đã đưa lên GitHub

Gói 1.0.1 sửa lỗi Swift `return from initializer without initializing all stored properties` ở `SavedFile` mà log GitHub Actions của bản 1.0 đã báo. Các thuộc tính được khai báo riêng và có hàm khởi tạo rõ ràng; có kiểm thử đọc/ghi lịch sử file. Đã sửa thêm việc đọc thuộc tính `@Published` trước khi khởi tạo xong AppModel, khai báo an toàn truyền giữa các hàng đợi cho HTTPConnection theo cơ chế chạy trên một serial queue, và cập nhật checkout/upload-artifact sang v6 sử dụng Node.js 24. Chưa có kết quả chạy lại trên macOS để xác nhận toàn bộ build thành công.

Nếu đã có repository, không cần tạo lại:

1. Giải nén `FlowDrop-iOS-iPadOS-Source-1.0.1.zip`.
2. Mở GitHub Desktop → chọn repository của bạn → **Repository → Show in Explorer**.
3. Chép đè nội dung gói mới vào thư mục repository, giữ nguyên thư mục `.git`. Đảm bảo cả `ios` và `.github` được cập nhật.
4. Trong GitHub Desktop, nhập Summary `Fix iOS build 1.0.1` → **Commit to main → Push origin**.
5. Trên GitHub, vào **Actions → Build FlowDrop iOS → Run workflow** để tạo lần chạy mới từ commit vừa push.
6. Nếu lỗi tiếp, tải artifact **FlowDrop-iOS-Build-Logs**, gửi file log tương ứng để chẩn đoán. File IPA chỉ xuất hiện khi bước build thành công.

## Làm trên Windows: đưa mã lên GitHub

1. Đăng nhập <https://github.com>. Bấm **+ → New repository**. Đặt tên `FlowDrop-iOS`, chọn **Private**, tích **Add a README file**, rồi **Create repository**.
2. Cài **GitHub Desktop** từ <https://desktop.github.com/download/>. Đăng nhập tài khoản GitHub của bạn trong ứng dụng.
3. Trong GitHub Desktop, chọn **File → Clone repository → GitHub.com**, chọn `FlowDrop-iOS` và **Clone**.
4. Chọn **Repository → Show in Explorer** để mở thư mục vừa clone.
5. Giải nén gói `FlowDrop-iOS-iPadOS-Source-1.0.1.zip`. Chép **nội dung bên trong** vào thư mục repository. Sau khi chép, phải có `ios` và `.github` trực tiếp trong thư mục repository, không nằm trong một thư mục lồng thêm. Không chép vào thư mục `.git`.
6. Trở lại GitHub Desktop. Ô **Summary** nhập `Add FlowDrop iOS source`. Bấm **Commit to main → Push origin**. Nếu repo dùng nhánh tên khác, commit và push lên nhánh mặc định đó.

Không cần cài Xcode, Swift, Node.js hay Android SDK trên Windows để chạy quy trình này. Gói nguồn không chứa tài khoản, khóa ký hoặc bộ cài Windows/Android.

## Build IPA bằng GitHub Actions

1. Mở repository trên GitHub bằng trình duyệt.
2. Kiểm tra hạn mức **Actions** trong phần **Settings → Billing / Usage** của tài khoản. Runner macOS có thể tiêu thụ hạn mức/phát sinh phí theo gói tài khoản. Workflow không tự chạy khi push; chỉ chạy thủ công.
3. Mở tab **Actions**. Nếu GitHub hỏi bật Actions, cho phép workflow trong repository của bạn.
4. Ở bên trái chọn **Build FlowDrop iOS**.
5. Bấm **Run workflow**, chọn nhánh mặc định rồi **Run workflow**.
6. Mở lần chạy vừa tạo. Đợi các bước kiểm thử và **Build unsigned IPA** hoàn thành. Nếu có bước đỏ, mở bước đó để xem log; lúc này chưa có IPA hợp lệ để cài.
7. Khi job xanh, kéo xuống **Artifacts**, tải `FlowDrop-iOS-iPadOS-Unsigned`.
8. Giải nén artifact. File cần dùng là **`FlowDrop-Unsigned.ipa`**. `SHA256SUMS.txt` là mã kiểm tra; `READ-ME-FIRST.txt` ghi tình trạng chưa ký.

**IPA này chưa được ký. Không thể cài bằng cách bấm vào IPA trên iPhone hoặc gửi IPA qua chat.** Build không yêu cầu mật khẩu, chứng chỉ Apple hay GitHub Secrets.

## Ký và cài từ Windows bằng Apple ID miễn phí

1. Tải **Sideloadly** đúng trang <https://sideloadly.io/>. Cài các thành phần Apple/iTunes/iCloud theo hướng dẫn hiện tại trên trang chính thức và [FAQ](https://sideloadly.io/faq.html).
2. Nối iPhone/iPad vào Windows bằng cáp USB. Mở khóa thiết bị, bấm **Tin cậy máy tính này / Trust** nếu được hỏi.
3. Mở Sideloadly. Chọn đúng thiết bị ở mục **iDevice**.
4. Kéo `FlowDrop-Unsigned.ipa` vào ô IPA. Nhập Apple ID của bạn trong Sideloadly, bấm **Start** và thực hiện bước xác thực Apple nếu công cụ yêu cầu. Không đưa mật khẩu Apple ID vào GitHub, mã nguồn hoặc cuộc chat.
5. Sau khi cài, nếu iOS yêu cầu tin cậy nhà phát triển, vào **Cài đặt → Cài đặt chung → VPN & Quản lý thiết bị**, chọn hồ sơ Apple ID dùng để ký và tin cậy.
6. Nếu iOS yêu cầu **Developer Mode**, vào **Cài đặt → Quyền riêng tư & Bảo mật → Chế độ nhà phát triển**, bật rồi làm theo yêu cầu khởi động lại/xác nhận. Mục này có thể xuất hiện sau lần cài thử đầu tiên.
7. Mở FlowDrop, cho phép **Mạng cục bộ / Local Network**. Khi bật tùy chọn thêm ảnh/video vào Ảnh, ứng dụng sẽ hỏi quyền thêm vào thư viện.

Apple ID miễn phí thường phải **ký lại khoảng mỗi 7 ngày**; còn có giới hạn ứng dụng/thiết bị theo cơ chế ký miễn phí hiện hành. Đây là cài thử ứng dụng riêng của bạn. Muốn phân phối qua TestFlight/App Store cần Apple Developer Program và quy trình ký/phát hành tương ứng. Chưa cấu hình TestFlight trong gói nguồn này.

## Dùng FlowDrop sau khi cài

1. Kết nối hai thiết bị cùng Wi-Fi, mở FlowDrop ở cả hai. Máy Windows/Android cần bản 1.9 trở lên.
2. Trong tab **Thiết bị**, chọn thiết bị nhận, **Chọn file → Gửi file**.
3. Trên thiết bị nhận, mở tab **Phiên truyền**, chọn **Nhận và lưu**. Có phần trăm, dung lượng và số file đã lưu. Máy gửi chỉ báo hoàn tất sau khi nhận được xác nhận máy nhận lưu đủ file.
4. File iPhone/iPad tự lưu trong **Tệp → Trên iPhone/iPad của tôi → FlowDrop**. Tab **Đã nhận** có nút mở/chia sẻ. Tùy chọn **Thêm ảnh và video vào Ảnh** tạo thêm bản trong thư viện Ảnh, không xóa bản trong Tệp.
5. Giữ FlowDrop mở đến khi xong. iOS giới hạn thời gian chạy nền; nếu bị dừng, phiên phải gửi lại. Chưa có tiếp tục truyền từ điểm dừng.

Nếu không thấy thiết bị, kiểm tra quyền Mạng cục bộ, cùng Wi-Fi, FlowDrop mở ở các máy, Windows Firewall và mạng Wi-Fi không bật cách ly thiết bị. Bản iOS dùng Bonjour `_flowdrop._tcp`; không dùng UDP multicast tùy chỉnh nên không cần entitlement multicast đặc biệt. Không có mã nhập địa chỉ trong luồng sử dụng chính.

## Chi tiết cho lập trình viên

- Mở `ios/FlowDropApple.xcodeproj`, scheme `FlowDropApple`. Target universal `1,2`, iOS 16+, Swift 5, không thư viện bên ngoài.
- Chạy `swift test --package-path ios/FlowDropCore` trên Mac để kiểm tra parser, metadata lớn, tên file, lưu chống ghi đè và HTTP hai host thật. Kiểm thử host dùng loopback, không thay thế kiểm tra trên LAN và thiết bị iOS thật.
- `bash ios/scripts/build-unsigned.sh` tạo icon vector, build Xcode và đóng gói IPA chưa ký vào `ios/output`.
- Giao thức tương thích luồng gửi trực tiếp 1.9: cache file ở máy gửi, đề nghị `/api/offers`, máy nhận xác nhận rồi tải từ máy gửi và báo trạng thái qua `/api/offers/status` có token riêng. Không triển khai các API tạo upload của bản legacy từ trình duyệt.
- File truyền bằng bộ đệm 64 KiB/URLSession download ra đĩa, không nạp toàn bộ file vào RAM. Có bản cache ở máy gửi và bản tạm ở máy nhận; dung lượng thực tế phụ thuộc bộ nhớ trống và hệ thống. Giới hạn metadata 8 MiB và số nguyên giao thức 2^53−1 được giữ để tương thích. Không đặt trần 10 file hay 50/200 MB.
- Phiên đang hoạt động ở bộ nhớ, lịch sử file đã nhận lưu trên thiết bị. Cache mã gửi không được khôi phục sau khi thoát ứng dụng. Không báo hoàn tất nếu chưa lưu đủ byte/file.
- Truyền HTTP trong LAN như Windows/Android hiện tại; chưa có mã hóa đầu cuối. Không có máy chủ cloud nhận nội dung file, SDK quảng cáo hoặc analytics.

Tham khảo: [Apple về tài khoản miễn phí và trả phí](https://developer.apple.com/help/account/basics/about-your-developer-account), [quyền mạng cục bộ](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy), [cài ứng dụng phát triển](https://developer.apple.com/documentation/xcode/distributing-your-app-to-registered-devices).
