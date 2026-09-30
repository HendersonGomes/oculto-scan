import json

from oculto_scan.cli import main
from oculto_scan.report import DISCLAIMER
from tests.workbook_factory import build_workbook, make_cpf

CPF = make_cpf("529982247")


def _proposta(path):
    build_workbook(
        path,
        [
            {
                "name": "Proposta",
                "cells": [
                    {"ref": "A1", "value": "Item"},
                    {"ref": "B1", "value": "Preço"},
                    {"ref": "B2", "formula": "Custos!B2*1.35", "value": 135},
                ],
                "comments": [
                    {"ref": "B2", "author": "Autora Sintetica", "text": "conferir BDI antes de enviar"}
                ],
            },
            {"name": "Custos", "state": "hidden", "cells": [{"ref": "B2", "value": 100}]},
        ],
        metadata={"creator": "Autora Sintetica", "company": "Construtora Exemplo Ltda"},
        external_target="file:///C:/Users/ana.sintetica/Documentos/custos.xlsx",
    )


def test_text_report_is_masked_and_fails_on_alto(tmp_path, capsys):
    path = tmp_path / "proposta.xlsx"
    _proposta(path)
    code = main([str(path)])
    captured = capsys.readouterr()
    assert code == 1
    assert "› fórmula oculta › alto" in captured.out
    assert "› aba oculta › alto" in captured.out
    assert DISCLAIMER in captured.out
    assert "1.35" not in captured.out
    assert "ana.sintetica" not in captured.out
    assert "Autora Sintetica" not in captured.out
    assert "conferir BDI" not in captured.out


def test_show_reveals_terminal_but_not_json(tmp_path, capsys):
    path = tmp_path / "pessoa.xlsx"
    build_workbook(
        path,
        [
            {
                "name": "Medicao",
                "cells": [
                    {"ref": "A1", "value": "CPF"},
                    {"ref": "A2", "value": CPF},
                ],
            }
        ],
    )
    code = main([str(path), "--show", "--fail-on", "info"])
    text = capsys.readouterr().out
    assert code == 1
    assert CPF in text

    code = main([str(path), "--show", "--format", "json", "--fail-on", "info"])
    raw = capsys.readouterr().out
    payload = json.loads(raw)
    assert code == 1
    assert payload["disclaimer"] == DISCLAIMER
    blob = json.dumps(payload)
    assert CPF not in blob
    assert "***.982.247-**" in blob
    assert any(item["rule"] == "cpf" for item in payload["findings"])


def test_exit_codes_follow_fail_on(tmp_path, capsys):
    path = tmp_path / "cnpj.xlsx"
    build_workbook(
        path,
        [{"name": "Proposta", "cells": [{"ref": "A1", "value": "11.222.333/0001-81"}]}],
    )
    assert main([str(path)]) == 0
    capsys.readouterr()
    assert main([str(path), "--fail-on", "info"]) == 1
    capsys.readouterr()
    assert main([str(path), "--fail-on", "nenhum"]) == 0
    capsys.readouterr()

    hidden = tmp_path / "oculta.xlsx"
    build_workbook(
        hidden,
        [
            {"name": "Proposta", "cells": [{"ref": "A1", "value": "ok"}]},
            {"name": "Custos", "state": "hidden"},
        ],
    )
    assert main([str(hidden), "--fail-on", "alto"]) == 1
    capsys.readouterr()
    assert main([str(hidden), "--fail-on", "nenhum"]) == 0


def test_recursive_directory_skips_temp_and_other_suffixes(tmp_path, capsys):
    nested = tmp_path / "licitacao" / "envio"
    nested.mkdir(parents=True)
    build_workbook(
        nested / "proposta.xlsx",
        [
            {"name": "Proposta", "cells": [{"ref": "A1", "value": "Item"}]},
            {"name": "Custos", "state": "hidden"},
        ],
    )
    (nested / "leia-me.txt").write_text("não é planilha", encoding="utf-8")
    (nested / "antigo.xls").write_bytes(b"nao e zip")
    (nested / "~$proposta.xlsx").write_bytes(b"lock")
    code = main([str(tmp_path / "licitacao")])
    out = capsys.readouterr().out
    assert code == 1
    assert "proposta.xlsx" in out
    assert "antigo.xls" not in out
    assert "~$proposta.xlsx" not in out


def test_missing_path_exits_2(tmp_path, capsys):
    missing = tmp_path / "nao-existe.xlsx"
    code = main([str(missing)])
    captured = capsys.readouterr()
    assert code == 2
    assert "não encontrado" in captured.err
