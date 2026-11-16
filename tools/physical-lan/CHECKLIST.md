# FlowDrop 2D.2-B — phiếu kết quả vật lý (chưa chạy)

Mặc định mọi dòng **NOT VERIFIED**. Chỉ đổi PASS khi đã làm và có evidence. FAIL khi assertion không đạt; BLOCKED khi điều kiện cản; SKIPPED cần lý do. Đừng đánh PASS từ protocol CI/emulator hoặc copy USB.

- Run ID / source-manifest SHA:
- Ngày giờ UTC + múi giờ:
- Sender: Windows/Android, OS/API, hardware, app version, binary SHA nếu có:
- Receiver: Windows/Android, OS/API, hardware, app version, binary SHA nếu có:
- Mode: black-box production1.13.0 / test artifact (source commit + producer run nếu có):
- Mạng: physical Wi-Fi / Ethernet↔Wi-Fi; router/private/guest/client-isolation/NIC/VPN (không mật khẩu/SSID cá nhân):
- Profile, file count, byte count:
- SHA nguồn Android đã kiểm trước gửi nếu có:
- SHA nguồn/đích và file comparison.json:
- Bắt đầu/kết thúc, elapsed/method, MB/s và Mbps (không trộn):
- CPU/RSS/read/write/discovery/cleanup measurement nếu thực đo, ngược lại NOT VERIFIED:

| ID | Điều kiện/case | Status | Evidence + actual/expected, SHA, bytes, timing/lý do |
|---|---|---|---|
| C01 | Windows → Android trực tiếp, consent, exact SHA | NOT VERIFIED | |
| C02 | Android → Windows trực tiếp, exact SHA nguồn Android + đích | NOT VERIFIED | |
| C03 | Windows → Windows hai máy native, exact SHA | NOT VERIFIED | |
| C04 | Android → Android hai máy vật lý, exact SHA | NOT VERIFIED | |
| C05 | Nhận bằng mã đúng/sai/thu hồi | NOT VERIFIED | |
| C06 | Empty/1KiB/1MiB/100MiB/1GiB/>4GiB từng hướng | NOT VERIFIED | Ghi riêng từng cỡ/hướng, không gộp PASS |
| C07 | 101 files trong một batch; lặp nhiều lượt | NOT VERIFIED | |
| C08 | Folder root/nested/empty/Unicode Việt-Trung-emoji | NOT VERIFIED | |
| C09 | Space/long name trong giới hạn OS; PNG/AVI/PDF/ZIP/bin | NOT VERIFIED | |
| C10 | Trùng file/root giữ bản cũ, distinct destination, SHA cả hai | NOT VERIFIED | |
| C11 | Discovery mDNS/UDP tự động, latency thực đo | NOT VERIFIED | |
| C12 | Rời mạng/đổi IP/kết nối lại/stale peer | NOT VERIFIED | |
| C13 | Nhiều NIC/VPN/Firewall profile phù hợp | NOT VERIFIED | Không tắt firewall |
| C14 | Router client isolation/multicast chặn | NOT VERIFIED | Topology; có thể BLOCKED hợp lệ |
| C15 | Android HOME/khóa/mở lại/OEM battery | NOT VERIFIED | |
| C16 | Recipient reject; sender cancel; receiver cancel | NOT VERIFIED | Tách ba thao tác |
| C17 | Disconnect25/50/75%, bytes thực, không completed giả | NOT VERIFIED | Tách ba tỷ lệ |
| C18 | App/backend dừng, restart, retained file SHA | NOT VERIFIED | |
| C19 | Disk full trên fixture riêng, không ảnh hưởng ổ cá nhân | NOT VERIFIED | |
| C20 | Source deleted/changed trước/sau staging | NOT VERIFIED | |
| C21 | Invalid request/path/ZIP/Origin/Host/capability trên máy riêng | NOT VERIFIED | |
| C22 | Transfer TTL24h/offer pending TTL, expired code | NOT VERIFIED | Không đổi giờ OS |
| C23 | Cleanup, không file dở/publication sai/session/process lạ | NOT VERIFIED | |
| C24 | Update signature + APK cert rejection | NOT VERIFIED | Fixture CI khác OS install thực |

Quan sát lỗi: test ID, bước tái hiện, expected/actual, P0/P1/P2/P3, log đã lọc. Không ghi token/mã đang còn hiệu lực. Kết luận từng hướng cần cả nhận diện native app, mạng và SHA; report integrity PASS một mình không đủ. Resume không được thiết kế trong baseline, không coi thiếu resume là regression mới.
