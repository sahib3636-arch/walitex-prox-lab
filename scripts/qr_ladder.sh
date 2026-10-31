#!/usr/bin/env bash
# qr_ladder.sh — does the *untouched* pack draw a QR on this emulator?
#
# The emulator cannot open the ⋮ menu on the phone-number screen, and the companion activity is not
# exported, so `am start` used to be refused. `adb root` makes the shell uid 0, which is allowed to
# start non-exported activities — so every build, patched or not, can now be driven into exactly the
# same screen with exactly the same intent the menu item builds.
#
#   case 1  original.apk  com.whatsapp.litex            the vendor's own artifact, 2.26.42.74
#   case 2  app.apk       $CLONE_PKG (com.whatsapp.pxmod) identity renamed, zero dex bytes changed
#
# Whoever shows a QR wins the argument about where the bug lives.
set -uo pipefail
OUT=out
mkdir -p "$OUT"
UI="python3 scripts/ui.py"

adb wait-for-device
adb root 2>&1 | tee "$OUT/root.txt" || true
sleep 6
adb wait-for-device
adb shell id 2>&1 | tee -a "$OUT/root.txt"
adb shell input keyevent KEYCODE_WAKEUP || true
adb shell wm dismiss-keyguard || true
adb shell settings put global window_animation_scale 0 || true
adb shell settings put global transition_animation_scale 0 || true
adb shell svc power stayon true || true

run_case() {  # run_case <tag> <apk> <package>
    local tag="$1" apk="$2" pkg="$3"
    echo "===== $tag : $apk ($pkg) ====="
    adb install -r -g "$apk" 2>&1 | tee "$OUT/install-$tag.txt"
    adb shell am force-stop "$pkg" >/dev/null 2>&1 || true
    adb logcat -c || true
    adb logcat -v threadtime > "$OUT/logcat-$tag.txt" 2>&1 &
    local lp=$!
    sleep 1
    adb shell am start -W -n "$pkg/com.whatsapp.litex.Main" >/dev/null 2>&1
    sleep 25
    for i in 1 2 3 4 5 6; do
        if $UI tap "got it" "ok" "agree and continue" "i agree" "accept" "continue" "allow" "while using the app" >/dev/null 2>&1; then
            sleep 4
        else
            break
        fi
    done
    $UI shot "$tag-01-before-companion" >/dev/null
    $UI list "$tag-01-before-companion" >/dev/null 2>&1 || true
    adb shell am start -W -n "$pkg/com.whatsapp.litex.companionmode.registration.ui.RegisterAsCompanionActivity" \
        --es entry_point entry_phone_reg 2>&1 | tee "$OUT/am-$tag.txt"
    for i in $(seq 1 6); do
        sleep 15
        $UI shot "$tag-watch-$i" >/dev/null
    done
    adb shell dumpsys window 2>/dev/null | grep -E "mCurrentFocus" | head -2 | tee -a "$OUT/focus-$tag.txt"
    kill $lp 2>/dev/null || true
    grep -aE "Closed before read completed|connect/connected|PROX-PROBE|companion" "$OUT/logcat-$tag.txt" |
        head -25 > "$OUT/highlights-$tag.txt" || true
    adb shell am force-stop "$pkg" >/dev/null 2>&1 || true
    sleep 4
}

CLONE_PKG="${CLONE_PKG:-com.whatsapp.pxmod}"
run_case original original.apk com.whatsapp.litex
run_case renamed  app.apk      "$CLONE_PKG"

echo done
exit 0
