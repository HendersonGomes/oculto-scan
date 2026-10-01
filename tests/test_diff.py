"""Synthetic before/after workbooks. No real personal data."""

import json
import sys

from oculto_scan.cli import main
from oculto_scan.diff import IDENTICAL, LIMITS, METADATA_ONLY, REVEALED_BANNER
from tests.workbook_factory import build_workbook

_PLACEHOLDER = (
    "[Threaded comment]\n\n"
    "Your version of Excel allows you to read this threaded comment; however, any edits to it "
    "will get removed if the file is opened in a newer version of Excel. "
    "Learn more: https://go.microsoft.com/fwlink/?linkid=870924"
)
_SCRIPT = "<script>alert(1)</script>"
_META = {
    "creator": "Autora Sintetica",
    "lastModifiedBy": "Autora Sintetica",
    "created": "2026-09-01T12:00:00Z",
    "modified": "2026-09-30T18:00:00Z",
    "lastPrinted": "2026-09-02T12:00:00Z",
    "revision": "4",
    "Application": "Microsoft Excel",
    "AppVersion": "16.0300",
    "Company": "Construtora Exemplo Ltda",
    "Manager": "Gerente Sintetico",
}


def _pair(tmp_path, name, sheets, **kwargs):
    path = tmp_path / name
    build_workbook(path, sheets, **kwargs)
    return path


def _base():
    return [
        {
            "name": "Proposta",
            "cells": [
                {"ref": "A1", "value": "Item"},
                {"ref": "C2", "formula": "Custos!B2*1.35", "value": 1350},
            ],
        },
        {"name": "Custos", "state": "hidden", "cells": [{"ref": "B2", "value": 1000}]},
    ]


def test_identical_bytes_say_the_file_was_not_saved_again(tmp_path, capsys):
    path = _pair(tmp_path, "original.xlsx", _base(), metadata=_META)
    copy = tmp_path / "copia.xlsx"
    copy.write_bytes(path.read_bytes())
    code = main(["diff", str(path), str(copy)])
    out = capsys.readouterr().out
    assert code == 0
    assert IDENTICAL in out
    assert LIMITS in out


def test_cell_formula_cache_created_and_deleted(tmp_path):
    from oculto_scan.diff import load_diff

    original = _pair(tmp_path, "original.xlsx", _base())
    received_sheets = [
        {
            "name": "Proposta",
            "cells": [
                {"ref": "A1", "value": "Item alterado"},
                {"ref": "C2", "formula": "Custos!B2*1.35", "value": 2000},
                {"ref": "D2", "formula": "Custos!B2*2", "value": 2000},
            ],
        },
        {"name": "Custos", "state": "hidden", "cells": [{"ref": "B2", "value": 1000}]},
    ]
    received = _pair(tmp_path, "recebido.xlsx", received_sheets)
    report = load_diff(original, received)
    assert report.exit_code == 1
    labels = {(item.cell, item.type_label) for item in report.changes}
    assert ("A1", "valor alterado") in labels
    assert ("C2", "valor em cache") in labels
    assert ("D2", "célula criada") in labels
    cache = next(item for item in report.changes if item.type_label == "valor em cache")
    assert "célula de origem" in cache.message
    assert "1.35" not in cache.before_masked
    assert "1.35" not in cache.after_masked


def test_deleted_cell_sheet_visibility_rows_and_rename(tmp_path):
    from oculto_scan.diff import load_diff

    original = _pair(
        tmp_path,
        "original.xlsx",
        [
            {
                "name": "Proposta",
                "hidden_rows": [5],
                "hidden_cols": [4],
                "cells": [{"ref": "A1", "value": "Item"}, {"ref": "B2", "value": "sai"}],
            },
            {"name": "Custos", "state": "hidden", "cells": [{"ref": "B2", "value": 1000}]},
        ],
    )
    received = _pair(
        tmp_path,
        "recebido.xlsx",
        [
            {
                "name": "Planilha",
                "hidden_cols": [4],
                "cells": [{"ref": "A1", "value": "Item"}],
            },
            {"name": "Custos", "state": "visible", "cells": [{"ref": "B2", "value": 1000}]},
            {"name": "Nova", "cells": [{"ref": "A1", "value": "extra"}]},
        ],
    )
    report = load_diff(original, received)
    labels = {item.type_label for item in report.changes}
    assert "aba renomeada" in labels
    assert "célula apagada" in labels
    assert "visibilidade da aba" in labels
    assert "linha reexibida" in labels
    assert "aba criada" in labels
    renamed = next(item for item in report.changes if item.type_label == "aba renomeada")
    assert renamed.before_raw == "Proposta"
    assert renamed.after_raw == "Planilha"


def test_sheet_becomes_very_hidden(tmp_path):
    from oculto_scan.diff import load_diff

    original = _pair(
        tmp_path,
        "original.xlsx",
        [{"name": "Custos", "state": "hidden", "cells": [{"ref": "B2", "value": 1000}]}],
    )
    received = _pair(
        tmp_path,
        "recebido.xlsx",
        [{"name": "Custos", "state": "veryHidden", "cells": [{"ref": "B2", "value": 1000}]}],
    )
    report = load_diff(original, received)
    change = next(item for item in report.changes if item.type_label == "visibilidade da aba")
    assert change.before_raw == "oculta"
    assert change.after_raw == "muito oculta"


def test_row_and_column_become_hidden(tmp_path):
    from oculto_scan.diff import load_diff

    original = _pair(tmp_path, "original.xlsx", [{"name": "Proposta", "cells": [{"ref": "A1", "value": "Item"}]}])
    received = _pair(
        tmp_path,
        "recebido.xlsx",
        [{"name": "Proposta", "hidden_rows": [8, 9], "hidden_cols": [3], "cells": [{"ref": "A1", "value": "Item"}]}],
    )
    report = load_diff(original, received)
    labels = {(item.cell, item.type_label) for item in report.changes}
    assert ("8:9", "linha ocultada") in labels
    assert ("C", "coluna ocultada") in labels


def test_comment_edit_and_legacy_thread_note_are_not_duplicated(tmp_path):
    from oculto_scan.diff import load_diff

    original = _pair(
        tmp_path,
        "original.xlsx",
        [
            {
                "name": "Proposta",
                "cells": [{"ref": "C2", "value": "preço"}],
                "comments": [
                    {
                        "ref": "C2",
                        "author": "tc={A1B2C3D4-E5F6-7890-ABCD-EF1234567890}",
                        "text": _PLACEHOLDER,
                    }
                ],
                "threads": [{"ref": "C2", "text": "margem interna"}],
            }
        ],
    )
    same = _pair(
        tmp_path,
        "igual.xlsx",
        [
            {
                "name": "Proposta",
                "cells": [{"ref": "C2", "value": "preço"}],
                "comments": [
                    {
                        "ref": "C2",
                        "author": "tc={A1B2C3D4-E5F6-7890-ABCD-EF1234567890}",
                        "text": _PLACEHOLDER,
                    }
                ],
                "threads": [{"ref": "C2", "text": "margem interna"}],
            }
        ],
    )
    quiet = load_diff(original, same)
    assert not any(item.type_label.startswith("comentário") for item in quiet.changes)
    edited = _pair(
        tmp_path,
        "editado.xlsx",
        [
            {
                "name": "Proposta",
                "cells": [{"ref": "C2", "value": "preço"}],
                "comments": [
                    {
                        "ref": "C2",
                        "author": "tc={A1B2C3D4-E5F6-7890-ABCD-EF1234567890}",
                        "text": _PLACEHOLDER,
                    }
                ],
                "threads": [{"ref": "C2", "text": "margem 35% não mostrar"}],
            }
        ],
    )
    report = load_diff(original, edited)
    comments = [item for item in report.changes if item.type_label.startswith("comentário")]
    assert len(comments) == 1
    assert comments[0].type_label == "comentário editado"
    assert "tc=" not in comments[0].message
    assert "tc=" not in comments[0].before_raw
    assert "margem 35% não mostrar" in comments[0].after_raw
    removed = _pair(tmp_path, "sem.xlsx", [{"name": "Proposta", "cells": [{"ref": "C2", "value": "preço"}]}])
    gone = load_diff(original, removed)
    assert any(item.type_label == "comentário removido" for item in gone.changes)


def test_defined_name_and_external_link(tmp_path):
    from oculto_scan.diff import load_diff

    original = _pair(
        tmp_path,
        "original.xlsx",
        [{"name": "Proposta", "cells": [{"ref": "A1", "value": "Item"}]}],
        defined_names=[{"name": "CustoUnitario", "formula": "Custos!$B$2"}],
    )
    received = _pair(
        tmp_path,
        "recebido.xlsx",
        [{"name": "Proposta", "cells": [{"ref": "A1", "value": "Item"}]}],
        defined_names=[{"name": "CustoUnitario", "formula": "Custos!$B$3"}],
        external_target="file:///C:/Users/ana.sintetica/custos.xlsx",
    )
    report = load_diff(original, received)
    assert any(item.type_label == "nome definido" for item in report.changes)
    link = next(item for item in report.changes if item.type_label == "vínculo externo")
    assert "ana.sintetica" not in link.after_masked
    assert "ana.sintetica" in link.after_raw


def test_metadata_fields_and_metadata_only_headline(tmp_path, capsys):
    from oculto_scan.diff import load_diff

    original = _pair(tmp_path, "original.xlsx", _base(), metadata=_META)
    changed = dict(_META)
    changed["lastModifiedBy"] = "Colega Sintetico"
    changed["modified"] = "2026-09-30T21:55:00Z"
    changed["revision"] = "5"
    received = _pair(tmp_path, "recebido.xlsx", _base(), metadata=changed)
    report = load_diff(original, received)
    assert report.headline == METADATA_ONLY
    assert report.exit_code == 1
    keys = {item.cell for item in report.changes}
    assert "lastModifiedBy" in keys
    assert "modified" in keys
    assert "revision" in keys
    assert all(item.category == "metadado" for item in report.changes)
    saved = next(row for row in report.metadata if row.key == "lastModifiedBy")
    assert saved.changed
    assert "Colega Sintetico" not in saved.after_masked
    code = main(["diff", str(original), str(received)])
    out = capsys.readouterr().out
    assert code == 1
    assert METADATA_ONLY in out
    assert "Colega Sintetico" not in out


def test_html_show_escapes_script_and_masked_html_hides_it(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    original = _pair(
        tmp_path,
        "original.xlsx",
        [{"name": "Proposta", "cells": [{"ref": "A1", "value": "ok"}]}],
        metadata={"lastModifiedBy": "Autora Sintetica"},
    )
    received = _pair(
        tmp_path,
        "recebido.xlsx",
        [
            {
                "name": "Proposta",
                "cells": [{"ref": "A1", "value": _SCRIPT}],
                "comments": [{"ref": "A1", "author": "Atacante", "text": _SCRIPT}],
            }
        ],
        metadata={"lastModifiedBy": _SCRIPT},
    )
    code = main(["diff", str(original), str(received), "--format", "html"])
    masked = (tmp_path / "oculto-scan-diff.html").read_text(encoding="utf-8")
    assert code == 1
    assert _SCRIPT not in masked
    assert "<script" not in masked.lower()
    assert "Quem salvou" in masked
    assert "Antes" in masked and "Depois" in masked
    assert REVEALED_BANNER not in masked

    code = main(["diff", str(original), str(received), "--show", "--format", "html"])
    revealed_path = tmp_path / "oculto-scan-diff-revelado.html"
    revealed = revealed_path.read_text(encoding="utf-8")
    captured = capsys.readouterr().out
    assert code == 1
    assert "oculto-scan-diff-revelado.html" in captured
    assert REVEALED_BANNER in revealed
    assert 'class="revelado"' in revealed
    assert _SCRIPT not in revealed
    assert "<script" not in revealed.lower()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in revealed
    assert "Atacante" in revealed


def test_json_stays_masked_and_missing_path_exits_2(tmp_path, capsys):
    original = _pair(tmp_path, "original.xlsx", _base(), metadata=_META)
    changed = dict(_META)
    changed["Company"] = "Outra Construtora"
    received = _pair(tmp_path, "recebido.xlsx", _base(), metadata=changed)
    code = main(["diff", str(original), str(received), "--show", "--format", "json"])
    raw = capsys.readouterr().out
    payload = json.loads(raw)
    assert code == 1
    assert payload["command"] == "diff"
    assert payload["version"] == "0.1.3"
    assert "Outra Construtora" not in raw
    assert LIMITS in payload["limits"]
    missing = tmp_path / "nao-existe.xlsx"
    assert main(["diff", str(original), str(missing)]) == 2


def test_text_colors_follow_tty_and_no_color(tmp_path, monkeypatch, capsys):
    original = _pair(tmp_path, "original.xlsx", _base())
    sheets = _base()
    sheets[0]["cells"][0]["value"] = "outro"
    received = _pair(tmp_path, "recebido.xlsx", sheets)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    main(["diff", str(original), str(received)])
    colored = capsys.readouterr().out
    assert "\033[31m" in colored
    assert "valor alterado" in colored
    main(["diff", str(original), str(received), "--no-color"])
    assert "\033[" not in capsys.readouterr().out
