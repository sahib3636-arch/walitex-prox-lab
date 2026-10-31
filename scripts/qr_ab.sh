#!/usr/bin/env bash
# qr_ab.sh — two builds, one emulator, one walk: which part of the identity rename kills the QR?
#
#   case 1  app.apk       package as shipped by that build (default: com.whatsapp.litex)
#   case 2  original.apk  package $CLONE_PKG (a renamed build)
#
# Both are driven through `adb root` + `am start` of the companion activity with the same extra the
# ⋮ menu item uses, so no build needs its own shim.
set -uo pipefail
OUT=out
mkdir -p "$OUT"
UI="python3 scripts/ui.py"

adb wait-for-device
adb root >/dev/null 2>&1 || true
sleep 6
adb wait-for-device
adb shell id | tee "$OUT/whoami.txt"
adb shell input keyevent KEYCODE_WAKEUP || true
adb shell wm dismiss-keyguard || true
adb shell settings put global window_animation_scale 0 || true
adb shell settings put global transition_animation_scale 0 || true
adb shell svc power stayon true || true

run_case() {  # run_case <tag> <apk> <package>
    local tag="$1" apk="$2" pkg="$3"
    echo "===== $tag : $apk as $pkg ====="
    # clear BOTH identities: a renamed build that keeps the original authorities (or account type)
    # must not share the device with the vendor app, otherwise the test conflates coexistence with
    # whatever the build itself broke.
    for p in com.whatsapp.litex com.whatsapp.pxmod "${CLONE_PKG:-com.whatsapp.pxmod}"; do
        adb shell pm uninstall "$p" >/dev/null 2>&1 || true
        adb uninstall "$p" >/dev/null 2>&1 || true
    done
    adb shell pm list packages | grep -E "whatsapp" | tee "$OUT/packages-$tag-before.txt"
    adb install -r -g "$apk" 2>&1 | tee "$OUT/install-$tag.txt"
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
    $UI shot "$tag-01-phone-screen" >/dev/null
    adb shell am start -W -n "$pkg/com.whatsapp.litex.companionmode.registration.ui.RegisterAsCompanionActivity" \
        --es entry_point entry_phone_reg 2>&1 | tee "$OUT/am-$tag.txt"
    for i in $(seq 1 6); do
        sleep 15
        $UI shot "$tag-watch-$i" >/dev/null
    done
    adb shell dumpsys window 2>/dev/null | grep -E "mCurrentFocus" | head -2 | tee -a "$OUT/focus-$tag.txt"
    kill $lp 2>/dev/null || true
    adb shell am force-stop "$pkg" >/dev/null 2>&1 || true
    sleep 4
}

case1_pkg="${CASE1_PKG:-com.whatsapp.litex}"
case2_pkg="${CLONE_PKG:-com.whatsapp.pxmod}"
run_case case1 app.apk      "$case1_pkg"
run_case case2 original.apk "$case2_pkg"

echo done
exit 0
