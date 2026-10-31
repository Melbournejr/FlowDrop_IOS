FlowDrop 1.11 cho Windows và Android:

- Chọn **Thư mục** để gửi: máy nhận tự tạo lại thư mục đúng tên gốc, giữ nguyên tên file, thư mục con, thư mục rỗng và nội dung. Không cần giải nén thủ công.
- Windows lưu trong thư mục nhận đã chọn. Android giữ cả cây thư mục trong `Download/FlowDrop/<Tên thư mục>`; ảnh/video gửi lẻ vẫn vào Album FlowDrop.
- Nếu đã có thư mục cùng tên, chỉ thêm số vào thư mục ngoài như `Dự án (1)`, không trộn hay ghi đè file cũ.
- Sửa nút **Mở thư mục** Windows: gọi Windows Shell trực tiếp, có phương án mở dự phòng và báo lỗi. Hỗ trợ đường dẫn có khoảng trắng/tiếng Việt.
- ZIP gửi như file thông thường vẫn được giữ nguyên ZIP.

**Cập nhật cả hai thiết bị lên 1.11** để tự khôi phục thư mục. Bản 1.10 đã có bộ cập nhật; có thể bấm Kiểm tra cập nhật hoặc cài đè EXE/APK. APK giữ nguyên khóa ký, versionCode 12; không cần gỡ bản cũ.

Đã kiểm tra bộ đọc Node/Java, tên tiếng Việt, chống ghi đè, gói lỗi/đường dẫn không an toàn và file ZIP64 hơn 4 GiB. Đã cài APK và kiểm tra nhận thư mục thật, MediaStore, ảnh trong thư mục và file lẻ trên Android 16 mô phỏng. Kiểm tra mở Explorer qua giao diện Windows chưa hoàn tất do phiên kiểm tra bị ngắt; cần xác nhận thêm trên Windows thật. Xem FlowDrop-Kiem-chung-1.11.json để biết phạm vi kiểm chứng.

Mã nguồn Windows/Android: FlowDrop-Source-1.11.zip. Windows 10/11 x64, Android 10 trở lên.
