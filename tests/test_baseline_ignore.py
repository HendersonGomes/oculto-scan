import json

from tests.workbook_factory import build_workbook, make_cpf

from oculto_scan.cli import main

CPF = make_cpf("529982247")


def _hidden(path):
    build_workbook(
        path,
        [
            {
                "name": "Medicao",
                "cells": [
                    {"ref": "A1", "value": "CPF"},
                    {"ref": "A2", "value": CPF},
                    {"ref": "B2", "formula": "A1*1.35", "value": 1},
                ],
            },
            {"name": "Custos", "state": "hidden", "cells": [{"ref": "A1", "value": 10}]},
        ],
    )


def test_baseline_stores_hmac_not_values(tmp_path, capsys):
    path = tmp_path / "medicao.xlsx"
    _hidden(path)
    baseline = tmp_path / "base.json"
    code = main([str(path), "--update-baseline", str(baseline)])
    err = capsys.readouterr().err
    assert code == 0
    assert "atualizada" in err
    raw = baseline.read_text(encoding="utf-8")
    assert CPF not in raw
    assert "1.35" not in raw
    assert "Custos" not in raw
    payload = json.loads(raw)
    assert payload["version"] == 1
    assert len(payload["salt"]) >= 32
    assert payload["entries"]

    code = main([str(path), "--baseline", str(baseline)])
    out = capsys.readouterr().out
    assert code == 0
    assert "aba oculta" not in out
    assert "ignorado" in out


def test_ignore_file_by_rule_and_cell(tmp_path, capsys):
    path = tmp_path / "medicao.xlsx"
    _hidden(path)
    ignore = tmp_path / "ignorar.txt"
    ignore.write_text(
        "# sintético\nrule:aba-oculta\nrule:formula-constante\ncell:Medicao!A2\n",
        encoding="utf-8",
    )
    code = main([str(path), "--ignore", str(ignore), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    rules = {item["rule"] for item in payload["findings"]}
    assert code == 0
    assert "aba-oculta" not in rules
    assert "formula-constante" not in rules
    assert "cpf" not in rules
    assert payload["summary"]["ignorados"] >= 3
