#!/usr/bin/env bash
# Drive WA ProX on a clean emulator until the "Link as companion device" screen, then watch it.
# Everything lands in out/ ; the workflow uploads out/ as an artifact.
set -uo pipefail
export PATH="$PATH:$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin"
OUT=out
mkdir -p "$OUT"
UI="python3 scripts/ui.py"
PKG=com.whatsapp.litey
MAIN=$PKG/com.whatsapp.litex.Main

say() { echo; echo "===== $* ====="; }

capture() {  # capture <tag>
    adb shell dumpsys window 2>/dev/null | grep -E "mCurrentFocus|mFocusedApp" | head -3
    adb shell dumpsys window 2>/dev/null | grep -E "mCurrentFocus|mFocusedApp" | head -3 >> "$OUT/focus.log"
    $UI shot "$1"
    $UI list "$1" || true
}

adb wait-for-device
adb shell input keyevent KEYCODE_WAKEUP || true
adb shell wm dismiss-keyguard || true
adb shell settings put system screen_off_timeout 1800000 || true
adb shell settings put global window_animation_scale 0 || true
adb shell settings put global transition_animation_scale 0 || true
adb shell settings put global animator_duration_scale 0 || true
adb shell svc power stayon true || true

say "emulator"
adb shell getprop ro.build.version.release
adb shell getprop ro.product.cpu.abi
adb shell wm size

say "install"
adb logcat -c || true
adb logcat -v threadtime > "$OUT/logcat.txt" 2>&1 &
LOGPID=$!
adb install -r -g app.apk 2>&1 | tee "$OUT/install.txt"
adb shell pm list packages | grep -i litey | tee -a "$OUT/install.txt"
adb shell dumpsys package "$PKG" | grep -E "versionName|firstInstallTime|lastUpdateTime" | head -3 | tee -a "$OUT/install.txt"

say "launch"
adb shell am start -W -n "$MAIN" 2>&1 | tee "$OUT/start.txt"
sleep 25
capture 01_first_screen

say "walk through whatever stands in front of the phone screen"
REACHED=0
for i in $(seq 1 12); do
    if $UI has "enter your phone number" "phone number" "verify your phone number" >/dev/null 2>&1; then
        echo "  REACHED the phone-number screen at step $i"
        REACHED=1
        break
    fi
    if $UI tap "got it" "ok" "agree and continue" "i agree" "accept" "continue" "allow" "while using the app" "confirm" "next"; then
        sleep 4
        capture "02_step$i"
    else
        echo "  nothing to advance on at step $i"
        sleep 5
        capture "02_stuck_$i"
    fi
done
echo "reached_phone_screen=$REACHED" | tee "$OUT/reached.txt"
capture 03_before_menu

COMPANION_ACT=$PKG/com.whatsapp.litex.companionmode.registration.ui.RegisterAsCompanionActivity
BOOTSTRAP_ACT=$PKG/com.whatsapp.litex.companionmode.registration.ui.CompanionBootstrapActivity

say "open the overflow menu (retry: popups do not always land on the first tap)"
MENU_OK=0
for attempt in 1 2 3; do
    adb shell input tap 300 52
    sleep 3
    $UI shot "04_menu_try$attempt" >/dev/null
    if $UI has "link as companion" "companion device" "link a device" >/dev/null 2>&1; then
        echo "  menu is open on attempt $attempt"
        MENU_OK=1
        $UI list "04_menu_try$attempt" || true
        break
    fi
    echo "  no menu after attempt $attempt"
    $UI list "04_menu_try$attempt" || true
done

if [ "$MENU_OK" = 1 ]; then
    say "tap Link as companion device"
    $UI tap "link as companion" "companion device" "link a device" || true
else
    say "menu never opened; starting the companion activity directly"
    adb shell am start -W -n "$COMPANION_ACT" 2>&1 | tee "$OUT/am_start_companion.txt"
fi
sleep 3
capture 05_companion_screen

if ! $UI has "link with phone number" "point your phone" "scan" "QR" "connecting" >/dev/null 2>&1; then
    say "companion screen not up; trying CompanionBootstrapActivity"
    adb shell am start -W -n "$BOOTSTRAP_ACT" 2>&1 | tee "$OUT/am_start_bootstrap.txt"
    sleep 3
    capture 05b_companion_screen
fi

say "watch the linking screen for 90 s"
for i in $(seq 1 6); do
    sleep 15
    capture "06_watch_$i"
    adb shell dumpsys window 2>/dev/null | grep -E "mCurrentFocus" | head -1
done

say "network state"
getent hosts g.whatsapp.net >/dev/null 2>&1 || true
adb shell ping -c 2 -W 3 g.whatsapp.net 2>&1 | tail -3 | tee "$OUT/net.txt" || true
adb shell "cat /proc/net/tcp /proc/net/tcp6 2>/dev/null | wc -l" >> "$OUT/net.txt" 2>&1 || true
adb shell dumpsys connectivity 2>/dev/null | head -30 >> "$OUT/net.txt" || true

say "collect"
adb logcat -b crash -d > "$OUT/crash.txt" 2>&1 || true
adb logcat -b events -d > "$OUT/events.txt" 2>&1 || true
adb shell dumpsys activity top > "$OUT/activity_top.txt" 2>&1 || true
adb shell dumpsys window windows > "$OUT/windows.txt" 2>&1 || true
kill $LOGPID 2>/dev/null || true
sleep 1

say "highlights from logcat"
grep -aE "PROX-PROBE|PROX-DBG|companion|FATAL|AndroidRuntime|WhatsApp|WaLog" "$OUT/logcat.txt" \
    | tail -120 | tee "$OUT/highlights.txt" || true

say "fatal exceptions (if any)"
grep -a -A25 "FATAL EXCEPTION" "$OUT/logcat.txt" | head -80 | tee "$OUT/fatals.txt" || true

exit 0

echo "done"
