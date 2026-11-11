# Hợp đồng tương thích FlowDrop 1.13.0

Đây là mô tả **[SRC]** từ [Source ZIP 1.13.0][Z], không phải đề xuất đổi giao thức. Các đường dẫn bên dưới tính từ `FlowDrop/` trong ZIP. Nhãn kiểm thử và giới hạn ở [AUDIT-REPORT.md](AUDIT-REPORT.md). Mọi thay đổi wire format cần chủ dự án phê duyệt và một ma trận tương thích.

## 1. Discovery và địa chỉ

| Cơ chế | Hợp đồng đọc từ nguồn |
| --- | --- |
| mDNS/DNS-SD | `_flowdrop._tcp`; TXT có `app=flowdrop`, `protocol=1`, `id`, `label`, `platform`, `version`, `direct=1`; có hint `ipv4` |
| UDP | IPv4, cổng 53317, multicast `239.255.77.77`, kèm broadcast; JSON có `app:"flowdrop"`, `discovery:1`, `kind:"hello"/"query"/"bye"`, `id`, `name`, `platform`, `port`, `version` |
| Xác minh peer | Gọi HTTP `/api/config`, đối chiếu tên ứng dụng/deviceId; loại self, hợp nhất theo ID thay vì tên hiển thị |
| Liveness | Node UDP gửi khoảng 3 giây/lần và loại peer sau 20 giây; mDNS Node có vòng làm mới 10 giây và cửa sổ 70 giây. Không ép mọi engine có cùng timeout |
| Cổng transfer | Dùng cổng peer quảng bá. Windows native chọn cổng động; Android ưu tiên 5173 và có fallback |

Nguồn: `scripts/discovery.mjs:7–44`, `scripts/lan-discovery.mjs:5–50`, `android/.../DeviceDiscovery.java:30–119`, `android/.../LanDiscovery.java:12–88`, `HostService.java:82`, `TransferServer.java:132–144`. `android/...` là `android/src/app/flowdrop/mobile/`.

Tên thiết bị và deviceId tự khai báo không phải chứng minh danh tính mật mã. Chưa có TLS, pairing hoặc chữ ký cho discovery/LAN payload. Không tự nâng `protocol`/`discovery` hoặc thay multicast/port để sửa lỗi tìm thiết bị.

## 2. Config và capability cục bộ

`GET /api/config` trả các trường như `name:"FlowDrop"`, `deviceName`, `deviceId`, `platform`, `version`, `mode:"local"`, `offerKey`, `direct:1`, `sessions:1`, `addresses`; có thể có trường riêng của engine như `discoveryName`. Client phải xử lý các trường bổ sung hợp lệ.

| Khả năng | Truyền ở đâu | Ý nghĩa |
| --- | --- | --- |
| Capability Windows native | `X-Desktop-Token`; được C++ nhận từ pipe `FLOWDROP_READY` | Điều khiển local API và tạo upload session ở host native |
| Capability Android | `X-Local-Token`; truyền nội bộ HostService/TransferClient | Tạo upload session trên loopback của chính ứng dụng |
| Upload token | `X-Upload-Token`; chỉ trả lúc tạo transfer | PUT, complete và revoke transfer đó |
| `offerKey` | Được trả trong config của máy nhận rồi gửi lại trong offer | Khớp process nhận hiện tại; không phải bí mật ghép đôi thiết bị |
| `statusToken` | Trong offer; dùng trong body status | Xem trạng thái của một offer; không công khai trong danh sách phiên |

Nguồn: `scripts/dev.mjs:23,43–54,86–99,129–130`, `scripts/peer-offers.mjs:10–43`, `android/.../TransferServer.java:228–244`, `TransferClient.java:14–16,36–45`.

**[TEST]** Cả Node native mode và JVM host từ chối tạo session không có capability, sai capability và request remote dù biết capability; không lộ capability trong config. Request Origin/Host/framing xấu cũng bị chặn. Đây chưa phải bảo vệ trước một OS đã bị chiếm quyền.

Không dùng hướng dẫn web prototype cũ để cho phép browser từ máy khác tạo upload trên native host. Thay đổi bảo vệ này sẽ làm mất ranh giới đã được thêm trong 1.13.

## 3. Transfer API

| Method / route | Request và kết quả chính |
| --- | --- |
| `POST /api/transfers` | Local capability + `{files:[{name,size,type?},...]}`. 201: `{code,files:[{id,name,size,type}],createdAt,expiresAt,token}` |
| `PUT /api/transfers/{code}/files/{id}` | `X-Upload-Token`, body nhị phân theo luồng. Phải đúng số byte metadata; upload chưa hoàn tất không được công khai |
| `POST /api/transfers/{code}/complete` | Upload token. Kiểm tra mọi file đã có đúng kích thước; chuyển trạng thái nội bộ sang `ready` |
| `GET /api/transfers/{code}` | Metadata công khai khi ready: code, files, createdAt, expiresAt; không có upload token |
| `GET /api/transfers/{code}/files/{id}` | Body nhị phân, Content-Length và Content-Disposition có tên UTF-8; không cần upload token nếu biết code/id còn hiệu lực |
| `DELETE /api/transfers/{code}` | Upload token; thu hồi metadata/file. Người biết code đọc không tự có quyền thu hồi |

Nguồn: `worker/index.js:1–87`, `android/.../TransferServer.java:20–22,228–328`, `TransferClient.java:36–73`.

Các số và chuỗi cần giữ:

- Mã sinh từ `ABCDEFGHJKLMNPQRSTUVWXYZ23456789`, dài 8 ký tự. Các validator nhận `[A-Z2-9]{8}`. Hai tập này không hoàn toàn đồng nhất; không tự đồng nhất chúng trong một bản sửa khác. Nhận bằng mã có bước bỏ khoảng trắng/dấu `-` và đổi uppercase (`scripts/code-lookup.mjs:3–11`).
- File ID là UUID; metadata validator kiểm tra ID duy nhất. Kích thước là số nguyên không âm, tổng trong phạm vi số nguyên an toàn JavaScript `2^53−1 = 9007199254740991`; Java dùng `long` nhưng giữ cùng giới hạn wire format.
- Metadata tối đa 8 MiB; một số control request chỉ 16 KiB. File name tối đa 255 đơn vị chuỗi theo validator và MIME được kiểm tra/giới hạn. Không thêm hạn mức sản phẩm 10 file/50 MiB/200 MiB.
- TTL transfer là 24 giờ; cần host giữ dữ liệu khả dụng. Mã này được tra trên LAN, không phải dịch vụ tra mã trên Internet.
- HTTP file body được stream, có kiểm tra byte count. Không thấy digest mật mã cho từng file trong transfer metadata. SHA-256 được dùng trong test và update, không được suy thành tính toàn vẹn mật mã của LAN transfer.
- Status thường gặp: 400 metadata/body sai, 403 thiếu quyền, 404 không tồn tại/đã thu hồi, 409 chưa ready/chưa đủ file, 410 hết hạn, 413 metadata/body quá phạm vi, 507 thiếu chỗ trống ở nơi có kiểm tra. Error body có `error`; không chuẩn hóa lại các khác biệt error status giữa hai engine khi chưa được duyệt.

**[TEST]** Unit và host JVM đã kiểm tra số byte, file rỗng, Unicode, fixed-length/chunked, expiry/revoke và upload dở. Không có kết luận mọi kích thước/thiết bị đều đã thử.

## 4. Offer và phiên làm việc

Sau khi host gửi đã stage và complete, nó POST tới máy nhận:

```json
{
  "code": "ABCDEFGH",
  "port": 12345,
  "deviceId": "opaque-sender-id",
  "offerKey": "opaque-current-receiver-key",
  "statusToken": "opaque-per-offer-token"
}
```

Ví dụ là dữ liệu giả, không phải mã hoặc token đang hoạt động.

Receiver dùng IP của socket gửi + port đã khai báo, gọi config và metadata ở máy gửi, đưa yêu cầu vào `pending`, rồi trả `{id,state,tracking:1}`. Không tự công bố file chỉ vì nhận offer. UI native dùng kênh điều khiển local để chấp nhận/từ chối; khi chấp nhận, receiver kéo file và chỉ báo completed sau khi lưu đủ.

`POST /api/offers/status` nhận `{id,token}`; token là `statusToken`. Trạng thái bao gồm `pending`, `accepted`, `transferring`, `completed`, `rejected`, `failed`, `expired`; `untracked` là fallback cục bộ cho peer không trả `tracking:1`. Trường phiên gồm `id`, `direction`, `name`, `code`, `count`, `size`, `bytes`, `filesDone`, `currentName`, timestamp và error. `completed` phải có `bytes==size` và `filesDone==count`, không chỉ là hoàn tất upload staging.

Nguồn: `scripts/peer-offers.mjs:6–82`, `android/.../TransferServer.java:40–127`, `ReceiveService.java:25–31,49–98`. Pending offer có TTL khoảng 120 giây; có giới hạn việc xác minh/offer đồng thời. Những giới hạn tài nguyên này không phải quota số file trong một lượt.

Nhận bằng mã tìm share local và trên các peer được phát hiện, kiểm tra code trả về, từ chối mã mơ hồ giữa nhiều peer nếu chưa chọn đúng peer. Vì vậy discovery hỏng cũng có thể khiến tìm mã hỏng (`scripts/code-lookup.mjs:9–29`, `android/.../CodeLookup.java`).

## 5. Thư mục và cách lưu

- MIME bắt buộc cho gói thư mục: `application/vnd.flowdrop.folder+zip`. ZIP thường với `application/zip` không được tự giải nén thành thư mục.
- Gói có một root, hỗ trợ Unicode, file rỗng, thư mục rỗng và ZIP64. Node tạo gói streaming; các reader xử lý cả các gói deflated hợp lệ.
- Từ chối traversal, absolute/drive path, liên kết, duplicate path, CRC/kích thước sai và định dạng không hỗ trợ. Có staging và rollback khi import lỗi; kiểm tra chỗ trống trước mở rộng mỗi entry, giữ khoảng 64 MiB dự phòng.
- Windows tạo root dưới thư mục nhận đã chọn; Android giữ toàn bộ cây dưới `Download/FlowDrop`. Khi trùng root, thêm hậu tố; không trộn vào thư mục cũ. Tên không an toàn có thể bị làm sạch hoặc từ chối tùy vị trí/engine; không hứa giữ mọi tên không hợp lệ trên Windows.
- File lẻ Windows đi qua `safeReceiveName`; Android đi qua `ReceiveFiles.safeName/route`. Ảnh/video lẻ đi album, nội dung ảnh trong folder vẫn nằm trong cây folder.

Nguồn: `scripts/folder-zip.mjs`, `scripts/folder-receive.mjs`, `scripts/desktop-storage.mjs:13–19,56–93`, `android/.../FolderArchive.java`, `FolderPackage.java`, `FolderReceive.java`, `ReceiveFiles.java`, `ReceiveService.java:69–98`.

**[TEST]** Bốn test folder nhỏ đã đạt: giữ cây/tên/root trùng, Java deflated → Node, dữ liệu/path/CRC lỗi và kích thước khai báo vượt dung lượng. Test ZIP64 trên 4 GiB bị loại khỏi lần chạy này; chưa có kết quả lớn mới.

## 6. Chữ ký và cập nhật

Envelope update là `{payload: "raw JSON UTF-8 string", signature: "base64"}`. Xác minh **đúng byte của chuỗi payload**, bằng RSA-SHA256 (SHA256withRSA); không parse rồi serialize lại trước khi verify.

Payload schema 1 có `app:"FlowDrop"`, `platforms.windows` và `platforms.android`; mỗi platform có `version`, `url`, `size`, `sha256`, Android có thêm `versionCode`. URL là HTTPS, không có userinfo. Giới hạn 1 GiB trong updater là giới hạn **bộ cài**, không phải file LAN. Windows so sánh version `x.y.z`; Android dùng versionCode tăng và đối chiếu package/versionName/certificate APK.

**[SRC][TEST]** Khóa RSA công khai ở Node, Android, publisher và `main/security` khớp nhau; manifest phát hành hiện tại verify được. Chứng thư APK giữ nguyên fingerprint đã ghi trong [RELEASE-PROCESS.md](RELEASE-PROCESS.md). Ed25519 của danh mục khóa không phải thuật toán thay thế cho updater.

Windows hỏi cập nhật, có Later, kiểm tra busy và hash lại trước khi chạy installer. Android có tự kiểm tra/job/cache, PackageInstaller và đường xử lý hệ điều hành yêu cầu xác nhận; không hứa silent install trên mọi thiết bị. Không chỉnh version comparison hay khóa để ép downgrade.

Nguồn: `scripts/secure-update.mjs`, `scripts/release-config.mjs`, `android/.../UpdateManifest.java`, `AppUpdates.java:65–146`, `.release/publish.py` ở nhánh 1.13.0.

## 7. Gián đoạn và tương thích

Không tìm thấy giao thức resume theo offset/chunk hoặc cam kết tiếp tục đúng byte sau mất kết nối. Poll trạng thái có thử lại; receipt có thể bỏ qua file đã lưu xong. Điều đó không đồng nghĩa resume một file dở. Không thay idle timeout thành timeout tổng ngắn cho file lớn.

Khả năng peer cũ tiếp tục hoạt động được tài liệu 1.13 mô tả; đợt này chưa chạy ma trận ứng dụng 1.12/1.13 trên máy thật. Fixture test mang tên phiên bản cũ cũng không phải bằng chứng đã chạy binary cũ. Xem [ma trận regression](REGRESSION-PLAN.md) trước mọi sửa đổi chạm protocol.

[Z]: https://github.com/Melbournejr/FlowDrop_IOS/releases/download/v1.13.0/FlowDrop-Source-1.13.zip
