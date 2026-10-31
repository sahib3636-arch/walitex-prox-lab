#!/usr/bin/env bash
# Verify a signed update installs over the untouched linked-base package without uninstalling it,
# and that app-owned preference data remains accessible after PackageManager's in-place replace.
set -euo pipefail
OUT=out
mkdir -p "$OUT"
PKG="${CLONE_PKG:-com.whatsapp.litex}"
ACT="litex.settings.PrivacyActivity"
UI="python3 scripts/toggles.py"

if [[ ! -s original.apk || ! -s app.apk ]]; then
  echo "original.apk and app.apk are required (supply workflow original_url)" | tee "$OUT/upgrade-error.txt"
  exit 2
fi

adb wait-for-device
adb root >/dev/null 2>&1 || true
sleep 5
adb wait-for-device
adb shell svc power stayon true >/dev/null 2>&1 || true

# Install the exact currently linked build as a clean emulator install.
adb install -g original.apk 2>&1 | tee "$OUT/base-install.txt"
adb shell dumpsys package "$PKG" > "$OUT/package-before.txt"

start_screen() {
  adb shell am force-stop "$PKG" >/dev/null 2>&1 || true
  sleep 1
  adb shell am start -W -n "$PKG/$ACT" > "$OUT/activity-start.txt" 2>&1
  sleep 6
}

start_screen
$UI list | tee "$OUT/toggles-before.txt"
# Persist two ordinary privacy choices through the app's own switch listeners.
$UI tap 0 | tee -a "$OUT/toggle-actions.txt"
sleep 2
$UI tap 2 | tee -a "$OUT/toggle-actions.txt"
sleep 2
$UI dump "$OUT/toggles-before-update.txt" | tee -a "$OUT/toggle-actions.txt"
adb shell "cat /data/data/$PKG/shared_prefs/litex_prefs.xml" > "$OUT/prefs-before.xml"

# Critical test: use install -r only; do not uninstall, clear data, or replace the app ID.
adb install -r app.apk 2>&1 | tee "$OUT/upgrade-install.txt"
adb shell dumpsys package "$PKG" > "$OUT/package-after.txt"
adb shell "cat /data/data/$PKG/shared_prefs/litex_prefs.xml" > "$OUT/prefs-after.xml"

start_screen
$UI dump "$OUT/toggles-after-update.txt" | tee "$OUT/toggles-after-update.txt"
adb exec-out screencap -p > "$OUT/screen-after-update.png" 2>/dev/null || true

# Fail closed if PackageManager did not complete an in-place update or the stored settings vanished.
grep -q 'Success' "$OUT/upgrade-install.txt"
grep -q 'walitex_hide_seen' "$OUT/prefs-after.xml"
grep -q 'hide_statusV2' "$OUT/prefs-after.xml"
grep -q '0: checked=true' "$OUT/toggles-after-update.txt"
grep -q '2: checked=true' "$OUT/toggles-after-update.txt"

echo 'IN_PLACE_INSTALL=PASS' | tee "$OUT/upgrade-result.txt"
echo 'PREFS_PRESERVED=PASS' | tee -a "$OUT/upgrade-result.txt"
# Record stable install identity/time fields for manual review.
grep -E 'userId=|firstInstallTime=|lastUpdateTime=|versionCode=|versionName=' "$OUT/package-before.txt" > "$OUT/package-before-summary.txt" || true
grep -E 'userId=|firstInstallTime=|lastUpdateTime=|versionCode=|versionName=' "$OUT/package-after.txt" > "$OUT/package-after-summary.txt" || true
adb shell am force-stop "$PKG" >/dev/null 2>&1 || true
