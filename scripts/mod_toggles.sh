#!/usr/bin/env bash
# mod_toggles.sh — walk every switch on the mod's Privacy screen and see which ones survive.
#
# The Premium chip in that list marks the paid ones; for those the native handler is expected to
# pop its "premium only" message and put the switch back. That is the user's symptom, reproduced or
# disproved on demand.
set -uo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/require_emulator.sh"
OUT=out
mkdir -p "$OUT"
PKG="${PKG:-com.whatsapp.litex}"
ACT="${ACT:-litex.settings.PrivacyActivity}"
UI="python3 scripts/toggles.py"

adb wait-for-device
require_android_emulator || exit $?
adb root >/dev/null 2>&1 || true
sleep 5
adb wait-for-device
adb shell svc power stayon true >/dev/null 2>&1 || true
adb shell pm uninstall "$PKG" >/dev/null 2>&1 || true
adb install -r -g app.apk 2>&1 | tee "$OUT/install.txt"
adb logcat -c || true
adb logcat -v threadtime > "$OUT/logcat.txt" 2>&1 &
LP=$!
sleep 2

start_screen() {
    adb shell am force-stop "$PKG" >/dev/null 2>&1
    sleep 1
    adb shell am start -W -n "$PKG/$ACT" >/dev/null 2>&1
    sleep 6
}

start_screen
adb exec-out screencap -p > "$OUT/screen-0.png" 2>/dev/null || true
N=$($UI list | tee "$OUT/list-0.txt" | wc -l)
echo "switches: $N"

i=0
while [ "$i" -lt "$N" ]; do
    $UI tap "$i" >> "$OUT/taps.txt" 2>&1
    sleep 3
    adb exec-out screencap -p > "$OUT/after-tap-$i.png" 2>/dev/null || true
    $UI dump "$OUT/state-$i.xml" >> "$OUT/taps.txt" 2>&1
    # fresh screen for the next one, so a reverted switch cannot be confused with a stale one
    start_screen
    i=$((i + 1))
done

# what survives a cold start, all at once
start_screen
adb exec-out screencap -p > "$OUT/final.png" 2>/dev/null || true
$UI dump "$OUT/final.xml" | tee "$OUT/final.txt"

adb shell "cat /data/data/$PKG/shared_prefs/litex_prefs.xml" > "$OUT/litex_prefs.xml" 2>&1
grep -iE "premium|prm" "$OUT/logcat.txt" | grep -v "walitex_premium_id" | head -40 > "$OUT/premium-log.txt"
# Preserve full diagnostic call stacks from trace builds; a single grep line would omit frames.
grep -n -A40 -B2 -E 'ProXDialogTrace|ProXCase22|ProXSetPrmBanner' "$OUT/logcat.txt" > "$OUT/dialog-trace.txt" || true
grep -n -E 'ProXToggleRead|ProXSwitchState|ProXGetPrm|ProXSetBoolean' "$OUT/logcat.txt" > "$OUT/toggle-trace.txt" || true
wc -l < "$OUT/premium-log.txt"

kill $LP 2>/dev/null || true
adb shell am force-stop "$PKG" >/dev/null 2>&1 || true
echo done
