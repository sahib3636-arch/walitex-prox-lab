#!/usr/bin/env bash
# key_alias_test.sh — why does a mod switch come back off?
#
# Three hypotheses, tested in one pass on the mod's Privacy screen:
#   A. the value is written to a *legacy* key while the screen reads the new one, and only a clean
#      close (back) runs whatever mirrors legacy -> new;
#   B. a hard stop loses it (i.e. only the clean close matters);
#   C. the screen reads `walitex_<name>_switch`, so seeding that key directly must light it up.
set -uo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/require_emulator.sh"
OUT=out
mkdir -p "$OUT"
PKG="${PKG:-com.whatsapp.litex}"
ACT="${ACT:-litex.settings.PrivacyActivity}"
PREFS="/data/data/$PKG/shared_prefs/litex_prefs.xml"
UI="python3 scripts/toggles.py"

adb wait-for-device
require_android_emulator || exit $?
adb root >/dev/null 2>&1 || true
sleep 5
adb wait-for-device
adb shell svc power stayon true >/dev/null 2>&1 || true
adb shell pm uninstall "$PKG" >/dev/null 2>&1 || true
adb install -r -g app.apk 2>&1 | tee "$OUT/install.txt"

open_screen() { adb shell am start -W -n "$PKG/$ACT" >/dev/null 2>&1; sleep 6; }
close_clean() { adb shell input keyevent KEYCODE_BACK >/dev/null 2>&1; sleep 3; }
close_hard()  { adb shell am force-stop "$PKG" >/dev/null 2>&1; sleep 2; }
dump()        { $UI dump "$OUT/$1.xml" | tee -a "$OUT/report.txt"; adb exec-out screencap -p > "$OUT/$1.png"; }

open_screen
$UI list | tee "$OUT/list.txt"
$UI tap 2 | tee -a "$OUT/report.txt"
sleep 3
close_clean
open_screen
$UI tap 2 | tee -a "$OUT/report.txt"      # toggle back off to start clean
sleep 3
close_hard
open_screen
$UI tap 2 | tee -a "$OUT/report.txt"      # on again, this time with a hard close
sleep 3
close_hard
echo "=== A/B: after hard close" >> "$OUT/report.txt"
open_screen
dump state-hard
echo "--- prefs after tap+hard close" >> "$OUT/report.txt"
adb shell "cat $PREFS" >> "$OUT/report.txt" 2>&1

# C: seed the new-style key directly and see if the screen lights up
adb shell "cp $PREFS /sdcard/p.xml && chmod 666 /sdcard/p.xml"
adb pull /sdcard/p.xml "$OUT/pulled.xml" >/dev/null 2>&1
python3 - "$OUT/pulled.xml" "$OUT/seeded.xml" <<'PY'
import sys
src, dst = sys.argv[1], sys.argv[2]
xml = open(src).read()
add = ('    <boolean name="walitex_hide_statusV2_switch" value="true" />\n'
       '    <boolean name="walitex_antirevoke_status_v2_switch" value="true" />\n'
       '    <boolean name="walitex_antirevoke_switch" value="true" />\n')
xml = xml.replace("</map>", add + "</map>")
open(dst, "w").write(xml)
print(xml)
PY
close_hard
UID_GID=$(adb shell "stat -c %U:%G $PREFS" | tr -d '\r')
adb push "$OUT/seeded.xml" /sdcard/seeded.xml >/dev/null 2>&1
adb shell "cat /sdcard/seeded.xml > $PREFS && chown $UID_GID $PREFS && chmod 660 $PREFS" || true
echo "--- prefs after seeding ($UID_GID)" >> "$OUT/report.txt"
adb shell "cat $PREFS" >> "$OUT/report.txt" 2>&1
open_screen
echo "=== C: after seeding walitex_*_switch" >> "$OUT/report.txt"
dump state-seeded

adb shell am force-stop "$PKG" >/dev/null 2>&1 || true
echo done
