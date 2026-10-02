"""Window layout data, missing stdio, and the two Windows executables. No display."""

import importlib.util
import sys
from pathlib import Path

from oculto_scan.cli import main as cli_main
from oculto_scan.gui import main as gui_main
from oculto_scan.gui_logic import (
    ACHADOS,
    ERRO,
    LIMPO,
    VAZIO,
    Session,
    card_counts,
    compare_files,
    scan_file,
    type_counts,
    view_state,
)
from oculto_scan.gui_theme import ALTO, AMBER, CARD, CREAM, INFO, INK, MEDIO, MUTED, NAVY, contrast_ratio
from oculto_scan.report import ensure_stdio, stdout_wants_color
from tests.workbook_factory import build_workbook

ROOT = Path(__file__).resolve().parents[1]


def test_text_on_the_dark_theme_stays_readable():
    assert contrast_ratio(CREAM, NAVY) >= 4.5
    assert contrast_ratio(MUTED, NAVY) >= 4.5
    assert contrast_ratio(ALTO, CARD) >= 4.5
    assert contrast_ratio(MEDIO, CARD) >= 4.5
    assert contrast_ratio(INFO, CARD) >= 4.5
    assert contrast_ratio(INK, AMBER) >= 4.5


def test_cards_follow_the_same_counts_as_the_report(tmp_path):
    empty = Session()
    assert view_state(empty) == VAZIO
    assert card_counts(empty) == []
    refused = scan_file(tmp_path / "nota.txt")
    assert view_state(refused) == ERRO
    assert card_counts(refused) == []

    clean = tmp_path / "medicao.xlsx"
    build_workbook(
        clean,
        [{"name": "Medicao", "cells": [{"ref": "A1", "value": "Item"}, {"ref": "B2", "value": 12}]}],
    )
    clean_session = scan_file(clean)
    assert view_state(clean_session) == LIMPO
    assert card_counts(clean_session) == [
        ("alto", "alto", 0),
        ("medio", "médio", 0),
        ("info", "info", 0),
        ("total", "total", 0),
    ]

    demo = tmp_path / "proposta.xlsx"
    build_workbook(
        demo,
        [
            {
                "name": "Proposta",
                "cells": [{"ref": "C2", "formula": "Custos!B2*1.35", "value": 1350}],
                "comments": [{"ref": "C2", "author": "Ana", "text": "conferir margem"}],
            },
            {"name": "Custos", "state": "hidden", "cells": [{"ref": "B2", "value": 1000}]},
        ],
    )
    session = scan_file(demo)
    assert view_state(session) == ACHADOS
    counts = {key: count for key, _label, count in card_counts(session)}
    assert counts["alto"] == 2
    assert counts["medio"] == 1
    assert counts["info"] == 1
    assert counts["total"] == 4
    kinds = dict(type_counts(session))
    assert kinds["aba oculta"] == 1
    assert kinds["fórmula oculta"] == 1

    original = tmp_path / "original.xlsx"
    received = tmp_path / "recebido.xlsx"
    build_workbook(original, [{"name": "Proposta", "cells": [{"ref": "A1", "value": "quantidade 12"}]}])
    build_workbook(received, [{"name": "Proposta", "cells": [{"ref": "A1", "value": "quantidade 40"}]}])
    diff = compare_files(original, received)
    assert view_state(diff) == ACHADOS
    diff_cards = {key: count for key, _label, count in card_counts(diff)}
    assert diff_cards["total"] >= 1


def test_missing_stdio_does_not_crash(monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    ensure_stdio()
    assert stdout_wants_color(no_color=False) is False
    print("janela")
    print("erro", file=sys.stderr)

    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    assert gui_main(["--version"]) == 0

    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    assert cli_main([]) == 2


def test_windows_split_keeps_a_window_and_a_console():
    spec = (ROOT / "packaging" / "oculto-scan.spec").read_text(encoding="utf-8")
    assert '"oculto-scan",\n    console=False' in spec
    assert '"oculto-scan-cli",\n    console=True' in spec
    assert "upx=False" in spec
    script = (ROOT / "packaging" / "oculto-scan.iss").read_text(encoding="utf-8-sig")
    assert "oculto-scan-cli.exe" in script
    assert 'Filename: "{app}\\{#MyAppExeName}"' in script
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    scripts, _, rest = pyproject.partition("[project.scripts]")
    assert scripts is not None
    block, _, _after = rest.partition("[project.gui-scripts]")
    assert "oculto-scan-gui" not in block
    assert 'oculto-scan = "oculto_scan.cli:console_main"' in block
    assert 'oculto-scan-gui = "oculto_scan.gui:console_main"' in pyproject
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "pythonw" in readme
    assert "oculto-scan-cli.exe" in readme
    assert "sem a janela preta" in readme


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_pe_subsystem_reads_the_optional_header(tmp_path):
    module = _load(ROOT / "packaging" / "pe_subsystem.py", "oculto_scan_pe_subsystem")
    blob = bytearray(256)
    blob[0:2] = b"MZ"
    blob[0x3C:0x40] = (64).to_bytes(4, "little")
    blob[64:68] = b"PE\0\0"
    blob[64 + 24 + 68 : 64 + 24 + 70] = (2).to_bytes(2, "little")
    path = tmp_path / "janela.exe"
    path.write_bytes(blob)
    assert module.pe_subsystem(path) == module.WINDOWS_GUI
    blob[64 + 24 + 68 : 64 + 24 + 70] = (3).to_bytes(2, "little")
    path.write_bytes(blob)
    assert module.pe_subsystem(path) == module.WINDOWS_CUI
    assert module.main([str(path), "3"]) == 0
