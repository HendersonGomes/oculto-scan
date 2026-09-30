import tarja

from oculto_scan.analyze import analyze
from oculto_scan.workbook import load_workbook
from tests.workbook_factory import build_workbook, make_cpf, make_pis

CPF_A = make_cpf("529982247")
CPF_B = make_cpf("390533447")
CPF_C = make_cpf("111444777")
PIS = make_pis("1205643787")
CNPJ = "11.222.333/0001-81"
CNPJ_ALPHA = "12.ABC.345/01DE-35"


def test_generators_match_tarja():
    assert tarja.validate("BR_CPF", CPF_A)
    assert tarja.validate("BR_CPF", CPF_B)
    assert tarja.validate("BR_NIS", PIS)
    assert tarja.validate("BR_CNPJ", CNPJ)
    assert tarja.validate("BR_CNPJ", CNPJ_ALPHA)


def _scan(tmp_path, name, sheets, **kwargs):
    path = tmp_path / name
    build_workbook(path, sheets, **kwargs)
    return analyze(load_workbook(path), name)


def test_cpf_needs_context_and_a_list_is_high(tmp_path):
    isolated = _scan(
        tmp_path,
        "qtd.xlsx",
        [
            {
                "name": "Orcamento",
                "cells": [
                    {"ref": "A1", "value": "Item"},
                    {"ref": "B1", "value": "Quantidade"},
                    {"ref": "B2", "value": CPF_A},
                ],
            }
        ],
    )
    assert not any(item.rule == "cpf" for item in isolated)

    invalid = CPF_A[:-1] + ("0" if CPF_A[-1] != "0" else "1")
    assert not tarja.validate("BR_CPF", invalid)
    bad_digit = _scan(
        tmp_path,
        "dv.xlsx",
        [
            {
                "name": "Medicao",
                "cells": [
                    {"ref": "A1", "value": "Funcionário"},
                    {"ref": "B1", "value": "CPF"},
                    {"ref": "B2", "value": invalid},
                ],
            }
        ],
    )
    assert not any(item.rule == "cpf" for item in bad_digit)

    one = _scan(
        tmp_path,
        "um.xlsx",
        [
            {
                "name": "Medicao",
                "cells": [
                    {"ref": "A1", "value": "Funcionário"},
                    {"ref": "B1", "value": "CPF"},
                    {"ref": "A2", "value": "Pessoa Sintetica"},
                    {"ref": "B2", "value": CPF_A},
                ],
            }
        ],
    )
    cpfs = [item for item in one if item.rule == "cpf"]
    assert len(cpfs) == 1
    assert cpfs[0].risk == "medio"
    assert cpfs[0].evidence_masked == "***.982.247-**"
    assert CPF_A not in cpfs[0].message

    many = _scan(
        tmp_path,
        "lista.xlsx",
        [
            {
                "name": "Medicao",
                "cells": [
                    {"ref": "A1", "value": "Empregado"},
                    {"ref": "B1", "value": "CPF"},
                    {"ref": "C1", "value": "Salário"},
                    {"ref": "A2", "value": "Pessoa Sintetica"},
                    {"ref": "B2", "value": CPF_A},
                    {"ref": "C2", "value": "3500"},
                    {"ref": "A3", "value": "Outra Pessoa Sintetica"},
                    {"ref": "B3", "value": CPF_B},
                    {"ref": "C3", "value": "2800"},
                    {"ref": "A4", "value": "Terceira Pessoa Sintetica"},
                    {"ref": "B4", "value": CPF_C},
                ],
            }
        ],
    )
    listed = [item for item in many if item.rule == "cpf"]
    assert len(listed) == 3
    assert all(item.risk == "alto" for item in listed)


def test_shared_strings_are_read(tmp_path):
    findings = _scan(
        tmp_path,
        "shared.xlsx",
        [
            {
                "name": "Medicao",
                "cells": [
                    {"ref": "A1", "value": "CPF"},
                    {"ref": "A2", "value": CPF_A},
                ],
            }
        ],
        use_shared_strings=True,
    )
    assert any(item.rule == "cpf" and item.evidence_raw == CPF_A for item in findings)


def test_cnpj_is_info_including_alphanumeric(tmp_path):
    findings = _scan(
        tmp_path,
        "cnpj.xlsx",
        [
            {
                "name": "Proposta",
                "cells": [
                    {"ref": "A1", "value": "Contratada"},
                    {"ref": "B1", "value": CNPJ},
                    {"ref": "B2", "value": CNPJ_ALPHA},
                ],
            }
        ],
    )
    cnpjs = [item for item in findings if item.rule == "cnpj"]
    assert len(cnpjs) == 2
    assert all(item.risk == "info" for item in cnpjs)
    assert any(item.evidence_masked == "**.ABC.345/01DE-**" for item in cnpjs)
    assert CNPJ_ALPHA not in "".join(item.message for item in cnpjs)


def test_pis_and_bank_context(tmp_path):
    findings = _scan(
        tmp_path,
        "folha.xlsx",
        [
            {
                "name": "Folha",
                "cells": [
                    {"ref": "A1", "value": "Empregado"},
                    {"ref": "B1", "value": "PIS"},
                    {"ref": "C1", "value": "Banco"},
                    {"ref": "D1", "value": "Agência"},
                    {"ref": "E1", "value": "Conta"},
                    {"ref": "A2", "value": "Pessoa Sintetica"},
                    {"ref": "B2", "value": PIS},
                    {"ref": "C2", "value": "001"},
                    {"ref": "D2", "value": "1234"},
                    {"ref": "E2", "value": "567890-1"},
                ],
            }
        ],
    )
    assert any(item.rule == "pis" and item.risk == "medio" for item in findings)
    banks = [item for item in findings if item.rule == "conta-bancaria"]
    kinds = {item.evidence_raw for item in banks}
    assert "1234" in kinds
    assert "567890-1" in kinds
    assert "001" in kinds
    assert any(item.risk == "alto" and item.evidence_raw == "567890-1" for item in banks)
    assert all("567890-1" not in (item.evidence_masked or "") for item in banks)
    # A bare account number with no label is not a finding.
    bare = _scan(
        tmp_path,
        "numeros.xlsx",
        [{"name": "Orcamento", "cells": [{"ref": "A1", "value": "Valor"}, {"ref": "A2", "value": "567890-1"}]}],
    )
    assert not any(item.rule == "conta-bancaria" for item in bare)
