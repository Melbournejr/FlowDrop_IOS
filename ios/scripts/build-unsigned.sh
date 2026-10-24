#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../.."
if [[ "$(uname -s)" != Darwin ]]; then
  echo "This build requires macOS and Xcode. Use the manual GitHub Actions workflow." >&2
  exit 1
fi
build_root="${RUNNER_TEMP:-$PWD/ios/.build}/FlowDropDerived"
export_dir="${FLOWDROP_OUTPUT_DIR:-$PWD/ios/output}"
mkdir -p "$export_dir"
swift ios/scripts/draw-icon.swift ios/FlowDropApple/Assets.xcassets/AppIcon.appiconset/AppIcon.png
xcodebuild -project ios/FlowDropApple.xcodeproj -scheme FlowDropApple \
  -configuration Release -sdk iphoneos -destination 'generic/platform=iOS' \
  -derivedDataPath "$build_root" \
  CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO CODE_SIGN_IDENTITY='' \
  CURRENT_PROJECT_VERSION="${GITHUB_RUN_NUMBER:-1}" build
app_path="$build_root/Build/Products/Release-iphoneos/FlowDrop.app"
test -d "$app_path"
package_dir="$(mktemp -d "${TMPDIR:-/tmp}/flowdrop-package.XXXXXX")"
trap 'rm -rf "$package_dir"' EXIT
mkdir "$package_dir/Payload"
ditto "$app_path" "$package_dir/Payload/FlowDrop.app"
ditto -c -k --keepParent "$package_dir/Payload" "$export_dir/FlowDrop-Unsigned.ipa"
shasum -a 256 "$export_dir/FlowDrop-Unsigned.ipa" > "$export_dir/SHA256SUMS.txt"
cat > "$export_dir/READ-ME-FIRST.txt" <<'NOTICE'
FlowDrop iOS / iPadOS — development build
This IPA is UNSIGNED. It cannot be installed by opening it on an iPhone/iPad.
Sign it with your own Apple ID using Sideloadly on Windows, or use Xcode signing.
Free Apple ID installation normally needs renewal every 7 days.
No Apple ID, password, certificate, or private key was used by this workflow.
Keep FlowDrop open on both devices while transferring files.
NOTICE
echo "Created unsigned IPA in: $export_dir"
