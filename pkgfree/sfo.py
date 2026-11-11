"""Minimal param.sfo reader."""

import struct

from .i18n import tr

SFO_MAGIC = b"\x00PSF"


def parse_sfo(data: bytes) -> dict:
    if len(data) < 20 or data[:4] != SFO_MAGIC:
        raise ValueError(tr("param.sfo non valido"))
    _, key_table, data_table, count = struct.unpack_from("<IIII", data, 4)
    result = {}
    for i in range(count):
        key_off, fmt, length, _max_len, data_off = struct.unpack_from("<HHIII", data, 20 + i * 16)
        key_start = key_table + key_off
        key = data[key_start:data.index(b"\x00", key_start)].decode("utf-8", "replace")
        raw = data[data_table + data_off:data_table + data_off + length]
        if fmt == 0x0404:
            result[key] = struct.unpack("<I", raw[:4])[0]
        else:
            result[key] = raw.split(b"\x00", 1)[0].decode("utf-8", "replace")
    return result


# -- full read/write (used to rebuild PKGs) -------------------------------------------

SFO_UTF8_SPECIAL = 0x0004
SFO_UTF8 = 0x0204
SFO_INTEGER = 0x0404


class SfoValue:
    """One param.sfo value with its storage format and reserved length."""

    def __init__(self, key: str, fmt: int, value, max_len: int):
        self.key, self.fmt, self.value, self.max_len = key, fmt, value, max_len

    def to_bytes(self) -> bytes:
        if self.fmt == SFO_INTEGER:
            return struct.pack("<I", self.value & 0xFFFFFFFF)
        raw = str(self.value).encode("utf-8")
        return raw + b"\x00" if self.fmt == SFO_UTF8 else raw

    @property
    def length(self) -> int:
        return len(self.to_bytes())


class Sfo:
    def __init__(self, values: list[SfoValue]):
        self.values = values

    @classmethod
    def parse(cls, data: bytes) -> "Sfo":
        if len(data) < 20 or data[:4] != SFO_MAGIC:
            raise ValueError(tr("param.sfo non valido"))
        _, key_table, data_table, count = struct.unpack_from("<IIII", data, 4)
        values = []
        for i in range(count):
            key_off, fmt, length, max_len, data_off = struct.unpack_from(
                "<HHIII", data, 20 + i * 16)
            key_start = key_table + key_off
            key = data[key_start:data.index(b"\x00", key_start)].decode("utf-8", "replace")
            raw = data[data_table + data_off:data_table + data_off + length]
            if fmt == SFO_INTEGER:
                value = struct.unpack("<I", raw[:4])[0]
            else:
                value = raw.split(b"\x00", 1)[0].decode("utf-8", "replace")
            values.append(SfoValue(key, fmt, value, max_len))
        return cls(values)

    def get(self, key: str, default=None):
        for v in self.values:
            if v.key == key:
                return v.value
        return default

    def set_str(self, key: str, value: str, max_len: int) -> None:
        self._set(SfoValue(key, SFO_UTF8, value, max_len))

    def set_int(self, key: str, value: int) -> None:
        self._set(SfoValue(key, SFO_INTEGER, value, 4))

    def _set(self, new: SfoValue) -> None:
        for i, v in enumerate(self.values):
            if v.key == new.key:
                new.max_len = max(new.max_len, v.max_len) if new.fmt != SFO_INTEGER else 4
                self.values[i] = new
                return
        self.values.append(new)

    def remove(self, key: str) -> None:
        self.values = [v for v in self.values if v.key != key]

    def to_bytes(self) -> bytes:
        values = sorted(self.values, key=lambda v: v.key)
        key_table = 0x14 + 0x10 * len(values)
        keys = b"".join(v.key.encode("ascii") + b"\x00" for v in values)
        data_table = key_table + len(keys)
        data_table += -data_table % 4
        out = bytearray(data_table + sum(v.max_len for v in values))
        struct.pack_into("<4sIIII", out, 0, SFO_MAGIC, 0x101, key_table, data_table, len(values))
        key_off = data_off = 0
        for i, v in enumerate(values):
            raw = v.to_bytes()[:v.max_len]
            struct.pack_into("<HHIII", out, 0x14 + 0x10 * i, key_off, v.fmt, len(raw),
                             v.max_len, data_off)
            k = v.key.encode("ascii") + b"\x00"
            out[key_table + key_off:key_table + key_off + len(k)] = k
            out[data_table + data_off:data_table + data_off + len(raw)] = raw
            key_off += len(k)
            data_off += v.max_len
        return bytes(out)
