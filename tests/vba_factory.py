"""Synthetic VBA project for tests. The macro is never executed.

The OLE container and the MS-OVBA dir stream are built here so the suite
does not ship a real workbook. oletools only reads the result.
"""

from __future__ import annotations

import struct

_ENDOFCHAIN = 0xFFFFFFFE
_FATSECT = 0xFFFFFFFD
_FREESECT = 0xFFFFFFFF
_NOSTREAM = 0xFFFFFFFF


def compress_vba(data: bytes) -> bytes:
    """MS-OVBA compressed container using literal tokens only."""
    out = bytearray(b"\x01")
    pos = 0
    while pos < len(data):
        block = data[pos : pos + 4096]
        pos += len(block)
        body = bytearray()
        index = 0
        while index < len(block):
            body.append(0)
            for _bit in range(8):
                if index >= len(block):
                    break
                body.append(block[index])
                index += 1
        chunk_len = 2 + len(body)
        header = (chunk_len - 3) & 0x0FFF
        header |= 0b011 << 12
        header |= 1 << 15
        out += struct.pack("<H", header)
        out += body
    return bytes(out)


def _record(record_id: int, payload: bytes) -> bytes:
    return struct.pack("<HI", record_id, len(payload)) + payload


def _dir_stream(module_name: str) -> bytes:
    name = module_name.encode("latin-1")
    name_u = module_name.encode("utf-16le")
    raw = bytearray()
    raw += _record(0x0001, struct.pack("<I", 1))  # syskind Windows
    raw += _record(0x0002, struct.pack("<I", 0x409))
    raw += _record(0x0014, struct.pack("<I", 0x409))
    raw += _record(0x0003, struct.pack("<H", 1252))
    raw += _record(0x0004, b"Obra")
    raw += _record(0x0005, b"")
    raw += struct.pack("<HI", 0x0040, 0)
    raw += _record(0x0006, b"")
    raw += struct.pack("<HI", 0x003D, 0)
    raw += _record(0x0007, struct.pack("<I", 0))
    raw += _record(0x0008, struct.pack("<I", 0))
    raw += struct.pack("<HI", 0x0009, 4)
    raw += struct.pack("<IH", 0, 0)
    raw += _record(0x000C, b"")
    raw += struct.pack("<HI", 0x003C, 0)
    raw += struct.pack("<H", 0x000F)  # PROJECTMODULES, size follows in parse_modules
    raw += struct.pack("<IH", 2, 1)  # size 2, one module
    raw += struct.pack("<HIH", 0x0013, 2, 0x4D)
    raw += _record(0x0019, name)
    raw += _record(0x0047, name_u)
    raw += _record(0x001A, name)
    raw += struct.pack("<HI", 0x0032, len(name_u))
    raw += name_u
    raw += _record(0x001C, b"")
    raw += struct.pack("<HI", 0x0048, 0)
    raw += _record(0x0031, struct.pack("<I", 0))
    raw += _record(0x001E, struct.pack("<I", 0))
    raw += _record(0x002C, struct.pack("<H", 0x42))
    raw += struct.pack("<HI", 0x0021, 0)  # procedural module, reserved
    raw += struct.pack("<HI", 0x002B, 0)  # terminator
    return compress_vba(bytes(raw))


def _dir_entry(name: str, kind: int, left: int, right: int, child: int, start: int, size: int) -> bytes:
    raw = bytearray(128)
    encoded = (name.encode("utf-16le") + b"\x00\x00")[:64]
    raw[0 : len(encoded)] = encoded
    struct.pack_into("<H", raw, 64, len(encoded))
    raw[66] = kind
    raw[67] = 1  # black
    struct.pack_into("<III", raw, 68, left, right, child)
    struct.pack_into("<II", raw, 116, start, size)
    return bytes(raw)


def build_vba_project(source: str, module_name: str = "Modulo1") -> bytes:
    """Return a vbaProject.bin whose only module is ``source``."""
    project = (
        'ID="{00000000-0000-0000-0000-000000000001}"\r\n'
        f"Module={module_name}\r\n"
        'Name="Obra"\r\n'
        'HelpContextID="0"\r\n'
        'VersionCompatible32="393222000"\r\n'
        "\r\n"
        "[Host Extender Info]\r\n"
        "&H00000001={3832D640-CF90-11CF-8E43-00A0C911005A};VBE;&H00000000\r\n"
    ).encode("latin-1")
    vba_project = bytes.fromhex("CC61FFFF000000000100")
    module = compress_vba(source.encode("latin-1"))
    directory = _dir_stream(module_name)
    streams = [
        ("PROJECT", project),
        ("Modulo1", module),
        ("dir", directory),
        ("_VBA_PROJECT", vba_project),
    ]
    return _ole(streams)


def _pack_mini(streams: list[tuple[str, bytes]]) -> tuple[bytes, bytes, list[tuple[int, int]]]:
    """Mini-stream bytes, mini-FAT sector, and (start, size) per stream."""
    mini = bytearray()
    fat: list[int] = []
    placed: list[tuple[int, int]] = []
    for _name, payload in streams:
        start = len(mini) // 64
        placed.append((start, len(payload)))
        chunk = payload
        if len(chunk) % 64:
            chunk += b"\x00" * (64 - (len(chunk) % 64))
        first = len(fat)
        count = len(chunk) // 64
        for index in range(count):
            fat.append(first + index + 1)
        if count:
            fat[-1] = _ENDOFCHAIN
        mini += chunk
    fat_bytes = bytearray(512)
    for index, value in enumerate(fat):
        struct.pack_into("<I", fat_bytes, index * 4, value)
    for index in range(len(fat), 128):
        struct.pack_into("<I", fat_bytes, index * 4, _FREESECT)
    return bytes(mini), bytes(fat_bytes), placed


def _ole(named: list[tuple[str, bytes]]) -> bytes:
    # Directory order: Root, PROJECT, VBA, Modulo1, dir, _VBA_PROJECT.
    # Mini-stream order matches the stream entries that have bytes.
    mini, mini_fat, placed = _pack_mini(named)
    mini_sectors = max(1, (len(mini) + 511) // 512)
    # sectors: 0 FAT, 1-2 directory, 3 mini FAT, 4... mini stream
    dir_start = 1
    mini_fat_sector = 3
    mini_start = 4
    total_sectors = mini_start + mini_sectors
    fat = [_FREESECT] * 128
    fat[0] = _FATSECT
    fat[1] = 2
    fat[2] = _ENDOFCHAIN
    fat[3] = _ENDOFCHAIN
    for offset in range(mini_sectors):
        sector = mini_start + offset
        fat[sector] = sector + 1 if offset + 1 < mini_sectors else _ENDOFCHAIN

    project_at, modulo_at, dir_at, vba_at = placed
    entries = [
        _dir_entry("Root Entry", 5, _NOSTREAM, _NOSTREAM, 1, mini_start, len(mini)),
        _dir_entry("PROJECT", 2, _NOSTREAM, 2, _NOSTREAM, project_at[0], project_at[1]),
        _dir_entry("VBA", 1, _NOSTREAM, _NOSTREAM, 3, 0, 0),
        _dir_entry(named[1][0], 2, 4, 5, _NOSTREAM, modulo_at[0], modulo_at[1]),
        _dir_entry("dir", 2, _NOSTREAM, _NOSTREAM, _NOSTREAM, dir_at[0], dir_at[1]),
        _dir_entry("_VBA_PROJECT", 2, _NOSTREAM, _NOSTREAM, _NOSTREAM, vba_at[0], vba_at[1]),
    ]
    directory = bytearray(1024)
    for index, entry in enumerate(entries):
        directory[index * 128 : (index + 1) * 128] = entry

    header = bytearray(512)
    header[0:8] = bytes.fromhex("D0CF11E0A1B11AE1")
    struct.pack_into("<H", header, 0x18, 0x003E)
    struct.pack_into("<H", header, 0x1A, 0x0003)
    struct.pack_into("<H", header, 0x1C, 0xFFFE)
    struct.pack_into("<H", header, 0x1E, 9)
    struct.pack_into("<H", header, 0x20, 6)
    struct.pack_into("<I", header, 0x2C, 1)
    struct.pack_into("<I", header, 0x30, dir_start)
    struct.pack_into("<I", header, 0x38, 4096)
    struct.pack_into("<I", header, 0x3C, mini_fat_sector)
    struct.pack_into("<I", header, 0x40, 1)
    struct.pack_into("<I", header, 0x44, _ENDOFCHAIN)
    struct.pack_into("<I", header, 0x4C, 0)
    for index in range(1, 109):
        struct.pack_into("<I", header, 0x4C + 4 * index, _FREESECT)

    fat_sector = bytearray(512)
    for index, value in enumerate(fat[:128]):
        struct.pack_into("<I", fat_sector, index * 4, value)

    blob = bytearray(header)
    blob += fat_sector
    blob += directory
    blob += mini_fat
    blob += mini
    if len(mini) % 512:
        blob += b"\x00" * (512 - (len(mini) % 512))
    # pad to the declared sector count
    while len(blob) < (total_sectors + 1) * 512:
        blob += b"\x00" * 512
    return bytes(blob)
