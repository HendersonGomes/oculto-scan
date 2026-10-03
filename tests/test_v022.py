"""v0.2.2: a heavy workbook must finish, stay under a memory bound, and keep the window alive."""

from __future__ import annotations

import os
import sys
import threading
import time
import tracemalloc

import pytest

from oculto_scan.analyze import analyze, scan_path
from oculto_scan.gui_logic import WINDOW_CARD_LIMIT, Session, cards_for_window, scan_file
from oculto_scan.models import Finding
from oculto_scan.workbook import load_workbook
from tests.workbook_factory import build_workbook, make_cpf

CPF = make_cpf("529982247")


def _fingerprint(finding: Finding) -> tuple:
    return (
        finding.rule,
        finding.sheet,
        finding.cell,
        finding.risk,
        finding.type_label,
        finding.evidence_raw,
        finding.evidence_masked,
        finding.message,
    )


def test_streamed_scan_matches_a_full_load(tmp_path):
    path = tmp_path / "proposta.xlsx"
    build_workbook(
        path,
        [
            {
                "name": "Proposta",
                "cells": [
                    {"ref": "A1", "value": "CPF"},
                    {"ref": "A2", "value": CPF},
                    {"ref": "B2", "formula": "Custos!B2*1.35", "value": 1350},
                    {"ref": "C1", "value": "Conta"},
                    {"ref": "C2", "value": "12345-6"},
                ],
                "comments": [{"ref": "B2", "author": "Ana Sintetica", "text": "conferir margem"}],
            },
            {"name": "Custos", "state": "hidden", "cells": [{"ref": "B2", "value": 1000}]},
        ],
        metadata={"creator": "Autora Sintetica", "company": "Construtora Exemplo"},
        use_shared_strings=True,
    )
    full = analyze(load_workbook(path), path.name)
    streamed, _network = scan_path(path, path.name)
    assert [_fingerprint(item) for item in streamed] == [_fingerprint(item) for item in full]


def test_heavy_sheet_finishes_quickly_and_stays_small(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    path = tmp_path / "pesada.xlsx"
    workbook = openpyxl.Workbook(write_only=True)
    for name in ("Proposta", "Medicao"):
        sheet = workbook.create_sheet(name)
        sheet.append(["Item", "Qtd", "Custo", "Total", "Obs", "Ref"])
        for row in range(2, 1202):
            sheet.append([f"Servico {row}", row, 10, f"=B{row}*C{row}*1.35", "nota interna", f"R{row}"])
    workbook.save(path)

    messages: list[str] = []
    tracemalloc.start()
    started = time.perf_counter()
    findings, _network = scan_path(path, path.name, progress=messages.append)
    elapsed = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert elapsed < 15
    assert peak < 200 * 1024 * 1024
    assert findings
    assert any(message.startswith("Lendo aba ") and " de " in message for message in messages)
    assert any(item.rule == "formula-constante" for item in findings)


def test_cancel_stops_before_the_report(tmp_path):
    path = tmp_path / "uma.xlsx"
    build_workbook(path, [{"name": "Proposta", "cells": [{"ref": "A1", "value": "Item"}]}])
    session = scan_file(path, cancel=lambda: True)
    assert session.error == "Análise cancelada."
    assert not session.ready


def test_file_over_the_limit_names_max_mb(tmp_path):
    path = tmp_path / "uma.xlsx"
    build_workbook(path, [{"name": "Proposta", "cells": [{"ref": "A1", "value": "Item"}]}])
    session = scan_file(path, max_mb=0)
    assert "limite de análise" in session.error
    assert "Use --max-mb" in session.error
    assert session.error


def test_window_keeps_the_two_hundred_most_severe_cards():
    findings = [
        Finding(
            file="pesada.xlsx",
            sheet="Proposta",
            cell="A1",
            rule="aba-oculta",
            type_label="aba oculta",
            risk="alto",
            message="Aba oculta.",
        )
    ]
    findings.extend(
        Finding(
            file="pesada.xlsx",
            sheet="Proposta",
            cell=f"B{index}",
            rule="formula-constante",
            type_label="constante",
            risk="info",
            message="Fórmula com constante numérica.",
        )
        for index in range(2, 252)
    )
    session = Session(mode="scan", findings=findings, scanned=1, names=("pesada.xlsx",))
    cards, extra = cards_for_window(session, show=False)
    assert len(cards) == WINDOW_CARD_LIMIT
    assert extra == len(findings) - WINDOW_CARD_LIMIT
    assert cards[0].severity == "alto"
    assert sum(card.severity == "info" for card in cards) == WINDOW_CARD_LIMIT - 1


def test_window_shows_progress_and_keeps_processing_events(tmp_path, monkeypatch):
    if sys.platform != "win32" and not os.environ.get("DISPLAY"):
        pytest.skip("sem display")
    tk = pytest.importorskip("tkinter")
    try:
        probe = tk.Tk()
    except tk.TclError:
        pytest.skip("sem display")
    probe.destroy()

    import oculto_scan.gui_logic as logic
    from oculto_scan.gui_window import App

    path = tmp_path / "uma.xlsx"
    build_workbook(path, [{"name": "Proposta", "cells": [{"ref": "A1", "value": "Item"}]}])
    started = threading.Event()
    real = logic.scan_file

    def slow(target, **kwargs):
        progress = kwargs.get("progress")
        cancel = kwargs.get("cancel")
        started.set()
        for index in range(1, 4):
            if cancel is not None and cancel():
                return Session(error="Análise cancelada.")
            if progress is not None:
                progress(f"Lendo aba {index} de 3 (Proposta)")
            time.sleep(0.2)
        return real(target)

    monkeypatch.setattr(logic, "scan_file", slow)
    root = tk.Tk()
    try:
        app = App(root)
        app._left.set(str(path))
        app._run()
        assert started.wait(2)
        assert "disabled" not in app._cancel_btn.state()
        began = time.perf_counter()
        for _pump in range(6):
            root.update()
        assert time.perf_counter() - began < 0.25
        assert app._busy is True
        deadline = time.perf_counter() + 2
        while app._busy and "Lendo aba" not in app._status.get() and time.perf_counter() < deadline:
            root.update()
            time.sleep(0.02)
        assert "Lendo aba" in app._status.get()
        app._cancel()
        deadline = time.perf_counter() + 2
        while app._busy and time.perf_counter() < deadline:
            root.update()
            time.sleep(0.02)
        assert app._busy is False
        assert app.session.error == "Análise cancelada."
        notes = [child.cget("text") for child in app._card_frame.winfo_children() if hasattr(child, "cget")]
        assert any("Análise cancelada." in text for text in notes)
    finally:
        root.destroy()
