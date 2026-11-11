# Bật các cài đặt bảo mật của kho

Các workflow trong mã nguồn không tự cấp thêm quyền quản trị cho tích hợp GitHub. Nếu API báo `Resource not accessible by integration (HTTP 403)`, tài khoản có quyền admin vẫn cần một kết nối được GitHub cấp đúng quyền để thay đổi Settings.

## 1. Bảo vệ mã nguồn

Mở [Settings → Rules → Rulesets](https://github.com/Melbournejr/FlowDrop_IOS/settings/rules). Tạo ruleset nhánh cho `main`, bật Active, chặn xóa nhánh và force push, yêu cầu pull request, một phê duyệt và giải quyết thảo luận. Bật yêu cầu Code Owner review và kiểm tra `Workflow safety` sau lần CI thành công đầu tiên. Chủ kho có thể dùng quyền bypass chỉ qua pull request để tự sửa khẩn cấp mà không phải thêm tài khoản thứ hai. Không cấp bypass cho mọi người có quyền write. Mẫu cấu hình nằm ở `security/main-ruleset.json`.

## 2. Quét lỗi và chống lộ khóa

Mở [Settings → Advanced Security](https://github.com/Melbournejr/FlowDrop_IOS/settings/security_analysis). Bật Dependabot alerts/security updates, secret scanning và push protection nếu giao diện cung cấp. Bật private vulnerability reporting để nhận báo cáo riêng tư. CodeQL đã có workflow riêng, vì vậy dùng advanced setup của workflow; không bật một default setup trùng lặp.

## 3. Giới hạn quyền Actions

Mở [Settings → Actions → General](https://github.com/Melbournejr/FlowDrop_IOS/settings/actions). Chọn mặc định Read repository contents and packages, tắt quyền Actions tạo/phê duyệt pull request và yêu cầu phê duyệt workflow từ cộng tác viên ngoài. Chỉ cho phép GitHub-owned Actions cùng các Actions đã được duyệt. Nếu có tùy chọn bắt buộc pin Actions bằng full commit SHA, chỉ bật sau khi đã xử lý các workflow cũ còn dùng tag.

## 4. Bản phát hành và tài khoản

Nếu Settings → General có Release immutability, bật để khóa tag và asset của các bản được publish sau đó. Các workflow phát hành hiện tạo draft, tải/kiểm tra đủ asset rồi mới publish, phù hợp với chế độ này. Không xóa hoặc sửa asset đã phát hành.

Bật passkey/2FA tại [bảo mật tài khoản GitHub](https://github.com/settings/security). Đây là thao tác xác minh của chính chủ tài khoản, không cần gửi mã OTP hoặc mật khẩu cho người khác.

## Secrets đang trống

Đây là trạng thái hợp lệ với pipeline hiện tại: iOS build IPA chưa ký; pipeline Windows/Android tải lên bộ cài đã chuẩn bị sẵn. Không đưa khóa ký APK/RSA lên GitHub hoặc vào chat chỉ để điền mục Secrets. Nếu sau này cần ký trên CI, phải thiết kế quyền môi trường release và giới hạn workflow trước.
