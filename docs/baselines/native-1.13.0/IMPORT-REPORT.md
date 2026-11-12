# FlowDrop 1.13.0 — nhập baseline nguồn native, Giai đoạn 2A

Ngày kiểm tra: **12/11/2026 UTC**. Nhánh: `baseline/native-source-1.13.0`. Base là main sau khi PR #3 merge: [`998e8feae1514a7e3ad52177fd598c8fb329f7b2`](https://github.com/Melbournejr/FlowDrop_IOS/commit/998e8feae1514a7e3ad52177fd598c8fb329f7b2).

## 1. Phạm vi và kết quả

**[CHECK] Đã nhập 110 file văn bản nguyên byte từ asset Release chính thức; loại 31 file.** Đây là baseline nguồn **có loại trừ**, chưa phải checkout có thể build nguyên bộ cài. Không sửa nội dung ứng dụng, protocol, UI, dependency/lockfile, test harness hoặc cấu hình ký. Không lấy các thay đổi quản lý khóa chưa commit từ checkout local cũ.

| Nhóm được nhập | Số file | Lý do cần giữ |
| --- | ---: | --- |
| `android/` | 26 | Manifest, vector drawable và production Java của Android |
| `desktop/windows/` | 9 | Win32/C++, resource nguồn, manifest, NSIS, PowerShell/VBS, runtime pin, vendored `json.hpp` dạng text |
| `scripts/` | 18 | Node host/shared, discovery, storage/folder, verifier updater và công cụ nguồn; loại hai script ký có mật khẩu |
| `tests/` | 47 | Unit, Node/JVM integration, stub và nguồn smoke test; giữ cả lỗi harness đã ghi nhận |
| `web/` | 5 | Text UI/shared assets, license và manifest font; không nhập font nhị phân |
| `worker/` | 1 | Handler dùng chung được Node host và test tham chiếu |
| `package.json`, `package-lock.json` | 2 | Đúng dependency và lệnh của ZIP, không cài hoặc cập nhật |
| `download-site/index.html` | 1 | Template nguồn được `scripts/build-downloads.mjs` tham chiếu; không deploy |
| `INSTALL.md` | 1 | Tài liệu payload được script đóng gói gốc tham chiếu; giữ nguyên, các mô tả không phải kiểm thử mới |

Danh sách từng file, SHA-256, kích thước, đường dẫn gốc, Git blob và mode nằm trong [manifest.json](manifest.json). [SHA256SUMS.txt](SHA256SUMS.txt) chỉ liệt kê 110 file nhập từ ZIP, không tự băm bốn tài liệu bằng chứng của đợt nhập này.

## 2. Nguồn gốc và kiểm tra ZIP

- **[CHECK]** Tải mới custom asset [FlowDrop-Source-1.13.zip](https://github.com/Melbournejr/FlowDrop_IOS/releases/download/v1.13.0/FlowDrop-Source-1.13.zip) của `v1.13.0`, asset ID `733185749`. Không dùng Source code ZIP tự sinh của tag hoặc checkout local cũ.
- **[CHECK]** Kích thước `611206` byte; SHA-256 `d1fea853ad992c0b8febf8efa1cc988ef52bc2ca8e6b798eb440f2c7a243a962` khớp cả bảng trong `docs/RELEASE-PROCESS.md` tại base commit và `digest` trong metadata GitHub Release.
- **[CHECK]** Kiểm tra toàn bộ 141 central-directory entry **trước khi ghi bất kỳ source nào**: root `FlowDrop/`, không absolute/drive/UNC/ADS/backslash, NUL/control, `.`/`..`, component rỗng, tên Windows reserved hoặc dấu chấm/khoảng trắng cuối. Không trùng path, không collision Unicode NFC/casefold và không xung đột file/parent-directory.
- **[CHECK]** Không có symlink/special file/reparse entry hoặc ZIP mã hóa; chỉ stored/deflate. Áp trần 10.000 entry, 100 MiB tổng, 32 MiB/file, tỷ lệ nén 1.000:1; ZIP thực tế có 2114636 byte giải nén.
- **[CHECK]** Đọc toàn bộ member để kiểm tra local header, CRC và kích thước trước khi nhập. Không dùng `extractall`; chỉ ghi các file allowlist qua tạo mới độc quyền, kiểm tra destination không có symlink và không ghi đè.
- **[CHECK]** Mỗi file nhập đối chiếu byte, SHA-256 và kích thước với member ZIP tương ứng. Bỏ duy nhất prefix `FlowDrop/`; không đổi encoding, newline, nội dung, tên hoặc dependency. ZIP dùng regular mode `100600`; Git biểu diễn file thường không executable là `100644`.

## 3. File chưa thể nhập và ranh giới bảo vệ

Danh sách đầy đủ **31 file**, digest và lý do từng file: [exclusions.json](exclusions.json).

| Nhóm loại trừ | Số file | Lý do / ảnh hưởng |
| --- | ---: | --- |
| `ios/**` | 21 | Giữ cây iOS trên main nguyên vẹn; không sửa/build iOS |
| `.github/workflows/flowdrop-ios.yml` | 1 | Giữ nguyên workflow hiện có, tránh chồng PR #1 |
| `.gitignore`, `README.md` | 2 | Không ghi đè policy và tài liệu đang có trên main |
| `SECURITY.md` | 1 | Path đã nằm trong PR #1 đang mở, xử lý ở nhiệm vụ riêng |
| `scripts/build-installers.py:35` | 1 | Có mật khẩu ký APK hardcode; loại nguyên file, không sửa hay in giá trị |
| `scripts/build-native-test-apk.py:16` | 1 | Có mật khẩu ký test APK hardcode; loại nguyên file, không sửa hay in giá trị |
| `desktop/windows/FlowDrop.ico` | 1 | Icon nhị phân, bị cấm nhập trong Giai đoạn 2A |
| `web/assets/fonts/BeVietnamPro-{Regular,Medium,Bold}.ttf` | 3 | Font nhị phân, bị cấm nhập trong Giai đoạn 2A |

**Không nhập keystore, dữ liệu người dùng, cache, dependency đã cài hoặc output build; không phát hiện private key/token hoạt động trong tập nhập theo các mẫu quét dưới đây.** Không sửa source để loại mật khẩu. Muốn đưa hai script ký vào cây mã phải có phê duyệt riêng trước khi sửa; giữ nguyên APK identity/alias và khóa updater gốc.

**[CHECK] Quét bí mật có giới hạn:** kiểm tra tên file nhạy cảm, UTF-8/NUL và mẫu private-key PEM, GitHub PAT, AWS access ID, Google API key, Slack token, credential URL, credential assignment và `pass:` argument trên toàn bộ text member; review các tham chiếu token/key để phân biệt dữ liệu chạy thử và khóa công khai. Hai finding mật khẩu được loại nguyên file. Quét lại tập file sẽ commit. Không cài công cụ/dependency mới. Đây không phải bằng chứng không tồn tại mọi loại bí mật hoặc kiểm toán toàn bộ lịch sử Git/log/Release.

**[CHECK] Public pin:** RSA public key trong `scripts/release-config.mjs` và Android `ReleaseConfig.java` trùng DER của `security/update-signing-public.pem` hiện có trên main; SHA-256 DER `10edffbf006bbd6e6a8fe5e8ab5859a44f62bdcd03aa3d339a158cbf4685c4b1`. Đó là khóa xác minh công khai, không phải private key. Không thay key, cert hoặc cấu hình ký; cây `security/` hiện có được giữ nguyên.

## 4. Kiểm tra đã chạy và chưa chạy

Các kiểm tra nhập nguồn chạy trên Linux, Python `3.12.14`, Git `2.52.0`; không chạy process ứng dụng. Validator cục bộ kiểm tra ZIP, staging, byte/hash, mode, allowlist và mẫu bí mật đều exit 0. `sha256sum --check docs/baselines/native-1.13.0/SHA256SUMS.txt` exit 0 cho 110 file. Riêng kiểm tra whitespace có kết quả khác 0 được giữ nguyên và ghi rõ trong bảng.

| Kiểm tra Giai đoạn 2A | Kết quả / giới hạn |
| --- | --- |
| Hash ZIP theo tài liệu và GitHub asset | Đạt; kiểm tra trước khi nhập |
| 141 path/type/header/CRC | Đạt; kiểm tra trước khi nhập |
| 110 file nhập so với ZIP và manifest SHA-256 | Đạt; không khác byte |
| Phân loại toàn bộ 141 file | 110 nhập + 31 loại; không có file bỏ sót |
| Quét file nhạy cảm/bí mật, public key pins | Hai file có mật khẩu bị loại; public pins khớp; giới hạn mẫu như mục 3 |
| Git diff/staging, file đã có trên main | Chỉ thêm file allowlist; không sửa/xóa file có sẵn; đối chiếu object hash và nội dung |
| `git diff --cached --check` | Exit 2: `tests/nsd-stubs/android/net/nsd/NsdManager.java:3` có dòng trắng cuối file, đã tồn tại trong ZIP. Giữ nguyên để không sửa baseline; không báo diff-check xanh |
| `ios/`, `.github/`, `security/`, `AGENTS.md`, sáu tài liệu Giai đoạn 1 | Không thay đổi so với base; các snapshot Giai đoạn 1 giữ ngày và kết quả lịch sử |
| Unit/integration/regression ứng dụng | **Không chạy trong Giai đoạn 2A**; số liệu Giai đoạn 1 không phải kết quả mới |
| Build/ký/cài Windows, Android hoặc iOS | **Không chạy** |
| Workflow/release/installer/dependency | Không sửa, không dispatch, không publish, không cài dependency |

Nhánh `baseline/native-source-1.13.0` được tạo mới từ main nêu trên; không ghi đè nhánh có sẵn. PR #1 vẫn mở với HEAD `2ccf9248ed6de184a200a950e1d37dd1e5b11741` tại lần đối chiếu ngày 12/11; không trùng bất kỳ path thay đổi nào của PR đó. PR này để **Draft**, không merge.

### Tự đối chiếu baseline sau khi checkout nhánh

Tại root repository, `sha256sum --check docs/baselines/native-1.13.0/SHA256SUMS.txt` kiểm tra file Git. Để đối chiếu ZIP mà không giải nén, tải asset chính thức rồi chạy đoạn Python chỉ đọc dưới đây; đối số là đường dẫn ZIP đã tải. Đoạn này là hướng dẫn tái kiểm, không phải test ứng dụng.

```bash
python3 - /path/to/FlowDrop-Source-1.13.zip <<'PY'
import hashlib, json, sys, zipfile
from pathlib import Path
m = json.loads(Path('docs/baselines/native-1.13.0/manifest.json').read_text())
e = json.loads(Path('docs/baselines/native-1.13.0/exclusions.json').read_text())
digest = lambda b: hashlib.sha256(b).hexdigest()
archive = Path(sys.argv[1])
assert digest(archive.read_bytes()) == m['source_archive']['sha256']
with zipfile.ZipFile(archive) as z:
    records = m['files'] + e['files']
    assert len(records) == len(z.infolist()) == 141
    assert {r['archive_path'] for r in records} == set(z.namelist())
    for r in records:
        raw = z.read(r['archive_path'])
        assert len(raw) == r['size'] and digest(raw) == r['sha256'], r['path']
    for r in m['files']:
        assert Path(r['path']).read_bytes() == z.read(r['archive_path']), r['path']
print('110 imported files match ZIP; 31 exclusions accounted for')
PY
```

## 5. Rủi ro còn lại và quyết định cần duyệt

1. **P1 — baseline chưa build đầy đủ:** thiếu hai script ký chứa mật khẩu; không thể gọi đây là build tái lập. Cần duyệt PR nhỏ dùng cơ chế secret từ môi trường/kho khóa ngoài Git, không đổi key/cert/alias và không lấy migration local chưa được review.
2. **P2 — thiếu bốn asset binary theo yêu cầu:** `FlowDrop.rc` vẫn tham chiếu icon và Node/web packaging vẫn tham chiếu font gốc. Không xóa tham chiếu, không đổi UI. Chủ dự án cần quyết định chính sách lưu/tải asset hash-pinned trong giai đoạn sau; source ZIP gốc không bị sửa và là nơi đối chiếu.
3. **P1 — test harness cũ còn nguyên:** lỗi `tests/large-transfer-integration.mjs:12` và request capability tại dòng 22/40 đã ghi ở Giai đoạn 1; đợt này không sửa hoặc chạy để che lỗi. Các harness dùng tool/JAR/path ngoài repo, chưa đảm bảo chạy được trên runner sạch.
4. **P2 — công cụ hosting là baseline lịch sử:** `npm run build`/`build:worker` còn cần dữ liệu release/font và `.openai/hosting.json` ngoài ZIP. Không thêm cấu hình deploy, không tuyên bố những lệnh này chạy được và không đưa payload bộ cài vào Git.
5. **P1 — giới hạn bảo mật/rollback đã kiểm toán vẫn còn:** LAN HTTP chưa có pairing/TLS, updater chống downgrade; đưa source vào Git không thay đổi hành vi hoặc chứng minh rollback ứng dụng trên OS thật.

Các mô tả `INSTALL.md`/template tải xuống là văn bản nguyên bản có thể lỗi thời; không dùng chúng thay bằng chứng kiểm thử mới. Chủ dự án cần review các loại trừ và phạm vi trước khi merge, không cần thay protocol, app UI hoặc dependency để hoàn tất nhập này.

## 6. Đề xuất Giai đoạn 2B — chưa triển khai

- PR sửa test harness riêng: tái hiện REG-001 trước, sửa path compile và cách lấy/truyền capability trong test; test fail trước/đạt sau, tuyệt đối không nới kiểm tra API production.
- Chuẩn hóa test tools/path và pin JAR/toolchain theo quyết định riêng; không tự cài/đổi dependency. Giữ package lock gốc ở PR nhập nguồn.
- Thiết kế CI **không phát hành**: fast unit/contract/update fixture, Node + JVM engine integration; đưa vào review riêng, đối chiếu PR #1 trước khi chạm workflow. Publisher hiện có giữ nguyên.
- Mở rộng Windows ↔ Android, Android ↔ Android và mixed-version, thư mục/ZIP64, file lớn, mất mạng, API security, SHA-256/chữ ký updater theo RG-01–RG-16 trong `docs/REGRESSION-PLAN.md`. Phân biệt engine fixture, emulator và OS thật; không suy ra đã đạt từ việc import nguồn.
- Xử lý hai script có mật khẩu và bốn binary asset bằng quyết định/PR riêng trước bất kỳ build hoặc ký nào. Không tạo key mới, không tự bật publisher.

## 7. Rollback và tính độc lập

Đây là một commit thêm baseline và bốn file bằng chứng. Khi PR còn Draft, main và bộ cài 1.13.0 không thay đổi. Nếu được merge sau này rồi cần quay lại cây mã trước nhập, dùng revert commit qua PR được review; không gỡ/cài lại ứng dụng hoặc xóa dữ liệu nhận, setting, history, keystore, Release hay tag. Rollback ứng dụng/OS là một kế hoạch khác chưa được kiểm chứng ở đợt này.
