"""Rasterize packaging/oculto-scan.svg into the icon files the app and the installer use.

Requires rsvg-convert. The generated files are committed so the Windows build
does not need that tool. Run: python packaging/build_icon.py
"""

from __future__ import annotations

import struct
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SVG = Path(__file__).resolve().parent / "oculto-scan.svg"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def _ico(images: list[tuple[int, bytes]]) -> bytes:
    count = len(images)
    header = struct.pack("<HHH", 0, 1, count)
    offset = 6 + 16 * count
    entries = bytearray()
    blobs = bytearray()
    for size, blob in images:
        stored = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", stored, stored, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
        blobs += blob
    return bytes(header + entries + blobs)


def render(svg: Path = SVG) -> None:
    package = ROOT / "src" / "oculto_scan"
    packaging = ROOT / "packaging"
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        images: list[tuple[int, bytes]] = []
        preview = b""
        for size in SIZES:
            png = folder / f"{size}.png"
            subprocess.run(
                ["rsvg-convert", "-w", str(size), "-h", str(size), "-o", str(png), str(svg)],
                check=True,
            )
            blob = png.read_bytes()
            images.append((size, blob))
            if size == 256:
                preview = blob
    ico = _ico(images)
    (packaging / "oculto-scan.ico").write_bytes(ico)
    (packaging / "oculto-scan.png").write_bytes(preview)
    (package / "oculto-scan.ico").write_bytes(ico)
    (package / "oculto-scan.png").write_bytes(preview)
    print(packaging / "oculto-scan.ico")


if __name__ == "__main__":
    render()
