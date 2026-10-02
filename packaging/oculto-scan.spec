# -*- mode: python ; coding: utf-8 -*-
"""Two Windows onefile builds. UPX stays off.

oculto-scan.exe is windowed: double-click and the installer shortcut open
only the Tk window. oculto-scan-cli.exe keeps a console for the terminal.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

root = Path(SPEC).resolve().parents[1]
icon_file = str(root / "packaging" / "oculto-scan.ico")

datas = [
    (str(root / "src" / "oculto_scan" / "oculto-scan.png"), "oculto_scan"),
    (str(root / "src" / "oculto_scan" / "oculto-scan.ico"), "oculto_scan"),
]
binaries = []
hiddenimports = collect_submodules("oculto_scan")
for package in (
    "oletools",
    "olefile",
    "pcodedmp",
    "colorclass",
    "easygui",
    "msoffcrypto",
    "cryptography",
    "tarja",
    "defusedxml",
):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden


def _onefile(entry: str, name: str, *, console: bool, version_file: str):
    analysis = Analysis(
        [entry],
        pathex=[str(root / "src")],
        binaries=binaries,
        datas=datas,
        hiddenimports=hiddenimports,
        hookspath=[],
        hooksconfig={},
        runtime_hooks=[],
        excludes=["pytest", "ruff"],
        noarchive=False,
    )
    pyz = PYZ(analysis.pure)
    return EXE(
        pyz,
        analysis.scripts,
        analysis.binaries,
        analysis.zipfiles,
        analysis.datas,
        [],
        name=name,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=console,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        version=version_file,
        icon=icon_file,
    )


# The name `exe` is what PyInstaller expects the spec to define.
exe = _onefile(
    str(root / "packaging" / "entry.py"),
    "oculto-scan",
    console=False,
    version_file=str(root / "build" / "file_version_info.txt"),
)
cli = _onefile(
    str(root / "packaging" / "entry_cli.py"),
    "oculto-scan-cli",
    console=True,
    version_file=str(root / "build" / "file_version_info_cli.txt"),
)
