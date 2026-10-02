"""Window logic without a display, plus the Windows version resource."""

import importlib.util
from pathlib import Path

from oculto_scan import __version__
from oculto_scan.cli import main
from oculto_scan.gui import main as gui_main
from oculto_scan.gui_logic import compare_files, result_html, result_text, scan_file, suggested_html_name
from tests.workbook_factory import build_workbook

_VERSION_INFO = Path(__file__).resolve().parents[1] / "packaging" / "write_version_info.py"


def _version_module():
    spec = importlib.util.spec_from_file_location("oculto_scan_version_info", _VERSION_INFO)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

_SECRET = "SEGREDO-VISIVEL-NAO-MASCARE"


def test_gui_version_does_not_need_a_window(capsys):
    assert gui_main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"oculto-scan {__version__}"
    assert main(["gui", "--version"]) == 0
    assert capsys.readouterr().out.strip() == f"oculto-scan {__version__}"


def test_scan_summary_stays_masked_until_reveal(tmp_path):
    path = tmp_path / "proposta.xlsx"
    build_workbook(
        path,
        [
            {
                "name": "Proposta",
                "cells": [{"ref": "A1", "value": "Item"}],
                "comments": [{"ref": "A1", "author": "Ana", "text": _SECRET}],
            },
            {"name": "Custos", "state": "hidden", "cells": [{"ref": "B2", "value": 10}]},
        ],
    )
    session = scan_file(path)
    assert session.ready
    masked = result_text(session, show=False)
    assert "alto" in masked
    assert "aba oculta" in masked
    assert _SECRET not in masked
    revealed = result_text(session, show=True)
    assert _SECRET in revealed
    page = result_html(session, show=False)
    assert _SECRET not in page
    assert "oculto-scan" in page
    assert suggested_html_name(show=False, mode="scan") == "oculto-scan-relatorio.html"
    assert suggested_html_name(show=True, mode="diff") == "oculto-scan-diff-revelado.html"


def test_rejects_other_suffixes_and_compares_two_files(tmp_path):
    other = tmp_path / "nota.txt"
    other.write_text("oi", encoding="utf-8")
    refused = scan_file(other)
    assert not refused.ready
    assert ".xlsx" in refused.error
    assert result_html(refused, show=True) == ""

    original = tmp_path / "original.xlsx"
    received = tmp_path / "recebido.xlsx"
    build_workbook(original, [{"name": "Proposta", "cells": [{"ref": "A1", "value": "quantidade 12"}]}])
    build_workbook(received, [{"name": "Proposta", "cells": [{"ref": "A1", "value": _SECRET}]}])
    session = compare_files(original, received)
    assert session.ready
    masked = result_text(session, show=False)
    assert _SECRET not in masked
    assert "antes:" in masked
    revealed = result_text(session, show=True)
    assert _SECRET in revealed
    page = result_html(session, show=False)
    assert _SECRET not in page
    assert "Antes" in page


def test_version_resource_uses_one_version_and_the_product_name():
    module = _version_module()
    quad = module.version_quad("0.1.7")
    assert quad == (0, 1, 7, 0)
    text = module.render_version_info("0.1.7")
    assert text.count("filevers=(0, 1, 7, 0)") == 1
    assert text.count("prodvers=(0, 1, 7, 0)") == 1
    assert text.count("0.1.7.0") == 2
    assert "StringStruct('ProductName', 'oculto-scan')" in text
    assert "StringStruct('FileDescription', 'Verifica se a planilha pode vazar dados antes do envio.')" in text
    assert "StringStruct('CompanyName', 'Henderson Gomes')" in text
    assert "StringStruct('Comments', 'Apache-2.0')" in text
    assert "StringStruct('InternalName', 'oculto-scan')" in text
    assert "StringStruct('FileVersion', '0.1.7.0')" in text
    assert "StringStruct('ProductVersion', '0.1.7.0')" in text
