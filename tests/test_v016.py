"""Next-step hints on the text report only."""

import json

from oculto_scan.cli import main, next_steps_text
from tests.workbook_factory import build_workbook


def _plain(path):
    build_workbook(path, [{"name": "Proposta", "cells": [{"ref": "A1", "value": "quantidade 12"}]}])


def _block(text: str) -> list[str]:
    assert "Próximos passos:" in text
    return text.split("Próximos passos:", 1)[1].strip().splitlines()


def test_text_ends_with_copyable_steps(tmp_path, capsys):
    path = tmp_path / "proposta.xlsx"
    _plain(path)
    code = main([str(path), "--no-color"])
    text = capsys.readouterr().out
    quoted = f'"{path}"'
    assert code == 0
    steps = _block(text)
    assert len(steps) == 4
    assert f"oculto-scan {quoted} --show" in text
    assert f"oculto-scan {quoted} --format html" in text
    assert f'oculto-scan diff {quoted} "recebido.xlsx"' in text
    assert "oculto-scan --help" in text
    assert "oculto-scan[macro]" not in text
    assert text.index("nenhum achado não significa arquivo limpo.") < text.index("Próximos passos:")


def test_json_and_html_omit_the_block(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "proposta.xlsx"
    _plain(path)
    code = main([str(path), "--format", "json"])
    raw = capsys.readouterr().out
    payload = json.loads(raw)
    assert code == 0
    assert "Próximos passos" not in raw
    assert "oculto-scan --help" not in raw
    assert payload["version"] == "0.1.12"
    assert "mapa_da_rede" in payload

    code = main([str(path), "--format", "html", "--output", "relatorio.html"])
    captured = capsys.readouterr()
    page = (tmp_path / "relatorio.html").read_text(encoding="utf-8")
    assert code == 0
    assert "Próximos passos" not in captured.out
    assert "Próximos passos" not in page
    assert "oculto-scan --help" not in page


def test_hints_stay_off_in_ci_and_with_the_flag(tmp_path, monkeypatch, capsys):
    path = tmp_path / "proposta.xlsx"
    _plain(path)
    monkeypatch.setenv("CI", "true")
    code = main([str(path), "--no-color"])
    text = capsys.readouterr().out
    assert code == 0
    assert "Próximos passos" not in text

    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    code = main([str(path), "--no-color"])
    text = capsys.readouterr().out
    assert code == 0
    assert "Próximos passos" not in text

    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    hidden = tmp_path / "oculta.xlsx"
    build_workbook(
        hidden,
        [
            {"name": "Proposta", "cells": [{"ref": "A1", "value": "ok"}]},
            {"name": "Custos", "state": "hidden"},
        ],
    )
    with_hints = main([str(hidden), "--no-color"])
    capsys.readouterr()
    without = main([str(hidden), "--no-color", "--no-hints"])
    quiet = capsys.readouterr().out
    assert with_hints == 1
    assert without == 1
    assert "Próximos passos" not in quiet


def test_macro_hint_only_for_xlsm_without_the_extra(tmp_path, monkeypatch, capsys):
    xlsm = tmp_path / "medicao.xlsm"
    build_workbook(
        xlsm,
        [{"name": "Proposta", "cells": [{"ref": "A1", "value": "quantidade 12"}]}],
        vba_blob=b"nao-e-um-projeto",
    )
    code = main([str(xlsm), "--no-color"])
    text = capsys.readouterr().out
    assert code == 0
    assert "Próximos passos" in text
    assert "python -m pip install" not in text

    real_import = __import__

    def _blocked(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "oletools" or name.startswith("oletools."):
            raise ImportError("oletools ausente")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", _blocked)
    code = main([str(xlsm), "--no-color"])
    text = capsys.readouterr().out
    quoted = f'"{xlsm}"'
    assert code == 3
    steps = _block(text)
    assert len(steps) == 4
    assert 'python -m pip install "oculto-scan[macro]"' in steps[0]
    assert f"oculto-scan {quoted} --show" in text
    assert "oculto-scan --help" in text

    shown = next_steps_text(str(xlsm), show=True, needs_macro=False)
    assert "--show" not in shown
    assert "--format json" in shown
    assert "--format html" in shown
