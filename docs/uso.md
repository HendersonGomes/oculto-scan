# Uso

[Voltar ao README](../README.md) · [Guia para iniciantes](guia-iniciante.md) · [Limitações](limitacoes.md) · [Segurança da ferramenta](seguranca-da-ferramenta.md)

## O que a ferramenta detecta

<a id="o-que-a-ferramenta-detecta"></a>

Só `.xlsx` e `.xlsm`. A macro, quando existe, é **lida só se o extra estiver instalado, e nunca executada**. Vínculo externo é **anotado e nunca aberto**. O mapa da rede junta usuário, caminho UNC, SharePoint, impressora e servidor num bloco só, sem repetir o que já saiu como vínculo ou metadado.

| Achado | Risco usual |
| --- | --- |
| Aba oculta ou muito oculta (very hidden) | alto |
| Linha ou coluna oculta | médio |
| Comentário (nota antiga e thread) | médio |
| Nome definido que aponta para área oculta ou outra pasta | alto |
| Nome definido comum | info |
| Vínculo externo / hiperlink para outro arquivo | alto |
| Macro (`vbaProject.bin`) presente | médio |
| Palavra suspeita na macro (AutoOpen, Workbook_Open, Shell, CreateObject, PowerShell, URLDownloadToFile, WScript) | alto |
| Environ, CallByName, ADODB.Stream, WinHttp na macro | médio |
| Endereço, IP ou caminho dentro da macro | alto / médio |
| Caminho UNC (`\\servidor\pasta`) no mapa da rede | alto |
| Pasta onde a planilha foi salva (absPath, OneDrive, UNC, HyperlinkBase, modelo, conexão, consulta, Power Query ou fonte de tabela dinâmica) | médio (alto se mostrar usuário, OneDrive de empresa, SharePoint ou UNC) |
| Usuário do Windows, caminho local, impressora, máquina ou servidor | médio |
| SharePoint ou OneDrive (pasta interna é alto; só o site é médio) | alto / médio |
| Metadado de autor, empresa, último editor | médio |
| Célula **visível** cuja fórmula referencia aba, linha ou coluna oculta, ou outra pasta | alto |
| Constante numérica na fórmula (`=A1*1.35`) | info |
| CPF com dígito válido e contexto; lista de CPFs | médio / alto |
| PIS/NIS com contexto | médio (alto se houver lista) |
| CNPJ numérico ou alfanumérico | info |
| Agência ou conta sob rótulo de banco | alto |
| Chave, token ou senha | alto |

A constante é só informativa: pode revelar fator de margem ou BDI, e também pode ser um arredondamento. Não reprova o arquivo no `--fail-on` padrão.

### CPF, CNPJ e conta

A detecção de CPF, CNPJ e PIS/NIS usa a biblioteca [tarja](https://github.com/macmaia/tarja) (Apache-2.0): dígito verificador, contexto em português e CNPJ alfanumérico. Um CPF válido **sem** contexto é descartado.

O CNPJ alfanumérico (12 posições `A–Z`/`0–9` e 2 dígitos verificadores, módulo 11, letra convertida por ASCII − 48) está coberto via tarja. **Confira contra a IN RFB nº 2.229/2024** antes de tratar o achado como definitivo: a norma é a fonte, e a implantação na Receita é posterior a esta v0.1.

Dado bancário só aparece quando há rótulo (`banco`, `agência`, `conta`) ou a mesma frase na célula. **Não existe validação genérica de dígito**: cada banco tem a sua. Um número solto numa coluna de quantidade não é conta.

### Segredos

Um subconjunto pequeno de padrões no estilo do [gitleaks](https://github.com/gitleaks/gitleaks) (MIT; atribuição no [`NOTICE`](../NOTICE)): chave de acesso AWS, PAT do GitHub, chave de API do GCP, token de bot do Slack, cabeçalho de chave privada, além de uma regra própria para `senha` / `password` / `api_key`. Detecção por entropia fica **desligada**; `--entropy` liga e tende a falso positivo.

## Instalação técnica

<a id="instalação-técnica"></a>

Para quem já usa terminal e vai desenvolver. Quem só vai rodar a ferramenta no Windows segue o [guia para iniciantes](guia-iniciante.md).

Python 3.10 ou mais novo.

```bash
python -m pip install -e ".[dev]"
oculto-scan --help
```

Para ler macro de `.xlsm` (o código não é executado):

```bash
python -m pip install -e ".[macro]"
```

Sem esse extra, um arquivo com macro termina com código 3 e a mensagem pede `oculto-scan[macro]`. As versões de `defusedxml`, `tarja` e, no extra, `oletools` estão fixadas no `pyproject.toml`. O oculto-scan não está no PyPI.

### Windows

O caminho recomendado é um ambiente virtual, como no [guia](guia-iniciante.md) (`py -m venv .venv`, ativar, `pip install -e .`). Apagar a pasta do projeto quebra essa instalação.

No PowerShell, se `oculto-scan` não for reconhecido porque a pasta Scripts do Python está fora do PATH, use:

```powershell
python -m oculto_scan proposta.xlsx
```

Ou acrescente a pasta Scripts ao PATH (em geral `%APPDATA%\Python\Python314\Scripts`, ou a pasta Scripts da instalação). O terminal do VS Code e o Windows Terminal passam a mostrar a cor de risco sozinhos; em `cmd` antigo o modo VT é ligado pela própria ferramenta, sem pacote extra.

No Windows, `oculto-scan gui` (o mesmo que `oculto-scan-gui`) usa o `pythonw` e não abre o console. `oculto-scan` continua no terminal. O `oculto-scan.exe` da release abre só a janela, sem a janela preta. O `oculto-scan-cli.exe` é a linha de comando.

## Como atualizar

<a id="como-atualizar"></a>

O programa não procura versão nova sozinho. Quando sair uma release, escolha um dos caminhos.

### Instalador

Baixe o setup novo e instale por cima. A versão antiga é substituída. Não precisa apagar a pasta antes.

https://github.com/HendersonGomes/oculto-scan/releases/latest/download/oculto-scan-setup.exe

Na pasta onde o arquivo foi salvo, confira o SHA-256. O hash tem de ser o da release.

```powershell
Get-FileHash -Algorithm SHA256 .\oculto-scan-setup.exe
```

### Arquivo .exe portátil

Baixe de novo e apague o arquivo antigo. `oculto-scan.exe` abre só a janela. `oculto-scan-cli.exe` é o terminal.

https://github.com/HendersonGomes/oculto-scan/releases/latest/download/oculto-scan.exe

```powershell
Get-FileHash -Algorithm SHA256 .\oculto-scan.exe
```

https://github.com/HendersonGomes/oculto-scan/releases/latest/download/oculto-scan-cli.exe

```powershell
Get-FileHash -Algorithm SHA256 .\oculto-scan-cli.exe
```

### Instalação pelo código

Entre na pasta do clone. Se o projeto não estiver em Documentos, use o caminho dessa pasta.

```powershell
cd $HOME\Documents\oculto-scan
```

```powershell
git pull
```

```powershell
python -m pip install -e ".[macro]"
```

```powershell
oculto-scan --version
```

O número tem de ser a versão que você acabou de baixar.

Para receber um e-mail a cada versão nova, abra https://github.com/HendersonGomes/oculto-scan e clique em **Watch** › **Custom** › **Releases**.

## Comandos

```bash
oculto-scan proposta.xlsx
oculto-scan pasta-de-licitacao/
oculto-scan medicao.xlsm --format json
oculto-scan proposta.xlsx --format html
oculto-scan proposta.xlsx --format html --output relatorio.html
oculto-scan proposta.xlsx --format html --show
oculto-scan orcamento.xlsx --fail-on medio
oculto-scan proposta.xlsx --show
oculto-scan proposta.xlsx --no-color
oculto-scan proposta.xlsx --no-hints
oculto-scan proposta.xlsx --ignore .oculto-ignore
oculto-scan proposta.xlsx --baseline .oculto-baseline.json
oculto-scan proposta.xlsx --update-baseline .oculto-baseline.json
oculto-scan diff enviada.xlsx recebida.xlsx
oculto-scan diff enviada.xlsx recebida.xlsx --format html
oculto-scan proposta.xlsx --limpar
oculto-scan proposta.xlsx --limpar --saida copia.xlsx --forcar
oculto-scan medicao.xlsm --limpar --remover-macros
oculto-scan proposta.xlsx --limpar --remover-ocultas
oculto-scan gui
```

<a id="limpar-uma-copia"></a>

### Limpar uma cópia

`oculto-scan proposta.xlsx --limpar` grava `proposta-limpa.xlsx` ao lado do original. O original não é aberto para escrita. `--saida` escolhe outro caminho. Se esse arquivo já existe, o comando para e pede `--forcar`. Nem `--forcar` substitui o arquivo de origem.

Por padrão a cópia perde:

- comentários e notas
- autor, empresa e última modificação (`docProps`)
- dado pessoal em propriedade personalizada (CPF, e-mail, caminho, nome de autor)
- vínculos `externalLinks` — a fórmula que dependia deles vira o valor em cache
- caminho de rede ou de usuário nos metadados
- pasta do último salvamento (`absPath`) e caminho legível em modelo, conexão, consulta e fonte externa de tabela dinâmica

Aba, linha e coluna ocultas **ficam**. Apagar uma aba oculta pode quebrar uma fórmula que ainda aponta para ela. O relatório só avisa. `--remover-ocultas` apaga a aba, esvazia a linha ou a coluna oculta (elas ficam visíveis e vazias, sem renumerar o resto) e troca a fórmula dependente pelo valor em cache.

`--remover-macros` em um `.xlsm` grava `.xlsx` sem `vbaProject`. Sem essa opção a macro continua na cópia e o texto avisa.

CPF, CNPJ e segredo **dentro da célula** não são reescritos. O relatório diz que ficaram para revisão humana.

Depois da cópia, o mesmo scan roda nela e o texto mostra o antes, o que saiu e o que ainda resta. Na janela, o botão **Gerar cópia limpa** faz o mesmo e o medidor passa a ser o da cópia. As três caixas são: apagar ocultas, remover macros e substituir a cópia se ela já existir.

Os limites da limpeza estão em [Limitações](limitacoes.md#copia-limpa).

Sem caminho, o programa mostra a ajuda e sai com código 2. A pasta atual não é varrida. Uma pasta informada no comando é varrida de forma recursiva, incluindo subpastas. Arquivos `~$...` (trava do Excel) e extensões que não sejam `.xlsx`/`.xlsm` são ignorados nessa varredura. Um `.xls` ou `.csv` passado direto no comando não é lido: a saída diz isso e o código é 3.

No terminal, o arquivo aparece uma vez como cabeçalho. Abaixo, cada achado é `aba › célula › tipo › risco`, com a explicação na linha seguinte. Alto sai em vermelho, médio em amarelo e info em ciano, quando a saída é um terminal. A cor desliga sozinha se a saída não for um TTY, se a variável `NO_COLOR` estiver definida, ou com `--no-color`. O JSON não muda e continua sempre mascarado.

`--format html` grava um relatório para ler e imprimir (no navegador, “Salvar como PDF”). Sem `--output`, o arquivo é `oculto-scan-relatorio.html` na pasta atual, e o caminho é impresso. O HTML é um arquivo só, com CSS embutido, sem JavaScript, sem fonte externa e sem rede. Sem `--show`, o valor no HTML fica mascarado.

| Código | Significado |
| --- | --- |
| 0 | Nada no nível de `--fail-on` ou acima |
| 1 | Há achado nesse nível ou acima |
| 2 | Caminho ausente, ignore ou linha de base inválidos, ou `--show` recusado no CI |
| 3 | Não analisado: ilegível, protegido por senha, corrompido, `.xls`/`.csv` passado no comando, acima do limite de tamanho, ou macro sem o extra oletools |

Se algum arquivo da leva não pôde ser lido, o código é 3, mesmo que outro arquivo tenha achado. Arquivo hostil (zip bomb, partes demais) continua no código 1.

`--fail-on` aceita `alto` (padrão), `medio`, `info` e `nenhum`. `medio` reprova médio e alto. Serve para pre-commit ou CI: o processo sai com erro quando o relatório tem achado grave.

`--show` revela o valor no terminal e no HTML. O JSON continua mascarado. Sem `--show`, CPF sai como `***.982.247-**`, senha só como tamanho (`(20 caracteres)`), vínculo e hiperlink só como site (`https://sharepoint.example`), e caminho absoluto só como nome do arquivo. Se `CI` ou `GITHUB_ACTIONS` estiver definido, `--show` é recusado e o processo sai com código 2: o log do CI não fica com CPF nem senha.

`--max-mb N` sobe o limite para analisar de propósito um arquivo maior. O padrão recusa acima de 64 MiB no total e 32 MiB por parte, com código 3 e o limite escrito na mensagem. Isso não é tratado como ataque. Razão de compressão alta e pacote com partes demais continuam como arquivo hostil.

`--format html --show` grava os valores reais (comentário, fórmula com a constante, autor dos metadados). Sem `--output`, o arquivo é `oculto-scan-relatorio-revelado.html`. Uma faixa vermelha no topo avisa para não enviar esse arquivo a terceiros. No Windows, `start oculto-scan-relatorio-revelado.html` abre no navegador.

Quando o Excel grava um comentário em thread, ele também deixa uma nota antiga de compatibilidade. O autor é `tc={GUID}` e o texto começa com “[Threaded comment]”, ou, no Excel em português, “[Comentário encadeado]” / “[Comentário em thread]”. Isso é o mesmo comentário. O relatório fica com um achado só (o thread) e nunca mostra `tc=...` como autor. Uma nota antiga de verdade, com texto próprio, continua no relatório.

<a id="comparar-o-que-voltou-diff"></a>

## Comparar o que voltou (`diff`)

`oculto-scan diff ORIGINAL.xlsx RECEBIDO.xlsx` compara a planilha que você enviou com a que o colega devolveu. A comparação é pelo endereço da célula (`Proposta!C2` com `Proposta!C2`). Inserir ou apagar linhas no meio desloca o que está abaixo, e o relatório lista várias mudanças, uma por célula. A saída segue o mesmo estilo: `aba › célula › tipo de mudança`, com antes e depois. `--format json` continua mascarado. `--format html` gera uma página com colunas Antes/Depois e um quadro **Quem salvou**. Sem `--output`, o arquivo é `oculto-scan-diff.html` (ou `oculto-scan-diff-revelado.html` com `--show`).

Quando os dois lados viram a mesma máscara (os dois `[n]`, por exemplo), a linha diz «valor alterado», com o tipo e o tamanho quando isso também mudou. Uma aba que só existe na planilha recebida e já veio oculta informa o estado de visibilidade.

A pasta do último salvamento aparece lado a lado. Se o mesmo usuário do Windows, o mesmo OneDrive ou a mesma pasta raiz aparece nos dois arquivos, o texto diz que isso é indício de autoria comum entre licitantes, não prova.

`--show` revela os valores no terminal e no HTML. No HTML, a faixa vermelha avisa para não enviar esse arquivo a terceiros. O JSON não revela. No CI, `--show` é recusado, como na varredura.

Códigos: `0` sem diferença, `1` com diferença, `2` caminho ausente ou `--show` recusado, `3` arquivo ilegível, corrompido ou acima do limite.

- Arquivos byte a byte iguais: «arquivo não foi salvo novamente».
- Só autor, data ou outro metadado mudou: «salvo de novo sem alteração de conteúdo detectada».
- Fórmula igual e valor em cache diferente: a célula de origem mudou e o arquivo foi salvo de novo.

Limites, de propósito: o arquivo **não guarda IP** nem o histórico de quem editou cada célula. `lastModifiedBy` é só quem salvou por último e **pode ser editado**. Abrir sem salvar **não deixa rastro**. Para histórico de verdade, use o Histórico de Versões ou Mostrar Alterações no OneDrive/SharePoint, e os logs de auditoria do Microsoft 365 quando precisar do endereço IP.

## Exemplo

Saída de terminal (sem as cores) de uma planilha sintética: aba oculta `Custos`, fórmula `Custos!B2*1.35` em `Proposta!C2` e um comentário nessa célula. O fator numérico não aparece.

```text
proposta.xlsx
  Proposta › C2 › fórmula oculta › alto
    Célula visível cuja fórmula referencia aba, linha ou coluna oculta (Custos!B2). O número mostrado pode depender de custo ou margem que não aparece na impressão.
    valor: Custos!B2*[n]
  Custos › — › aba oculta › alto
    Aba oculta. Em proposta, orçamento ou edital isso costuma esconder custo, margem ou memória de cálculo, e o destinatário revela a aba com um clique.
  Proposta › C2 › comentário › médio
    Há comentário em thread nesta célula. Comentário interno muitas vezes descreve margem, premissa ou ressalva que não está na célula visível.
    valor: texto mascarado (14 caracteres)
  Proposta › C2 › constante › info
    Fórmula com constante numérica. Pode revelar o método de margem ou BDI (por exemplo um fator multiplicando o custo). É informativo: constante sozinha não prova vazamento.
    valor: Custos!B2*[n]
---
Resumo: 2 alto, 1 médio, 1 info (4 no total). 0 ignorado(s).
nenhum achado não significa arquivo limpo.
```

No terminal, `alto` fica vermelho, `médio` amarelo e `info` ciano, e a linha do resumo sai em negrito. O código de saída é 1, porque o padrão de `--fail-on` é `alto`.

O mesmo conteúdo em HTML (`oculto-scan proposta.xlsx --format html`) traz o quadro com as três contagens, uma tabela por arquivo e o aviso do rodapé. Dá para imprimir ou salvar em PDF pelo navegador.

## Ignorar um achado

Há dois mecanismos, os dois sem gravar o valor.

**Ignore** (texto, revisão humana), por regra ou por lugar:

```text
# .oculto-ignore
rule:formula-constante
rule:aba-oculta
file:proposta-sintetica.xlsx
sheet:proposta-sintetica.xlsx/Custos
cell:Medicao!B2
cell:proposta-sintetica.xlsx/Proposta/C2
```

`oculto-scan proposta.xlsx --ignore .oculto-ignore`

**Linha de base** (HMAC). O arquivo guarda um sal local e o HMAC de `regra + caminho + aba + célula`. Não guarda CPF, senha nem fórmula.

```bash
oculto-scan pasta/ --update-baseline .oculto-baseline.json
oculto-scan pasta/ --baseline .oculto-baseline.json
```

O update inclui os achados daquela corrida e termina com código 0. Uma célula nova continua alertando. Não commite a linha de base se o caminho do arquivo já for sensível; o valor em si não está lá.
