#!/usr/bin/env python3
"""
Minimal, surgical dex patcher for the microphone work.

Two single-instruction sites decide which audio source WhatsApp asks the OS for:

  * `classes12.dex`, `LX/Pyx;->A02(...)`   — the Opus voice-note recorder.
      :cond_1c5  abProp.getInt(0x34b3) -> used verbatim when non-zero
                 else `const/4 v8, 0x1`  (AudioSource.MIC)   <-- the fallback to patch
      v8 becomes OpusRecorderConfig.audioSource (ctor param 1) and is handed to the native
      Oboe/AudioRecord recorder.

  * `classes4.dex`, `LX/5Cy;->A00()Z`      — the MediaRecorder path, `setAudioSource(0x1)`.

We do not rebuild either dex (a smali round-trip of a 20 MB dex is a much bigger change than
the feature needs). We locate the instruction by parsing the dex structures, overwrite the
literal nibble, then restore the adler32 checksum and SHA-1 signature so nothing downstream
notices. Every other byte is untouched, which is asserted before returning.

Usage:
    python3 mic_patch.py --list
    python3 mic_patch.py --dex classes12.dex --to 5      # CAMCORDER
"""
import argparse
import hashlib
import struct
import sys
import zlib
from pathlib import Path

# AudioSource constants (android.media.MediaRecorder.AudioSource / AudioRecord)
SOURCES = {1: "MIC", 5: "CAMCORDER", 6: "VOICE_RECOGNITION", 7: "VOICE_COMMUNICATION",
           9: "UNPROCESSED", 0: "DEFAULT"}


# --------------------------------------------------------------------------- #
def uleb(data, i):
    shift = val = 0
    while True:
        b = data[i]
        i += 1
        val |= (b & 0x7F) << shift
        if not b & 0x80:
            return val, i
        shift += 7


def header(data):
    (string_ids_size, string_ids_off, type_ids_size, type_ids_off, proto_ids_size,
     proto_ids_off, field_ids_size, field_ids_off, method_ids_size, method_ids_off,
     class_defs_size, class_defs_off) = struct.unpack_from("<12I", data, 56)
    return dict(string_ids=(string_ids_size, string_ids_off),
                type_ids=(type_ids_size, type_ids_off),
                proto_ids=(proto_ids_size, proto_ids_off),
                method_ids=(method_ids_size, method_ids_off),
                class_defs=(class_defs_size, class_defs_off))


def string_at(data, h, idx):
    size, off = h["string_ids"]
    (str_off,) = struct.unpack_from("<I", data, off + 4 * idx)
    n, i = uleb(data, str_off)
    return data[i:i + n].decode("utf-8", "replace")


def type_name(data, h, type_idx):
    size, off = h["type_ids"]
    (str_idx,) = struct.unpack_from("<I", data, off + 4 * type_idx)
    return string_at(data, h, str_idx)


def method_id(data, h, idx):
    size, off = h["method_ids"]
    cls_idx, proto_idx, name_idx = struct.unpack_from("<HHI", data, off + 8 * idx)
    return type_name(data, h, cls_idx), string_at(data, h, name_idx)


def find_method(data, h, want_class, want_method):
    """Return (code_off, insns_off, insns_size) for the first matching method."""
    hdr = header(data)
    size, off = hdr["class_defs"]
    hits = []
    for n in range(size):
        (class_idx, _flags, _super, _ifaces, _src, _anno, class_data_off,
         _static) = struct.unpack_from("<8I", data, off + 32 * n)
        if not class_data_off:
            continue
        cname = type_name(data, hdr, class_idx)
        i = class_data_off
        sf, i = uleb(data, i)
        inf, i = uleb(data, i)
        dm, i = uleb(data, i)
        vm, i = uleb(data, i)
        idx = 0
        for _ in range(sf + inf):
            _d, i = uleb(data, i)
            _a, i = uleb(data, i)
        for count in (dm, vm):
            idx = 0
            for _ in range(count):
                diff, i = uleb(data, i)
                _acc, i = uleb(data, i)
                code_off, i = uleb(data, i)
                idx += diff
                mname = method_id(data, hdr, idx)[1]
                if code_off and cname == want_class and mname == want_method:
                    registers, ins, outs, tries, dbg, insns_size = struct.unpack_from(
                        "<HHHHII", data, code_off)
                    hits.append((code_off, code_off + 16, insns_size))
    return hits


def find_const4(data, insns_off, insns_size, register, limit_candidates=None):
    """Offsets (absolute) of `const/4 vREG, #literal` inside one method."""
    out = []
    for k in range(insns_size - 1):
        unit = struct.unpack_from("<H", data, insns_off + 2 * k)[0]
        if unit & 0xFF != 0x12:            # opcode 0x12 = const/4, literal/reg in high byte
            continue
        pair = unit >> 8
        lit, reg = pair >> 4, pair & 0xF
        if reg == register:
            out.append((insns_off + 2 * k, lit))
    return out


def fix_checksums(data: bytearray):
    data[12:32] = hashlib.sha1(bytes(data[32:])).digest()
    struct.pack_into("<I", data, 8, zlib.adler32(bytes(data[12:])) & 0xFFFFFFFF)


def patch_site(data: bytes, want_class, want_method, register, new_source, expect=None):
    h = header(data)
    hits = find_method(data, h, want_class, want_method)
    if len(hits) != 1:
        raise SystemExit(f"{want_class}->{want_method}: expected 1 code item, got {len(hits)}")
    code_off, insns_off, insns_size = hits[0]
    cands = find_const4(data, insns_off, insns_size, register)
    if expect is not None:
        cands = [c for c in cands if c[1] == expect]
    if len(cands) != 1:
        raise SystemExit(f"{want_class}->{want_method}: {len(cands)} candidate const/4 v{register} "
                         f"instructions, expected exactly 1: {cands}")
    off, lit = cands[0]
    out = bytearray(data)
    unit = struct.unpack_from("<H", out, off)[0]
    reg = (unit >> 8) & 0xF
    out[off:off + 2] = struct.pack("<H", 0x12 | (new_source << 12) | (reg << 8))
    fix_checksums(out)
    changed = [i for i in range(len(out)) if out[i] != data[i]]
    outside_checksum = [i for i in changed if not (8 <= i < 32)]
    if len(outside_checksum) != 1:
        raise SystemExit(f"patch touched {len(outside_checksum)} bytes of code, expected 1")
    return bytes(out), dict(site=f"{want_class}->{want_method}", reg=reg, insn_offset=off,
                            code_off=code_off, was=lit, now=new_source,
                            was_name=SOURCES.get(lit), now_name=SOURCES.get(new_source))


# --------------------------------------------------------------------------- #
# The two sites, as constants so the build script and the tests agree.
SITES = [
    ("classes12.dex", "LX/Pyx;", "A02", 8, 1),     # Opus voice-note fallback: MIC
    ("classes4.dex", "LX/5Cy;", "A00", 4, 1),      # MediaRecorder setAudioSource(MIC)
]


def build_variant(dex_blobs: dict, source: int) -> tuple[dict, list]:
    """dex_blobs: {name: bytes} -> patched copy with both sites moved to `source`."""
    out, report = {}, []
    for name, cls, meth, reg, expect in SITES:
        if name not in dex_blobs:
            continue
        patched, info = patch_site(dex_blobs[name], cls, meth, reg, source, expect=expect)
        dex_blobs = dict(dex_blobs)
        dex_blobs[name] = patched
        out[name] = patched
        report.append(info)
    return out, report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dex", required=True)
    ap.add_argument("--to", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    data = Path(a.dex).read_bytes()
    h = header(data)
    if a.list:
        for name, cls, meth, reg, expect in SITES:
            for code_off, insns_off, n in find_method(data, h, cls, meth):
                print(f"{cls}->{meth} code_off=0x{code_off:x} "
                      f"const/4 v{reg}: {find_const4(data, insns_off, n, reg)}")
        return 0
    if a.to not in SOURCES:
        print(f"unknown source {a.to}; known: {SOURCES}", file=sys.stderr)
        return 2
    patched, info = patch_site(data, "LX/Pyx;", "A02", 8, a.to)
    Path(a.out).write_bytes(patched)
    print(info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
