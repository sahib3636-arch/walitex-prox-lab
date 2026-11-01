#!/usr/bin/env bash
# Fail closed before any driver installs, uninstalls, clears, launches, or mutates an Android app.
# These test scripts are for disposable emulators only, never the user's linked phone.
require_android_emulator() {
    if ! command -v adb >/dev/null 2>&1; then
        echo "Refusing Android test: adb is not installed or not on PATH." >&2
        return 2
    fi

    local serial="${ANDROID_SERIAL:-}"
    local -a active=()
    while IFS= read -r device; do
        [[ -n "$device" ]] && active+=("$device")
    done < <(adb devices | awk 'NR > 1 && $2 == "device" { print $1 }')

    if [[ -z "$serial" ]]; then
        if (( ${#active[@]} != 1 )); then
            echo "Refusing Android test: expected exactly one authorized ADB target, found ${#active[@]}." >&2
            echo "Set ANDROID_SERIAL to a disposable emulator; physical-device runs are blocked." >&2
            return 2
        fi
        serial="${active[0]}"
    else
        local found=0 device
        for device in "${active[@]}"; do
            [[ "$device" == "$serial" ]] && found=1
        done
        if (( found == 0 )); then
            echo "Refusing Android test: ANDROID_SERIAL=$serial is not an authorized connected device." >&2
            return 2
        fi
    fi

    local qemu
    qemu="$(adb -s "$serial" shell getprop ro.kernel.qemu 2>/dev/null | tr -d '\r')"
    if [[ "$qemu" != "1" ]]; then
        echo "Refusing Android test: ADB target $serial is not an Android emulator (ro.kernel.qemu=$qemu)." >&2
        echo "No package install/uninstall or app-data operation was performed." >&2
        return 2
    fi

    export ANDROID_SERIAL="$serial"
    echo "Android emulator guard: PASS (serial=$serial, ro.kernel.qemu=1)" >&2
}
