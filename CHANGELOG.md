# Changelog

## 0.1.6

- O texto do terminal termina com **Próximos passos**: até quatro comandos com o caminho do arquivo, entre aspas, para copiar no PowerShell. Pode aparecer `--show`, HTML, JSON, `diff`, `--help` e, só em `.xlsm` sem o extra, o comando para instalar a leitura de macro.
- O bloco não entra no JSON nem no HTML. Não aparece quando `CI` ou `GITHUB_ACTIONS` está definido. `--no-hints` desliga. Os códigos de saída não mudam.

## 0.1.5

- Seção **Mapa da rede** no texto, no JSON e no HTML: usuário do Windows (`DOMINIO\usuario`), caminho UNC (`\\servidor\pasta`), site de SharePoint ou OneDrive, impressora e nome de máquina ou servidor. Os valores saem mascarados; `--show` revela no terminal e no HTML. O JSON continua mascarado. Um indício que já é achado (por exemplo um vínculo externo) aparece no mapa e não é repetido na lista.
- Leitura de macro em `.xlsm` sem executar nada e sem testar senha do editor VBA. O extra é `pip install -e ".[macro]"` (oletools). Sem o extra, a macro fica como «não analisado» e a saída é 3. Com o extra, o relatório lista os módulos, palavras suspeitas (AutoOpen, Workbook_Open, Shell, URLDownloadToFile, CreateObject, WScript, PowerShell e outras) e indicadores (endereço, IP, caminho).
- O `diff` aceita `.xlsm` e aponta quando a macro existe só num dos dois arquivos.

## 0.1.4

- O HTML escapa o nome do arquivo e traz uma política de conteúdo restritiva. Nome com `{` ou `<script>` não quebra a página.
- Vínculo e hiperlink mostram só o site. Texto entre aspas na fórmula vira um marcador. Senha mostra só o tamanho. O diff usa a mesma máscara de CPF e de segredo. Caminho absoluto vira o nome do arquivo.
- `--show` é recusado quando `CI` ou `GITHUB_ACTIONS` está definido.
- Código de saída 3, «não analisado», com a causa: ilegível, senha, corrompido, `.xls`/`.csv` passado no comando, ou arquivo acima do limite. Planilha grande deixa de ser chamada de hostil. `--max-mb` analisa um arquivo maior de propósito. Um arquivo quebrado no meio da pasta não interrompe o resto.
- A saída do terminal fica em UTF-8. O relatório é gravado só para quem rodou, quando o sistema permite.
- Aba com acento e sem aspas (`=Orçamento!B5`) é reconhecida. `Tabela1[Valor]` não é vínculo externo. `LOG10` deslocado continua `LOG10`.
- Cabeçalho de CPF vale mesmo fora da primeira linha. Coluna Telefone, Código ou Quantidade não gera alerta de CPF. CPF numérico de 10 dígitos (sem o zero à esquerda) entra quando a coluna é de CPF.
- Formato `;;;`, coluna ou linha quase sem largura, e conteúdo fora da área de impressão entram no relatório. E-mail de quem comentou e o cache do vínculo externo também.
- O diff compara pelo endereço da célula: inserir linhas gera várias mudanças. Aba nova que já vem oculta informa isso. Valor mascarado que mudou diz «valor alterado».
- Sem caminho, o programa mostra a ajuda e não varre a pasta atual. No Windows, a instalação recomendada é um ambiente virtual.

## 0.1.3

- Subcomando `oculto-scan diff ORIGINAL.xlsx RECEBIDO.xlsx`: células, abas, ocultação, comentários, nomes, vínculos e quem salvou.
- Se os bytes forem iguais, a mensagem é «arquivo não foi salvo novamente». Se só metadados mudaram, «salvo de novo sem alteração de conteúdo detectada».
- Terminal, JSON mascarado e HTML com colunas Antes/Depois. `--show` revela os valores no terminal e no HTML, com a mesma faixa e o mesmo fuso do relatório de varredura.

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
