"""Limits for untrusted OOXML packages.

The scanner never extracts a member to disk. Declared sizes are checked
before a read, and every read is capped so a lying local header cannot
expand without bound.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED = 64 * 1024 * 1024
MAX_MEMBER_UNCOMPRESSED = 32 * 1024 * 1024
MAX_MEMBERS = 2000
MAX_RATIO = 200
RATIO_MIN_UNCOMPRESSED = 1 * 1024 * 1024
READ_CHUNK = 64 * 1024


class ZipSafetyError(Exception):
    """The package looks hostile (zip bomb, too many parts, or too large)."""


def open_office_package(path: Path) -> zipfile.ZipFile:
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ZipSafetyError(
            f"arquivo acima do limite de {MAX_FILE_BYTES // (1024 * 1024)} MiB"
        )
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ZipSafetyError("não é um pacote zip válido") from exc

    infos = archive.infolist()
    if len(infos) > MAX_MEMBERS:
        archive.close()
        raise ZipSafetyError(f"pacote com mais de {MAX_MEMBERS} membros")

    total = 0
    for info in infos:
        if info.flag_bits & 0x1:
            archive.close()
            raise ZipSafetyError("membro criptografado não é lido")
        declared = info.file_size
        if declared > MAX_MEMBER_UNCOMPRESSED:
            archive.close()
            raise ZipSafetyError("membro descompactado acima do limite")
        total += declared
        if total > MAX_TOTAL_UNCOMPRESSED:
            archive.close()
            raise ZipSafetyError("tamanho descompactado total acima do limite")
        if info.compress_size and declared >= RATIO_MIN_UNCOMPRESSED:
            ratio = declared / info.compress_size
            if ratio > MAX_RATIO:
                archive.close()
                raise ZipSafetyError(
                    f"razão de compressão {ratio:.0f}:1 acima do limite"
                )
    return archive


def read_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    limit = MAX_MEMBER_UNCOMPRESSED
    chunks: list[bytes] = []
    total = 0
    with archive.open(info, "r") as handle:
        while True:
            block = handle.read(min(READ_CHUNK, limit - total + 1))
            if not block:
                break
            total += len(block)
            if total > limit:
                raise ZipSafetyError("leitura descompactada acima do limite")
            chunks.append(block)
    if info.compress_size and total >= RATIO_MIN_UNCOMPRESSED:
        ratio = total / info.compress_size
        if ratio > MAX_RATIO:
            raise ZipSafetyError(f"razão de compressão {ratio:.0f}:1 acima do limite")
    return b"".join(chunks)
