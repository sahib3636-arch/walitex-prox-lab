#!/usr/bin/env python3
"""Tiny uiautomator driver: dump the hierarchy, list what is on screen, tap by label.

  python3 ui.py list 01            # print every text / content-desc with its centre
  python3 ui.py tap "Agree" "Accept"   # tap the first node whose text contains one of these
  python3 ui.py shot 02            # save out/02.png
  python3 ui.py key BACK|HOME|ENTER

Everything is also appended to out/ui.log so a failed run is still readable afterwards.
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path
from xml.etree import ElementTree as ET

OUT = Path("out")
OUT.mkdir(exist_ok=True)
LOG = OUT / "ui.log"


def log(msg: str) -> None:
    print(msg, flush=True)
    with LOG.open("a") as f:
        f.write(msg + "\n")


def sh(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True)


def shot(name: str) -> None:
    p = OUT / f"{name}.png"
    with p.open("wb") as f:
        subprocess.run(["adb", "exec-out", "screencap", "-p"], stdout=f, stderr=subprocess.DEVNULL)
    log(f"  screenshot {p}")


def dump(tag: str = "ui"):
    """uiautomator dump is flaky right after a transition; retry a few times."""
    local = OUT / f"{tag}.xml"
    for attempt in range(4):
        sh("adb", "shell", "uiautomator", "dump", "/sdcard/ui.xml")
        r = sh("adb", "pull", "/sdcard/ui.xml", str(local))
        if r.returncode == 0 and local.exists() and local.stat().st_size > 200:
            try:
                return ET.parse(local).getroot()
            except ET.ParseError:
                pass
        time.sleep(2)
    return None


def centre(node) -> tuple[int, int] | None:
    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
    if not m:
        return None
    x1, y1, x2, y2 = map(int, m.groups())
    return (x1 + x2) // 2, (y1 + y2) // 2


def labels(node):
    for attr in ("text", "content-desc"):
        v = (node.get(attr) or "").strip()
        if v:
            yield attr, v


def listing(root) -> list[str]:
    rows = []
    for n in root.iter("node"):
        for attr, v in labels(n):
            c = centre(n)
            rows.append(f"{attr:12s} {v!r:60s} at {c}")
    return rows


def require_emulator() -> bool:
    guard = Path(__file__).with_name("require_emulator.sh")
    result = subprocess.run(
        ["bash", "-c", 'source "$1"; require_android_emulator', "emulator-guard", str(guard)],
        check=False,
    )
    return result.returncode == 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd not in {"shot", "key", "raw", "has", "list", "tap"}:
        print(f"unknown command {cmd}")
        return 2
    if not require_emulator():
        return 2

    if cmd == "shot":
        shot(args[0] if args else "shot")
        return 0

    if cmd == "key":
        sh("adb", "shell", "input", "keyevent", args[0])
        log(f"  key {args[0]}")
        time.sleep(1)
        return 0

    if cmd == "raw":
        sh("adb", "shell", "input", *args)
        log(f"  input {' '.join(args)}")
        time.sleep(1)
        return 0

    if cmd == "has":
        root = dump("has")
        if root is None:
            return 1
        wanted = [a.lower() for a in args]
        for n in root.iter("node"):
            for attr, v in labels(n):
                lv = " ".join(v.lower().split())
                if any(w in lv for w in wanted):
                    log(f"  found {attr}={v!r}")
                    return 0
        return 1

    if cmd in ("list", "tap"):
        tag = args[0] if cmd == "list" and args else "ui"
        root = dump(tag)
        if root is None:
            log(f"!! could not dump ui for {cmd}")
            return 1
        rows = listing(root)
        if cmd == "list":
            log(f"--- {len(rows)} labelled nodes ---")
            for r in rows:
                log("  " + r)
            return 0
        # keyword-major (the order of arguments is the priority order), and within a keyword the
        # best candidate wins: an exact label beats a substring, and a clickable node beats plain
        # text. The EULA page contains the sentence 'Tap "Agree and continue"…', so a naive
        # substring match taps the paragraph in the middle of the screen instead of the button.
        wanted = [a.lower() for a in args]
        parent = {c: p for p in root.iter("node") for c in p}

        def clickable(n) -> bool:
            cur = n
            for _ in range(6):
                if cur is None:
                    break
                if (cur.get("clickable") or "").lower() == "true":
                    return True
                cur = parent.get(cur)
            return False

        for w in wanted:
            best = None
            for n in root.iter("node"):
                for attr, v in labels(n):
                    lv = " ".join(v.lower().split())
                    if w not in lv:
                        continue
                    score = (0 if lv == w else (1 if lv.startswith(w) else 2),
                             0 if clickable(n) else 1)
                    c = centre(n)
                    if c and (best is None or score < best[0]):
                        best = (score, attr, v, c)
            if best is None:
                continue
            _, attr, v, c = best
            log(f"  tap {attr}={v!r} at {c} for {w!r}")
            sh("adb", "shell", "input", "tap", str(c[0]), str(c[1]))
            time.sleep(2)
            return 0
        log(f"  no node matched {wanted}; on screen:")
        for r in rows[:40]:
            log("    " + r)
        return 1

    print(f"unknown command {cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
