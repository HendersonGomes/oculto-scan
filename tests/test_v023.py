"""v0.2.3: the HTML report stays small, and saving it does not freeze the window."""

from __future__ import annotations

import os
import sys
import threading
import time

import pytest

from oculto_scan.models import Finding
from oculto_scan.report import HTML_CELL_EXAMPLES, HTML_ROWS_PER_TYPE, render_html, render_json

_MESSAGE = (
    "Fórmula com constante numérica. Pode revelar o método de margem "
    "ou BDI. É informativo: constante sozinha não prova vazamento."
)


def _constante(index: int, *, message: str = _MESSAGE, raw: str = "") -> Finding:
    return Finding(
        file="proposta.xlsx",
        sheet="Proposta",
        cell=f"{index:05d}",
        rule="formula-constante",
        type_label="constante",
        risk="info",
        message=message,
        evidence_masked=f"formula {index:05d}",
        evidence_raw=raw or f"SEGREDO-{index:05d}",
    )


def test_repeated_findings_collapse_to_one_row_with_twenty_examples():
    findings = [_constante(index) for index in range(1, 26)]
    page = render_html(findings, ignored=0, scanned=1, files=["proposta.xlsx"], show=False)
    assert "25" in page
    assert "e mais 5 células" in page
    assert "Proposta!00001" in page
    assert "Proposta!00020" in page
    assert "Proposta!00021" not in page
    assert page.count("Proposta!") == HTML_CELL_EXAMPLES
    assert "SEGREDO-" not in page
    assert "Valor mascarado" in page
    assert "--format json" in page

    revealed = render_html(findings[:1], ignored=0, scanned=1, files=["proposta.xlsx"], show=True)
    assert "SEGREDO-00001" in revealed
    assert "Valor revelado" in revealed


def test_hundred_thousand_findings_stay_under_two_megabytes():
    findings = [_constante(index) for index in range(1, 100_001)]
    started = time.perf_counter()
    page = render_html(findings, ignored=0, scanned=1, files=["proposta.xlsx"])
    elapsed = time.perf_counter() - started
    assert elapsed < 3
    assert len(page.encode("utf-8")) < 2 * 1024 * 1024
    assert "100.000" in page
    assert f"e mais {100_000 - HTML_CELL_EXAMPLES:,} células".replace(",", ".") in page
    assert "SEGREDO-" not in page
    assert "<script" not in page.lower()
    full = render_json(findings, ignored=0, scanned=1)
    assert full.count('"rule"') == 100_000


def test_each_type_keeps_at_most_five_hundred_detail_rows():
    findings = [_constante(index, message=f"explicação {index:04d}") for index in range(1, HTML_ROWS_PER_TYPE + 101)]
    page = render_html(findings, ignored=0, scanned=1, files=["proposta.xlsx"])
    assert "Mais 100 achados deste tipo ficaram de fora" in page
    assert "explicação 0001" in page
    assert f"explicação {HTML_ROWS_PER_TYPE + 100:04d}" not in page
    assert page.lower().count("<tr") <= HTML_ROWS_PER_TYPE + 3


def test_grouped_html_still_escapes_spreadsheet_text():
    hostile = "<script>alert(1)</script>"
    finding = Finding(
        file="a<b>.xlsx",
        sheet=hostile,
        cell="A1",
        rule="comentario",
        type_label=hostile,
        risk="medio",
        message=hostile,
        evidence_masked=hostile,
        evidence_raw=hostile,
    )
    page = render_html([finding], ignored=0, scanned=1, files=["a<b>.xlsx"])
    assert hostile not in page
    assert "<script" not in page.lower()
    assert page.lower().count("&lt;script&gt;") >= 3
    assert "a&lt;b&gt;.xlsx" in page


def test_window_keeps_processing_events_while_saving_the_report(tmp_path, monkeypatch):
    if sys.platform != "win32" and not os.environ.get("DISPLAY"):
        pytest.skip("sem display")
    tk = pytest.importorskip("tkinter")
    try:
        probe = tk.Tk()
    except tk.TclError:
        pytest.skip("sem display")
    probe.destroy()

    from oculto_scan.gui_logic import Session
    from oculto_scan.gui_window import App

    started = threading.Event()
    holder: dict[str, int] = {}

    def slow(session, *, show):
        holder["thread"] = threading.get_ident()
        started.set()
        time.sleep(0.4)
        return "<!DOCTYPE html><html><body>ok</body></html>"

    def opened(path):
        holder["open"] = threading.get_ident()
        time.sleep(0.2)

    monkeypatch.setattr("oculto_scan.gui_window.result_html", slow)
    monkeypatch.setattr("oculto_scan.gui_window.open_document", opened)
    dest = tmp_path / "relatorio.html"
    monkeypatch.setattr(
        "oculto_scan.gui_window.filedialog.asksaveasfilename",
        lambda **_kwargs: str(dest),
    )
    root = tk.Tk()
    try:
        app = App(root)
        app.session = Session(
            mode="scan",
            findings=[_constante(1)],
            scanned=1,
            names=("proposta.xlsx",),
        )
        app._save()
        assert started.wait(2)
        began = time.perf_counter()
        for _pump in range(6):
            root.update()
        assert time.perf_counter() - began < 0.25
        assert app._busy is True
        assert app._status.get() == "Gerando relatório..."
        assert "disabled" in app._save_btn.state()
        assert "disabled" in app._open_btn.state()
        assert "disabled" in app._cancel_btn.state()
        assert holder["thread"] != threading.get_ident()
        deadline = time.perf_counter() + 3
        while app._busy and time.perf_counter() < deadline:
            root.update()
            time.sleep(0.02)
        assert app._busy is False
        assert dest.is_file()
        assert "Relatório salvo" in app._status.get()
        assert "disabled" not in app._save_btn.state()

        app._open()
        deadline = time.perf_counter() + 3
        while app._busy and time.perf_counter() < deadline:
            root.update()
            time.sleep(0.02)
        assert holder["open"] != threading.get_ident()
        assert app._busy is False
    finally:
        root.destroy()
