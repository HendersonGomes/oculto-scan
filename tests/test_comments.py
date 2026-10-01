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
                        "author": "Engenheira Sintetica",
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
    assert "nota antiga" in note.message
    assert "Engenheira Sintetica" not in note.message


def test_portuguese_excel_placeholder_collapses_with_the_thread(tmp_path):
    """pt-BR Excel writes ``[Comentário encadeado]`` and author ``tc={GUID}``."""
    path = tmp_path / "encadeado.xlsx"
    placeholder = (
        "[Comentário encadeado]\n\n"
        "Sua versão do Excel permite ler este comentário encadeado; porém, qualquer edição "
        "será removida se o arquivo for aberto numa versão mais recente do Excel."
    )
    build_workbook(
        path,
        [
            {
                "name": "Proposta",
                "cells": [{"ref": "C2", "value": "preço"}],
                "comments": [{"ref": "C2", "author": _TC_AUTHOR, "text": placeholder}],
                "threads": [{"ref": "C2", "text": "margem 35% não mostrar"}],
            }
        ],
    )
    findings = analyze(load_workbook(path), "encadeado.xlsx")
    assert _rules_on(findings, "C2") == ["comentario-thread"]
    thread = next(item for item in findings if item.rule == "comentario-thread")
    assert thread.evidence_raw == "margem 35% não mostrar"
    blob = "\n".join(item.message + (item.evidence_raw or "") for item in findings)
    assert "tc=" not in blob
    assert "tc***" not in blob
    assert "Comentário encadeado" not in blob
    assert "Autor:" not in thread.message


def test_localized_prefixes_collapse_even_without_tc_author(tmp_path):
    path = tmp_path / "prefixos.xlsx"
    comments = []
    threads = []
    for index, prefix in enumerate(
        ("[Comentário em thread]", "[Threaded comment]", "[Comentario encadenado]"),
        start=2,
    ):
        ref = f"C{index}"
        comments.append(
            {
                "ref": ref,
                "author": "Revisor Sintetico",
                "text": prefix + "\n\nTexto de compatibilidade do Excel.",
            }
        )
        threads.append({"ref": ref, "text": f"nota {index}"})
    build_workbook(
        path,
        [{"name": "Proposta", "cells": [{"ref": "A1", "value": "Item"}], "comments": comments, "threads": threads}],
    )
    findings = analyze(load_workbook(path), "prefixos.xlsx")
    assert not any(item.rule == "comentario" for item in findings)
    assert sum(item.rule == "comentario-thread" for item in findings) == 3


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
