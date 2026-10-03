# Changelog

## 0.2.4

- O relatório mostra a pasta onde o Excel salvou a planilha, e também HyperlinkBase, modelo, conexão, consulta e fonte externa de tabela dinâmica. Usuário do Windows e nome do OneDrive ou da empresa saem mascarados. O valor real só aparece com «Mostrar valores reais».
- Na comparação, as duas pastas ficam lado a lado. O mesmo usuário ou a mesma pasta raiz é marcado como indício de autoria comum entre licitantes, não como prova.
- A cópia limpa tira essa pasta e os outros caminhos cobertos que dá para apagar sem quebrar o arquivo. O bloco da consulta Power Query não é reescrito.

## 0.2.3

- O relatório HTML deixa de listar cada célula. Achados do mesmo tipo viram uma linha com a quantidade e até 20 exemplos. O topo resume gravidade e tipo, e as seções abrem e fecham.
- A página fica pequena mesmo com dezenas de milhares de achados. A lista de cada célula continua em `--format json`.
- Salvar e abrir o relatório não trava a janela. Enquanto grava, aparece «Gerando relatório...» e os botões ficam desligados.

## 0.2.2

- Planilha grande deixa de travar a janela. A aba é lida em fluxo, sem montar o XML inteiro na memória, e a busca de cabeçalho não percorre a aba de novo para cada célula.
- A janela mostra no máximo 200 cartões, os mais graves, e avisa quantos achados ficaram só no relatório. O texto completo continua no HTML.
- Durante a análise aparece «Lendo aba X de Y». O botão Cancelar interrompe. Arquivo acima do limite continua recusado, e a janela mostra a mensagem do `--max-mb`.

## 0.2.1

- A janela deixa de travar ao maximizar durante a comparação de duas planilhas. A análise roda fora da thread da janela. Redimensionar espera um instante e só ajusta a largura do texto, sem recriar os cartões. Enquanto analisa, a janela mostra «Analisando...» e os botões ficam desligados.

## Documentação

- A página principal do README ficou curta. O passo a passo, o uso completo, as limitações, a segurança da ferramenta, o roteiro e a política de assinatura de código estão em `docs/`. A versão do programa não mudou.

## 0.2.0

- Modo `--limpar` grava uma cópia (`proposta-limpa.xlsx`, ou o caminho de `--saida`). O original não é alterado. Se a cópia já existe, o comando recusa, a menos que haja `--forcar`. A cópia nunca substitui o original.
- Por padrão saem comentários e notas, autor, empresa e última modificação, dado pessoal em propriedade personalizada, vínculo `externalLinks` (a fórmula que dependia dele vira o valor em cache) e caminho de rede ou de usuário nos metadados.
- Aba, linha e coluna ocultas ficam. Apagar pode quebrar fórmula. `--remover-ocultas` apaga a aba oculta, esvazia linha e coluna ocultas sem renumerar o resto, e troca a fórmula dependente pelo valor em cache. Sem valor em cache, a célula fica vazia.
- `--remover-macros` grava `.xlsx` sem `vbaProject`. Sem a opção, o `.xlsm` continua com a macro e o relatório avisa.
- CPF, CNPJ e segredo em célula não mudam. O relatório diz que ficaram para revisão humana. Em seguida a cópia é varrida: o texto mostra o antes, o que saiu e o que ainda resta.
- Na janela, depois do scan, **Gerar cópia limpa** grava a cópia e o medidor passa a mostrar o risco dela. As opções ficam em caixas. Continua offline e mascarado por padrão. O programa em si não ganhou dependência nova.

## 0.1.12

- Janela com medidor de risco: semicírculo com a nota Limpo, Baixo, Médio ou Alto (o pior achado; quatro ou mais infos sobem para Médio). Embaixo, cartões curtos com gravidade, título simples, aba ou célula e uma linha do que fazer. O texto longo continua só no relatório HTML, no terminal e no JSON. Sem dependência nova. Arrastar e soltar continua de fora.
- No Windows, o atalho e o `oculto-scan.exe` abrem só a janela, sem a janela preta do console. O terminal fica no `oculto-scan-cli.exe`. No `pip`, `oculto-scan-gui` usa o `pythonw`. Se não houver console, o programa não quebra quando a saída padrão vem vazia.

## 0.1.11

- Ícone próprio: lupa sobre uma planilha, ponto âmbar, fundo navy. Entra no `.exe`, na janela e no instalador.
- Instalador `oculto-scan-setup.exe` em português. Por padrão instala para o usuário atual, sem administrador, e há opção de instalar para todos. Atalho no menu Iniciar, atalho opcional na área de trabalho e entrada em Adicionar ou remover programas. Uma versão nova instala por cima. O `.exe` portátil continua na mesma release. Sem UPX. A assinatura continua desligada.

## 0.1.10

- Menu **Ajuda** › **Contato / suporte** na janela, também na caixa **Sobre**. O botão abre o programa de e-mail do computador. O oculto-scan não envia a mensagem e não acessa a rede. O endereço não aparece no README: lá a orientação é usar esse menu ou abrir uma issue.
- O que já estava na 0.1.9, que não teve release: seção **Como atualizar** no README (baixar o `.exe` de novo ou `git pull` na pasta do clone) e menu **Ajuda** com os passos de atualização, a página de download e a versão instalada.

## 0.1.9

- Seção **Como atualizar** no README: baixar o `.exe` de novo na última release, ou `git pull` na pasta do clone. O programa não procura versão nova sozinho. No GitHub, **Watch** › **Custom** › **Releases** avisa por e-mail.
- Menu **Ajuda** na janela: os mesmos passos, a página de download no navegador e a versão instalada (licença Apache-2.0). Abrir a página não faz o programa buscar nada na rede.

## 0.1.8

- O mapa da rede deixa de ler um pedaço de caminho UNC como usuário do Windows. Em `\\SERVIDOR-OBRAS\propostas`, o servidor continua como máquina e o caminho como rede; `OBRAS\propostas` não vira `DOMINIO\usuario`. Um `CONSTRUTORA\joao.silva` isolado continua sendo detectado.

## 0.1.7

- Janela offline em português (`oculto-scan gui` ou `oculto-scan-gui`), feita com Tk, que já vem com o Python. Escolher um `.xlsx` ou `.xlsm`, escanear, ver o resumo mascarado e revelar só se a pessoa marcar a opção. Dá para salvar ou abrir o HTML e comparar dois arquivos. A lógica é a mesma de `scan_bytes` e `diff_bytes`.
- O `.exe` de Windows é gerado no GitHub Actions, sem UPX e sem cache, com a versão `0.1.7.0` em todos os campos do arquivo e o nome do produto `oculto-scan`. A macro (oletools) entra no executável. A assinatura SignPath fica desligada. Uma tag `v*` publica a release com o `.exe` e o SHA-256. O arquivo ainda não é assinado.

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
