"""Icon, installer script and update text. No Windows and no display."""

import struct
from pathlib import Path

from oculto_scan.gui_help import update_help_text

ROOT = Path(__file__).resolve().parents[1]
_ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
_APP_ID = "EC7DF64B-360E-4FE7-B685-27540C3E6978"


def _ico_sizes(path: Path) -> list[int]:
    data = path.read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data, 0)
    assert reserved == 0
    assert kind == 1
    sizes: list[int] = []
    for index in range(count):
        width, height = struct.unpack_from("<BB", data, 6 + 16 * index)
        sizes.append(256 if width == 0 else width)
        assert (256 if height == 0 else height) == sizes[-1]
    return sizes


def test_icon_files_have_every_size_and_the_navy_amber_source():
    svg = (ROOT / "packaging" / "oculto-scan.svg").read_text(encoding="utf-8")
    assert "#0E2433" in svg
    assert "#E6A317" in svg
    assert "microsoft" not in svg.casefold()
    assert "excel" not in svg.casefold()
    packaging = ROOT / "packaging" / "oculto-scan.ico"
    bundled = ROOT / "src" / "oculto_scan" / "oculto-scan.ico"
    png = ROOT / "src" / "oculto_scan" / "oculto-scan.png"
    assert packaging.read_bytes() == bundled.read_bytes()
    assert png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert tuple(_ico_sizes(packaging)) == _ICO_SIZES


def test_installer_script_is_per_user_and_upgrades_in_place():
    script = (ROOT / "packaging" / "oculto-scan.iss").read_text(encoding="utf-8-sig")
    version = ""
    for line in (ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        if line.startswith("version = "):
            version = line.split("=", 1)[1].strip().strip('"')
    assert version == "0.2.4"
    assert f'#define MyAppVersion "{version}"' in script
    assert f'#define MyAppVersionQuad "{version}.0"' in script
    assert _APP_ID in script
    assert "PrivilegesRequired=lowest" in script
    assert "PrivilegesRequiredOverridesAllowed=dialog" in script
    assert "brazilianportuguese" in script
    assert "LicenseFile=..\\LICENSE" in script
    assert "Flags: unchecked" in script
    assert "postinstall" in script


def test_readme_offers_the_installer_and_hides_nothing_about_updating():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "oculto-scan-setup.exe" in readme
    assert "instale por cima" in readme
    assert "Não há instalador" not in readme
    text = update_help_text()
    assert "instale por cima" in text
    assert "oculto-scan-setup.exe" in text
    assert "Arquivo .exe portátil" in text
