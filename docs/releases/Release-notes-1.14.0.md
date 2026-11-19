# FlowDrop 1.14.0 — Windows và Android

- Truyền từ xa mặc định qua pinned TLS, ghép thiết bị bằng mã xác nhận sáu số trên cả hai màn hình. Danh tính TLS được lưu bằng DPAPI trên Windows và AndroidKeyStore trên Android. Có phiên xác thực, chống phát lại và thu hồi tin cậy.
- Sửa nhận file bằng mã tám ký tự khi discovery đến muộn; chuẩn hóa mã và báo lỗi rõ hơn. Mã chia sẻ khác mã xác nhận ghép thiết bị.
- Sửa khác biệt Android JSON/HMAC khiến đã xác nhận ghép nối nhưng gửi file vẫn bị từ chối.
- Giữ nhận đủ byte, SHA-256 khi có digest, chống ghi đè và xác nhận hoàn tất từ máy nhận. Giữ gửi thư mục/cấu trúc tên, ZIP64, phiên truyền, Share sheet Android và Send To Windows.
- Auto/LAN là mặc định. **Turbo/Wi-Fi Direct và thiết lập mạng qua Bluetooth là thử nghiệm**: có chỉ dẫn từng bước, khôi phục kết nối giới hạn và chẩn đoán cục bộ. Chưa bảo đảm mọi driver/OEM ổn định hoặc tốc độ hai chiều bằng nhau. Nếu bị ngắt, chuyển sang LAN. Chưa có resume theo offset cho file dở.
- Tương thích thiết bị 1.13 qua HTTP chỉ khi bật chủ động, có cảnh báo không mã hóa; tắt sau khởi động lại. TLS lỗi không tự chuyển sang HTTP. Nên cập nhật cả hai máy lên 1.14 và xác nhận ghép nối mới.

## Cập nhật từ 1.13.0

- Cài đè, **không gỡ ứng dụng**. APK chính thức phải là `app.flowdrop.mobile`, versionName `1.14.0`, versionCode `15`, minSdk 29/targetSdk 35, cùng chứng thư ký gốc của 1.13.0. Không dùng FlowDrop Preview/TEST ONLY để cập nhật ứng dụng chính.
- Windows giữ thư mục cài đặt, settings, receipt/history hiện có, UUID thiết bị và file đã nhận. Dừng phiên truyền trước cập nhật; sao lưu dữ liệu quan trọng. Khóa/danh tính TLS mới được tạo lần đầu cho tính năng bảo mật, không thay UUID thiết bị cũ. Phiên truyền đang chạy không được khôi phục qua restart.
- APK giữ cùng package/chứng thư để Android cập nhật tại chỗ và giữ dữ liệu. Chỉ coi cập nhật production đã xác minh sau khi APK được ký bằng khóa gốc và thử cài đè; kiểm thử bằng khóa tạm không chứng minh điều này.
- Bộ cài và `latest.json` phải được kiểm SHA-256, chữ ký RSA gốc và chứng thư APK trước phát hành. EXE chưa có Authenticode; chữ ký RSA của feed là cơ chế xác minh cập nhật, không phải chứng thư Windows Shell.
- Giữ Release 1.13.0. Android chặn downgrade thông thường; giữ bản cũ không đồng nghĩa có thể tự hạ versionCode mà vẫn giữ dữ liệu. Không gỡ app để ép rollback.

iOS/iPadOS tiếp tục tạm dừng. Không có cam kết tốc độ hoặc chứng nhận an toàn mật mã độc lập từ kết quả CI.
