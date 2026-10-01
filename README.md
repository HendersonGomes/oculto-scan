# oculto-scan

Scanner de vazamento de dados em arquivos de obra (planilhas, propostas, medições). Offline, open source.

O oculto-scan lê planilhas `.xlsx` e `.xlsm` **antes** do envio ou da publicação: proposta de preços, boletim de medição, orçamento, laudo. O relatório junta, num lugar só, o que um engenheiro ou um auditor olharia na pasta — aba escondida, fórmula que puxa custo oculto, vínculo para `C:\Users\...`, autor nos metadados, CPF de empregado, senha deixada numa célula.

**nenhum achado não significa arquivo limpo.**

O oculto-scan não está no PyPI. Instale a partir deste repositório.

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

```powershell
python -m pip install -e .
```

O ponto no final é a pasta em que você está. A instalação usa a internet esta única vez, para buscar duas bibliotecas pequenas. A leitura da planilha, depois, é offline: nada é enviado para fora.

Se aparecer erro de arquivo não encontrado, o terminal não está dentro de `oculto-scan`. Rode `cd oculto-scan` de novo.

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

### 7. Como ler o resultado

O nome do arquivo aparece uma vez, no topo. Cada achado embaixo segue `aba › célula › tipo › risco`, com uma frase explicando e, quando cabe, uma linha `valor:`.

- **alto**, em vermelho: olhe antes de enviar a planilha.
- **médio**, em amarelo: vale revisar.
- **info**, em ciano: anotação. Sozinha, não reprova o arquivo.

O `valor:` vem mascarado. O fator `1,35` aparece como `[n]`. Nome de pessoa vira as primeiras letras e asteriscos. O texto de um comentário não é impresso; só o tamanho (`texto mascarado (14 caracteres)`).

No fim há um resumo (`2 alto, 1 médio, 1 info`) e a frase **nenhum achado não significa arquivo limpo**: relatório vazio não é atestado de que o arquivo pode sair.

Se o VS Code pintar o fim do comando de vermelho, a ferramenta rodou. Esse aviso costuma ser o código de saída 1: existe achado alto.

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
git pull
python -m pip install -e .
```

Se a pasta do projeto estiver em outro lugar, o `cd` é o caminho dessa pasta.

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

Só `.xlsx` e `.xlsm`. A macro, quando existe, é **registrada e nunca executada**. Vínculo externo é **anotado e nunca aberto**.

| Achado | Risco usual |
| --- | --- |
| Aba oculta ou muito oculta (very hidden) | alto |
| Linha ou coluna oculta | médio |
| Comentário (nota antiga e thread) | médio |
| Nome definido que aponta para área oculta ou outra pasta | alto |
| Nome definido comum | info |
| Vínculo externo / hiperlink para outro arquivo | alto |
| Macro (`vbaProject.bin`) | médio |
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

As versões de `defusedxml` e `tarja` estão fixadas no `pyproject.toml`.

### Windows

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
oculto-scan proposta.xlsx --ignore .oculto-ignore
oculto-scan proposta.xlsx --baseline .oculto-baseline.json
oculto-scan proposta.xlsx --update-baseline .oculto-baseline.json
oculto-scan diff enviada.xlsx recebida.xlsx
oculto-scan diff enviada.xlsx recebida.xlsx --format html
```

A pasta é varrida de forma recursiva. Arquivos `~$...` (trava do Excel) e extensões que não sejam `.xlsx`/`.xlsm` são ignorados.

No terminal, o arquivo aparece uma vez como cabeçalho. Abaixo, cada achado é `aba › célula › tipo › risco`, com a explicação na linha seguinte. Alto sai em vermelho, médio em amarelo e info em ciano, quando a saída é um terminal. A cor desliga sozinha se a saída não for um TTY, se a variável `NO_COLOR` estiver definida, ou com `--no-color`. O JSON não muda e continua sempre mascarado.

`--format html` grava um relatório para ler e imprimir (no navegador, “Salvar como PDF”). Sem `--output`, o arquivo é `oculto-scan-relatorio.html` na pasta atual, e o caminho é impresso. O HTML é um arquivo só, com CSS embutido, sem JavaScript, sem fonte externa e sem rede. Sem `--show`, o valor no HTML fica mascarado.

| Código | Significado |
| --- | --- |
| 0 | Nada no nível de `--fail-on` ou acima |
| 1 | Há achado nesse nível ou acima |
| 2 | Caminho ausente, ignore ou linha de base inválidos |

`--fail-on` aceita `alto` (padrão), `medio`, `info` e `nenhum`. `medio` reprova médio e alto. Serve para pre-commit ou CI: o processo sai com erro quando o relatório tem achado grave.

`--show` revela o valor no terminal e no HTML. O JSON continua mascarado. Sem `--show`, CPF sai como `***.982.247-**`, segredo como prefixo e tamanho (`AKIA… (20 caracteres)`), caminho com o usuário trocado (`C:\Users\a***\...`).

`--format html --show` grava os valores reais (comentário, fórmula com a constante, autor dos metadados). Sem `--output`, o arquivo é `oculto-scan-relatorio-revelado.html`. Uma faixa vermelha no topo avisa para não enviar esse arquivo a terceiros. No Windows, `start oculto-scan-relatorio-revelado.html` abre no navegador.

Quando o Excel grava um comentário em thread, ele também deixa uma nota antiga de compatibilidade. O autor é `tc={GUID}` e o texto começa com “[Threaded comment]”, ou, no Excel em português, “[Comentário encadeado]” / “[Comentário em thread]”. Isso é o mesmo comentário. O relatório fica com um achado só (o thread) e nunca mostra `tc=...` como autor. Uma nota antiga de verdade, com texto próprio, continua no relatório.

## Comparar o que voltou (`diff`)

`oculto-scan diff ORIGINAL.xlsx RECEBIDO.xlsx` compara a planilha que você enviou com a que o colega devolveu. A saída segue o mesmo estilo: `aba › célula › tipo de mudança`, com antes e depois. `--format json` continua mascarado. `--format html` gera uma página com colunas Antes/Depois e um quadro **Quem salvou**. Sem `--output`, o arquivo é `oculto-scan-diff.html` (ou `oculto-scan-diff-revelado.html` com `--show`).

`--show` revela os valores no terminal e no HTML. No HTML, a faixa vermelha avisa para não enviar esse arquivo a terceiros. O JSON não revela.

Códigos: `0` sem diferença, `1` com diferença, `2` erro de leitura.

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
- Limite de zip bomb: tamanho do arquivo, tamanho descompactado, número de membros e razão de compressão. A leitura de cada membro também é limitada.
- Macro não é executada nem descompilada. O binário `vbaProject.bin` não é vasculhado em busca de segredo — de propósito.
- Vínculo externo não é resolvido, mesmo que o caminho exista na máquina.

## Limitações

- Só OOXML (`.xlsx`/`.xlsm`). `.xls`, PDF, DOCX e imagem ficam para depois.
- Aba oculta é risco alto porque o destinatário a revela com um clique. Linha e coluna oculta ficam em médio: planilha de engenharia esconde faixa o tempo todo. O que sobe para alto é a célula visível que **depende** dessa faixa.
- Fórmula compartilhada é deslocada pela referência relativa do mestre. `INDIRECT` não é avaliado. Validação de dados, cache de tabela dinâmica e objeto incorporado não são lidos.
- Rótulo bancário é procurado nas três primeiras linhas da coluna, ou na própria frase da célula.
- Salário em si não vira achado: quase toda coluna de preço é um número. Ele só ajuda o contexto do CPF.
- Entropia desligada por padrão.
- Um relatório limpo não é arquivo limpo.

## Roteiro v0.2

- PDF com tarja falsa (redação que ainda leva o texto por baixo).
- DOCX com revisão e comentário (tracked changes).
- EXIF e metadado de imagem.
- SARIF e uma GitHub Action pronta.
- Comparar arquivos de licitantes pelo autor e pelos metadados, como **indício** de autoria compartilhada — não prova de conluio.

## Licença e créditos

Apache-2.0. Veja `LICENSE` e `NOTICE`.

- [tarja](https://github.com/macmaia/tarja), Maria Alice Maia — CPF, CNPJ (inclusive alfanumérico) e PIS/NIS. Apache-2.0.
- [defusedxml](https://github.com/tiran/defusedxml) — leitura de XML hostil.
- [gitleaks](https://github.com/gitleaks/gitleaks) — os padrões de token copiados estão sob MIT, com atribuição no `NOTICE`. A regra de `senha` é deste projeto.

O oculto-scan não substitui revisão humana nem assessoria jurídica. Não publica pacote no PyPI nesta versão.
