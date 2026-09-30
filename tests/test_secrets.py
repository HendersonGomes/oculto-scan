from oculto_scan.analyze import analyze
from oculto_scan.secrets import find_secrets
from oculto_scan.workbook import load_workbook
from tests.workbook_factory import build_workbook

AWS = "AKIAIOSFODNN7EXAMPLE"
GITHUB = "ghp_" + "a1" * 18
# Built at runtime so the source file does not contain a contiguous token.
SLACK = "xox" + "b-" + "123456789012" + "-" + "123456789012" + "-" + "AbCdEfGhIjKlMnOpQrStUvWx"


def test_curated_patterns_and_portuguese_password():
    hits = find_secrets(f"token {AWS} e {GITHUB}")
    rules = {hit.rule for hit in hits}
    assert "aws-access-token" in rules
    assert "github-pat" in rules
    senha = find_secrets("senha: s3gr3d0-sintetico")
    assert any(hit.rule == "senha-ou-token" and hit.value == "s3gr3d0-sintetico" for hit in senha)
    assert find_secrets("senha: exemplo") == []


def test_secrets_in_cells_entropy_off_by_default(tmp_path):
    noisy = "aB3xQ9mN4pL8rT2vW6yZ1cD5"
    path = tmp_path / "chaves.xlsx"
    build_workbook(
        path,
        [
            {
                "name": "Notas",
                "cells": [
                    {"ref": "A1", "value": f"aws {AWS}"},
                    {"ref": "A2", "value": f"git {GITHUB}"},
                    {"ref": "A3", "value": SLACK},
                    {"ref": "A4", "value": "-----BEGIN RSA PRIVATE KEY-----"},
                    {"ref": "A5", "value": "AIzaSyA1234567890abcDEFGHIJKLMNOPQRSTUV"},
                    {"ref": "A6", "value": f"id interno {noisy}"},
                ],
            }
        ],
    )
    workbook = load_workbook(path)
    quiet = analyze(workbook, "chaves.xlsx", entropy=False)
    rules = {item.evidence_raw for item in quiet if item.rule == "segredo"}
    assert AWS in rules
    assert GITHUB in rules
    assert any(item.rule == "segredo" and item.evidence_raw and item.evidence_raw.startswith("xoxb-") for item in quiet)
    assert any("PRIVATE KEY" in (item.evidence_raw or "") for item in quiet)
    assert any(item.evidence_raw and item.evidence_raw.startswith("AIza") for item in quiet)
    assert not any(item.rule == "entropia" for item in quiet)
    assert all(AWS not in (item.evidence_masked or "") for item in quiet if item.rule == "segredo")

    loud = analyze(workbook, "chaves.xlsx", entropy=True)
    assert any(item.rule == "entropia" for item in loud)
