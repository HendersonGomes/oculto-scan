# Changelog

## 0.1.2

- `--format html --show` revela os valores, com faixa vermelha de aviso. Sem `--show`, o HTML continua mascarado. O nome padrão do arquivo revelado é `oculto-scan-relatorio-revelado.html`.
- A nota legada do comentário em thread também é reconhecida no Excel em português (`[Comentário encadeado]`, `[Comentário em thread]`) e em espanhol, pelo autor `tc={GUID}` na mesma célula.
- A data do relatório HTML usa o fuso da máquina, com o deslocamento visível (`30/09/2026 21:55 (UTC-03:00)`).

## 0.1.1

- Relatório HTML (`--format html`, `--output`) em um arquivo só, com CSS embutido e estilo de impressão. O valor fica mascarado mesmo com `--show`.
- Terminal agrupado por arquivo (`aba › célula › tipo › risco`), com cor por risco. A cor respeita TTY, `NO_COLOR` e `--no-color`. No Windows o modo VT é ligado sem dependência nova.
- Nota legada de compatibilidade do comentário em thread (autor `tc={GUID}` e texto placeholder) deixa de duplicar o achado. `tc=...` não aparece como autor.
- Nota de instalação no Windows: `python -m oculto_scan` quando a pasta Scripts está fora do PATH.
- Passo a passo no README para quem nunca usou o terminal, com planilha de demonstração.

## 0.1.0

- Primeira versão: varredura offline de `.xlsx` e `.xlsm` para vazamento em planilha de obra.
