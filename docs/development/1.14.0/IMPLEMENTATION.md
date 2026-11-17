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
