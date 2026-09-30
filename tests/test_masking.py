from oculto_scan.masking import (
    mask_account,
    mask_cnpj,
    mask_cpf,
    mask_formula,
    mask_path,
    mask_pis,
    mask_secret,
    mask_text,
)


def test_mask_cpf_keeps_middle_digits():
    assert mask_cpf("529.982.247-25") == "***.982.247-**"
    assert mask_cpf("52998224725") == "***.982.247-**"


def test_mask_cnpj_numeric_and_alphanumeric():
    assert mask_cnpj("11.222.333/0001-81") == "**.222.333/0001-**"
    assert mask_cnpj("12.ABC.345/01DE-35") == "**.ABC.345/01DE-**"


def test_mask_pis_secret_account_and_path():
    assert mask_pis("120.56437.87-4") == "***.56437.**-*"
    masked = mask_secret("AKIAIOSFODNN7EXAMPLE")
    assert masked.startswith("AKIA")
    assert "AKIAIOSFODNN7EXAMPLE" not in masked
    assert "20 caracteres" in masked
    assert "567890" not in mask_account("567890-1")
    assert mask_account("567890-1").endswith("dígitos)")
    assert "ana.sintetica" not in mask_path(r"C:\Users\ana.sintetica\custos.xlsx")
    assert "a***" in mask_path(r"C:\Users\ana.sintetica\custos.xlsx")
    assert mask_text("Autora Sintetica") == "Au**** Si*******"
    assert mask_formula("Custos!B2*1.35") == "Custos!B2*[n]"
