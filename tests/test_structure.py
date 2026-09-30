from oculto_scan.analyze import analyze
from oculto_scan.workbook import load_workbook
from tests.workbook_factory import build_workbook


def test_hidden_and_very_hidden_sheets(tmp_path):
    path = tmp_path / "abas.xlsx"
    build_workbook(
        path,
        [
            {"name": "Proposta", "cells": [{"ref": "A1", "value": "Item"}]},
            {"name": "Custos", "state": "hidden", "cells": [{"ref": "A1", "value": 10}]},
            {"name": "Margem", "state": "veryHidden", "cells": [{"ref": "A1", "value": 1.35}]},
        ],
    )
    findings = analyze(load_workbook(path), "abas.xlsx")
    by_rule = {item.rule: item for item in findings}
    assert by_rule["aba-oculta"].sheet == "Custos"
    assert by_rule["aba-oculta"].risk == "alto"
    assert by_rule["aba-muito-oculta"].sheet == "Margem"
    assert by_rule["aba-muito-oculta"].risk == "alto"


def test_hidden_rows_columns_comments_and_metadata(tmp_path):
    path = tmp_path / "estrutura.xlsx"
    build_workbook(
        path,
        [
            {
                "name": "Proposta",
                "hidden_rows": [5, 6, 8],
                "hidden_cols": [4],
                "cells": [{"ref": "A1", "value": "Item"}, {"ref": "A5", "value": 3}],
                "comments": [
                    {
                        "ref": "A1",
                        "author": "Autora Sintetica",
                        "text": "não revelar a margem nesta célula",
                    }
                ],
                "threads": [{"ref": "B2", "text": "premissa interna do BDI"}],
            }
        ],
        defined_names=[
            {"name": "TaxaVisivel", "formula": "Proposta!$A$1"},
            {"name": "NomeEscondido", "formula": "Proposta!$A$1", "hidden": True},
        ],
        metadata={
            "creator": "Autora Sintetica",
            "lastModifiedBy": "Revisor Sintetico",
            "company": "Construtora Exemplo Ltda",
            "title": "Proposta sintetica",
        },
        external_target="file:///C:/Users/ana.sintetica/Documentos/custos.xlsx",
        hyperlink={"sheet": "Proposta", "target": r"C:\Users\ana.sintetica\notas\laudo.pdf"},
    )
    findings = analyze(load_workbook(path), "estrutura.xlsx")
    rules = {item.rule for item in findings}
    assert "linha-oculta" in rules
    assert "coluna-oculta" in rules
    assert "comentario" in rules
    assert "comentario-thread" in rules
    assert "nome-definido" in rules
    assert "vinculo-externo" in rules
    assert "metadado" in rules
    row_finding = next(item for item in findings if item.rule == "linha-oculta" and item.cell == "5:6")
    assert row_finding.risk == "medio"
    assert any(item.rule == "linha-oculta" and item.cell == "8" for item in findings)
    external = [item for item in findings if item.rule == "vinculo-externo"]
    assert len(external) == 2
    assert all("ana.sintetica" not in (item.evidence_masked or "") for item in external)
    assert all(item.risk == "alto" for item in external)
    thread = next(item for item in findings if item.rule == "comentario-thread")
    assert "00000000" not in thread.message
    assert "{" not in thread.message
    comment = next(item for item in findings if item.rule == "comentario")
    assert "não revelar" not in comment.message
    assert "Autora Sintetica" not in comment.message
    assert comment.evidence_raw == "não revelar a margem nesta célula"
    meta = next(item for item in findings if item.cell == "creator")
    assert meta.risk == "medio"
    assert "Autora Sintetica" not in (meta.evidence_masked or "")
    title = next(item for item in findings if item.cell == "title")
    assert title.risk == "info"


def test_macro_presence_does_not_read_payload(tmp_path):
    path = tmp_path / "com-macro.xlsm"
    secret = b"AKIAIOSFODNN7EXAMPLE-dentro-da-macro"
    build_workbook(
        path,
        [{"name": "Proposta", "cells": [{"ref": "A1", "value": "sem segredo aqui"}]}],
        vba_blob=secret,
    )
    findings = analyze(load_workbook(path), "com-macro.xlsm")
    macros = [item for item in findings if item.rule == "macro"]
    assert len(macros) == 1
    assert macros[0].risk == "medio"
    blob = secret.decode()
    assert all(blob not in (item.evidence_raw or "") for item in findings)
    assert all(blob not in item.message for item in findings)
    assert not any(item.rule == "segredo" for item in findings)
