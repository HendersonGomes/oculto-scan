# Changelog

## 0.1.3

- Subcomando `oculto-scan diff ORIGINAL.xlsx RECEBIDO.xlsx`: células, abas, ocultação, comentários, nomes, vínculos e quem salvou.
- Se os bytes forem iguais, a mensagem é «arquivo não foi salvo novamente». Se só metadados mudaram, «salvo de novo sem alteração de conteúdo detectada».
- Terminal, JSON mascarado e HTML com colunas Antes/Depois. `--show` revela os valores no terminal e no HTML.

## 0.1.1

- Relatório HTML (`--format html`, `--output`) em um arquivo só, com CSS embutido e estilo de impressão. O valor fica mascarado mesmo com `--show`.
- Terminal agrupado por arquivo (`aba › célula › tipo › risco`), com cor por risco. A cor respeita TTY, `NO_COLOR` e `--no-color`. No Windows o modo VT é ligado sem dependência nova.
- Nota legada de compatibilidade do comentário em thread (autor `tc={GUID}` e texto placeholder) deixa de duplicar o achado. `tc=...` não aparece como autor.
- Nota de instalação no Windows: `python -m oculto_scan` quando a pasta Scripts está fora do PATH.
- Passo a passo no README para quem nunca usou o terminal, com planilha de demonstração.

## 0.1.0

- Primeira versão: varredura offline de `.xlsx` e `.xlsm` para vazamento em planilha de obra.
