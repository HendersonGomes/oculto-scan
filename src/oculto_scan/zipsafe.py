"""Limits for untrusted OOXML packages.

The scanner never extracts a member to disk. Declared sizes are checked
before a read, and every read is capped so a lying local header cannot
expand without bound.

Compression ratio and member count are hostile. Size above the analysis
limit is a separate error: a large legitimate workbook is not an attack.
"""

from __future__ import annotations

import io
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
    """The package looks hostile (zip bomb, too many parts, or encrypted)."""


class FileTooLargeError(Exception):
    """The package is above the analysis size limit. It is not hostile."""


def _mib(limit: int) -> int:
    return max(limit // (1024 * 1024), 1)


def _limits(max_mb: int | None) -> tuple[int, int, int]:
    """File size, total uncompressed, and per-part uncompressed limits."""
    if max_mb is None:
        return MAX_FILE_BYTES, MAX_TOTAL_UNCOMPRESSED, MAX_MEMBER_UNCOMPRESSED
    raised = max_mb * 1024 * 1024
    return raised, raised, raised


def _too_large(limit: int, kind: str) -> FileTooLargeError:
    return FileTooLargeError(
        f"arquivo acima do limite de análise ({_mib(limit)} MiB, {kind}). "
        "Use --max-mb para analisar um arquivo maior de propósito."
    )


def _reject_archive(
    archive: zipfile.ZipFile,
    *,
    total_limit: int,
    member_limit: int,
) -> None:
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
        if declared > member_limit:
            archive.close()
            raise _too_large(member_limit, "por parte")
        total += declared
        if total > total_limit:
            archive.close()
            raise _too_large(total_limit, "total descompactado")
        if info.compress_size and declared >= RATIO_MIN_UNCOMPRESSED:
            ratio = declared / info.compress_size
            if ratio > MAX_RATIO:
                archive.close()
                raise ZipSafetyError(f"razão de compressão {ratio:.0f}:1 acima do limite")


def open_office_package(path: Path, *, max_mb: int | None = None) -> zipfile.ZipFile:
    file_limit, total_limit, member_limit = _limits(max_mb)
    size = path.stat().st_size
    if size > file_limit:
        raise _too_large(file_limit, "arquivo")
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ZipSafetyError("não é um pacote zip válido") from exc
    _reject_archive(archive, total_limit=total_limit, member_limit=member_limit)
    return archive


def open_office_bytes(data: bytes, *, max_mb: int | None = None) -> zipfile.ZipFile:
    file_limit, total_limit, member_limit = _limits(max_mb)
    if len(data) > file_limit:
        raise _too_large(file_limit, "arquivo")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ZipSafetyError("não é um pacote zip válido") from exc
    _reject_archive(archive, total_limit=total_limit, member_limit=member_limit)
    return archive


def read_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo, *, max_mb: int | None = None) -> bytes:
    _file_limit, _total_limit, member_limit = _limits(max_mb)
    limit = member_limit
    chunks: list[bytes] = []
    total = 0
    with archive.open(info, "r") as handle:
        while True:
            block = handle.read(min(READ_CHUNK, limit - total + 1))
            if not block:
                break
            total += len(block)
            if total > limit:
                raise _too_large(limit, "por parte")
            chunks.append(block)
    if info.compress_size and total >= RATIO_MIN_UNCOMPRESSED:
        ratio = total / info.compress_size
        if ratio > MAX_RATIO:
            raise ZipSafetyError(f"razão de compressão {ratio:.0f}:1 acima do limite")
    return b"".join(chunks)
