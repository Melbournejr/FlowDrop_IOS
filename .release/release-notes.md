# FlowDrop 1.13.0

- Android: xuất hiện trong menu Chia sẻ của Thư viện và trình quản lý file; nhận một/nhiều file, giữ tên, xem trước và chọn thiết bị rồi mới gửi.
- API tạo phiên gửi dùng khóa quyền riêng của ứng dụng; Windows không còn trả khóa qua HTTP chưa xác thực.
- Chặn yêu cầu từ website khác, Host giả và HTTP nhập nhằng; giới hạn công việc xác minh đồng thời và đóng socket không hoạt động.
- Kiểm tra mã, ID, tên, kiểu và dung lượng file; kiểm tra chỗ trống khi khôi phục thư mục.
- Windows dùng Node 24.22.2 LTS đã xác minh checksum. Giữ khóa ký cập nhật và APK gốc.

Cài đè, không gỡ bản cũ. APK versionCode 14. Đường truyền file LAN vẫn dùng HTTP, chưa mã hóa; dùng mạng tin cậy cho dữ liệu nhạy cảm. Xem SECURITY.md trong mã nguồn để biết phạm vi.

Đã kiểm tra chia sẻ file Android 16 với ứng dụng nguồn khác UID, gửi qua dịch vụ native đúng dữ liệu, cùng các kiểm thử mạng/bảo mật Node/Java và giao diện Windows trong Wine. Chưa thử bản này trên thiết bị vật lý.
