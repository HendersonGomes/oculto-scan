"""UNC path segments are not Windows domain users. Fixtures are synthetic."""

from oculto_scan.analyze import analyze
from oculto_scan.workbook import load_workbook
from tests.workbook_factory import build_workbook

_HYPHEN = r"\\SERVIDOR-OBRAS\propostas"
_SHORT = r"\\srv-01\propostas"
_DOTTED = r"\\servidor.empresa.local\propostas"
_SCORE = r"\\SERVIDOR_OBRAS\propostas"
_LOCAL = r"C:\Users\joao"
_REAL = r"CONSTRUTORA\joao.silva"
_BESIDE = rf"ver {_HYPHEN} e {_REAL}"


def test_unc_segments_are_not_domain_users(tmp_path):
    path = tmp_path / "rede.xlsx"
    build_workbook(
        path,
        [
            {
                "name": "Proposta",
                "cells": [
                    {"ref": "A1", "value": _HYPHEN},
                    {"ref": "A2", "value": _SHORT},
                    {"ref": "A3", "value": _DOTTED},
                    {"ref": "A4", "value": _SCORE},
                    {"ref": "A5", "value": _LOCAL},
                    {"ref": "A6", "value": _REAL},
                    {"ref": "A7", "value": _BESIDE},
                ],
            }
        ],
    )
    workbook = load_workbook(path)
    analyze(workbook, path.name)
    by_kind: dict[str, set[str]] = {}
    for hint in workbook.network_hints:
        by_kind.setdefault(hint.kind, set()).add(hint.evidence_raw)

    users = by_kind["usuario"]
    assert _HYPHEN in by_kind["unc"]
    assert _SHORT in by_kind["unc"]
    assert _DOTTED in by_kind["unc"]
    assert _SCORE in by_kind["unc"]
    assert "SERVIDOR-OBRAS" in by_kind["maquina"]
    assert "srv-01" in by_kind["maquina"]
    assert "servidor.empresa.local" in by_kind["maquina"]
    assert "SERVIDOR_OBRAS" in by_kind["maquina"]
    assert _LOCAL in by_kind["caminho"]
    assert r"OBRAS\propostas" not in users
    assert r"01\propostas" not in users
    assert r"local\propostas" not in users
    assert r"Users\joao" not in users
    assert "joao" in users
    assert _REAL in users
    assert users == {"joao", _REAL}
