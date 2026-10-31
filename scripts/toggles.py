#!/usr/bin/env python3
"""toggles.py — list, tap and re-read the switch widgets of the mod's settings screen.

    python3 scripts/toggles.py list
    python3 scripts/toggles.py tap 0
    python3 scripts/toggles.py dump out/foo.xml
"""
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

SWITCH_HINTS = ("SwitchCompat", "Switch", "CheckBox", "android.widget.Switch")


def ui_dump(dest: str) -> str:
    subprocess.run(["adb", "shell", "uiautomator", "dump", "/sdcard/ui.xml"],
                   capture_output=True)
    subprocess.run(["adb", "pull", "/sdcard/ui.xml", dest], capture_output=True)
    return dest


def nodes(path: str):
    tree = ET.parse(path)
    out = []
    for n in tree.iter("node"):
        cls = n.get("class", "")
        if any(h in cls for h in SWITCH_HINTS):
            out.append(dict(cls=cls.split(".")[-1],
                            text=n.get("text", ""),
                            desc=n.get("content-desc", ""),
                            checked=n.get("checked", ""),
                            bounds=n.get("bounds", ""),
                            clickable=n.get("clickable", "")))
    return out


def centre(bounds: str):
    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds or "")
    if not m:
        return None
    x1, y1, x2, y2 = map(int, m.groups())
    return (x1 + x2) // 2, (y1 + y2) // 2


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    path = sys.argv[2] if len(sys.argv) > 2 else "/tmp/ui.xml"
    if cmd == "list":
        ui_dump(path)
        for i, n in enumerate(nodes(path)):
            print(f"{i}: {n['cls']:12s} checked={n['checked']:5s} text={n['text'][:40]!r} "
                  f"desc={n['desc'][:40]!r} {n['bounds']}")
    elif cmd == "tap":
        idx = int(sys.argv[2])
        ui_dump("/tmp/ui_tap.xml")
        ns = nodes("/tmp/ui_tap.xml")
        if idx >= len(ns):
            print(f"no switch #{idx} (found {len(ns)})")
            return 2
        c = centre(ns[idx]["bounds"])
        print("tap", idx, ns[idx], c)
        subprocess.run(["adb", "shell", "input", "tap", str(c[0]), str(c[1])], check=False)
    elif cmd == "dump":
        ui_dump(path)
        for i, n in enumerate(nodes(path)):
            print(f"{i}: checked={n['checked']:5s} text={n['text'][:40]!r}")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
