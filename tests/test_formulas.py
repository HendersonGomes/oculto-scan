from oculto_scan.formulas import parse_formula
from oculto_scan.workbook import load_workbook
from tests.workbook_factory import build_workbook


def test_parse_hidden_sheet_constant_and_external():
    info = parse_formula("Custos!B2*1.35")
    assert ("Custos", "B2") in info.sheet_refs
    assert "1.35" in info.constants

    trivial = parse_formula("A1*1+0")
    assert trivial.constants == []

    external = parse_formula(r"'C:\Users\ana\[precos.xlsx]Custos'!A1")
    assert external.external
    assert external.sheet_refs == []

    named = parse_formula("CustoUnitario*1.1", {"CustoUnitario"})
    assert "CustoUnitario" in named.names
    assert "1.1" in named.constants


def test_shared_formula_is_shifted_and_visible_cell_alerts(tmp_path):
    path = tmp_path / "formulas.xlsx"
    build_workbook(
        path,
        [
            {
                "name": "Proposta",
                "cells": [
                    {"ref": "A1", "value": "Item"},
                    {"ref": "B2", "formula": "A2*1.35", "value": 1, "shared": "0", "shared_ref": "B2:B3"},
                    {"ref": "B3", "shared": "0", "value": 2},
                    {"ref": "C2", "formula": "Custos!B2"},
                    {"ref": "A5", "value": 10},
                    {"ref": "D2", "formula": "A5*2"},
                ],
                "hidden_rows": [5],
            },
            {
                "name": "Custos",
                "state": "hidden",
                "cells": [{"ref": "B2", "value": 80}],
            },
            {
                "name": "Margem",
                "state": "hidden",
                "cells": [{"ref": "A1", "formula": "Custos!B2*9"}],
            },
        ],
    )
    workbook = load_workbook(path)
    proposta = workbook.sheet_by_name("Proposta")
    assert proposta is not None
    formulas = {cell.ref: cell.formula for cell in proposta.cells}
    assert formulas["B2"] == "A2*1.35"
    assert formulas["B3"] == "A3*1.35"

    from oculto_scan.analyze import analyze

    findings = analyze(workbook, "formulas.xlsx")
    hidden_refs = [item for item in findings if item.rule == "formula-referencia-oculta"]
    cells = {item.cell for item in hidden_refs}
    assert "C2" in cells
    assert "D2" in cells
    # The formula that lives on the hidden sheet is not the visible-cell rule.
    assert all(item.sheet != "Margem" for item in hidden_refs)
    constants = [item for item in findings if item.rule == "formula-constante"]
    assert any(item.cell == "D2" for item in constants)
    assert all(item.risk == "info" for item in constants)


def test_external_formula_on_visible_cell(tmp_path):
    path = tmp_path / "externa.xlsx"
    build_workbook(
        path,
        [
            {
                "name": "Proposta",
                "cells": [
                    {
                        "ref": "B2",
                        "formula": r"'C:\Users\ana.sintetica\[base.xlsx]Custos'!A1",
                    }
                ],
            }
        ],
    )
    from oculto_scan.analyze import analyze

    findings = analyze(load_workbook(path), "externa.xlsx")
    hits = [item for item in findings if item.rule == "formula-vinculo-externo"]
    assert len(hits) == 1
    assert hits[0].risk == "alto"
    assert "ana.sintetica" not in (hits[0].evidence_masked or "")
    assert "ana.sintetica" not in hits[0].message


def test_defined_name_used_by_visible_cell(tmp_path):
    path = tmp_path / "nomes.xlsx"
    build_workbook(
        path,
        [
            {
                "name": "Proposta",
                "cells": [{"ref": "B2", "formula": "CustoUnitario*1.1", "value": 1}],
            },
            {"name": "Custos", "state": "hidden", "cells": [{"ref": "B2", "value": 50}]},
        ],
        defined_names=[{"name": "CustoUnitario", "formula": "Custos!$B$2"}],
    )
    from oculto_scan.analyze import analyze

    workbook = load_workbook(path)
    findings = analyze(workbook, "nomes.xlsx")
    assert any(item.rule == "nome-definido-oculto" for item in findings)
    assert any(item.rule == "formula-referencia-oculta" and item.cell == "B2" for item in findings)
