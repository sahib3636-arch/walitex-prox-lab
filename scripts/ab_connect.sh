#!/usr/bin/env bash
# A/B: does the server keep the socket open for the untouched WA LiteX and close it for ours?
#
# Both apps do the same thing on a clean device the moment they launch: open a pre-registration
# connection to g.whatsapp.net:443 and send companion_hello / login traffic. The clone's verbose
# logging (mf4 patch) shows the server closing the stream ~40 ms after the handshake. The original
# prints nothing to logcat, so the same question is answered from the outside instead: sample
# /proc/net/tcp{,6} for the lifetime of a connected socket to port 443 (§01BB), every 4 s.
set -uo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/require_emulator.sh"
OUT=out
mkdir -p "$OUT"

adb wait-for-device
require_android_emulator || exit $?
adb shell input keyevent KEYCODE_WAKEUP || true
adb shell wm dismiss-keyguard || true
adb shell settings put global window_animation_scale 0 || true
adb shell settings put global transition_animation_scale 0 || true
adb shell svc power stayon true || true

audit() {  # audit <tag> <package>
    local tag="$1"
    local uid
    uid=$(adb shell dumpsys package "$2" 2>/dev/null | grep -m1 -o "userId=[0-9]*" | cut -d= -f2)
    echo "package=$2 uid=$uid" | tee "$OUT/uid-$tag.txt"
    adb logcat -c || true
    adb logcat -v threadtime > "$OUT/logcat-$tag.txt" 2>&1 &
    local lp=$!
    sleep 1
    adb shell am start -W -n "$2/com.whatsapp.litex.Main" 2>&1 | tee "$OUT/start-$tag.txt"
    sleep 12
    {
        echo "=== sockets $tag uid=$uid"
        for i in $(seq 1 18); do
            echo "--- sample $i $(date -u +%H:%M:%S)"
            adb shell "cat /proc/net/tcp /proc/net/tcp6 2>/dev/null" |
                awk -v uid="$uid" 'NR > 1 && $4 == "01" { n = split($3, a, ":"); if (a[n] == "01BB" && $8 == uid) print "  mine->443  " $2 " -> " a[n-1] ":" a[n] "  uid=" $8 }'
            sleep 4
        done
    } >> "$OUT/sockets-$tag.txt" 2>&1
    adb shell dumpsys window 2>/dev/null | grep -E "mCurrentFocus" | head -1 >> "$OUT/sockets-$tag.txt"
    kill $lp 2>/dev/null || true
    sleep 1
    grep -aE "PROX-PROBE|Closed before read completed|connect/connected|reportDisconnect" "$OUT/logcat-$tag.txt" |
        head -40 > "$OUT/highlights-$tag.txt" || true
    adb shell am force-stop "$2" 2>/dev/null || true
    sleep 3
}

echo "===== clone ====="
adb install -r -g app.apk 2>&1 | tee "$OUT/install-clone.txt"
CLONE_PKG="${CLONE_PKG:-com.whatsapp.litey}"
echo "clone package: $CLONE_PKG"
audit clone "$CLONE_PKG"

echo "===== original ====="
adb install -r -g original.apk 2>&1 | tee "$OUT/install-original.txt"
audit original com.whatsapp.litex

echo done
