import json
import sys
from datetime import datetime, timedelta, timezone

from oculto_scan.cli import main
from oculto_scan.models import Finding
from oculto_scan.report import DISCLAIMER, enable_windows_vt, render_html, render_json, render_text
from tests.workbook_factory import build_workbook, make_cpf

CPF = make_cpf("529982247")
_SCRIPT = "<script>alert(1)</script>"


def _finding(**overrides) -> Finding:
    data = dict(
        file="proposta.xlsx",
        sheet="Proposta",
        cell="C2",
        rule="comentario",
        type_label="comentário",
        risk="medio",
        message="Há comentário nesta célula.",
        evidence_masked="texto mascarado (4 caracteres)",
        evidence_raw="SEGREDO-CRU",
    )
    data.update(overrides)
    return Finding(**data)


def test_html_document_escapes_spreadsheet_text_and_hides_raw_values():
    payload = _SCRIPT
    finding = _finding(
        file="a<b>.xlsx",
        sheet=payload,
        message=f"Há nota {payload}",
        evidence_masked=payload,
    )
    page = render_html([finding], ignored=0, scanned=1, files=["a<b>.xlsx"])
    assert "<!DOCTYPE html>" in page
    assert "@media print" in page
    assert "oculto-scan" in page
    assert "0.1.8" in page
    assert DISCLAIMER in page
    assert 'class="resumo"' in page
    assert ">1</strong><span>médio</span>" in page
    assert "SEGREDO-CRU" not in page
    assert "<script" not in page.lower()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "a&lt;b&gt;.xlsx" in page
    assert "http://" not in page
    assert "https://" not in page
    assert "<link" not in page.lower()
    assert "stylesheet" not in page.lower()


def test_html_orders_by_severity_and_splits_tables_by_file():
    findings = [
        _finding(file="b.xlsx", risk="info", type_label="constante", cell="A1", rule="formula-constante"),
        _finding(file="a.xlsx", risk="alto", type_label="aba oculta", cell="", rule="aba-oculta", sheet="Custos"),
        _finding(file="a.xlsx", risk="medio", cell="B2"),
    ]
    page = render_html(findings, ignored=2, scanned=2, files=["a.xlsx", "b.xlsx"])
    assert page.index("a.xlsx") < page.index("b.xlsx")
    assert page.index("aba oculta") < page.index("comentário")
    assert page.count("<table>") == 2
    assert ">2</strong><span>ignorados" not in page
    assert ">2</dd>" in page


def test_text_groups_the_file_and_paints_risk(monkeypatch):
    findings = [
        _finding(risk="alto", type_label="fórmula oculta", rule="formula-referencia-oculta", sheet="Proposta"),
        _finding(risk="medio", cell="B2"),
        _finding(risk="info", type_label="constante", rule="formula-constante", cell="C3"),
    ]
    plain = render_text(findings, show=False, ignored=0, scanned=1, color=False)
    assert plain.startswith("proposta.xlsx\n")
    assert plain.count("proposta.xlsx") == 1
    assert "  Proposta › C2 › fórmula oculta › alto" in plain
    assert "  Proposta › B2 › comentário › médio" in plain
    assert "  Proposta › C3 › constante › info" in plain
    assert "\033[" not in plain
    assert "SEGREDO-CRU" not in plain
    assert "Resumo: 1 alto, 1 médio, 1 info" in plain

    colored = render_text(findings, show=True, ignored=0, scanned=1, color=True)
    assert "\033[1mproposta.xlsx\033[0m" in colored
    assert "\033[31malto\033[0m" in colored
    assert "\033[33mmédio\033[0m" in colored
    assert "\033[36minfo\033[0m" in colored
    assert "SEGREDO-CRU" in colored
    assert "\033[1mResumo:\033[0m" in colored

    monkeypatch.delenv("NO_COLOR", raising=False)
    assert enable_windows_vt() is False or sys.platform == "win32"


def test_json_shape_is_unchanged():
    raw = render_json([_finding()], ignored=0, scanned=1)
    payload = json.loads(raw)
    assert set(payload) == {
        "tool",
        "version",
        "disclaimer",
        "scanned",
        "summary",
        "findings",
        "mapa_da_rede",
    }
    assert set(payload["findings"][0]) == {
        "file",
        "sheet",
        "cell",
        "rule",
        "type",
        "risk",
        "message",
        "value",
    }
    assert payload["version"] == "0.1.8"
    assert payload["mapa_da_rede"] == []
    assert "SEGREDO-CRU" not in raw
    assert "\033[" not in raw


def _xss_workbook(path):
    build_workbook(
        path,
        [
            {
                "name": "Proposta",
                "cells": [
                    {"ref": "A1", "value": "CPF"},
                    {"ref": "A2", "value": CPF},
                    {"ref": "B2", "formula": "Custos!B2*1.35", "value": 135},
                ],
                "comments": [
                    {"ref": "B2", "author": "Atacante", "text": _SCRIPT},
                ],
            },
            {"name": _SCRIPT, "state": "hidden", "cells": [{"ref": "B2", "value": 10}]},
        ],
        metadata={"creator": "Autora Sintetica"},
        external_target="file:///C:/Users/ana.sintetica/" + _SCRIPT,
    )


def test_html_without_show_stays_masked(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "xss.xlsx"
    _xss_workbook(path)
    code = main([str(path), "--format", "html", "--fail-on", "info"])
    captured = capsys.readouterr()
    report = tmp_path / "oculto-scan-relatorio.html"
    assert code == 1
    assert report.is_file()
    assert "oculto-scan-relatorio.html" in captured.out
    assert not (tmp_path / "oculto-scan-relatorio-revelado.html").exists()
    page = report.read_text(encoding="utf-8")
    assert CPF not in page
    assert "***.982.247-**" in page
    assert "1.35" not in page
    assert "Autora Sintetica" not in page
    assert _SCRIPT not in page
    assert "<script" not in page.lower()
    assert "&lt;script&gt;" in page
    assert "ana.sintetica" not in page
    assert "dados revelados" not in page
    assert "Valor mascarado" in page
    assert DISCLAIMER in page


def test_html_show_reveals_values_banner_and_escapes_script(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "xss.xlsx"
    _xss_workbook(path)
    code = main([str(path), "--show", "--format", "html", "--fail-on", "info"])
    captured = capsys.readouterr()
    report = tmp_path / "oculto-scan-relatorio-revelado.html"
    assert code == 1
    assert report.is_file()
    assert "oculto-scan-relatorio-revelado.html" in captured.out
    assert not (tmp_path / "oculto-scan-relatorio.html").exists()
    page = report.read_text(encoding="utf-8")
    assert "Este relatório contém os dados revelados (--show). Não envie este arquivo a terceiros." in page
    assert 'class="revelado"' in page
    assert CPF in page
    assert "1.35" in page
    assert "Autora Sintetica" in page
    assert "Custos!B2*1.35" in page
    assert _SCRIPT not in page
    assert "<script" not in page.lower()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "Valor revelado" in page
    assert DISCLAIMER in page


def test_html_stamp_uses_local_offset():
    when = datetime(2026, 9, 30, 21, 55, tzinfo=timezone(timedelta(hours=-3)))
    page = render_html([], ignored=0, scanned=0, files=[], generated_at=when)
    assert "30/09/2026 21:55 (UTC-03:00)" in page
    assert "+0000" not in page


def test_html_output_flag_writes_the_given_path(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "proposta.xlsx"
    build_workbook(
        path,
        [
            {"name": "Proposta", "cells": [{"ref": "A1", "value": "Item"}]},
            {"name": "Custos", "state": "hidden"},
        ],
    )
    dest = tmp_path / "saida" / "relatorio.html"
    code = main([str(path), "--format", "html", "--output", str(dest)])
    out = capsys.readouterr().out
    assert code == 1
    assert dest.is_file()
    assert str(dest) in out
    assert not (tmp_path / "oculto-scan-relatorio.html").exists()
    page = dest.read_text(encoding="utf-8")
    assert "Custos" in page
    assert page.index("alto") < page.index("médio") or "aba oculta" in page


def test_output_without_html_is_rejected(capsys):
    code = main([".", "--output", "relatorio.html"])
    captured = capsys.readouterr()
    assert code == 2
    assert "--format html" in captured.err


def test_colors_obey_tty_no_color_and_flag(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "cores.xlsx"
    build_workbook(
        path,
        [
            {
                "name": "Proposta",
                "cells": [
                    {"ref": "A1", "value": "CNPJ"},
                    {"ref": "A2", "value": "11.222.333/0001-81"},
                    {"ref": "B2", "formula": "Custos!B2*1.35"},
                ],
                "comments": [{"ref": "B2", "author": "Autora Sintetica", "text": "nota interna"}],
            },
            {"name": "Custos", "state": "hidden", "cells": [{"ref": "B2", "value": 10}]},
        ],
    )

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    main([str(path), "--fail-on", "info"])
    plain = capsys.readouterr().out
    assert "\033[" not in plain
    report = plain.split("Próximos passos:", 1)[0]
    assert report.count("cores.xlsx") == 1
    assert "› fórmula oculta › alto" in plain
    assert "› comentário › médio" in plain

    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    main([str(path), "--fail-on", "info"])
    colored = capsys.readouterr().out
    assert "\033[31m" in colored
    assert "\033[33m" in colored
    assert "\033[36m" in colored

    main([str(path), "--no-color", "--fail-on", "info"])
    assert "\033[" not in capsys.readouterr().out

    monkeypatch.setenv("NO_COLOR", "1")
    main([str(path), "--fail-on", "info"])
    assert "\033[" not in capsys.readouterr().out
