#!/usr/bin/env bash
# Archive Mini Bozor and hand it to TestFlight. Written to run over SSH on the
# build Mac, where nothing can prompt for a password or a certificate.
#
# One-time setup on that Mac:
#   * Xcode 16 installed, and `sudo xcode-select -s /Applications/Xcode.app`
#   * the App Store Connect API key saved as
#     ~/.appstoreconnect/private_keys/AuthKey_<KEY_ID>.p8, mode 600
#   * an app record for uz.minibozor created in App Store Connect
#   * the dev backend published over the tailnet:
#     sudo tailscale serve --bg --https=443 http://127.0.0.1:8000
#
#   * the account's identifiers copied into ios/testflight.env — see
#     testflight.env.example
#
# Every value below can be overridden from the environment.
set -euo pipefail
cd "$(dirname "$0")"

# The identifiers are read, never written here. This repository is public, and
# a key id sitting in it next to an issuer id leaves the .p8 as the only thing
# between a stranger and the developer account — so testflight.env is
# gitignored and its absence is an error rather than a default.
if [ -f testflight.env ]; then
	set -a
	. ./testflight.env
	set +a
fi

for required in KEY_ID ISSUER_ID TEAM_ID; do
	if [ -z "${!required:-}" ]; then
		echo "$required is not set. Copy testflight.env.example to" >&2
		echo "ios/testflight.env and fill it in, or pass $required=... here." >&2
		exit 1
	fi
done

KEY_PATH="${KEY_PATH:-$HOME/.appstoreconnect/private_keys/AuthKey_$KEY_ID.p8}"

# Where the test build looks for the backend. Tailscale fronts the FastAPI dev
# server with a real certificate on the tailnet name, so App Transport Security
# needs no exception and the phone reaches it from any network.
API_HOST="${API_HOST:?set API_HOST in ios/testflight.env}"

# TestFlight rejects a build number it has already seen.
BUILD_NUMBER="${BUILD_NUMBER:-$(date +%Y%m%d%H%M)}"

ARCHIVE="build/MiniBozor.xcarchive"
mkdir -p build

[ -f "$KEY_PATH" ] || { echo "API key not found: $KEY_PATH" >&2; exit 1; }

# codesign reads the login keychain, which an SSH session finds locked.
if [ -n "${KEYCHAIN_PASSWORD:-}" ]; then
	security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$HOME/Library/Keychains/login.keychain-db"
fi
security find-identity -v -p codesigning | grep -q "Apple Distribution" ||
	echo "note: no Apple Distribution certificate yet — -allowProvisioningUpdates will try to create one" >&2

auth=(
	-authenticationKeyPath "$KEY_PATH"
	-authenticationKeyID "$KEY_ID"
	-authenticationKeyIssuerID "$ISSUER_ID"
)

echo "==> archiving build $BUILD_NUMBER against $API_HOST"
rm -rf "$ARCHIVE"
xcodebuild -project MiniBozor.xcodeproj -scheme MiniBozor \
	-configuration Release -destination 'generic/platform=iOS' \
	-archivePath "$ARCHIVE" \
	-allowProvisioningUpdates "${auth[@]}" \
	DEVELOPMENT_TEAM="$TEAM_ID" \
	CURRENT_PROJECT_VERSION="$BUILD_NUMBER" \
	MB_API_BASE_URL="$API_HOST/api/v1" \
	MB_MEDIA_BASE_URL="$API_HOST/media" \
	archive

cat > build/ExportOptions.plist <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>method</key>
	<string>app-store-connect</string>
	<key>destination</key>
	<string>upload</string>
	<key>teamID</key>
	<string>$TEAM_ID</string>
	<key>uploadSymbols</key>
	<true/>
	<key>manageAppVersionAndBuildNumber</key>
	<false/>
</dict>
</plist>
PLIST

echo "==> uploading to App Store Connect"
xcodebuild -exportArchive \
	-archivePath "$ARCHIVE" \
	-exportPath build/export \
	-exportOptionsPlist build/ExportOptions.plist \
	-allowProvisioningUpdates "${auth[@]}"

echo "==> build $BUILD_NUMBER uploaded; TestFlight processing takes a few minutes"
