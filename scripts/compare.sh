#!/usr/bin/env bash
# A/B baseline: the untouched WA LiteX and our clone, same emulator, same minute, same walk.
# If the original shows a QR here and the clone does not, the fault is ours and the two logcats
# can be diffed. If neither shows a QR, the emulator cannot answer this question by itself.
set -uo pipefail
export PATH="$PATH:$ANDROID_HOME/platform-tools"
OUT=out; mkdir -p "$OUT"

adb wait-for-device
adb shell input keyevent KEYCODE_WAKEUP || true
adb shell wm dismiss-keyguard || true
adb shell settings put system screen_off_timeout 1800000 || true
adb shell settings put global window_animation_scale 0 || true
adb shell settings put global transition_animation_scale 0 || true
adb shell settings put global animator_duration_scale 0 || true
adb shell svc power stayon true || true

echo "abilist: $(adb shell getprop ro.product.cpu.abilist)"
echo "bridge:  $(adb shell getprop ro.dalvik.vm.native.bridge)"
{ echo "abilist=$(adb shell getprop ro.product.cpu.abilist)"
  echo "bridge=$(adb shell getprop ro.dalvik.vm.native.bridge)"
  adb shell getprop | grep -iE "native.bridge|abilist|arch" ; } > "$OUT/abi.txt" 2>&1

adb install -r -g app.apk      2>&1 | tee "$OUT/install-clone.txt"
adb install -r -g original.apk 2>&1 | tee "$OUT/install-original.txt"
adb shell pm list packages | grep -i whatsapp | tee -a "$OUT/install-clone.txt"

bash scripts/drive_one.sh com.whatsapp.litey com.whatsapp.litex.Main clone
bash scripts/drive_one.sh com.whatsapp.litex com.whatsapp.litex.Main original

adb shell dumpsys activity top > "$OUT/activity_top.txt" 2>&1 || true
echo done
