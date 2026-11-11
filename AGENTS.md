# Quy tắc làm việc với FlowDrop

Các quy tắc dưới đây áp dụng lâu dài cho các nhiệm vụ sửa lỗi, kiểm thử và phát triển FlowDrop. Phạm vi riêng của đợt kiểm toán Giai đoạn 1 được ghi trong [báo cáo kiểm toán](docs/AUDIT-REPORT.md).

## Mục tiêu và phạm vi

- Bảo toàn hành vi FlowDrop 1.13.0, dữ liệu đã nhận và khả năng khôi phục bản đã phát hành.
- Windows và Android là hai nền tảng chính. iOS/iPadOS đang tạm dừng: không sửa, build hoặc mở rộng iOS nếu chủ dự án chưa yêu cầu rõ.
- Đọc `docs/AUDIT-REPORT.md`, `docs/ARCHITECTURE.md`, `docs/PROTOCOL.md` và `docs/FEATURES.md` trước khi thay đổi ứng dụng.
- Kiểm tra `git status`, nhánh, commit và các PR đang mở. Không ghi đè thay đổi của người khác. Đặc biệt đọc PR #1 trước khi làm bảo mật/CI để tránh trùng việc.
- `main` tại mốc kiểm toán chưa chứa trực tiếp mã Android/Windows. Nguồn tương ứng 1.13.0 nằm trong asset ZIP và payload nhánh automation; không coi các đường dẫn được ghi trong ZIP là thư mục đã tồn tại trên `main`.
- Không tự ý di chuyển/import nguồn native vào `main`; việc đó cần một nhiệm vụ và PR riêng.

## Kiểm soát thay đổi

1. Chỉ sửa chức năng được yêu cầu. Không kết hợp refactor, đổi giao diện, đổi dependency hay dọn mã không liên quan.
2. Không xóa hoặc thay thế tính năng đang hoạt động. Giữ danh sách bất biến trong `docs/FEATURES.md` và chạy kiểm tra liên quan.
3. Không thay đổi giao thức nếu chưa được chủ dự án phê duyệt rõ. Giao thức bao gồm discovery, route/method HTTP, schema JSON, kiểu số, MIME thư mục, token, trạng thái phiên, quy tắc complete/revoke/expiry và định dạng chữ ký cập nhật.
4. Không thay khóa ký APK, chứng thư/danh tính APK, khóa RSA cập nhật, khóa công khai được ghim, alias hoặc cấu hình ký. Không tự sinh khóa thay thế khi thiếu khóa gốc. Việc quản lý khóa phải là nhiệm vụ riêng có phương án tương thích/khôi phục.
5. Không đưa khóa riêng, mật khẩu, token, keystore hoặc gói khôi phục khóa vào Git, log, artifact CI hay Release. Chỉ đối chiếu fingerprint công khai.
6. Không tự động merge vào `main`, không force push và không xóa nhánh/tag/release/asset. Tạo PR để chủ dự án kiểm tra; mặc định Draft khi công việc cần quyết định hoặc xác minh thêm.
7. Không tự động tạo/publish Release, dispatch workflow phát hành, build/cài bản mới hoặc thay `latest.json` đang phục vụ. Quyền sửa mã không đồng nghĩa quyền phát hành.
8. Không sửa workflow hoặc dependency nếu nhiệm vụ không yêu cầu. Mọi quyền GitHub Settings cần xác minh riêng; tài liệu hay AGENTS.md không tự bật bảo vệ nhánh.
9. Chọn nhánh mới; nếu tên đã tồn tại, báo cáo và dùng tên khác. Không ghi đè nhánh cũ.
10. Ưu tiên thay đổi nhỏ, độc lập, có thể revert bằng commit riêng. Không dùng thao tác rollback có thể xóa dữ liệu người dùng.

## Quy trình sửa lỗi và kiểm thử

- Mỗi lỗi phải có: điều kiện tái hiện, phiên bản/nền tảng, thao tác hoặc request cụ thể, kết quả mong đợi, kết quả thực tế và bằng chứng/log đã loại bí mật.
- Xác định bài kiểm tra trước khi sửa. Với lỗi chức năng hoặc bảo mật, ưu tiên regression test thể hiện lỗi trước sửa và đạt sau sửa. Nếu không tái hiện được, ghi rõ, không báo đã sửa.
- Đọc script trước khi chạy: một số test cần JDK/JAR ngoài repo, ghi vào đường dẫn tuyệt đối hoặc dùng hơn 4 GiB đĩa. Dùng thư mục dữ liệu thử riêng; không dùng Downloads, APK/EXE, keystore hay cấu hình của người dùng làm dữ liệu thử.
- Không giảm bảo vệ API, bỏ kiểm tra chữ ký/CRC/kích thước, thay key hoặc đổi protocol để làm test xanh. Test harness lỗi phải được phân biệt với lỗi sản phẩm.
- Dùng kiểm tra thích hợp ở `docs/REGRESSION-PLAN.md`. Phân biệt unit/mock, JVM/stub, engine HTTP, Wine/emulator và thiết bị thật; chúng không thay thế nhau.
- Không báo kiểm thử thành công nếu chưa thực sự chạy. Ghi lệnh, môi trường, exit code, bài bị loại, thất bại và giới hạn. Không gọi toàn bộ suite thành công khi chỉ chọn một test.
- Thay đổi có thể ảnh hưởng hai nền tảng phải kiểm tra cả hai chiều Windows ↔ Android và Android ↔ Android; kiểm tra phiên bản cũ/mới khi liên quan tương thích. Nếu chưa thể chạy, để rõ là chưa xác minh và chuyển quyết định cho chủ dự án.
- Không tự cài/đổi dependency hay cập nhật toolchain chỉ để che lỗi môi trường. Mọi thay đổi như vậy phải được nêu trong phạm vi được duyệt.

## Kết thúc một thay đổi

- Kiểm tra diff theo allowlist nhiệm vụ; không mang theo thay đổi đang dở từ checkout khác.
- Báo cáo: điều gì thay đổi, lý do, kiểm thử đã chạy, kiểm thử chưa chạy, rủi ro và cách revert.
- Tách bằng chứng từ mã nguồn, kiểm thử đã chạy, báo cáo cũ và điều chưa xác minh. Không suy diễn báo cáo lịch sử thành kết quả mới.
- Dừng trước merge/phát hành để chủ dự án quyết định. Không hỏi lại quyền cho các bước đọc, kiểm tra hoặc hoàn thiện PR đã được giao.
