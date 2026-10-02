"""Read the Windows subsystem of a PE file. No extra dependency.

2 is the windowed subsystem (no console). 3 is the console subsystem.
"""

from __future__ import annotations

import sys
from pathlib import Path

WINDOWS_GUI = 2
WINDOWS_CUI = 3


def pe_subsystem(path: Path) -> int:
    data = path.read_bytes()
    if data[:2] != b"MZ":
        raise ValueError(f"{path} não é um executável PE")
    pe = int.from_bytes(data[0x3C:0x40], "little")
    if data[pe : pe + 4] != b"PE\0\0":
        raise ValueError(f"{path} não é um executável PE")
    # Subsystem sits 68 bytes into the optional header for PE32 and PE32+.
    return int.from_bytes(data[pe + 24 + 68 : pe + 24 + 70], "little")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("uso: pe_subsystem.py ARQUIVO 2|3", file=sys.stderr)
        return 2
    found = pe_subsystem(Path(args[0]))
    expected = int(args[1])
    if found != expected:
        print(f"subsystem {found} != {expected}", file=sys.stderr)
        return 1
    print(found)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
