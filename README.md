# oculto-scan

[![CI](https://github.com/HendersonGomes/oculto-scan/actions/workflows/ci.yml/badge.svg)](https://github.com/HendersonGomes/oculto-scan/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/HendersonGomes/oculto-scan)](https://github.com/HendersonGomes/oculto-scan/releases/latest)
[![Licença Apache-2.0](https://img.shields.io/github/license/HendersonGomes/oculto-scan)](https://github.com/HendersonGomes/oculto-scan/blob/main/LICENSE)

[![Baixar oculto-scan.exe para Windows](https://img.shields.io/badge/Baixar-oculto--scan.exe-1f5f6b?style=for-the-badge)](https://github.com/HendersonGomes/oculto-scan/releases/latest/download/oculto-scan.exe)

Se a ferramenta ajudou, deixe uma estrela neste repositório.

Scanner de vazamento de dados em arquivos de obra (planilhas, propostas, medições). Offline, open source.

O oculto-scan lê planilhas `.xlsx` e `.xlsm` **antes** do envio ou da publicação: proposta de preços, boletim de medição, orçamento, laudo. O relatório junta, num lugar só, o que um engenheiro ou um auditor olharia na pasta — aba escondida, fórmula que puxa custo oculto, vínculo para `C:\Users\...`, autor nos metadados, CPF de empregado, senha deixada numa célula.

**nenhum achado não significa arquivo limpo.**

O oculto-scan não está no PyPI. Instale a partir deste repositório, ou use o botão acima. O programa verifica vazamento de dados antes do envio. Não é uma ferramenta de invasão.

## Apoie o projeto / serviço de checagem

O projeto aceita apoio pelo [GitHub Sponsors](https://github.com/sponsors/HendersonGomes).

Henderson Gomes faz checagem de arquivos antes do envio para construtoras. O contato é pelo [perfil no GitHub](https://github.com/HendersonGomes) ou pelo perfil dele no LinkedIn.

## Baixar o programa para Windows (.exe)

Quem não quer instalar Python pode usar a janela. O arquivo é `oculto-scan.exe`, na página de releases:

https://github.com/HendersonGomes/oculto-scan/releases

Ele ainda **não é assinado**. Não há instalador: o download é só o programa. A macro já vem dentro do `.exe`. Nada é enviado para a internet.

### Aviso do SmartScreen

O Windows pode dizer que o aplicativo não é reconhecido. Isso acontece porque a assinatura ainda não está ativa, não porque o arquivo foi alterado no caminho.

1. Na janela azul, clique em **Mais informações**.
2. Clique em **Executar assim mesmo**.

Se o botão não aparecer, confira o SHA-256 antes de seguir.

### Conferir o SHA-256

Cada release traz o hash ao lado do `.exe` (arquivo `oculto-scan.exe.sha256` e a mesma linha nas notas). No PowerShell, na pasta onde o arquivo foi salvo:

```powershell
Get-FileHash -Algorithm SHA256 .\oculto-scan.exe
```

O hash tem de ser igual ao da release. Se for diferente, apague o arquivo e baixe de novo.

### Desinstalar

Não tem instalador, serviço nem entrada no menu Iniciar. Para remover, apague `oculto-scan.exe`.

### Abrir a janela com Python

Na pasta do projeto, com o ambiente virtual ativado:

```powershell
python -m pip install -e ".[macro]"
oculto-scan gui
```

O mesmo comando é `oculto-scan-gui`. A opção de macro é necessária para ler VBA. O `.exe` já inclui essa parte. A janela pede o arquivo pelo botão **Escolher**. Arrastar e soltar ficou de fora: no Windows isso exige um gancho na janela, e esse tipo de gancho é o que o antivírus costuma marcar.

## Passo a passo para iniciantes (Windows)

Este caminho é para quem nunca abriu um terminal. Cada bloco abaixo é um comando: copie, cole no terminal e aperte Enter. Espere a resposta antes do próximo.

### 1. Abrir o terminal

Escolha um dos dois:

- Tecla Windows, digite `PowerShell`, Enter. Abre uma janela com um cursor piscando.
- No VS Code: menu **Terminal › Novo Terminal**. O painel de baixo é o mesmo PowerShell.

### 2. Conferir Python e Git

```powershell
python --version
git --version
```

O Python precisa ser 3.10 ou mais novo (`Python 3.12.x`, `Python 3.14.x`, etc.). O Git responde com `git version ...`.

Se o PowerShell disser que `python` não é reconhecido, instale por um destes caminhos e deixe marcada a opção **Add python.exe to PATH**:

- [python.org/downloads](https://www.python.org/downloads/)
- [Microsoft Store](https://apps.microsoft.com/store/search/Python): procure “Python 3.12” (ou 3.14)

Se `git` não for reconhecido, instale em [git-scm.com/download/win](https://git-scm.com/download/win). Pode aceitar as opções padrão da instalação.

Feche o terminal, abra de novo e repita os dois comandos. Só siga em frente quando os dois responderem com um número de versão.

### 3. Baixar o programa

```powershell
cd $HOME\Documents
git clone https://github.com/HendersonGomes/oculto-scan
cd oculto-scan
```

`cd` entra numa pasta. `$HOME` é a sua pasta de usuário (`C:\Users\<voce>`). O segundo comando baixa o projeto. O terceiro entra na pasta `oculto-scan`.

Se o `cd $HOME\Documents` disser que a pasta não existe, use `cd $HOME\Documentos`.

### 4. Instalar

Use um ambiente virtual, para a ferramenta não se misturar com outros programas Python. `py` é o lançador do Python no Windows. Se `py` não for reconhecido, troque por `python`.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

O ponto no final é a pasta em que você está. A instalação usa a internet esta única vez, para buscar duas bibliotecas pequenas. A leitura da planilha, depois, é offline: nada é enviado para fora.

Quem prefere um comando só, sem pasta de projeto aberta no dia a dia, pode usar o [pipx](https://pipx.pypa.io/): `pipx install -e .` dentro da pasta do projeto.

Se aparecer erro de arquivo não encontrado, o terminal não está dentro de `oculto-scan`. Rode `cd oculto-scan` de novo.

Se o PowerShell recusar o `Activate.ps1`, rode uma vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` e tente de novo.

**Não apague a pasta `oculto-scan`.** A instalação aponta para ela. Se a pasta sumir, o comando quebra. Para atualizar, use o passo 8. Para desinstalar, rode `pip uninstall oculto-scan` com o ambiente ativado e só então apague a pasta.

### 5. Se `oculto-scan` não for reconhecido

No fim da instalação pode aparecer um aviso de que a pasta **Scripts** está fora do PATH. Aí o comando `oculto-scan` sozinho não funciona. Há dois jeitos:

**Jeito simples,** que já funciona sem mudar nada. Use sempre esta forma:

```powershell
python -m oculto_scan --help
```

**Jeito permanente.** Copie a pasta Scripts que o aviso mostrou (algo como `C:\Users\<voce>\AppData\Roaming\Python\Python314\Scripts`) e cole no lugar do trecho `<pasta Scripts mostrada no aviso>`:

```powershell
[Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path","User") + ";<pasta Scripts mostrada no aviso>", "User")
```

Feche o terminal e abra outro. Aí `oculto-scan --help` passa a funcionar. Se não quiser mexer no PATH, fique no `python -m oculto_scan`.

### 6. Rodar na sua planilha

No Explorer, clique uma vez no arquivo `.xlsx`. Segure Shift, clique com o botão direito e escolha **Copiar como caminho**. Cole no terminal, entre aspas, depois do nome do programa:

```powershell
python -m oculto_scan "C:\Users\<voce>\Documentos\proposta.xlsx"
```

As aspas importam quando o caminho tem espaço.

A pasta Documentos muitas vezes está no OneDrive. Nesse caso o caminho copiado é `C:\Users\<voce>\OneDrive\Documentos\proposta.xlsx`. Use o caminho que o Explorer copiou.

Erro comum: colar só o caminho, sem `oculto-scan` ou `python -m oculto_scan` na frente. O PowerShell tenta abrir a planilha como se fosse um comando e responde que não reconhece o arquivo.

Rodar o programa sem nenhum arquivo também não varre a pasta em que você está. Ele mostra a ajuda e pede um caminho. Para varrer uma pasta, informe essa pasta no comando.

### 7. Como ler o resultado

O nome do arquivo aparece uma vez, no topo. Cada achado embaixo segue `aba › célula › tipo › risco`, com uma frase explicando e, quando cabe, uma linha `valor:`.

- **alto**, em vermelho: olhe antes de enviar a planilha.
- **médio**, em amarelo: vale revisar.
- **info**, em ciano: anotação. Sozinha, não reprova o arquivo.

O `valor:` vem mascarado. O fator `1,35` aparece como `[n]`. Nome de pessoa vira as primeiras letras e asteriscos. O texto de um comentário não é impresso; só o tamanho (`texto mascarado (14 caracteres)`).

No fim há um resumo (`2 alto, 1 médio, 1 info`) e a frase **nenhum achado não significa arquivo limpo**: relatório vazio não é atestado de que o arquivo pode sair.

Depois dos achados vem o **Mapa da rede**. É a parte que mostra o que a planilha entrega da estrutura interna: usuário do Windows (também no formato `DOMINIO\usuario`), caminho de rede (`\\servidor\pasta`), site do SharePoint ou do OneDrive, impressora e nome de máquina. Sem `--show`, o nome fica mascarado. O site do SharePoint (o tenant) continua visível, porque ele já está no endereço; a pasta interna não sai.

Planilha `.xlsm` pode ter macro. A ferramenta não executa a macro e não tenta senha. Para ler o código VBA, instale o extra (veja mais abaixo). Sem ele, o relatório diz que a macro não foi analisada e o programa termina com código 3.

Se o VS Code pintar o fim do comando de vermelho, a ferramenta rodou. Esse aviso costuma ser o código de saída 1: existe achado alto.

No fim do texto aparece **Próximos passos**: poucos comandos, com o caminho do arquivo entre aspas, para copiar e colar no PowerShell. Pode ser ver os valores (`--show`), gerar a página HTML, gerar JSON, comparar com `diff` ou abrir a ajuda (`--help`). Se o arquivo for `.xlsm` e o extra de macro não estiver instalado, entra também o comando de instalação. Esse bloco só existe no texto do terminal. JSON e HTML ficam iguais. Em CI ele não aparece. Para desligar no seu computador: `--no-hints`.

Para uma página que dá para mostrar ou imprimir:

```powershell
python -m oculto_scan "C:\Users\<voce>\Documentos\proposta.xlsx" --format html
```

O programa grava `oculto-scan-relatorio.html` na pasta atual e imprime o caminho. Abra no navegador. Para PDF: Ctrl+P e escolha salvar como PDF.

Para ver o texto do comentário, a fórmula inteira e o autor, use `--show`. Esse arquivo mostra os dados de verdade: não envie a terceiros.

```powershell
python -m oculto_scan "C:\Users\<voce>\Documentos\proposta.xlsx" --format html --show
start oculto-scan-relatorio-revelado.html
```

Para ver o que mudou numa planilha que você enviou e recebeu de volta:

```powershell
oculto-scan diff "C:\Users\<voce>\Documentos\original.xlsx" "C:\Users\<voce>\Documentos\recebido.xlsx" --format html
start oculto-scan-diff.html
```

Se `oculto-scan` não for reconhecido, troque por `python -m oculto_scan diff`. O relatório diz o que mudou e quem salvou por último. Ele não mostra IP: o arquivo não guarda isso. Quem só abriu e não salvou não deixa rastro.

### 8. Atualizar para uma versão nova

```powershell
cd $HOME\Documents\oculto-scan
.\.venv\Scripts\Activate.ps1
git pull
pip install -e .
```

Se a pasta do projeto estiver em outro lugar, o `cd` é o caminho dessa pasta. Apagar essa pasta quebra a instalação: o comando deixa de achar o programa.

### Monte uma planilha de demonstração

1. Abra o Excel e crie uma pasta em branco.
2. Renomeie a primeira aba para `Proposta` (clique duas vezes no nome da aba).
3. Clique no `+` e crie a aba `Custos`.
4. Em `Custos`, na célula B2, digite `1000`.
5. Volte para `Proposta`, célula C2, e digite `=Custos!B2*1,35`. Enter. A célula mostra `1350`.
6. Clique com o botão direito na aba `Custos` e escolha **Ocultar**.
7. Em `Proposta`, clique com o botão direito em C2, escolha comentário (Novo comentário ou Inserir comentário) e escreva uma frase curta, por exemplo `conferir margem`.
8. Arquivo › Salvar como › Pasta de Trabalho do Excel (`.xlsx`), na pasta Documentos, com o nome `proposta.xlsx`.

Rode o comando do passo 6 apontando para esse arquivo. O resultado fica nesta linha, com o seu caminho no lugar de `proposta.xlsx`:

```text
proposta.xlsx
  Custos › — › aba oculta › alto
    Aba oculta. Em proposta, orçamento ou edital isso costuma esconder custo, margem ou memória de cálculo, e o destinatário revela a aba com um clique.
  Proposta › C2 › fórmula oculta › alto
    Célula visível cuja fórmula referencia aba, linha ou coluna oculta (Custos!B2). O número mostrado pode depender de custo ou margem que não aparece na impressão.
    valor: Custos!B2*[n]
  Proposta › C2 › comentário › médio
    Há comentário em thread nesta célula. Comentário interno muitas vezes descreve margem, premissa ou ressalva que não está na célula visível.
    valor: texto mascarado (15 caracteres)
  Proposta › C2 › constante › info
    Fórmula com constante numérica. Pode revelar o método de margem ou BDI (por exemplo um fator multiplicando o custo). É informativo: constante sozinha não prova vazamento.
    valor: Custos!B2*[n]
---
Resumo: 2 alto, 1 médio, 1 info (4 no total). 0 ignorado(s).
nenhum achado não significa arquivo limpo.
```

O que cada linha quer dizer:

- A aba `Custos` está escondida, e isso é alto: quem recebe a planilha mostra a aba com um clique.
- A célula visível C2 multiplica um número dessa aba. O `1,35` não sai no relatório; no lugar fica `[n]`.
- O comentário entra uma vez só, como médio. No Excel atual o menu é um comentário em thread; a linha diz isso. Se o menu foi Nota, a linha diz «nota antiga» e pode mostrar o autor mascarado. O Excel às vezes grava as duas coisas juntas; a ferramenta mostra um achado só.
- A constante é info: registra que existe um fator, sem tratar isso como vazamento grave.
- O Excel também grava quem salvou o arquivo. Pode aparecer uma linha extra de metadado, em médio, com o nome mascarado. A frase que você escreveu no comentário não aparece.

O `1350` na tela pode ir na proposta. O ponto do relatório é a fórmula ainda apontar para a aba oculta.

## O que isto não é

Não é mais um detector genérico. Já existem gitleaks, trufflehog e detect-secrets para segredo em repositório; Presidio para dado pessoal em texto; mat2 e exiftool para metadado de mídia; o Inspetor de Documento do Office para o que o próprio Excel enxerga. O valor aqui é **um relatório só**, com o contexto de obra: a aba oculta de custo numa proposta não é o mesmo problema que um token num commit, e o CNPJ numa medição em geral é dado obrigatório, não vazamento.

## Por que

Três cenas que o relatório tenta pegar antes do arquivo sair:

- **Proposta de preços** com aba ou coluna oculta de custo e margem. A célula visível mostra o preço; a fórmula (`=Custos!B2*1.35`) entrega o método. Um vínculo `C:\Users\...` aponta para a planilha que não vai no e-mail e ainda identifica a máquina. Autor e empresa ficam nos metadados.
- **Edital com orçamento sigiloso** que vaza pela aba oculta, por um nome definido que aponta para essa aba, ou pelo metadado de quem montou o arquivo.
- **Medição** com relação de empregados: CPF, PIS, salário, agência e conta. O CPF só entra no relatório com dígito verificador **e** contexto (cabeçalho ou palavras como funcionário, empregado, PIS, salário), porque cerca de 1% dos números de 11 dígitos passa no dígito por acaso. Vários CPFs no mesmo lugar são risco alto.

## O que a v0.1 detecta

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

Um subconjunto pequeno de padrões no estilo do [gitleaks](https://github.com/gitleaks/gitleaks) (MIT; atribuição no `NOTICE`): chave de acesso AWS, PAT do GitHub, chave de API do GCP, token de bot do Slack, cabeçalho de chave privada, além de uma regra própria para `senha` / `password` / `api_key`. Detecção por entropia fica **desligada**; `--entropy` liga e tende a falso positivo.

## Instalação técnica

Para quem já usa terminal e vai desenvolver. Quem só vai rodar a ferramenta no Windows segue o passo a passo do início.

Python 3.10 ou mais novo.

```bash
python -m pip install -e ".[dev]"
oculto-scan --help
```

Para ler macro de `.xlsm` (o código não é executado):

```bash
python -m pip install -e ".[macro]"
```

Sem esse extra, um arquivo com macro termina com código 3 e a mensagem pede `oculto-scan[macro]`. As versões de `defusedxml`, `tarja` e, no extra, `oletools` estão fixadas no `pyproject.toml`.

### Windows

O caminho recomendado é um ambiente virtual, como no passo a passo do início (`py -m venv .venv`, ativar, `pip install -e .`). Apagar a pasta do projeto quebra essa instalação.

No PowerShell, se `oculto-scan` não for reconhecido porque a pasta Scripts do Python está fora do PATH, use:

```powershell
python -m oculto_scan proposta.xlsx
```

Ou acrescente a pasta Scripts ao PATH (em geral `%APPDATA%\Python\Python314\Scripts`, ou a pasta Scripts da instalação). O terminal do VS Code e o Windows Terminal passam a mostrar a cor de risco sozinhos; em `cmd` antigo o modo VT é ligado pela própria ferramenta, sem pacote extra.

## Uso

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
oculto-scan gui
```

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

## Comparar o que voltou (`diff`)

`oculto-scan diff ORIGINAL.xlsx RECEBIDO.xlsx` compara a planilha que você enviou com a que o colega devolveu. A comparação é pelo endereço da célula (`Proposta!C2` com `Proposta!C2`). Inserir ou apagar linhas no meio desloca o que está abaixo, e o relatório lista várias mudanças, uma por célula. A saída segue o mesmo estilo: `aba › célula › tipo de mudança`, com antes e depois. `--format json` continua mascarado. `--format html` gera uma página com colunas Antes/Depois e um quadro **Quem salvou**. Sem `--output`, o arquivo é `oculto-scan-diff.html` (ou `oculto-scan-diff-revelado.html` com `--show`).

Quando os dois lados viram a mesma máscara (os dois `[n]`, por exemplo), a linha diz «valor alterado», com o tipo e o tamanho quando isso também mudou. Uma aba que só existe na planilha recebida e já veio oculta informa o estado de visibilidade.

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

## Segurança da própria ferramenta

- Sem rede. Não há cliente HTTP no código, e a tarja não tem dependência de execução.
- Valor mascarado em toda saída, salvo `--show` no terminal e no HTML. O JSON continua mascarado.
- XML com defusedxml (sem entidade externa, sem expansão de DTD).
- Zip bomb continua recusado: razão de compressão, número de partes e membro criptografado. Tamanho acima do limite (64 MiB no total, 32 MiB por parte) é «não analisado», código 3, com o limite na mensagem. `--max-mb` sobe esse limite de propósito. A leitura de cada parte também é limitada.
- Relatório HTML e JSON no disco ficam com permissão restrita (só quem rodou) quando o sistema permite. A saída do terminal é UTF-8.
- Macro não é executada e a senha do editor VBA não é testada. Sem o extra `oletools`, o binário não é lido e a saída é 3. Com o extra, só o texto do VBA é lido (módulos, palavras suspeitas e indicadores). O binário não é vasculhado em busca de segredo.
- Vínculo externo não é resolvido, mesmo que o caminho exista na máquina.

## Limitações

- Só OOXML (`.xlsx`/`.xlsm`). Um `.xls` ou `.csv` passado no comando é «não analisado» (código 3). Dentro de uma pasta, essas extensões continuam de fora. PDF, DOCX e imagem ficam para depois.
- Sem `pip install -e ".[macro]"`, a macro de um `.xlsm` não é lida (código 3). Com o extra, a leitura é estática: nada é executado. Projeto VBA ilegível também fica como não analisado, sem tentativa de senha.
- Aba oculta é risco alto porque o destinatário a revela com um clique. Linha e coluna oculta ficam em médio: planilha de engenharia esconde faixa o tempo todo. O que sobe para alto é a célula visível que **depende** dessa faixa.
- Fórmula compartilhada é deslocada pela referência relativa do mestre. `INDIRECT` não é avaliado. Validação de dados, cache de tabela dinâmica e objeto incorporado não são lidos.
- O cabeçalho de CPF e de dado bancário é a célula de texto mais próxima acima na coluna, mesmo que não seja a linha 1. Se a coluna não tem cabeçalho, vale o rótulo à esquerda. Cabeçalho Telefone, Código ou Quantidade não vira alerta de CPF.
- Salário em si não vira achado: quase toda coluna de preço é um número. Ele só ajuda o contexto do CPF.
- Entropia desligada por padrão.
- Um relatório limpo não é arquivo limpo.

## Roteiro v0.2

- PDF com tarja falsa (redação que ainda leva o texto por baixo).
- DOCX com revisão e comentário (tracked changes).
- EXIF e metadado de imagem.
- SARIF e uma GitHub Action pronta.
- Comparar arquivos de licitantes pelo autor e pelos metadados, como **indício** de autoria compartilhada — não prova de conluio.

## Code signing policy

A assinatura de código ainda **não está ativa**. O `oculto-scan.exe` publicado hoje **não é assinado** e não deve ser descrito como assinado. Esta seção deixa o projeto pronto para pedir a assinatura gratuita da SignPath Foundation. O passo de assinatura no GitHub Actions está desligado até existirem o token e os IDs.

Quando a assinatura for ligada, a atribuição exigida será: “Free code signing provided by SignPath.io, certificate by SignPath Foundation”. Essa frase **não** vale para os arquivos publicados agora.

- Author (autor): Henderson Gomes (@HendersonGomes)
- Reviewer (revisor): Henderson Gomes (@HendersonGomes)
- Approver (aprovador): Henderson Gomes (@HendersonGomes)

Cada release que venha a ser assinada precisa de aprovação manual do aprovador. O build roda só em runners hospedados pelo GitHub, a partir do código deste repositório, sem cache não verificado. O nome do produto no `.exe` é `oculto-scan` e a versão é a mesma em todos os campos do arquivo.

This program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it.

O oculto-scan não tem cliente de rede. Ele lê a planilha que você escolhe e grava o relatório neste computador. defusedxml, tarja e oletools não enviam dados. O programa é uma verificação de privacidade e de vazamento de dados antes do envio. Não explora falhas e não altera o sistema.

## Licença e créditos

Apache-2.0. Veja `LICENSE` e `NOTICE`.

- [tarja](https://github.com/macmaia/tarja), Maria Alice Maia — CPF, CNPJ (inclusive alfanumérico) e PIS/NIS. Apache-2.0.
- [defusedxml](https://github.com/tiran/defusedxml) — leitura de XML hostil.
- [gitleaks](https://github.com/gitleaks/gitleaks) — os padrões de token copiados estão sob MIT, com atribuição no `NOTICE`. A regra de `senha` é deste projeto.
- [oletools](https://github.com/decalage2/oletools) — leitura estática de macro no extra e no `.exe`. BSD. A macro não é executada.
- [PyInstaller](https://pyinstaller.org) — só para montar o `.exe` de Windows. O executável não usa UPX.

O oculto-scan não substitui revisão humana nem assessoria jurídica. Não publica pacote no PyPI nesta versão.
