"""v0.2.5: report dates, Brazilian numbers, and clearer diff wording."""

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from oculto_scan.analyze import analyze
from oculto_scan.cli import main
from oculto_scan.diff import load_diff, render_diff_html, render_diff_text
from oculto_scan.gui_logic import Session, result_text, window_cards
from oculto_scan.report import format_pt_number, format_stored_datetime, render_html, render_text
from oculto_scan.workbook import load_workbook
from tests.workbook_factory import build_workbook

_ROOT = Path(__file__).resolve().parents[1]


def test_stamp_uses_a_short_local_zone():
    when = datetime(2026, 9, 30, 21, 55, tzinfo=timezone(timedelta(hours=-3)))
    page = render_html([], ignored=0, scanned=0, files=[], generated_at=when)
    assert "30/09/2026 21:55 (horário local, UTC-3)" in page
    half = datetime(2026, 9, 30, 21, 55, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    page = render_html([], ignored=0, scanned=0, files=[], generated_at=half)
    assert "30/09/2026 21:55 (horário local, UTC+5:30)" in page


def test_numbers_keep_only_the_decimals_they_already_have():
    assert format_pt_number("48.5") == "48,5"
    assert format_pt_number("9.15") == "9,15"
    assert format_pt_number("7.8") == "7,8"
    assert format_pt_number("7.80") == "7,8"
    assert format_pt_number("5000") == "5.000"
    assert format_pt_number("42") == "42"
    assert format_pt_number("-1200.5") == "-1.200,5"
    assert format_pt_number("E4*F4") is None


def test_stored_dates_follow_the_computer_zone(monkeypatch):
    monkeypatch.setenv("TZ", "America/Fortaleza")
    time.tzset()
    assert format_stored_datetime("2026-10-03T17:35:13Z") == "03/10/2026 14:35"
    assert format_stored_datetime("2026-03-18T09:15:00Z") == "18/03/2026 06:15"


def test_formula_replaced_by_a_fixed_number_is_one_row(tmp_path, monkeypatch):
    monkeypatch.setenv("TZ", "America/Fortaleza")
    time.tzset()
    original = tmp_path / "enviada.xlsx"
    received = tmp_path / "devolvida.xlsx"
    build_workbook(
        original,
        [
            {
                "name": "Medição",
                "cells": [
                    {"ref": "C4", "value": "Forma de compensado"},
                    {"ref": "E4", "value": 86},
                    {"ref": "F4", "value": 68.4},
                    {"ref": "G4", "formula": "E4*F4", "value": 5882.4},
                ],
            }
        ],
        metadata={"modified": "2026-03-12T18:40:00Z", "lastModifiedBy": "Engenheira Ana Exemplo"},
    )
    build_workbook(
        received,
        [
            {
                "name": "Medição",
                "cells": [
                    {"ref": "C4", "value": "Forma de compensado"},
                    {"ref": "E4", "value": 86},
                    {"ref": "F4", "value": 68.4},
                    {"ref": "G4", "value": 5000},
                    {"ref": "C9", "value": "Lastro de concreto magro"},
                ],
                "hidden_rows": [9],
                "comments": [
                    {"ref": "E3", "author": "Fiscal João Exemplo", "text": "Quantidade reduzida."}
                ],
            },
        ],
        metadata={"modified": "2026-03-18T09:15:00Z", "lastModifiedBy": "Fiscal João Exemplo"},
    )
    report = load_diff(original, received)
    fixed = [item for item in report.changes if item.cell == "G4"]
    assert [item.type_label for item in fixed] == ["fórmula virou valor fixo"]
    assert fixed[0].category == "conteudo"
    assert fixed[0].before_raw == "E4*F4"
    assert fixed[0].after_raw == "5000"
    assert "número fixo" in fixed[0].message
    assert "Em medição" in fixed[0].message
    note = next(item for item in report.changes if item.type_label == "comentário novo")
    assert note.message == "Há uma nota nova nesta célula."
    hidden = next(item for item in report.changes if item.type_label == "linha ocultada")
    assert hidden.cell == "9"
    assert hidden.after_raw == "Lastro de concreto magro"
    saved = next(item for item in report.changes if item.cell == "lastModifiedBy")
    assert saved.message.startswith("Quem salvou por último mudou.")
    modified = next(item for item in report.changes if item.cell == "modified")
    assert modified.before_raw == "2026-03-12T18:40:00Z"
    assert modified.after_raw == "2026-03-18T09:15:00Z"

    page = render_diff_html(report, show=True)
    assert "E4*F4" in page
    assert "5.000" in page
    assert "48,5" not in page
    assert "Linha 9 · Lastro de concreto magro" in page
    assert "Há uma nota nova nesta célula." in page
    assert "Quem salvou por último mudou." in page
    assert "12/03/2026 15:40" in page
    assert "18/03/2026 06:15" in page
    assert "2026-03-18T09:15:00Z" not in page

    masked = render_diff_html(report, show=False)
    assert "Lastro de concreto magro" not in masked
    assert "Linha 9 ·" in masked
    assert "5.000" not in masked

    text = render_diff_text(report, show=True, color=False)
    assert "fórmula virou valor fixo" in text
    assert "E4*F4" in text
    assert "5.000" in text
    assert "Linha 9 · Lastro de concreto magro" in text
    assert "12/03/2026 15:40" in text
    assert "18/03/2026 06:15" in text
    quiet = render_diff_text(report, show=False, color=False)
    assert "Lastro de concreto magro" not in quiet
    assert "5.000" not in quiet

    session = Session(mode="diff", diff=report)
    cards = window_cards(session, show=True)
    fixed_card = next(card for card in cards if card.title == "Fórmula virou valor fixo")
    assert fixed_card.severity == "alto"
    assert "E4*F4" in fixed_card.action
    assert "5.000" in fixed_card.action
    assert any("Linha 9 · Lastro de concreto magro" in card.where for card in cards)
    hidden_cards = window_cards(session, show=False)
    assert any("Linha 9 ·" in card.where for card in hidden_cards)
    assert all("Lastro de concreto magro" not in card.where for card in hidden_cards)
    window = result_text(session, show=True)
    assert "5.000" in window
    assert "18/03/2026 06:15" in window

    findings = analyze(load_workbook(received), "devolvida.xlsx")
    hidden_row = next(item for item in findings if item.rule == "linha-oculta")
    assert hidden_row.cell == "9"
    assert hidden_row.evidence_raw == "Linha 9 · Lastro de concreto magro"
    scan = render_text(findings, show=True, ignored=0, scanned=1, color=False)
    assert "Linha 9 · Lastro de concreto magro" in scan
    scan_masked = render_text(findings, show=False, ignored=0, scanned=1, color=False)
    assert "Lastro de concreto magro" not in scan_masked
    scan_page = render_html(findings, ignored=0, scanned=1, files=["devolvida.xlsx"], show=True)
    assert "Linha 9 · Lastro de concreto magro" in scan_page
    scan_hidden = render_html(findings, ignored=0, scanned=1, files=["devolvida.xlsx"], show=False)
    assert "Lastro de concreto magro" not in scan_hidden
    scan_cards = window_cards(Session(mode="scan", findings=findings), show=True)
    assert any("Linha 9 · Lastro de concreto magro" in card.where for card in scan_cards)


def test_json_keeps_iso_dates_and_skips_brazilian_numbers(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("TZ", "America/Fortaleza")
    time.tzset()
    original = tmp_path / "original.xlsx"
    received = tmp_path / "recebido.xlsx"
    build_workbook(
        original,
        [{"name": "Medição", "cells": [{"ref": "G4", "formula": "E4*F4", "value": 5882.4}]}],
        metadata={"modified": "2026-03-12T18:40:00Z"},
    )
    build_workbook(
        received,
        [{"name": "Medição", "cells": [{"ref": "G4", "value": 5000}, {"ref": "E3", "value": 48.5}]}],
        metadata={"modified": "2026-03-18T09:15:00Z"},
    )
    code = main(["diff", str(original), str(received), "--show", "--format", "json"])
    raw = capsys.readouterr().out
    assert code == 1
    assert "5.000" not in raw
    assert "48,5" not in raw
    assert "48.5" not in raw
    assert "5000" not in raw
    assert "18/03/2026" not in raw
    assert "2026-03-18T09:15:00Z" in raw
    assert "2026-03-12T18:40:00Z" in raw


def test_example_measurement_modified_dates_differ():
    sent = _ROOT / "examples" / "medicao" / "medicao-03-enviada.xlsx"
    back = _ROOT / "examples" / "medicao" / "medicao-03-devolvida.xlsx"
    report = load_diff(sent, back)
    modified = next(row for row in report.metadata if row.key == "modified")
    assert modified.changed
    assert modified.before_raw != modified.after_raw
    hidden = next(item for item in report.changes if item.type_label == "linha ocultada")
    assert "Lastro de concreto magro" in hidden.after_raw
    fixed = [item for item in report.changes if item.type_label == "fórmula virou valor fixo"]
    assert len(fixed) == 1
    assert fixed[0].before_raw == "E4*F4"
    assert fixed[0].after_raw == "5000"
