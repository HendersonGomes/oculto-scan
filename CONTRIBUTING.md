# Como contribuir

Uma mudança por pull request. Correção, teste e texto de ajuda da mesma correção podem ir juntos. Dois assuntos diferentes ficam em dois PRs.

Falha de segurança não entra em issue nem em PR público. O caminho está em [SECURITY.md](SECURITY.md).

## Testes

Na pasta do clone, com Python 3.10 ou mais novo:

```powershell
python -m pip install -e ".[dev,macro]"
python -m ruff check src tests packaging
python -m pytest
```

O `pytest` não abre janela. A lógica da janela é testada sem display. O CI roda o mesmo par de comandos em 3.10, 3.12 e 3.14.

## Estilo

- Texto que a pessoa vê: português.
- Código, comentário e nome: inglês.
- Ruff: linha de até 120, alvo Python 3.10, regras E, F, I e W.
- Sem dependência nova, salvo quando o PR for só para isso.
- O relatório de terminal, JSON e HTML não muda de texto por causa de ajuste visual da janela.

## Planilha de exemplo

Não suba planilha real nem dado de cliente. Não cole CPF, caminho de rede, nome de obra ou preço verdadeiro no issue, no PR ou no git.

Exemplo de teste sai de `tests/workbook_factory.py`: planilha fictícia, valor mascarado. Se o teste precisa de um arquivo, gere um assim. Não commite `.xlsx` de cliente.
