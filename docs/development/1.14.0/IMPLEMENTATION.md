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
when the user explicitly stops Turbo or the host shuts down, never another app's group.

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

## CI findings retained during development

Initial head `21d7caadde69a5d213adb2f94081571bebba6a9a` built and independently
verified both TEST ONLY installers. It did **not** pass all runtime/regression
checks. The failures remain in `evidence/ci-initial-21d7caa`:

- ZIP64 suite's code-lookup assertion expected the old generic error text. The
  >4 GiB ZIP operation itself passed. The assertion now requires the requested
  distinct unknown/revoked-code message; sizes/cases remain unchanged.
- Android API29/35 sharesheet test used a synthetic 1.13 HTTP recipient. It now
  asserts compatibility defaults off, explicitly selects that mode for the old
  fixture, retains every grant/consent/byte assertion and resets it afterwards.
  Explicit compatibility makes HTTP target requests cleartext, including newer
  hosts if both owners opt in; it is never selected because TLS failed.
- Windows native startup timed out. The added real Windows vault probe exposed
  `DriveNotFoundException` from New-SelfSignedCertificate in a clean PowerShell
  session. The helper now explicitly initializes the Certificate provider/drive,
  uses UTF-8 private pipes, and returns only public exception type/identifier.
  Native tests additionally check real TLS/pin rejection, DPAPI persistence,
  Unicode names, encrypted storage, corrupt-vault refusal and restart identity.

At head `d4320d9295806b34f5f55d4509441ec97aa637fc`, Native Regression including
all ZIP64 cases passed; Windows runtime remained failed at provider setup.
These are historical observations, not PASS claims for later heads. Latest
four-workflow results and downloadable TEST ONLY artifacts are recorded in
[Draft PR #12](https://github.com/Melbournejr/FlowDrop_IOS/pull/12) after CI at the
final head. SKIPPED/BLOCKED/unfinished jobs do not count as verification.

The added native TLS probe at `d4320d9` also found an Android Conscrypt handshake
failure on both API29/35. New transport keys now authorize the raw/prehashed RSA
operation needed by the TLS provider (`DIGEST_NONE` alongside SHA-256/SHA-512),
without changing certificate validation, APK/update keys, TLS version negotiation
or authentication. Native tests continue requiring an actual successful TLS
handshake and rejection of an unpaired request; a failure records only public
exception classes/keywords and requested key types. It is not a simulated PASS.
Previously created experimental transport keys are not silently replaced.

Android logcat at `d4320d9` records **KeyStoreException: Incompatible padding
mode** in Conscrypt `rsaSignDigestWithPrivateKey`. The [AOSP implementation](https://android.googlesource.com/platform/external/conscrypt/+/refs/heads/android10-release/common/src/main/java/org/conscrypt/CryptoUpcalls.java)
uses `Cipher.ENCRYPT_MODE` with an already encoded RSA signature (including the
`RSA_NO_PADDING` path). The new device key also permits this raw operation, while
retaining SIGN/VERIFY purposes only. Conscrypt still performs the standard TLS
RSA-PSS/PKCS1 scheme, handshake hashing and peer validation; this does not create
an unpadded TLS signature algorithm. Actual OS probes require **both TLS1.2 and
TLS1.3** plus unpaired-request rejection; neither version is disabled to hide the
failure. New test profiles are fresh; no existing key is deleted or regenerated.

A subsequent Windows probe reported `FormatXmlUpdateException` while importing
the Security module. The helper now invokes the inbox PowerShell executable by
absolute system path, uses only inbox Windows PowerShell module locations in its
child environment and imports its own `$PSHOME` Security manifest explicitly.
This prevents inherited PowerShell7 module paths from shadowing Desktop modules;
the real Windows vault test deliberately supplies an invalid inherited module
path. No user/system environment or policy is changed.

A separate regression reproduced a stale ten-minute token after the receiver
loses volatile sessions on restart (`session-renew-before.log`, actual exit1).
Clients now discard an auth-rejected token and renew once with fresh request
nonce/HMAC over pinned TLS. Java only replays GET or a fully captured control POST
up to16KiB; file streams are not buffered/replayed. Revoked trust still rejects
renewal. Node unit and real Node/Java GET/POST transfer tests passed after the fix;
this is engine proof, not two-device OS reboot proof.

At `7f31623` the Windows vault probe hit its90s timeout; it was recorded as FAIL,
not converted to PASS. The final helper removes the Certificate provider/PKI
cmdlet dependency entirely: .NET4.7.2+ `CertificateRequest` creates the RSA2048 /
SHA-256 leaf in memory, with no certificate-store writes or private-key files.
CurrentUser DPAPI storage and existing identity format remain the same. Private
IPC reads exactly one newline-terminated JSON record rather than waiting for EOF.
The Windows runner must still demonstrate real DPAPI, TLS and native assertions
at the final head before this path can be considered verified.

The Windows .NET probe then reported a property-assignment error during key
creation. The generator now requests RSA2048 in the CSP constructor, avoiding
its read-only KeySize property. Error records include only a public exception
identifier and script line number. The private CSP key is not persisted and is
disposed after the encrypted PFX is returned through the private pipe.

Turbo ownership state is visible across callback/network threads. A late
create-success callback after stop/LAN selection immediately cleans its own
lease; removal additionally checks the generated passphrase, not just the SSID.
Manual physical regression: start Turbo, immediately stop the host or select LAN,
then verify no FlowDrop-owned group remains and another app's group is retained.
This cancellation/driver test remains NOT VERIFIED without real Wi-Fi hardware.
ETA is shown only after at least one byte has moved.

The opt-in public stage trace at `9d88191` showed certificate generation/export
and two DPAPI protects completed, then a later helper stalled at `Add-Type` before
reading input. The helper now uses strongly named framework assembly loads and
.NET JSON serialization directly: no Add-Type, ConvertFrom/To-Json, New-Object,
Certificate provider or module autoload. Private JSON parse failures return a
fixed message instead of echoing potentially secret stdout. Trace is opt-in in
the isolated Windows probe, not enabled by the installed app.

At `652778c`, actual Windows DPAPI completed creation, encrypted persistence,
Unicode trust reload and corrupt-vault rejection (probe exit 0). Its expected
corrupt-input diagnostic lacked a newline and joined the result JSON in the
recorder's combined stderr/stdout stream, causing JSONDecodeError in W05 before
app launch. Error records now end with a newline; the same probe assertions and
native runtime prerequisites remain mandatory. This is a log framing fix, not
a relaxation of corruption rejection or a claim that later native tests ran.

## Android Preview installation beside the current app

The owner requested a separately named app after discovering the TEST ONLY APK
cannot replace production because its signing certificate differs. A display
name alone does not isolate Android packages. The new **FlowDrop Preview** build
uses `app.flowdrop.preview`; the original `app.flowdrop.mobile` source/manifest,
version, production certificate pin and update verifier remain unchanged.

`scripts/android_preview.py` makes an isolated working-source overlay, relocates
the Java namespace/internal actions, and directs received files/folders/media to
`Download/FlowDrop Preview` and `DCIM/FlowDrop Preview`. Private settings, history,
device identity, KeyStore and trust are scoped by its separate Android UID. The
default advertised name includes Preview; its preferred HTTP port is5175 with
the existing dynamic conflict fallback. The TLS/file/discovery protocol remains
unchanged, so Preview can pair with1.14 Windows;1.13 still needs explicit legacy.

Preview has no production feed/PackageInstaller entry points, update service,
boot receiver or install/update permissions. Its updater UI reports that a new
Preview APK must be installed manually. The APK is test-signed; new CI runs use
new disposable keys, so a later Preview may require uninstalling only Preview.
Do not remove the original FlowDrop or its data. No production key is accessed.

The existing runtime producer exports a clearly named Preview APK after real
compiler/signature/zipalign/resource verification. Required A17 runs on API29/35:
install beside the original-package test app, check distinct UID/data directory,
launch Preview, observe no updater job, uninstall only Preview, then verify the
original APK SHA/private-data marker and launch. These tests use an isolated
emulator and a test-signed original-package app, not the owner's production phone.
Existing native groups remain mandatory. Final-head run/results/download links
are in PR12; until executed, coexistence must not be reported as PASS.

Rollback: revert the dedicated Preview commit. Neither production source nor
workflow/release/signing configuration is changed by this addition.

## Windows Preview installation beside the current app

The owner requested the same separation for Windows. The earlier regular TEST
ONLY EXE uses production install/data paths and is not a side-by-side installer.
`scripts/windows_preview.py` now builds **FlowDrop Preview** in an isolated source
overlay. The original Windows/native/Node source, installer and update verifier
in Git remain unchanged. Runtime build verification produces both installers;
the publisher is unchanged. The existing runtime workflow adds two narrowly
scoped uploads of already verified Preview-only APK/EXE files, avoiding accidental
selection of the regular installer from the mixed CI bundle. The upload action
pin, read-only permissions, opt-in labels and release boundaries are unchanged.

Preview executable: `FlowDropPreview.exe`. Default program directory:
`%LOCALAPPDATA%\Programs\FlowDrop Preview`; data/DPAPI/trust/settings/history:
`%LOCALAPPDATA%\FlowDrop Preview\Data`; default receive directory: the system
Downloads folder plus `FlowDrop Preview`. Native class/mutex, firewall preference
registry, uninstall registry, Desktop/Start menu/Send To links and process are
separate. Its startup and stop helper always target its own data path even if
an inherited `FLOWDROP_DATA_DIR` points to the original app. HTTP uses the existing
ephemeral-port mechanism; TLS/discovery/file protocol, icon/fonts, Node/npm and
signing/update public keys are retained.

The Preview updater has no network/feed/download/installer implementation. A
manual update click explains using a separate Preview installer, the automatic
checkbox is disabled, and local API attempts cannot enable/install production
updates. Both interactive directory validation and the installation section
reject an existing `FlowDrop.exe`; silent `/D=<original>` must exit2 before any
original program is stopped or changed. Uninstall targets only Preview program,
shortcuts and registration; received files and Preview data remain outside it.

Required W22 on the owned Windows VM installs both variants, verifies payload,
two HWND classes and process/backend identities/ports/data paths, separate Send To,
single-instance routing, rejected update toggles and the original-directory
guard. It uninstalls only Preview and checks original EXE/data
canary/device ID/shortcut SHA, registry and still-running backend. This uses the
source-built test app in a fresh VM, not the owner's real installation. New unit
tests cover overlay isolation, disabled updater execution and artifact rejection;
unit results alone do not establish Windows installation/runtime success.

Use only `FlowDrop-Preview-Setup-1.14.0-Windows-x64-TEST-ONLY.exe` for side-by-side
testing. The regular `FlowDrop-Setup-...` file in the same CI archive still uses
the original install paths. Final-head CI and artifact hashes are recorded in
PR12 after execution. No merge/release or Authenticode/production key use.

Rollback: revert the Windows Preview commit; keep the original app/data. On a
test machine use the **FlowDrop Preview** uninstall entry, never the original
FlowDrop entry. Physical Windows10/11 Wi-Fi/OEM interoperability remains unverified.

## Native Android request authentication after successful pairing

The owner physically paired Preview on Android16 and Windows, confirmed both
six-digit codes, then received an authentication rejection before any file bytes
moved. Source inspection found that Android's platform `org.json.JSONStringer`
escapes every `/`, unlike Node `JSON.stringify` and the JVM test JSON JAR. Pairing
transcripts contain constrained IDs/fingerprints and no slash, so their codes can
match while the HMAC tuple containing `/api/secure/session` differs byte-for-byte.
Both sending directions are affected. This is not a file-size limit.

The [Android16 platform implementation](https://android.googlesource.com/platform/libcore/+/android16-release/json/src/main/java/org/json/JSONStringer.java)
and Android10 source explicitly include `case '/'` in string escaping. No AOSP
source/library is imported into the application; it is evidence only.

Before fix, head `9aead915a671be43979a26fede861b16b42d2506` deliberately added a
public Windows HMAC vector to the native A13 test, without changing production.
Both emulator API29 and35 actually failed with **Windows/Android request signature
mismatch (JSON slash escaping)**. JVM/Node regression remained green, exposing
the prior coverage gap. [Before native run](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/44093541611),
[API29 failure](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/44093541611/artifacts/14332778781),
[API35 failure](https://github.com/Melbournejr/FlowDrop_IOS/actions/runs/44093541611/artifacts/14332258648).
The instrumentation shell process returned0 but its terminal instrumentation
result was failure0, not success-1; the runtime gate correctly failed.

Fix: encode the known string-only HMAC tuple explicitly using the existing
Windows `JSON.stringify` byte format, independent of Android/JVM JSON serializers.
Quotes, backslashes, C0 controls, UTF-8, paired and lone UTF-16 surrogates are
covered by118 Node/JVM vectors. HMAC-SHA256, tag/method/route/time/nonce/session
fields, keys, TLS/pinning, timestamp window, anti-replay and file limits are
unchanged. This corrects Android to the existing1.14 protocol, without a second
accepted encoding or an HTTP fallback. Normal JSON request/response bodies and
the already-matching pairing/SAS algorithm remain unchanged.

The native Windows vector remains mandatory in A13 after the fix. Final-head
native/build/regression/cross-platform results and APK SHA are recorded in PR12;
source/JVM equality alone is not a physical Windows↔Android transfer PASS.
The first local JVM attempt was blocked by sandbox EPERM; the permitted rerun
actually compiled/executed and passed118 vectors.

All Android1.14 Preview peers should use the corrected APK for secure transfers.
Windows Preview already uses the reference byte format and needs no reinstall.
Because CI APK keys are disposable, replacing an installed Android Preview may
require uninstalling **only Preview**, which resets its private history/settings/
trust; retain the original FlowDrop and any files the owner wants to keep.
After reinstall, select the new live device and compare/confirm both six-digit
codes again. Production1.13 remains on its explicit legacy compatibility policy.
The unrelated Windows Wi-Fi QR is for joining an OS hotspot, not FlowDrop pairing.


## Turbo retained across transfers; Bluetooth setup preview

Owner evidence (18 November 2026, Asia/Saigon): Xiaomi14 Pro/Android16 created
Wi-Fi Direct5GHz and Windows IntelAC9560 joined it. Owner subsequently reported
all three files received. This is owner-reported completion, not an independent
file-hash verification. A later desktop-to-phone test reached about30 in the UI
(unit not independently recorded), then the link disappeared before the next file.
No private SSID/passphrase/MAC or uploaded screenshots/video are committed.

Source root cause: TurboLink tick called stop after observing an active transfer
followed by no active transfer. The new JVM test executes the real class against
explicit radio stubs: old source fails `first completed transfer tears down Turbo`;
new source retains the group through completion, idle and another transfer. Stop
is explicit through Stop Turbo, selecting LAN or host shutdown. A failed OS remove
keeps owned credentials for retry. Unowned groups are never removed/adopted solely
because their name resembles FlowDrop. This fixes the demonstrated lifecycle bug,
not all possible vendor power/radio disconnects. No idle lifetime guarantee after
Android terminates the host process is claimed.

The Android Turbo dialog now refreshes in place and reports actual creating,
blocked and ready state. It no longer unconditionally toasts `creating` after a
blocked request. Network credentials stay in the local dialog, not public config.

New opt-in Bluetooth rendezvous is setup-only: first pair the phone and Windows
in OS Bluetooth Settings. Create Turbo on Android, choose `Connect Windows via
Bluetooth`, then Windows Connection -> Bluetooth -> select a bonded device and
accept on the phone. The listener is opened only by that user action, accepts one
connection within60seconds, closes on dialog dismissal/background/host-change,
requires OS bonding and secure authenticated/encrypted RFCOMM, bounds request and
response, and refuses malformed input or a changed Turbo group. Windows requires
explicit selection/approval before leaving its current WLAN and requests a
WPA2-AES temporary profile in memory; it never saves a WLAN password/profile.

Bluetooth transfers only the current owned SSID/passphrase, not file bytes, trust
secrets, APK/update keys or local API capabilities. Independent pinned TLS and
both-screen FlowDrop pairing remain mandatory; Bluetooth bonding does not create
FlowDrop trust or enable HTTP compatibility. No discovery/pairing/file route or
wire schema changes. The separate rendezvous uses a fixed service UUID and
FlowDropLink1 marker, not the eight-character transfer code or six-digit SAS.
Android requests BLUETOOTH_CONNECT on31+ (legacy Bluetooth permissions on29/30),
not unrestricted Bluetooth scans. Windows uses OS Bluetooth/WLAN system libraries;
no npm/runtime/toolchain dependency or signing identity changes.

Checks distinguish real Java behavior with radio mocks, actual Android compile,
Windows cross-compile/link, and native OS CI from physical Bluetooth/Wi-Fi testing.
Radio pairing, RFCOMM interoperability and repeated real-device Turbo transfers
remain NOT VERIFIED until exercised on supported hardware. Native CI success is
not a substitute for those tests. No speed improvement or80-100MB/s claim.
Final-head build/runtime/regression/download evidence belongs in Draft PR12.
Rollback: revert the dedicated Turbo/Bluetooth commits in a PR; no data deletion,
main force push, production re-signing, or release/feed changes.

## Foreground DIRECT loss: recovery and one-entry connection UI

Owner follow-up: DIRECT still disconnects/disappears while the phone screen is
on and FlowDrop is open. Screen-off/process termination is not established as
the cause. The actual Xiaomi14 Pro/Intel9560 radio failure is NOT REPRODUCED in
the cloud. Do not describe the following state fix as a proven driver/radio fix.

An additional app-state defect IS reproduced: the previous TurboLink discards
its owned lease after a single null group-info callback. The new real-class JVM
fixture fails against exact previous source5244049 with `BUG: transient group
query discards live ownership`. Radio APIs in this test are explicit stubs.

TurboLink now tolerates a transient null for9seconds, allows30seconds for group
formation, times out stalled queries after6seconds and ignores callbacks from
old generations. After confirmed loss it recreates the same owned network and
credentials at most twice per user start. Credentials are withheld when not
confirmed ready. An unknown/replaced group blocks recovery; neither SSID prefix
nor a stale callback authorizes adoption/removal. A cancelled late create may
only remove the exact group/credentials created by that cancelled request.
Channel reconnection is bounded to two attempts. Explicit LAN/Stop/host shutdown
remain effective; no timer after file completion tears down a healthy group.

Windows observes association without active radio scans, retries an interrupted
temporary-profile join at most twice and waits at least10seconds after a failed
attempt. It respects a connected different network and stops recovery instead
of replacing it. The user can stop recovery from the connection dialog. Network
restoration does not implement file-offset resume: a file session already marked
failed must be sent again. An initial join only confirms association, not DHCP,
peer discovery, TLS trust or file completion.

Android has a main-screen `Kết nối trực tiếp với máy tính` entry. It starts sharing
if needed, requests the necessary permissions, creates/awaits the group and opens
the secure Bluetooth listener in one flow. Windows `Kết nối trực tiếp` opens one
bonded-device chooser, replacing chained Yes/No prompts. First-time OS Bluetooth
bonding, explicit phone consent and independent FlowDrop TLS/SAS remain required.
Manual credentials, hotspot and Auto/LAN options remain available. No promise of
silent connection on unsupported radios or removal of OS confirmation is made.

Private Android preferences retain only64 typed events (time, enum, integer);
restoration rejects unknown types and discards extra fields. The optional copied
diagnostic includes build commit, API, host/foreground state, Wi-Fi enabled state,
group/channel/recovery flags and these bounded events. Windows copies only build,
recovery flags and interface state/link rate/signal/PHY/query codes. Neither report
includes SSID, password, IP/MAC, device/file names, pairing codes, tokens, certificates,
trust secrets or arbitrary exception strings. Preview overlays stamp the reviewed
40-hex source commit; no version or production signing/update identity is changed.
Diagnostics are local/explicit clipboard actions, not network telemetry.

Verification includes the before/after JVM fixture, async recovery/stale callback/
cancelled-create/diagnostic sanitization cases, native Android entry/report checks
and a real Windows chooser-open/cancel assertion without radio operations. The
existing transfer, consent, authentication and coexistence assertions are retained.
Final-head workflow results and checked Preview artifact hashes are recorded in
Draft PR12 after CI completes. Physical repeated transfers, OEM radio stability,
Bluetooth interoperability and throughput remain NOT VERIFIED by cloud CI.
If DIRECT still drops, copy the diagnostics before uninstalling Preview so its
private event history is retained for investigation. Revert this dedicated change
through a PR to roll back; do not delete received files or change production keys.

First native CI ataffe644: Android29/35, build, regression includingZIP64 and
engine E2E passed; Windows W15 failed at the new chooser assertion before its
transfer steps. The initial predicate combined window visibility with GetDlgItem
for TaskDialog command links, so that log alone cannot establish whether the
window or a control lookup failed. The harness now requires the visible actual
dialog, then uses Windows UI Automation to require all four enabled/on-screen
button roles/names (pairing, manual hotspot, diagnostics, Auto/LAN), and finally
cancels via the TaskDialog API. Windowless DirectUI controls cannot be verified
by assuming one HWND per button. No production change, skipped transfer test or
weaker outcome is used for this harness correction. The failed run/artifact is
retained at44236103819/14397765812; final-head rerun status belongs in PR12.

## Direct setup progress and Android outgoing measurements

Owner follow-up: the Preview is almost usable, Windows-to-phone reports about50
in the UI, phone-to-Windows remains slower. Units and exact reverse-direction
rate have not been independently established. The owner clarified that the main
connection obstacle is knowing when it has finished and which device to select.

Android now shows explicit three-stage progress: phone network preparation,
computer Wi-Fi setup, and discovery of FlowDrop. After network discovery, actual
peers on the owned Direct interface appear as send-target buttons inside the same
dialog. The user still chooses a target and goes through the existing TLS/SAS
confirmation when needed. Delivering Bluetooth credentials alone is never called
Wi-Fi/FlowDrop completion. Timeout/retry and manual/LAN/Stop/diagnostic controls
remain available. A Bluetooth delivered flag only becomes true after an approved
reply is flushed; denials/malformed/unbonded cases do not become delivered.

Windows has a persistent progress row, independent of transient transfer status.
After association it immediately rescans. It may highlight the unique discovered
peer at the DHCP gateway of the exact WLAN interface/SSID it joined. This is a
location hint, not authentication: it does not trust, pair or send a file. Missing
gateway, other-network association, ambiguous endpoints, credentials/path in URL
or invalid port cannot select a peer. Multiple FlowDrop instances explicitly ask
the user to choose; an existing manual selection is not replaced by polling.
Independent pinned TLS and both-screen SAS remain unchanged.

Source inspection: phone sending stages a copy locally, then the receiver pulls
it via TLS. No fixed send quota/rate limiter was found in this path. Linux/JVM
measurements of four32MiB+17byte transfers before/after an experimental128KiB
copy showed substantial warmup variance; warm-run medians were approximately42.6
and41.6MiB/s. They DO NOT establish a throughput gain or explain the Xiaomi radio.
The larger-buffer/FileInputStream experiment was discarded. The original64KiB
Files stream, staging, SHA/length checks, routes and completion semantics remain.

Accepted Android TCP sockets request TCP_NODELAY to avoid Nagle/delayed-ACK delay
in small HTTP/TLS bursts. The OS-selected send-buffer size is retained. No physical
throughput gain is claimed from this setting. Eight bounded, local-only outgoing
body samples now record bytes written, body-write success (not receiver receipt),
TLS flag, elapsed/disk-read/TLS-write milliseconds, bulk-write count, buffer size
and actual socket settings. TLS-write time includes crypto and backpressure; it
cannot alone distinguish radio/CPU/receiver disk. Samples are added to explicitly
copied diagnostics, not HTTP endpoints, wire metadata or telemetry. No file names,
paths, codes, URLs, peer identities or credentials are recorded. Copy samples use
a dedicated short lock, not the server/session lock.

Tests add real pinned-TLS2MiB+17byte repeated downloads with exact SHA, bounded and
sanitized samples and the accepted socket's TCP_NODELAY; real Android downloads
must populate bounded samples too. Windows helper checks unique/absent/ambiguous/
malformed gateway hints and the persistent status control. Physical discovery,
DHCP/Wi-Fi association, clarity on the owner's devices and asymmetric throughput
remain NOT VERIFIED by cloud CI. Final head CI/artifact evidence is recorded in
Draft PR12; no release/version/signing/dependency/iOS/workflow changes are made.
Rollback is a PR revert of this dedicated change and feature source pins, without
deleting received files, re-signing production or changing main protection.
