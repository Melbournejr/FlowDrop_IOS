# FlowDrop 1.13.0 — kiểm thử LAN vật lý (2D.2-B)

Đây là hướng dẫn tạo **bằng chứng mới trên máy của chủ dự án**. Kết quả CI Node/JVM, emulator và thao tác copy tự kiểm của toolkit không chứng minh Wi-Fi vật lý hoặc Windows ↔ Android native E2E.

## Bắt đầu nhanh trên Windows 10/11

1. Tải artifact **FlowDrop-2D2-Owner-Toolkit** từ workflow Cross-platform E2E của PR 2D.2, giải nén. Artifact chứa script và tài liệu, không chứa APK/EXE. Đối chiếu SHA256SUMS.txt/toolkit-manifest.json với artifact đúng head trong PR. Dùng Python **3.12 trở lên** từ python.org nếu máy chưa có. Không cần biết lập trình.
2. Giữ nguyên FlowDrop production đang dùng. Xem phiên bản trên cả hai thiết bị; ghi đúng phiên bản thực tế vào CHECKLIST.md. Nếu không phải 1.13.0, ghi khác baseline. Không gỡ production, cài đè test APK hoặc cung cấp khóa ký.
3. Mở PowerShell tại thư mục toolkit, chạy `./Run-FlowDrop-LAN.ps1`. Menu 1 tạo dữ liệu, 2 kiểm môi trường, 3 bắt đầu bấm giờ, 4 dừng giờ, 5 so sánh file, 6 xuất báo cáo, 7 kiểm lại SHA nguồn. Nếu chính sách PowerShell của máy không cho chạy script, dùng các lệnh Python dưới đây; toolkit không thay ExecutionPolicy.
4. Chọn **thư mục thử mới** dưới một thư mục có sẵn, ví dụ `C:\Users\you\Desktop\FlowDrop-LAN-01`. Không dùng thư mục Downloads hoặc thư mục dữ liệu FlowDrop làm workspace. Script từ chối ghi đè thư mục đã tồn tại; không có chức năng tự xóa.
5. Cùng Wi-Fi tin cậy, mở FlowDrop hai bên, chọn thiết bị và gửi **cả thư mục `FlowDrop-LAN-<run>` vừa tạo**. Receiver chấp nhận, chờ kết thúc, rồi kiểm SHA bên nhận. File trong thư mục giữ nguyên cây dưới Download/FlowDrop trên Android; ảnh/video trong cây không tự tách sang album.
6. Chạy Report và điền checklist. Gửi lại report.json, comparison.json, source-manifest.json, evidence-manifest.json, SHA256SUMS.txt và checklist. Chỉ những quan sát đã làm mới đánh PASS. Không gửi profile/cache/token/mã chia sẻ đang dùng hoặc logcat thô.

Trong repository, các script nằm ở `tools/physical-lan/`. Trong ZIP phát cho chủ dự án, các script và hướng dẫn nằm cùng thư mục.

## Lệnh tương đương không cần menu

Thay đường dẫn mẫu bằng nơi của bạn. Đường dẫn phải ở trong dấu nháy nếu có khoảng trắng.

```powershell
python -X utf8 ./flowdrop_lan.py --root "C:\Users\you\Desktop\FlowDrop-LAN-01" prepare
python -X utf8 ./flowdrop_lan.py --root "C:\Users\you\Desktop\FlowDrop-LAN-01" environment
./Collect-FlowDrop-Network.ps1 -Root "C:\Users\you\Desktop\FlowDrop-LAN-01"
python -X utf8 ./flowdrop_lan.py --root "C:\Users\you\Desktop\FlowDrop-LAN-01" hash-source
python -X utf8 ./flowdrop_lan.py --root "C:\Users\you\Desktop\FlowDrop-LAN-01" start --direction Windows-to-Android --mode blackbox-production-1.13.0 --network physical-wifi
# Bấm Gửi trong FlowDrop; chờ receiver báo kết thúc.
python -X utf8 ./flowdrop_lan.py --root "C:\Users\you\Desktop\FlowDrop-LAN-01" stop
```

`start/stop` phải chạy trên **cùng máy điều khiển**, không trên hai máy khác nhau. Khoảng đo chứa thao tác UI và thời gian phản ứng của người dùng. Report tách MB/s (10⁶ byte/giây) và Mbps (10⁶ bit/giây, gấp 8), không gọi đây là throughput thuần của Wi-Fi. Để trống CPU/RSS/discovery latency nếu chưa đo; Task Manager/Performance Monitor có thể cung cấp bằng chứng riêng với thời điểm và phương pháp.

Mỗi lượt thử độc lập dùng workspace mới. Nút bấm giờ không được reset im lặng. Source manifest được hash trước gửi; nguồn thay đổi hoặc manifest sửa sau bắt đầu sẽ bị chặn. Dữ liệu sinh gồm 110 file: rỗng, 1 KiB, 1 MiB, 101 file trong một thư mục, tên Việt/Trung/emoji/khoảng trắng/tên dài, PNG 2×2, AVI RGB tổng hợp, PDF trắng hợp lệ, ZIP, cây lồng và hai thư mục rỗng. **101 file trong một batch không phải cam kết 101 upload chạy song song**; app 1.13 có thứ tự streaming riêng.

Các profile tải lớn phải chọn rõ và kiểm cả hai máy đủ đĩa: `100m` = 100 MiB, `1g` = 1 GiB, `zip64` = 4 GiB + 17 byte. Không sparse/truncate giả dữ liệu; generator ghi đủ byte và hash theo luồng, bộ đệm 64 KiB. Ngoài bản gốc, app có thể cần staging, bản ZIP và file nhận; dự trù tối thiểu **5 lần dung lượng** mỗi đầu, cộng dung lượng OS. Guard local chỉ kiểm phần đĩa của generator, không chứng nhận receiver đủ chỗ.

```powershell
python -X utf8 ./flowdrop_lan.py --root "C:\Users\you\Desktop\FlowDrop-LAN-Large01" prepare --profile 100m --allow-large
# Lượt riêng: thay 100m bằng 1g hoặc zip64 khi đã kiểm đủ tài nguyên.
```

## So sánh nguồn và đích Windows

Đưa toolkit và source-manifest.json + file marker `.flowdrop-lan-test.json` của lượt đó vào một workspace điều khiển trên máy nhận (USB được phép dùng để chuyển **manifest**, không được coi copy USB là FlowDrop PASS). `compare` chỉ đọc các **đường dẫn file tổng hợp có trong manifest** dưới thư mục đã chọn; không quét thư mục cá nhân hoặc thư mục Downloads toàn bộ. Không xóa file thừa.

```powershell
python -X utf8 ./flowdrop_lan.py --root "C:\Users\you\Desktop\FlowDrop-LAN-01" compare --received-dir "D:\FlowDrop-Test-Receive\FlowDrop-LAN-<run>"
python -X utf8 ./flowdrop_lan.py --root "C:\Users\you\Desktop\FlowDrop-LAN-01" report
```

Khi gửi lại cùng thư mục, chọn chính root mới app tạo, ví dụ `FlowDrop-LAN-<run> (1)`. Kiểm root cũ giữ nguyên hash; app không được trộn vào nó. Với thử **file lẻ** bị thêm hậu tố, có thể cung cấp `--name-map names.json`, một JSON object ánh xạ đúng source relative path sang tên đích thực. Tool chặn traversal, đường dẫn tuyệt đối, junction/symlink, hard link, gộp hai nguồn thành một đích và tên mất tiền tố FD của lượt. Không đổi expected hash để ép PASS.

Đối với hai Windows, A giữ start/stop; B chạy compare. Chuyển comparison.json của B về A (cùng run ID), rồi Report trên A nếu muốn gộp timing. Thư mục payload không cần tồn tại tại B để so sánh từ manifest. File nhận thực phải đến từ FlowDrop, không copy USB trong bước nhận đang đánh giá.

## Android ADB chỉ đọc, không cài/gỡ ứng dụng

Không bắt buộc ADB để gửi/nhận; cần ADB hoặc một công cụ hash tin cậy trên Android để có bằng chứng SHA tại đúng đầu Android. Không suy SHA từ tên/kích thước hoặc chỉ từ ảnh thông báo thành công. Nếu không có hash ở Android thì case giữ **NOT VERIFIED**.

Tải Platform Tools từ Google chính thức, xác minh nguồn; bật USB debugging trên thiết bị thử do bạn quản lý, chấp nhận đúng máy Windows của bạn. Kết nối USB chỉ để đọc metadata/hash; **truyền FlowDrop vẫn qua Wi-Fi**, không adb push/pull để tạo bằng chứng nhận.

```powershell
& "C:\Android\platform-tools\adb.exe" devices
& "C:\Android\platform-tools\adb.exe" -s YOUR_SERIAL shell getprop ro.build.version.sdk
& "C:\Android\platform-tools\adb.exe" -s YOUR_SERIAL shell dumpsys package app.flowdrop.mobile
python -X utf8 ./flowdrop_lan.py --root "C:\Users\you\Desktop\FlowDrop-LAN-01" adb-hash --adb "C:\Android\platform-tools\adb.exe" --serial YOUR_SERIAL --remote-dir "/sdcard/Download/FlowDrop/FlowDrop-LAN-<run>"
python -X utf8 ./flowdrop_lan.py --root "C:\Users\you\Desktop\FlowDrop-LAN-01" report
```

Trong package output chỉ cần đối chiếu versionName/versionCode/targetSdk; không export toàn bộ dumpsys hoặc app profile. `adb-hash` tự nhắm một serial, chỉ `get-state/getprop/stat/sha256sum/test` trên đường dẫn tổng hợp đã biết, không logcat, content provider, token, password, install, uninstall hoặc force-stop. Serial chỉ lưu SHA-256, không lưu nguyên serial. Dùng đúng tên root thực; nếu root đã bị thêm hậu tố khi nhận lần hai, có thể hash bằng công cụ độc lập hoặc chọn lượt workspace mới; ADB helper cố ý chỉ nhận root nguyên tên UUID để tránh đọc nhầm dữ liệu cá nhân.

**Android → Windows:** ban đầu tạo manifest/fixture trên máy điều khiển, copy USB fixture vào `/sdcard/Download/FlowDrop/FlowDrop-LAN-<run>` để chuẩn bị **nguồn**; việc chuẩn bị này không phải test transfer. Trước khi gửi, chạy lệnh `adb-hash` trên nguồn Android với thêm `--purpose source`; kết quả riêng ở android-source-comparison.json. Sau đó chọn thư mục đó trong FlowDrop Android, gửi qua Wi-Fi sang Windows, chạy compare trên file nhận. Giữ cả SHA nguồn Android và SHA đích Windows. Android → Android làm tương tự, hai serial khác nhau; hash nguồn với `--purpose source`, đích mặc định, ghi thiết bị gửi/nhận vào checklist. Không cài test APK lên điện thoại production.

## Discovery, nhận bằng mã và topology

Mỗi case ghi thời điểm, OS/API, app version/hash nếu đo được, loại Wi-Fi/Ethernet, router/client-isolation, số adapter và kết quả thực.

- Tự phát hiện: đóng/mở danh sách thiết bị, đo từ khi mở FlowDrop đầu kia đến tên xuất hiện; giữ device ID riêng tư ngoài evidence công khai nếu không cần. Cơ chế thật là mDNS `_flowdrop._tcp` và UDP 53317 / 239.255.77.77, xác minh bằng `/api/config`; nhìn thấy tên không chứng minh danh tính mật mã.
- Gửi trực tiếp cần chấp nhận bên nhận; receiver phải chưa có dữ liệu trước consent. Sau nhận, đối chiếu SHA, bộ đếm byte/file và trạng thái kết thúc cả hai bên.
- Nhận bằng code: tạo mã mới, nhập ở máy nhận cùng Wi-Fi; thử mã sai, mã đã thu hồi, mã có whitespace theo chuẩn app. Không lưu mã còn hiệu lực trong ảnh/report. Mã được tìm qua các peer, không phải dịch vụ Internet.
- IP trực tiếp chỉ thử ở luồng UI thực sự có hỗ trợ; không khẳng định mọi UI 1.13 có ô IP. Không dựng API mở ghi remote hoặc chia sẻ local capability để thay luồng của app.
- Rời Wi-Fi, kết nối lại, đổi IP/DHCP và nhiều NIC/VPN: chờ danh sách cũ hết hạn theo từng engine, kiểm không gửi nhầm máy, thiết bị trở lại xuất hiện đúng. Node UDP có cửa sổ khoảng20s; mDNS Node khoảng70s; Android khác cơ chế/timeout. Không áp một deadline sai cho mọi engine.
- Windows Firewall: `Collect-FlowDrop-Network.ps1` chỉ đọc adapter/profile/rule FlowDrop; không tắt firewall. Nếu cần cho phép ứng dụng trên mạng Private tin cậy, chủ máy dùng đúng cơ chế app/Windows và ghi lại lựa chọn. Không auto mở rule rộng.
- Router guest Wi-Fi/client isolation có thể chặn peer dù cùng SSID. Ghi BLOCKED và topology; không kết luận ứng dụng lỗi nếu router cố ý cô lập. Không tự thay cấu hình router/VPN.
- Foreground/background Android: HOME, khóa màn hình và mở lại, ghi thời gian/notification/byte progress. OEM battery behavior và Android16 cần thiết bị thật; emulator không thay bằng chứng này.

## Fault injection và kết quả mong đợi

Thử trên dữ liệu tổng hợp và máy/volume thử; không xóa dữ liệu hay làm đầy ổ production.

| Case | Thao tác / assertion |
|---|---|
| Người nhận từ chối | Không file được lưu trước/không báo completed; sender thấy rejected nếu tracking hỗ trợ |
| Sender/receiver hủy | Hủy bằng UI đúng bên; không báo hoàn tất giả, file dở không công khai, file đã lưu trước đó giữ SHA |
| Disconnect25/50/75 | Ngắt Wi-Fi thủ công khi UI cho thấy xấp xỉ tỷ lệ đó, ghi bytes thực + tỷ lệ quan sát, rồi kết nối lại. Không gọi tỷ lệ nhìn bằng mắt là byte-exact |
| Tắt app/backend | Chỉ dừng FlowDrop của máy thử bằng thao tác hệ điều hành; không kill toàn bộ node.exe hoặc Explorer. Kiểm failure/lifecycle/file dở, mở lại giữ file đã lưu |
| Hết dung lượng | Chỉ thử volume phụ hoặc máy thử với giới hạn đã biết. Không chạy script lấp đầy C: hay điện thoại đang giữ dữ liệu cá nhân; không có fixture an toàn thì NOT VERIFIED |
| Nguồn bị xóa/đổi | Chỉ file tổng hợp. Ghi rõ trước hay sau staging: sau stage có thể vẫn gửi thành công hợp lệ từ bản đã cache; không mặc định phải fail |
| Trùng tên/root | Hai code/lượt độc lập; tên/root mới có hậu tố, không trộn/ghi đè, so SHA cả bản cũ và mới |
| Request/path/ZIP lỗi | Tests engine cũ/mới kiểm tự động; không fuzz app production của người khác. Native/folder API chỉ thử trên máy riêng và giữ byte/path assertions |
| Mã sai/thu hồi/hết hạn | Không download/completed giả. TTL transfer24h cần lượt dài thực; không đổi đồng hồ OS để giả kết quả. Offer pending khoảng120s là TTL khác |
| Repeated transfer | Mỗi lượt có code/receiver consent/SHA riêng, kiểm cleanup/session và process. Không yêu cầu resume theo offset khi baseline chưa thiết kế |

Test update signature, APK certificate rejection/PackageInstaller và downgrade phải tách khỏi dữ liệu LAN: có protocol fixtures trong Native Regression, nhưng cài signed update production end-to-end chưa được kiểm. Không dùng APK sai chứng thư thử cài đè điện thoại đang dùng; không xin key/password production.

## Phạm vi, bảo mật, kết quả và gửi bằng chứng

`report.json` cố ý giữ physical_wifi/native_e2e là NOT VERIFIED nếu chỉ có SHA/timing. Chủ dự án/reviewer điền CHECKLIST.md với bằng chứng nhận diện hai native app + thiết bị + mạng + thao tác + SHA nguồn/đích mới có thể nghiệm thu 2D.2-B. File hash trùng sau copy local hoặc USB không được diễn giải thành FlowDrop E2E PASS. Test-artifact mode phải có provenance đúng commit; black-box production chỉ chứng minh binary thực đang dùng, không suy nó build từ head PR.

HTTP LAN và discovery hiện cleartext, tên thiết bị không có pairing mật mã. Không gửi file cá nhân/nhạy cảm trong lượt thử. Toolkit không triển khai TLS, resume, cài app, đổi signing pin, tắt firewall hoặc tunnel công cộng. Log có chỉ định rõ các trường còn NOT VERIFIED. Giữ workspace đến khi đối chiếu xong; tự xóa **chính thư mục dữ liệu tổng hợp đó** bằng Explorer nếu muốn, không có cleanup tự động trên máy cá nhân.

Trước chia sẻ report, chỉ giữ file allowlist trong evidence-manifest.json và checklist; network-environment.json có địa chỉ IP nội bộ phục vụ chẩn đoán, có thể che khi công khai và ghi SHA bản đã che riêng. Không upload logcat/profile/session/token/keystore. SHA là integrity evidence, không phải chữ ký xác thực người thực hiện.
