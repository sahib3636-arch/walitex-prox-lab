#!/usr/bin/env bash
# mod_probe.sh — reproduce "the toggles flip back off" on an emulator, with the prefs file in hand.
#
#   PKG=com.whatsapp.litex scripts/mod_probe.sh
#
# 1. install app.apk, open the mod's own settings activities directly (they are declared in the
#    manifest, so `adb root` is not even needed for the exported ones) — no WhatsApp registration and
#    no companion link required;
# 2. list every switch, tap the first one, re-read the screen;
# 3. leave the screen, come back, re-read — that is the user's "close the sheet, it toggles itself off";
# 4. finally dump the app's shared_prefs so the keys that were written (or not) are visible.
set -uo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/require_emulator.sh"
OUT=out
mkdir -p "$OUT"
PKG="${PKG:-com.whatsapp.litex}"
UI="python3 scripts/toggles.py"

adb wait-for-device
require_android_emulator || exit $?
adb root >/dev/null 2>&1 || true
sleep 5
adb wait-for-device
adb shell svc power stayon true >/dev/null 2>&1 || true
adb shell settings put global window_animation_scale 0 >/dev/null 2>&1 || true
adb shell settings put global transition_animation_scale 0 >/dev/null 2>&1 || true

adb shell pm uninstall "$PKG" >/dev/null 2>&1 || true
adb install -r -g app.apk 2>&1 | tee "$OUT/install.txt"
adb logcat -c || true
adb logcat -v threadtime > "$OUT/logcat.txt" 2>&1 &
LP=$!
sleep 2

probe() {  # probe <tag> <activity>
    local tag="$1" act="$2"
    echo "===== $tag : $act"
    adb shell am start -W -n "$PKG/$act" 2>&1 | tee -a "$OUT/am.txt"
    sleep 8
    adb exec-out screencap -p > "$OUT/$tag.png" 2>/dev/null || true
    $UI dump "$OUT/$tag.xml" | tee -a "$OUT/toggles.txt"
}

probe open1 litex.settings.PrivacyActivity
adb shell am force-stop "$PKG" >/dev/null 2>&1
sleep 2
probe open2 litex.settings.PrivacyActivity
$UI tap 0 | tee -a "$OUT/toggles.txt"
sleep 4
adb exec-out screencap -p > "$OUT/after-tap.png" 2>/dev/null || true
$UI dump "$OUT/after-tap.xml" | tee -a "$OUT/toggles.txt"
adb shell input keyevent KEYCODE_BACK >/dev/null 2>&1
sleep 3
adb shell am force-stop "$PKG" >/dev/null 2>&1
sleep 2
probe reopen litex.settings.PrivacyActivity

# other mod screens, in case Privacy is empty on an unregistered install
probe customization litex.settings.CustomizationActivity
probe media litex.settings.MediaActivity
probe settings litex.settings.SettingsActivity

adb shell "ls -la /data/data/$PKG/shared_prefs" 2>&1 | tee "$OUT/prefs-list.txt"
for f in $(adb shell "ls /data/data/$PKG/shared_prefs" 2>/dev/null | tr -d '\r'); do
    adb shell "cat /data/data/$PKG/shared_prefs/$f" 2>/dev/null > "$OUT/pref-$f"
done
grep -ho 'name="walitex_[^"]*"' "$OUT"/pref-* 2>/dev/null | sort -u > "$OUT/walitex-keys.txt"
wc -l < "$OUT/walitex-keys.txt"

kill $LP 2>/dev/null || true
adb shell am force-stop "$PKG" >/dev/null 2>&1 || true
echo done
