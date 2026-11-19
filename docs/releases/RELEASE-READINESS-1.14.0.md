# FlowDrop 1.14.0 — chuẩn bị bản chính thức

Phạm vi: PR #12, tiếp tục nhánh `feature/flowdrop-1.14.0`, không merge/publish. Chủ dự án xác nhận giữ Android keystore và RSA update private key gốc. Hai khóa chỉ được dùng trên máy Windows tin cậy của chủ dự án; không upload/GitHub Secrets/chat. Kết quả cuối, source HEAD, CI và checksum artifact được ghi tại PR #12 và Draft Release, không suy từ báo cáo cũ.

## Quyết định phát hành

- Auto/LAN vẫn mặc định. Turbo/Wi-Fi Direct/Bluetooth rendezvous có nhãn **thử nghiệm**, không cam kết ổn định mọi OEM/driver hay tốc độ hai chiều bằng nhau. Không tự bật legacy khi TLS lỗi.
- Package Android `app.flowdrop.mobile`, versionName `1.14.0`, versionCode `15`, minSdk 29/targetSdk 35. Không dùng Preview hoặc APK TEST ONLY để cập nhật ứng dụng chính.
- SHA-256 chứng thư bắt buộc: `65cbed4feb375d2c3c2eb94e668bd7aaee7ce5b24f436887873a6fa11719f97f`. Alias `flowdrop` không đổi. RSA phải có public key trùng pin hiện tại; không tạo/thay khóa.
- Mã nhận, HMAC Android, TLS/SAS/session/replay/revocation, kiểm tra SHA/length/CRC và chống ghi đè giữ nguyên logic đã kiểm ở PR12. Đợt này không thêm tính năng truyền file mới.
- Chưa phát hiện P0 mới từ lượt đọc/test liên quan; đây không phải chứng nhận kiểm toán mật mã độc lập. P1 còn lại là kiểm chứng artifact được ký production và Android install-over bằng APK đó. P2: Turbo phần cứng, throughput bất đối xứng và fault/disk-full dài trên máy thật chưa được chứng minh đầy đủ.

## CI và build

Run `44454199123` thất bại ở setup integration, exit22: log cho thấy Maven trả404 khi tải `org.json:json:20240303`; test integration chưa chạy. Probe sau đó tải200 và SHA256 đúng `3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed`. Đã yêu cầu rerun riêng các job lỗi, không bỏ required check. Trạng thái rerun/final HEAD phải đọc lại từ GitHub.

Các lượt chuẩn bị sau tiếp tục gặp404 từ `repo.maven.apache.org`, kể cả retry. Test setup nay retry tối đa3 lần trong ngân sách hữu hạn, sau lỗi tải mới thử endpoint Maven Central chính thức `repo1.maven.org` cho **cùng artifact/version/SHA**. Probe cả hai endpoint đã cho cùng SHA trên. Hash sai phải dừng, không thử mirror để che lỗi; hết các endpoint cố định vẫn lỗi thì setup FAIL và tests NOT VERIFIED. URL thực tải được ghi riêng trong setup.json. Không đổi dependency, checksum hay required check.

Sau khi cả hai host Central tiếp tục404 trên runner, bổ sung mirror Maven Central do Google phục vụ: `https://maven-central.storage-download.googleapis.com/maven2/org/json/json/20240303/json-20240303.jar`. Probe thực cũng trả đúng SHA/78332byte. Chỉ tối đa ba endpoint HTTPS cố định, không URL tùy ý; tất cả đều lỗi thì FAIL, hash sai từ bất kỳ endpoint nào phải dừng trước compile. Không coi mirror tự tạo checksum là chứng cứ: so với SHA độc lập đã pin từ baseline.

Các lỗi build-control đã tái hiện: thiếu record hash cho chuỗi User-Agent Android đã sửa; npm từ chối dùng cùng file user/global config; Python3.12.16 không có trên Windows2025; Windows PowerShell con kế thừa module path của pwsh nên không tìm thấy Get-FileHash. Sửa tương ứng: bổ sung source pin/test, tách npmrc (npm ci thực chạy fixture rỗng), dùng Windows Python3.12.10 như CI hiện có, chọn module tích hợp đúng engine trong tiến trình script ký. Lỗi đầu và exit code vẫn giữ trong run lịch sử; chỉ run cuối được dùng cho kết luận.

Kiểm tra process trên Windows sau đó cho environment/quote/path PASS nhưng exact stdin hash FAIL. Script ký chuyển sang ghi UTF-8 raw không BOM với newline cố định và xóa byte buffer sau ghi; kiểm tra dùng thêm ký tự Unicode tổng hợp. Không đổi cách nhập khóa/mật khẩu hoặc bỏ assertion stdin.

Run44464009474 xác nhận stdin có96byte thay vì93 và ký tự đầu U+FEFF (65279): BOM3byte xuất hiện ngay khi Process.Start khởi tạo StreamWriter.AutoFlush, trước khi ghi raw. Đối chiếu mã .NET Framework chính thức `microsoft/referencesource` (Process.cs và mscorlib/system/io/streamwriter.cs) xác nhận cơ chế này. Sửa bằng cách đặt Console.InputEncoding thành UTF8Encoding(false) riêng trong lúc Start rồi khôi phục ngay trong finally, vẫn ghi raw và giữ exact byte/hash/Unicode assertions. Chỉ run sau sửa mới chứng minh kết quả cuối.

Giữ toàn bộ Native Regression (kể cả ZIP64), Native Build, Native Runtime và Cross-platform tại final HEAD. Workflow bổ sung `Native Release Preparation` chỉ contents:read, không production secrets/publisher. Nó dùng toolchain đã pin, chạy builder lại từ source, xuất APK production-layout **chưa ký** và EXE production. Không đổi tên/tái sử dụng artifact TEST ONLY thành release.

APK chưa ký được kiểm zipalign, packaged package/version/SDK/permissions, inventory/font, bytecode Java8 và trạng thái không có chữ ký. Windows được kiểm PE64/GUI/version/icon/runtime/dependency/NSIS payload bằng công cụ hiện có. Công cụ local gồm Node Windows24.22.2 đã pin, apksigner từ SDK35 đã xác thực và Windows JRE21.0.13+9 chính thức. JRE Windows có digest/size công khai của Adoptium, SHA256 `2332c0b4cff6bed722da3567c91d5e47568bcba863fa4945d0a8d6fc76158628`, giấy phép/NOTICE đi cùng archive. Không tải `latest`, không sửa dependency ứng dụng.

## Bảo toàn dữ liệu khi cập nhật

Windows giữ `%LOCALAPPDATA%\Programs\FlowDrop` và `%LOCALAPPDATA%\FlowDrop\Data`. Bộ kiểm tra VM phải tải đúng EXE1.13 chính thức/hash đã pin, tạo settings/receipt/file nhận tổng hợp và đổi tên, sau đó cài EXE1.14 lên app đang chạy. Nó kiểm UUID, tên, settings, receipt/history, byte của file nhận và danh tính TLS mới ổn định qua restart. Không chạy script VM này trên máy cá nhân; script từ chối môi trường khác hoặc profile có sẵn FlowDrop. Kết quả thực chạy nằm trong artifact Windows Upgrade của workflow bổ sung.

Android: cùng package/certificate và versionCode14→15 là điều kiện cập nhật tại chỗ. Đường dẫn preferences/storage không đổi trong đợt phát hành; app sẽ tạo danh tính TLS mới lần đầu, không thay UUID thiết bị. **Chưa thể xác nhận Android production install-over trong cloud khi chưa có APK được ký gốc.** Không re-sign1.13 bằng khóa tạm để giả lập production upgrade, không uninstall để ép cài. Sau ký, nên thử `adb install -r` trên thiết bị thử có1.13 và dữ liệu tổng hợp trước máy chính.

## Một việc chủ dự án cần làm: ký cục bộ

1. Tải `FlowDrop-1.14.0-LOCAL-SIGNING-KIT.zip` từ artifact `Release Preparation` tại final HEAD, đối chiếu checksum rồi giải nén vào thư mục riêng. Không đặt keystore/private key vào gói này.
2. Mở PowerShell tại thư mục vừa giải nén, chạy:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\Start-ReleaseSigning.ps1
   ```

3. Chọn hai khóa gốc trong hộp thoại; nhập mật khẩu ẩn. Mật khẩu keystore đi qua stdin của apksigner, mật khẩu RSA chỉ vào environment của child process cục bộ; không argv/password file/log/cache/GITHUB_ENV. Không in raw child errors. Script không truy cập GitHub hay cài ứng dụng lên máy cá nhân.
4. Script kiểm signature APK và exact fingerprint1.13, đối chiếu mọi entry APK với unsigned build proof, kiểm EXE SHA/size, giải mã RSA gốc cục bộ, xác minh public pin, ký đúng raw payload và verify cả Windows/Android. Chỉ xuất thư mục đầy đủ sau khi các kiểm tra đạt; không ghi đè output cũ. ZIP kết quả chỉ có năm file công khai bên dưới. Upload năm file đó lên Draft Release, không upload khóa và chưa bấm Publish.

Gói ký được chạy kiểm checksum và Java/Node thật trên Windows VM; kiểm thử stdin/env/quote/error dùng giá trị giả. Điều đó không phải đã ký bằng private key production. Chỉ báo production-signed PASS sau khi apksigner/RSA verifier thực chạy với output chủ dự án.

## Năm asset cuối

- `FlowDrop-1.14.0-Android.apk`
- `FlowDrop-Setup-1.14.0-Windows-x64.exe`
- `latest.json` — RSA-SHA256 gốc, URL releasev1.14.0, versionCode15, SHA256/size đúng cả hai installer
- `SHA256SUMS-release.txt`
- `Release-notes-1.14.0.md` — pinned TLS/pairing, mã chia sẻ, experimental Turbo, explicit legacy và lưu ý cập nhật

Draft có thể giữ EXE/notes trong lúc chờ owner signing; nó chưa phải bộ phát hành đầy đủ. Không công bố/tag/latest-feed cho tới khi đủ năm asset, chữ ký/certificate/checksum hợp lệ, CI final HEAD đạt và chủ dự án xác nhận phát hành. Giữ nguyên Release1.13 và assets cũ. Android chống downgrade: rollback không đồng nghĩa uninstall/hạ versionCode an toàn; dùng sao lưu và bản sửa tiếp theo nếu cần. Revert thay đổi chuẩn bị qua PR; không reset main, sửa protectMain hoặc thay production keys.
