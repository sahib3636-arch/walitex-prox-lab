#!/usr/bin/env bash
# A/B: does the server keep the socket open for the untouched WA LiteX and close it for ours?
#
# Both apps do the same thing on a clean device the moment they launch: open a pre-registration
# connection to g.whatsapp.net:443 and send companion_hello / login traffic. The clone's verbose
# logging (mf4 patch) shows the server closing the stream ~40 ms after the handshake. The original
# prints nothing to logcat, so the same question is answered from the outside instead: sample
# /proc/net/tcp{,6} for the lifetime of a connected socket to port 443 (§01BB), every 4 s.
set -uo pipefail
OUT=out
mkdir -p "$OUT"

adb wait-for-device
adb shell input keyevent KEYCODE_WAKEUP || true
adb shell wm dismiss-keyguard || true
adb shell settings put global window_animation_scale 0 || true
adb shell settings put global transition_animation_scale 0 || true
adb shell svc power stayon true || true

audit() {  # audit <tag>
    local tag="$1"
    adb logcat -c || true
    adb logcat -v threadtime > "$OUT/logcat-$tag.txt" 2>&1 &
    local lp=$!
    sleep 1
    {
        echo "=== sockets $tag"
        for i in $(seq 1 18); do
            echo "--- sample $i $(date -u +%H:%M:%S)"
            adb shell "cat /proc/net/tcp /proc/net/tcp6 2>/dev/null" | awk 'NR > 1 && $4 == "01"' |
                awk '{ n = split($3, a, ":"); if (a[n] == "01BB") print "  ESTABLISHED->443  " $2 " -> " a[n-1] ":" a[n] }'
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
adb shell am start -W -n com.whatsapp.litey/com.whatsapp.litex.Main 2>&1 | tee "$OUT/start-clone.txt"
sleep 15
audit clone com.whatsapp.litey

echo "===== original ====="
adb install -r -g original.apk 2>&1 | tee "$OUT/install-original.txt"
adb shell am start -W -n com.whatsapp.litex/com.whatsapp.litex.Main 2>&1 | tee "$OUT/start-original.txt"
sleep 15
audit original com.whatsapp.litex

echo done
