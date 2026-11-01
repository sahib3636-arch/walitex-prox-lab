"""Minimal signing/ZIP helpers for update_linked.py.

The linked base APK and signing keystore are intentionally kept outside this repository.
Set PROX_BUILD_DIR, PROX_KEYSTORE, PROX_LINEAGE, PROX_KEY_ALIAS, and PROX_KEY_PASS privately.
"""
from __future__ import annotations

import os
import subprocess
import zipfile
from pathlib import Path

BUILD_DIR = Path(os.environ.get("PROX_BUILD_DIR", str(Path.home() / "prox-build")))
KEYSTORE = Path(os.environ.get("PROX_KEYSTORE", str(BUILD_DIR / "keys" / "prox-mod-a.p12")))
LINEAGE = Path(os.environ.get("PROX_LINEAGE", str(BUILD_DIR / "keys" / "lineage.bin")))
KEY_ALIAS = os.environ.get("PROX_KEY_ALIAS", "prox-mod-a")


def _run(argv: list[str]) -> str:
    proc = subprocess.run(argv, text=True, capture_output=True)
    if proc.returncode:
        raise RuntimeError(
            f"command failed ({proc.returncode}): {argv[0]}\n"
            f"stdout:\n{proc.stdout[-3000:]}\nstderr:\n{proc.stderr[-3000:]}"
        )
    return proc.stdout


def zipalign(source: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    _run(["zipalign", "-p", "-f", "4", str(source), str(output)])


def sign(apk: Path) -> str:
    """Sign with the pre-existing identity; the password is read only from the process env."""
    password = os.environ.get("PROX_KEY_PASS")
    if not password:
        raise RuntimeError("PROX_KEY_PASS is required; load it privately and never commit it")
    if not KEYSTORE.is_file() or not LINEAGE.is_file():
        raise RuntimeError("private keystore/lineage files are missing outside the repository")

    signed = apk.with_name(apk.stem + ".tmp.apk")
    _run([
        "apksigner", "sign",
        "--ks", str(KEYSTORE), "--ks-key-alias", KEY_ALIAS,
        "--ks-pass", "env:PROX_KEY_PASS",
        "--lineage", str(LINEAGE), "--rotation-min-sdk-version", "28",
        "--v1-signing-enabled", "true", "--v2-signing-enabled", "true",
        "--v3-signing-enabled", "true", "--min-sdk-version", "23",
        "--max-sdk-version", "36", "--out", str(signed), str(apk),
    ])
    signed.replace(apk)
    return _run(["apksigner", "verify", "--print-certs", "-v", str(apk)])


def entries(path: Path) -> dict[str, tuple[int, int, int]]:
    with zipfile.ZipFile(path) as archive:
        return {
            item.filename: (item.file_size, item.compress_type, item.CRC)
            for item in archive.infolist()
        }
