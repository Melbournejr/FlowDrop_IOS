# FlowDrop 1.14.0 development

Base: `ebaa66049464fe20e3ba22b1031df2f62fe124c7` (merged PR #11).
One feature branch/PR; independent commits for rollback. No release/merge authorized.

## Share-code regression

Reproduction: start real Node desktop API with an empty peer list; create a ready
share on the production Java host, then advertise it over real mDNS 2.2 seconds
after starting `/api/desktop/receive`. Original desktop lookup stops at about
1.2 seconds. Original Java resolver snapshots an empty candidate collection.
Both return failure even though discovery subsequently finds the source.
This establishes a cold-discovery race in the source, not the sole possible
cause on the owner's physical devices.

Fix: bounded dynamic discovery polling, consistent Unicode whitespace/hyphen
normalization, distinct invalid/expired/unknown messages. Existing selection,
metadata bounds, local capabilities and file scope remain enforced. Failed
code probes have bounded, per-address 25/minute buckets in both hosts.

`evidence/code-before` records actual exit 1 and three failed engine cases.
`evidence/code-after` records actual exit 0 and SHA-256 exact downloads in all
three directions. Tests run on Linux Node 24 / JVM 21, not Windows/Android OS.
Additional npm unit, security integration and peer integration commands all
exit 0; details are in the command exit manifest. OS and physical verification
remain separate.

Rollback: revert the dedicated share-code commit; no data migration occurs.

## TLS and trusted devices

A second TLS listener serves remote data. The HTTP listener remains for native
loopback IPC and public `/api/config` bootstrap; remote data is refused by
default. Discovery is an untrusted location hint. Self-signed RSA device leaves
bind the existing device ID to a deterministic DNS name. Clients check validity,
self-signature, strong public key, identity name and pinned certificate SHA-256.
No accept-all certificate/hostname callback or HTTP fallback is used.

New device transport keys are independent of APK/update signing keys. Windows
stores its transport identity and trust secrets with CurrentUser DPAPI; Android
uses non-exportable AndroidKeyStore RSA and an AES-GCM protected trust store.
Linux engine tests use isolated temporary identities, removed in cleanup; they
are not persistent production Windows vault tests.

Pairing uses SHA-256 commitments to 256-bit random nonces bound to both device
IDs/certificate fingerprints, then reveal and a six-digit short authentication
string compared on BOTH screens. The receiver also makes a reverse pinned TLS
request to prove the initiator actually operates the claimed certificate and
has a matching outstanding proposal. Both confirmations are required before a
random 256-bit pairing secret is delivered via TLS. Attempts are bounded to
three per address per five minutes; pending proposals expire after two minutes.
Existing trust cannot be silently replaced. This application handshake has not
received an independent cryptographic review.

Data requests require HMAC-SHA256, a random ten-minute session token, timestamp
within two minutes, and a one-use 256-bit nonce. Replays, unpaired access, changed
certificate pins and wrong sender IDs are rejected. Forgetting a device removes
trust, invalidates sessions and closes tracked transfers; unfinished files retain
existing cleanup/publication rules. Standard TLS protects every stream. New
uploads add an optional streaming SHA-256; receivers check it before publishing
files or extracting folders. Legacy staged shares without a digest retain TLS,
length and folder CRC checks.

Select a peer and use **Bảo mật → Ghép nối**, or select it on Android. Compare
both codes and confirm only if they match. Forget the device from Bảo mật to
revoke trust. Old 1.13 peers require the explicit, warned HTTP compatibility
option on the 1.14 device. It is off again after restart. TLS failures never
activate compatibility automatically. Existing HTTP regression suites explicitly
select this mode; the additional TLS suite runs with it off.

## Turbo and transfer experience

Android offers Auto/LAN/Turbo through public Wi-Fi Direct APIs. Hardware and OS
permissions are checked first. Where supported, creation requests a 5 GHz group;
UI only labels 5 GHz after `WifiP2pGroup.getFrequency()` reports a matching actual
frequency. A uniquely named group, owned P2P interface routing and separate LAN
discovery preserve the same TLS transport. Cleanup removes only that owned group
after a transfer finishes or the user stops it, never another app's group.

Windows provides a semi-automatic Mobile Hotspot settings flow and reads the
current association's actual BSS frequency through WLAN APIs. The owner selects
a supported hotspot band in OS settings. FlowDrop does not claim to control
Windows drivers or automatically turn off a user-created hotspot. Alternatively,
Windows can join the Android-created group as ordinary Wi-Fi. Auto prefers the
existing LAN; user confirmation is needed to create/join a new link. API/driver
failure retains LAN with the same security policy.

Physical Wi-Fi Direct interoperability, hotspot creation and 5 GHz operation are
**NOT VERIFIED** in cloud VMs/emulators. No throughput improvement is claimed.
Existing bounded streaming/buffer sizes and large-folder logic are retained;
free-space checks and approximate remaining time supplement existing live speed.
QR and resumable partial transfers remain backlog, avoiding a new dependency or
unsafe partial-file reuse in this upgrade.

## Version and compatibility boundaries

Test version is 1.14.0 / Android code 15. Package ID, save locations, existing data,
fonts/icon, runtime/npm dependencies, production APK certificate inventory and
RSA update key remain unchanged. No iOS/publisher/feed/tag/release changes.
Historical 1.13 manifests are retained; the feature source manifest explicitly
pins authorized changed/new bytes for CI rather than claiming 1.13 source equality.
