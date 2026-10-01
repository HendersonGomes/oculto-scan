"""Threaded-comment compatibility notes must not duplicate the real thread."""

from oculto_scan.analyze import analyze
from oculto_scan.workbook import load_workbook
from tests.workbook_factory import build_workbook

_PLACEHOLDER = (
    "[Threaded comment]\n\n"
    "Your version of Excel allows you to read this threaded comment; however, any edits to it "
    "will get removed if the file is opened in a newer version of Excel. "
    "Learn more: https://go.microsoft.com/fwlink/?linkid=870924"
)
_TC_AUTHOR = "tc={A1B2C3D4-E5F6-7890-ABCD-EF1234567890}"


def _rules_on(findings, ref: str) -> list[str]:
    return [item.rule for item in findings if item.cell.replace("$", "").upper() == ref.upper()]


def test_placeholder_and_thread_collapse_to_one_finding(tmp_path):
    path = tmp_path / "thread.xlsx"
    build_workbook(
        path,
        [
            {
                "name": "Proposta",
                "cells": [{"ref": "C2", "value": "preço"}],
                "comments": [
                    {"ref": "C2", "author": _TC_AUTHOR, "text": _PLACEHOLDER},
                    {
                        "ref": "D4",
                        "author": "Engenheira Sintetica",
                        "text": "nota legada de verdade sobre a margem",
                    },
                ],
                "threads": [{"ref": "C2", "text": "custo interno."}],
            }
        ],
    )
    findings = analyze(load_workbook(path), "thread.xlsx")
    assert _rules_on(findings, "C2") == ["comentario-thread"]
    thread = next(item for item in findings if item.rule == "comentario-thread")
    assert "comentário em thread" in thread.message
    assert "tc=" not in thread.message
    assert "tc***" not in thread.message
    assert _TC_AUTHOR not in thread.message
    assert "A1B2C3D4" not in thread.message
    legacy = next(item for item in findings if item.rule == "comentario")
    assert legacy.cell == "D4"
    assert "nota antiga" in legacy.message
    assert "Engenheira Sintetica" not in legacy.message


def test_real_legacy_note_next_to_a_thread_stays(tmp_path):
    path = tmp_path / "duas.xlsx"
    build_workbook(
        path,
        [
            {
                "name": "Proposta",
                "cells": [{"ref": "C2", "value": "preço"}],
                "comments": [
                    {
                        "ref": "C2",
                        "author": _TC_AUTHOR,
                        "text": "nota independente, não é o aviso do Excel",
                    }
                ],
                "threads": [{"ref": "C2", "text": "custo interno."}],
            }
        ],
    )
    findings = analyze(load_workbook(path), "duas.xlsx")
    assert _rules_on(findings, "C2") == ["comentario", "comentario-thread"]
    note = next(item for item in findings if item.rule == "comentario")
    assert "tc=" not in note.message
    assert "tc***" not in note.message
    assert "Autor:" not in note.message


def test_placeholder_without_a_thread_is_still_a_finding(tmp_path):
    path = tmp_path / "so-nota.xlsx"
    build_workbook(
        path,
        [
            {
                "name": "Proposta",
                "cells": [{"ref": "C2", "value": "preço"}],
                "comments": [{"ref": "C2", "author": _TC_AUTHOR, "text": _PLACEHOLDER}],
            }
        ],
    )
    findings = analyze(load_workbook(path), "so-nota.xlsx")
    notes = [item for item in findings if item.rule == "comentario"]
    assert len(notes) == 1
    assert "tc=" not in notes[0].message
    assert "tc***" not in notes[0].message
