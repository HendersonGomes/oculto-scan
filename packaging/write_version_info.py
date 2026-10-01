"""Write the Windows version resource. Every version field uses the same value."""

from __future__ import annotations

import argparse
from pathlib import Path


def read_project_version(pyproject: Path) -> str:
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        if line.startswith("version = "):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("version ausente no pyproject.toml")


def version_quad(version: str) -> tuple[int, int, int, int]:
    numbers = [int(piece) for piece in version.split(".") if piece.isdecimal()]
    if len(numbers) < 2:
        raise SystemExit(f"versão inválida: {version}")
    while len(numbers) < 4:
        numbers.append(0)
    return numbers[0], numbers[1], numbers[2], numbers[3]


def render_version_info(version: str) -> str:
    quad = version_quad(version)
    text = ".".join(str(part) for part in quad)
    return f"""# UTF-8
# Generated from pyproject.toml. Do not edit by hand.
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={quad},
    prodvers={quad},
    mask=0x3F,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
    ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
        StringStruct('CompanyName', 'oculto-scan'),
        StringStruct('FileDescription', 'oculto-scan'),
        StringStruct('FileVersion', '{text}'),
        StringStruct('InternalName', 'oculto-scan'),
        StringStruct('LegalCopyright', 'Copyright 2026 Henderson Gomes'),
        StringStruct('OriginalFilename', 'oculto-scan.exe'),
        StringStruct('ProductName', 'oculto-scan'),
        StringStruct('ProductVersion', '{text}')
        ])
      ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    parser.add_argument("--output", type=Path, default=Path("build/file_version_info.txt"))
    args = parser.parse_args()
    version = read_project_version(args.pyproject)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_version_info(version), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
