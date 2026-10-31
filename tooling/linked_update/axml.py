#!/usr/bin/env python3
"""Tiny binary AndroidManifest.xml (AXML) editor.

Only two operations are needed to make this app installable next to the original:

    set_attribute(...)   change the *string* value of an existing attribute
    pool.append(s)       add a string, keeping every existing index stable

New strings are appended to the pool, so no offsets inside the document shift; only the pool
chunk grows and the document header size is updated. Everything else is left byte for byte, which
is why this is safer than a full `apktool b` on a 124 MB app with 15 000 resources.
"""
from __future__ import annotations

import struct

RES_XML_TYPE = 0x0003
RES_STRING_POOL_TYPE = 0x0001
RES_XML_START_ELEMENT_TYPE = 0x0102
RES_XML_END_ELEMENT_TYPE = 0x0103
RES_XML_RESOURCE_MAP_TYPE = 0x0180
TYPE_STRING = 0x03
TYPE_REFERENCE = 0x01
NO_ENTRY = 0xFFFFFFFF


class Pool:
    def __init__(self, chunk: bytes):
        (self.type, self.header_size, self.size, self.string_count, self.style_count,
         self.flags, self.strings_start, self.styles_start) = struct.unpack_from("<HHIIIIII", chunk, 0)
        assert self.type == RES_STRING_POOL_TYPE, hex(self.type)
        self.utf8 = bool(self.flags & 0x100)
        self.offsets = list(struct.unpack_from(f"<{self.string_count}I", chunk, self.header_size))
        data = chunk[self.strings_start:]
        self.strings = [self._decode(data, off) for off in self.offsets]
        self.style_data = chunk[self.styles_start:] if self.styles_start else b""

    def _decode(self, data: bytes, off: int) -> str:
        if self.utf8:
            n = data[off]
            i = off + 1
            if n & 0x80:
                n = ((n & 0x7F) << 8) | data[i]
                i += 1
            end = data.index(b"\x00", i)
            return data[i:end].decode("utf-8")
        (n,) = struct.unpack_from("<H", data, off)
        i = off + 2
        if n & 0x8000:
            (n2,) = struct.unpack_from("<H", data, i)
            n = ((n & 0x7FFF) << 16) | n2
            i += 2
        return data[i:i + n * 2].decode("utf-16-le")

    def _encode(self, s: str) -> bytes:
        if self.utf8:
            b = s.encode("utf-8")
            n = len(s)                      # utf-16 code units
            if n > 0x7F:
                return bytes([0x80 | (n >> 8), n & 0xFF]) + b + b"\x00"
            return bytes([n]) + b + b"\x00"
        b = s.encode("utf-16-le")
        n = len(s)
        if n > 0x7FFF:
            return struct.pack("<HH", 0x8000 | (n >> 16), n & 0xFFFF) + b + b"\x00\x00"
        return struct.pack("<H", n) + b + b"\x00\x00"

    def append(self, s: str) -> int:
        """Append a string and return its index. Existing indices are untouched."""
        if s in self.strings:
            return self.strings.index(s)     # pools are deduplicated by the linker; keep it that way
        data = b"".join(self._encode(x) for x in self.strings)
        new_off = len(data)
        self.strings.append(s)
        self.offsets.append(new_off)
        self.string_count += 1
        return len(self.strings) - 1

    def to_bytes(self) -> bytes:
        data = b"".join(self._encode(s) for s in self.strings)
        padded = data + b"\x00" * ((4 - len(data) % 4) % 4)
        strings_start = self.header_size + 4 * self.string_count + 4 * self.style_count
        styles_start = strings_start + len(padded) if self.style_count else 0
        body = struct.pack(f"<{self.string_count}I", *self.offsets)
        if self.style_count:
            body += b"\x00" * (4 * self.style_count)
        size = strings_start + len(padded) + len(self.style_data)
        return (struct.pack("<HHIIIIII", RES_STRING_POOL_TYPE, self.header_size, size,
                            self.string_count, self.style_count, self.flags,
                            strings_start, styles_start)
                + body + padded + self.style_data)


class Axml:
    def __init__(self, data: bytes):
        self.file_size = len(data)
        (typ, hdr, size) = struct.unpack_from("<HHI", data, 0)
        assert typ == RES_XML_TYPE, hex(typ)
        assert size == len(data), (size, len(data))
        self.xml_header_size = hdr
        self.pool = Pool(data[hdr:])
        self.rest = data[hdr + self.pool.size:]

    # -- elements ---------------------------------------------------------- #
    def elements(self):
        """Yield (offset_in_rest, element_name, attributes) for every start element."""
        p = 0
        rest = self.rest
        while p + 8 <= len(rest):
            typ, hdr, size = struct.unpack_from("<HHI", rest, p)
            if size == 0:
                break
            if typ == RES_XML_START_ELEMENT_TYPE:
                ns, name = struct.unpack_from("<II", rest, p + 16)
                (attr_start, attr_size, attr_count) = struct.unpack_from("<HHH", rest, p + 24)
                attrs = []
                base = p + 16 + attr_start
                for i in range(attr_count):
                    a = base + i * attr_size
                    ans, aname, raw = struct.unpack_from("<III", rest, a)
                    (vsize, res0, dtype, ddata) = struct.unpack_from("<HBBI", rest, a + 12)
                    attrs.append((a, self.pool.strings[ans] if ans != NO_ENTRY else "",
                                  self.pool.strings[aname], raw, dtype, ddata))
                yield p, self.pool.strings[name], attrs
            p += size

    def set_string(self, attr_offset: int, value: str) -> None:
        """Point an existing attribute at `value` (appended to the pool)."""
        idx = self.pool.append(value)
        rest = bytearray(self.rest)
        # Res_value right after rawValue: size(u16) res0(u8) dataType(u8) data(u32)
        struct.pack_into("<I", rest, attr_offset + 8, idx)        # rawValue
        struct.pack_into("<B", rest, attr_offset + 15, TYPE_STRING)
        struct.pack_into("<I", rest, attr_offset + 16, idx)       # typed value data
        self.rest = bytes(rest)

    def to_bytes(self) -> bytes:
        pool = self.pool.to_bytes()
        total = self.xml_header_size + len(pool) + len(self.rest)
        head = struct.pack("<HHI", RES_XML_TYPE, self.xml_header_size, total)
        return head + pool + self.rest


def value_of(attr) -> str:
    _, _, _, raw, dtype, ddata = attr
    if dtype == TYPE_STRING:
        return None            # caller resolves through the pool (raw index)
    return None
