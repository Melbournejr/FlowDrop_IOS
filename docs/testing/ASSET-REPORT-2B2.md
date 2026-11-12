# FlowDrop — khôi phục tài nguyên và hoàn thiện test, Giai đoạn 2B.2

Ngày quan sát: **12/11/2026, Asia/Saigon**. Nhánh `fix/restore-baseline-fonts-1.13.0`, base main [`6f13c909ca146dcb54fa6e0e3874e76875a090af`](https://github.com/Melbournejr/FlowDrop_IOS/commit/6f13c909ca146dcb54fa6e0e3874e76875a090af).

## 1. Kết quả và phạm vi

**[API] PR #5 đã merge** ở commit `6f13c909ca146dcb54fa6e0e3874e76875a090af`. Đã clone main mới nhất, đọc AGENTS, regression plan, báo cáo 2B.1 và toàn bộ JSON manifest/exclusions baseline trước khi làm việc; xác nhận remote main trùng và tạo nhánh mới, không ghi đè nhánh có sẵn.

**[CHECK] Khôi phục nguyên byte đúng ba BeVietnamPro TTF của custom Source ZIP 1.13.0**, tổng **409228 byte**. Khớp hash ZIP, exclusions baseline và font manifest. Có full OFL 1.1 sẵn trong cùng thư mục, giữ nguyên byte. Không đổi font khác, tên, glyph, encoding, CSS, Java/C++ UI hoặc thiết kế.

**[TEST] Hai lệnh HTTP và Android-host: exit 1 trước → exit 0 sau.** Toàn bộ **13/13 lệnh Node/JVM đã chạy đạt sau khôi phục**, trước là 11/13. Không sửa bất kỳ test/helper hoặc assertion nào; không skip hay giảm kích thước/tiêu chí. Có log, exit code và checksum để đối chiếu.

**[AUDIT] `FlowDrop.ico` chỉ được kiểm tra cho build về sau, không nhập.** Cấu trúc/hash đã xác minh; chưa đủ bằng chứng giấy phép/nguồn gốc riêng cho icon. Phạm vi nhập ở PR này chỉ gồm ba font đã có OFL rõ ràng. Không dùng OFL của font để cấp quyền cho icon hoặc phần mềm FlowDrop nói chung. Quyết định về icon được để riêng trước một nhiệm vụ khôi phục icon/build sau này.

## 2. Nguyên nhân thiếu tài nguyên — source và log mới

- Baseline Giai đoạn 2A loại bốn binary: ba TTF và icon. Đây là phạm vi riêng của đợt nhập 2A, không phải lệnh cấm lâu dài trong AGENTS. Không sửa manifest/exclusions cũ để che lịch sử; thêm provenance cho lượt khôi phục này.
- `web/style.css:1` tham chiếu cả ba TTF ở weight 400/500/700. `scripts/dev.mjs:82` đọc đúng path `web/assets/fonts/...`; thiếu file sau khi đã chuẩn bị response khiến client nhận `UND_ERR_SOCKET`. [Log trước](assets-2b2-logs/before/http.log).
- `TransferServer.java:250` ánh xạ các URL font vào Asset provider. `tests/HostHarness.java` đọc từ `web/`; thiếu TTF trả 500 trong khi assertion ở `android-host-integration.mjs:21` yêu cầu 200. [Log trước](assets-2b2-logs/before/android-host.log).
- `MainActivity.java:75` dùng Regular/Bold qua Android assets; `FlowDrop.cpp:401` đăng ký cả ba font trong thư mục web. Khôi phục đúng các file gốc giải quyết đầu vào thiếu, không đổi xử lý HTTP, capability, UI hoặc packaging/signing script.

Không có bằng chứng cần sửa helper độc lập trong đợt này; **toàn bộ `tests/` giữ nguyên**. Các phần còn lại sau assertion font nay đã thực sự chạy: 1 MiB/file rỗng, byte SHA-256, lưu đĩa, partial upload cleanup, revoke, expiry, metadata bounds, fixed/chunked upload và các kiểm tra quyền.

## 3. Provenance và kiểm tra trước khi nhập

Nguồn: [FlowDrop-Source-1.13.zip](https://github.com/Melbournejr/FlowDrop_IOS/releases/download/v1.13.0/FlowDrop-Source-1.13.zip) của Release `v1.13.0`, asset ID `733185749`, **611206 byte**. SHA-256 `d1fea853ad992c0b8febf8efa1cc988ef52bc2ca8e6b798eb440f2c7a243a962` khớp `docs/RELEASE-PROCESS.md`, metadata GitHub asset và `docs/baselines/native-1.13.0/manifest.json`.

Đã tải mới từ Release chính thức. Kiểm tra đủ 141 path/type trước ghi file: không traversal/absolute/drive/ADS/backslash, NUL/control, symlink/special/reparse, duplicate/casefold/Unicode collision hoặc file/parent conflict; kiểm local header/CRC/kích thước, compression/encryption và giới hạn giải nén. Chỉ lấy ba member allowlist bằng ghi mới độc quyền/no-follow, không `extractall`, không ghi đè. [Bằng chứng ZIP](assets-2b2-logs/archive-validation.json).

| Font gốc | Byte | SHA-256 |
| --- | ---: | --- |
| `BeVietnamPro-Regular.ttf` | 132948 | `cd1ef6e9d7db28ad5cdb88a65ccbe693870e60d340b791f349d248342b4fe4c3` |
| `BeVietnamPro-Medium.ttf` | 135980 | `b60832bfa0fcd015158112c64d7e3fdad3b0c6287d1823f85a3103636e845268` |
| `BeVietnamPro-Bold.ttf` | 140300 | `7f738fe5c43c8872807b20e2d30d42163618de8a4daf7f48a939adac32c16847` |

Ba hash trùng cả ZIP, `exclusions.json` 2A và `web/assets/fonts/manifest.json` hiện có. Kiểm tra bảng name/OS2 và sfnt bằng fontTools có sẵn (4.61.1), không cài dependency: version **1.002**, weights **400/500/700**, embedding flags **0**, tổng sfnt **0xb1b0afba**. Không chuyển format, subset, sửa bảng font hoặc tạo lại asset.

Provenance đầy đủ: [FONT-RESTORATION-1.13.0-2B2.json](../assets/FONT-RESTORATION-1.13.0-2B2.json). Kiểm tra lại từ root repository:

```bash
sha256sum --check docs/assets/FONT-RESTORATION-SHA256SUMS.txt
```

Danh sách đó kiểm ba TTF, OFL.txt và font manifest gốc. Không thêm quyền executable; Git mode các TTF là `100644`.

## 4. OFL và quyền lưu trữ/phân phối

**[LICENSE]** `web/assets/fonts/OFL.txt` có thông báo **Copyright 2021 The Be Vietnam Pro Project Authors (https://github.com/bettergui/BeVietnamPro)** và toàn văn **SIL Open Font License 1.1**. File 4397 byte, SHA-256 `6b7f8f73609a25ea78c891e34cf37b06f8a676b7ea986e941e43b009110f2a85`, trùng nguyên byte với ZIP; không sửa nó. Metadata nhúng nameID 0/13/14 ở cả ba TTF xác nhận cùng tác giả/copyright và OFL 1.1.

Các căn cứ áp dụng cho chính ba font này:

- Phần Permission cho phép copy/embed/redistribute bản sửa hoặc nguyên bản; điều kiện 1 cấm bán font riêng lẻ. Repository phân phối nguồn ứng dụng cùng font, không tạo sản phẩm bán font độc lập.
- Điều kiện 2 cho phép bundle/phân phối cùng software khi mỗi bản có thông báo bản quyền và giấy phép. Giữ toàn bộ `OFL.txt` cạnh font và giữ metadata nhúng đáp ứng phần tài nguyên được nhập; các gói tương lai vẫn phải mang notice/license.
- Điều kiện 3 về Reserved Font Name khi có bản sửa: không đổi tên hoặc sửa font ở đây, vì byte trùng bản phát hành nguồn.
- Điều kiện 5 yêu cầu font tiếp tục thuộc OFL. Không gán một license khác cho font và không suy OFL trở thành license cho code FlowDrop hay icon.

**Quyết định phạm vi:** đủ bằng chứng nguồn gốc và giấy phép để đưa **ba font OFL nguyên bản** vào Draft PR theo yêu cầu 2B.2; không có quyết định bản quyền/binary bổ sung cần chờ đối với ba file đã nêu. Ngoại lệ binary chỉ gồm đúng ba TTF nhỏ (409228 byte), không nhập installer, runtime, JAR, keystore, private key hoặc icon. AGENTS không có binary allowlist lâu dài cấm font; quy định loại binary của 2A giữ nguyên trong báo cáo lịch sử. Không thay chính sách toàn repository.

## 5. Icon và các tham chiếu để chuẩn bị build sau

**[CHECK]** Source ZIP chứa `desktop/windows/FlowDrop.ico`: **19820 byte**, SHA-256 `cce4d31a79b6350c73daa884e9493d6ebc70746ac8e7471c924e0ad1b767650e`, khớp exclusions baseline. ICONDIR type 1, sáu PNG 32-bit kích thước **16/32/48/64/128/256**; offsets/sizes nằm trong file, kích thước IHDR và CRC các PNG chunk hợp lệ. Không chuyển/resize hoặc sinh icon khác.

**[?] Quyền icon:** trong snapshot repository/ZIP được kiểm tra chưa tìm thấy giấy phép hoặc chứng cứ nguồn sáng tác riêng cho ICO. `LegalCopyright "FlowDrop"` trong NSIS không tự chứng minh quyền cho tệp icon. Không tự áp OFL/MIT của thành phần khác cho nó, không nhập ICO trong PR này. Nếu muốn khôi phục icon ở bước tiếp theo, chủ dự án cần xác nhận quyền/provenance và phạm vi lưu trữ binary trước khi thực hiện. Hạng mục này là kiểm tra cho build sau theo yêu cầu 6, không mở rộng allowlist nhập font.

| Tham chiếu | Trạng thái sau lượt này | Hệ quả |
| --- | --- | --- |
| CSS / Node / Java host / Win32 private font registration | Ba TTF gốc đã có; OFL/font manifest giữ nguyên | Sáu request font ở hai engine đã kiểm 200/type/byte/hash |
| `FlowDrop.rc:4` → `FlowDrop.ico` | Vẫn thiếu, icon chỉ kiểm tra trong ZIP | `windres` sẽ cần input này ở bước build; chưa tuyên bố Windows build sẵn sàng |
| `FlowDrop.rc:3` → `FlowDrop.manifest` | Có sẵn | Không sửa manifest |
| Android `@drawable/ic_launcher` | XML vector có sẵn | Không cần nhập icon Android mới hoặc sửa manifest |
| `/favicon.svg`, `/manifest.webmanifest` | Được sinh inline bởi Node/Java handlers | Không phải file tĩnh bị thiếu |
| `.openai/hosting.json` của build website cũ | Thiếu trong cả source ZIP/main | Input deployment cũ, không tạo trong đợt font |
| Hai Python script ký/đóng gói bị loại ở 2A | Vẫn không có trên main | Không sửa/khôi phục; cần nhiệm vụ được duyệt riêng trước build installer |
| Node Windows runtime/SDK/MinGW/NSIS | Prerequisite/build payload ngoài Git, có runtime pin hiện có | Không tải runtime, thay dependency hoặc build/cài app |

Inventory có đường dẫn nguồn và tool hiện có: [resource-references.json](assets-2b2-logs/resource-references.json). Không kiểm tra bằng cách build EXE/APK hoặc ký lại.

## 6. Kiểm thử trước/sau — log và exit code

Linux; Node `v24.19.0`, Java `openjdk version "21.0.12.1" 2026-08-18`, Python 3.12.14. JAR org.json:json:20240303 giữ SHA-256 `3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed`. `npm ci --ignore-scripts` cài đúng 8 package từ lock với cache riêng; package/lock không đổi.

Trước: 12/11/2026 15:06:21 +0700 → 12/11/2026 15:10:05 +0700. Sau: 12/11/2026 15:29:40 +0700 → 12/11/2026 15:32:09 +0700. Cùng 13 lệnh, không thay source test/flags/data size. Trước 11/13 đạt, hai lỗi đã nêu; sau **13/13 đạt**, không timeout. Runner điều phối chạy tiếp để thu đủ log, exit của từng lệnh con được giữ bên dưới và trong JSON.

| Lệnh | Trước: exit / thời gian | Sau: exit / thời gian | Log |
| --- | --- | --- | --- |
| `npm test` | 0 / 0.732s | 0 / 0.607s | [trước](assets-2b2-logs/before/unit.log) · [sau](assets-2b2-logs/after/unit.log) |
| `node --test tests/harness.test.mjs` | 0 / 1.597s | 0 / 0.452s | [trước](assets-2b2-logs/before/harness-unit.log) · [sau](assets-2b2-logs/after/harness-unit.log) |
| `node tests/http-integration.mjs` | 1 / 0.438s | 0 / 1.713s | [trước](assets-2b2-logs/before/http.log) · [sau](assets-2b2-logs/after/http.log) |
| `node tests/discovery-integration.mjs` | 0 / 3.302s | 0 / 3.08s | [trước](assets-2b2-logs/before/discovery.log) · [sau](assets-2b2-logs/after/discovery.log) |
| `node tests/peer-integration.mjs` | 0 / 12.113s | 0 / 11.904s | [trước](assets-2b2-logs/before/peer.log) · [sau](assets-2b2-logs/after/peer.log) |
| `node tests/lan-discovery-integration.mjs` | 0 / 18.565s | 0 / 16.646s | [trước](assets-2b2-logs/before/lan-discovery.log) · [sau](assets-2b2-logs/after/lan-discovery.log) |
| `node tests/android-host-integration.mjs` | 1 / 2.535s | 0 / 2.615s | [trước](assets-2b2-logs/before/android-host.log) · [sau](assets-2b2-logs/after/android-host.log) |
| `node tests/android-discovery-state.mjs` | 0 / 2.241s | 0 / 1.781s | [trước](assets-2b2-logs/before/android-discovery.log) · [sau](assets-2b2-logs/after/android-discovery.log) |
| `node tests/security-integration.mjs` | 0 / 12.587s | 0 / 13.108s | [trước](assets-2b2-logs/before/security.log) · [sau](assets-2b2-logs/after/security.log) |
| `node tests/large-transfer-integration.mjs` | 0 / 19.495s | 0 / 16.313s | [trước](assets-2b2-logs/before/large-transfer.log) · [sau](assets-2b2-logs/after/large-transfer.log) |
| `node --test tests/features-1.10.test.mjs` | 0 / 57.7s | 0 / 22.975s | [trước](assets-2b2-logs/before/features.log) · [sau](assets-2b2-logs/after/features.log) |
| `node --test tests/folder-receive.test.mjs` | 0 / 66.734s | 0 / 34.198s | [trước](assets-2b2-logs/before/folders.log) · [sau](assets-2b2-logs/after/folders.log) |
| `node tests/android-native-client.mjs` | 0 / 25.887s | 0 / 23.708s | [trước](assets-2b2-logs/before/native-client.log) · [sau](assets-2b2-logs/after/native-client.log) |

Nhóm Node test có **10/10 unit**, **16/16 helper**, **4/4 features**, **5/5 folder**, không skip. Các script integration còn lại đều exit 0 sau khôi phục. Bài >4 GiB chạy tuần tự sau kiểm tra ít nhất 18 GiB đĩa trống và cgroup RAM >=2 GiB; thực tế khoảng 19,29 GiB trống, RAM limit 8 GiB, CPU quota 2 core. Có wall timeout 600/900/1500s cho features/folder/native-client. Không giảm size để lấy PASS; thời gian không được coi là benchmark.

**[TEST] Probe tài nguyên riêng:** sáu GET (3 font × Node native/JVM Android), đều **200**, `Content-Type: font/ttf`, đúng số byte và SHA-256 manifest gốc; probe exit 0, 2.487s, không sót scratch. [Log](assets-2b2-logs/font-http.log) · [JSON](assets-2b2-logs/font-http.json). Probe không sửa hoặc thêm helper vào `tests/`.

Không có suite đã đạt trước chuyển sang lỗi sau trong lượt thực thi này. Không phát hiện lỗi độc lập đòi hỏi sửa helper/production. Log được loại capability/UUID runtime; toàn bộ file bằng chứng có [checksum](ASSET-LOG-SHA256SUMS.txt).

## 7. Diff, rủi ro và rollback

- Thêm ba TTF gốc; thêm provenance/checksum, báo cáo và log. Chỉ sửa tài liệu hướng dẫn hiện hành `REGRESSION-HARNESS.md` để phân biệt kết quả lịch sử 2B.1 với kết quả 2B.2. Không sửa báo cáo cũ, manifest import, font manifest hoặc OFL.
- **201 file main đã đối chiếu:** 200 file giữ nguyên byte, một file hướng dẫn cập nhật; toàn bộ code ứng dụng, **49 file tests/helper/fixture**, iOS, workflows, signing identities, dependency/lock và AGENTS không đổi. [source-integrity.json](assets-2b2-logs/source-integrity.json).
- Không thay signing script, keystore/certificate/key/pin, giao thức hoặc UI code. Không thực hiện PR #1, CI/release workflow, build/ký/cài hoặc publish.
- Chưa chạy Win32/Wine, Android emulator/device/MediaStore/share UI, ma trận binary cũ/mới hoặc install/update/downgrade. Kết quả xanh chỉ dành cho các lệnh Node/JVM đã liệt kê; icon/build prerequisites và quyền icon vẫn là gate riêng cho tương lai. Không gọi đây là release/build-ready.
- Giữ Draft. Rollback qua PR revert commit khôi phục tài nguyên/tài liệu; không gỡ/cài app hay xóa dữ liệu người dùng/khóa/Release. Revert font sẽ làm tái xuất hiện hai lỗi asset đã ghi trước; cần giữ log để biết đó là hệ quả dự kiến.

Không cần đổi protocol, test criteria hoặc font/giao diện khác để giải quyết hai lỗi. Bước tiếp theo là chủ dự án review phạm vi ba font OFL và kết quả kiểm thử; việc khôi phục icon hoặc chuẩn bị build phải có quyết định riêng theo bằng chứng còn thiếu, không tự làm trong PR này.
