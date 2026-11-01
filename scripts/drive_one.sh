#!/usr/bin/env bash
# drive_one.sh <package> <main-activity> <tag>  — same walk as probe.sh, parameterised so the
# original WA LiteX and the clone can be driven back to back on one emulator (A/B baseline).
set -uo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/require_emulator.sh"
require_android_emulator || exit $?
UI="python3 scripts/ui.py"
PKG="$1"; MAIN="$2"; TAG="$3"
OUT=out
mkdir -p "$OUT" "out/$TAG"

capture() {
    adb shell dumpsys window 2>/dev/null | grep -E "mCurrentFocus" | head -2 >> "$OUT/focus.log"
    $UI shot "$TAG/$1" >/dev/null
    $UI list "$TAG/$1" >/dev/null 2>&1 || true
}

echo "===== $TAG : $PKG ====="
adb logcat -c || true
adb logcat -v threadtime > "$OUT/logcat-$TAG.txt" 2>&1 &
LP=$!
sleep 1

adb shell am start -W -n "$PKG/$MAIN" 2>&1 | tee "$OUT/$TAG-start.txt"
sleep 25
capture 01_first_screen

for i in 1 2 3 4 5 6; do
    if $UI tap "got it" "ok" "agree and continue" "i agree" "accept" "continue" "confirm" "allow" "while using the app" "next" >/dev/null; then
        sleep 4
        capture "02_step$i"
    else
        break
    fi
done
capture 03_before_menu

MENU_OK=0
for attempt in 1 2 3; do
    adb shell input tap 300 52
    sleep 3
    if $UI has "link as companion" "companion device" "link a device" >/dev/null 2>&1; then
        MENU_OK=1; break
    fi
done
if [ "$MENU_OK" = 1 ]; then
    $UI tap "link as companion" "companion device" "link a device" >/dev/null || true
else
    adb shell am start -W -n "$PKG/com.whatsapp.litex.companionmode.registration.ui.RegisterAsCompanionActivity" >> "$OUT/$TAG-am.txt" 2>&1
fi
sleep 3
capture 05_companion_screen

for i in $(seq 1 5); do
    sleep 15
    capture "06_watch_$i"
done

adb logcat -b crash -d > "$OUT/crash-$TAG.txt" 2>&1 || true
kill $LP 2>/dev/null || true
sleep 1
grep -aE "PROX-PROBE|PROX-DBG|companion/|FATAL EXCEPTION" "$OUT/logcat-$TAG.txt" | tail -80 > "$OUT/highlights-$TAG.txt" || true
adb uninstall "$PKG" >/dev/null 2>&1 || true
