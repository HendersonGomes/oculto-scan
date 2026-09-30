# oculto-scan

Scanner de vazamento de dados em arquivos de obra (planilhas, propostas, medições). Offline, open source.

A v0.1 lê planilhas `.xlsx` e `.xlsm` **antes** do envio ou da publicação: proposta de preços, boletim de medição, orçamento, laudo. O relatório junta, num lugar só, o que um engenheiro ou um auditor olharia na pasta — aba escondida, fórmula que puxa custo oculto, vínculo para `C:\Users\...`, autor nos metadados, CPF de empregado, senha deixada numa célula.

**nenhum achado não significa arquivo limpo.**

O oculto-scan não está no PyPI. Instale a partir deste repositório.

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

## Instalação

Python 3.10 ou mais novo.

```bash
python -m pip install -e ".[dev]"
oculto-scan --help
```

As versões de `defusedxml` e `tarja` estão fixadas no `pyproject.toml`.

## Uso

```bash
oculto-scan proposta.xlsx
oculto-scan pasta-de-licitacao/
oculto-scan medicao.xlsm --format json
oculto-scan orcamento.xlsx --fail-on medio
oculto-scan proposta.xlsx --show
oculto-scan proposta.xlsx --ignore .oculto-ignore
oculto-scan proposta.xlsx --baseline .oculto-baseline.json
oculto-scan proposta.xlsx --update-baseline .oculto-baseline.json
```

A pasta é varrida de forma recursiva. Arquivos `~$...` (trava do Excel) e extensões que não sejam `.xlsx`/`.xlsm` são ignorados.

Cada linha do texto segue `arquivo › aba › célula › tipo › risco`, com uma explicação curta. O JSON repete o mesmo conteúdo, sempre mascarado.

| Código | Significado |
| --- | --- |
| 0 | Nada no nível de `--fail-on` ou acima |
| 1 | Há achado nesse nível ou acima |
| 2 | Caminho ausente, ignore ou linha de base inválidos |

`--fail-on` aceita `alto` (padrão), `medio`, `info` e `nenhum`. `medio` reprova médio e alto. Serve para pre-commit ou CI: o processo sai com erro quando o relatório tem achado grave.

`--show` revela o valor **só no texto do terminal**. O JSON continua mascarado, para não gravar CPF ou senha em artefato de CI. Sem `--show`, CPF sai como `***.982.247-**`, segredo como prefixo e tamanho (`AKIA… (20 caracteres)`), caminho com o usuário trocado (`C:\Users\a***\...`).

## Exemplo

Relatório real da v0.1 sobre uma planilha sintética (nomes fictícios, CPF com dígito calculado, sem dado de pessoa real). A fórmula era `Custos!B2*1.35`; o fator não aparece. O caminho era `C:\Users\ana.sintetica\...`.

```text
proposta-sintetica.xlsx › — › — › vínculo externo › alto
  Vínculo externo ou hiperlink para outro arquivo. Caminhos locais (C:\Users\...) identificam a máquina e podem apontar para uma planilha de custo que não deveria sair.
  valor: file:///C:/Users/a***/Documentos/custos-internos.xlsx
proposta-sintetica.xlsx › — › CustoUnitario › nome definido › alto
  Nome definido aponta para área oculta ou para outra pasta. Uma célula visível pode usar esse nome sem mostrar a origem.
  valor: Custos!$B$2
proposta-sintetica.xlsx › Custos › — › aba oculta › alto
  Aba oculta. Em proposta, orçamento ou edital isso costuma esconder custo, margem ou memória de cálculo, e o destinatário revela a aba com um clique.
proposta-sintetica.xlsx › Margem › — › aba muito oculta › alto
  Aba muito oculta (very hidden). Não aparece na lista de abas; só sai desse estado por VBA ou pelo editor de XML. Sinal forte de conteúdo que não deveria seguir com o arquivo.
proposta-sintetica.xlsx › Medicao › A4 › segredo › alto
  Possível segredo (aws-access-token). Chave, token ou senha não devem viajar dentro de proposta, medição ou laudo.
  valor: AKIA… (20 caracteres)
proposta-sintetica.xlsx › Medicao › B2 › CPF › alto
  Lista de CPFs com dígito verificador válido e contexto de pessoa (cabeçalho, rótulo ou texto como funcionário, PIS ou salário). Vários CPFs no mesmo lugar indicam relação de empregados.
  valor: ***.982.247-**
proposta-sintetica.xlsx › Medicao › B3 › CPF › alto
  Lista de CPFs com dígito verificador válido e contexto de pessoa (cabeçalho, rótulo ou texto como funcionário, PIS ou salário). Vários CPFs no mesmo lugar indicam relação de empregados.
  valor: ***.533.447-**
proposta-sintetica.xlsx › Medicao › E2 › dado bancário › alto
  Dado bancário identificado pelo rótulo «agência». Não há validação genérica de dígito: cada banco usa a sua.
  valor: **34 (4 dígitos)
proposta-sintetica.xlsx › Medicao › F2 › dado bancário › alto
  Dado bancário identificado pelo rótulo «conta». Não há validação genérica de dígito: cada banco usa a sua.
  valor: *****01 (7 dígitos)
proposta-sintetica.xlsx › Proposta › C2 › fórmula oculta › alto
  Célula visível cuja fórmula referencia aba, linha ou coluna oculta (Custos!B2). O número mostrado pode depender de custo ou margem que não aparece na impressão.
  valor: Custos!B2*[n]
proposta-sintetica.xlsx › — › — › macro › médio
  A pasta contém macro (vbaProject.bin). O oculto-scan não executa e não descompila macro; só registra a presença.
  valor: vbaProject.bin
proposta-sintetica.xlsx › — › Company › metadado › médio
  Metadado do arquivo. Autor, empresa e último editor identificam quem preparou a proposta e, entre licitantes, são indício de autoria compartilhada — não prova de conluio.
  valor: Co********* Ex***** Lt**
proposta-sintetica.xlsx › — › creator › metadado › médio
  Metadado do arquivo. Autor, empresa e último editor identificam quem preparou a proposta e, entre licitantes, são indício de autoria compartilhada — não prova de conluio.
  valor: Au**** Si*******
proposta-sintetica.xlsx › — › lastModifiedBy › metadado › médio
  Metadado do arquivo. Autor, empresa e último editor identificam quem preparou a proposta e, entre licitantes, são indício de autoria compartilhada — não prova de conluio.
  valor: Re***** Si*******
proposta-sintetica.xlsx › Medicao › C2 › PIS › médio
  PIS/NIS/PASEP com dígito verificador válido e contexto de trabalhador. Pode fazer parte de folha ou medição com relação de empregados.
  valor: ***.56437.**-*
proposta-sintetica.xlsx › Medicao › D2 › dado bancário › médio
  Dado bancário identificado pelo rótulo «banco». Não há validação genérica de dígito: cada banco usa a sua.
  valor: **01 (3 dígitos)
proposta-sintetica.xlsx › Proposta › B2 › comentário › médio
  Há comentário em thread nesta célula. Comentário interno muitas vezes descreve margem, premissa ou ressalva que não está na célula visível.
  valor: texto mascarado (43 caracteres)
proposta-sintetica.xlsx › Proposta › C2 › comentário › médio
  Há nota antiga nesta célula. Autor: Au**** Si*******. Comentário interno muitas vezes descreve margem, premissa ou ressalva que não está na célula visível.
  valor: texto mascarado (37 caracteres)
proposta-sintetica.xlsx › Proposta › E:E › coluna oculta › médio
  Coluna ou faixa de colunas oculta. Em planilha de preço isso é um lugar típico de custo e BDI.
proposta-sintetica.xlsx › — › title › metadado › info
  Metadado descritivo do arquivo (título, assunto ou semelhante).
  valor: Pr****** si*******
proposta-sintetica.xlsx › Medicao › G2 › CNPJ › info
  CNPJ válido (numérico ou alfanumérico). Informativo: em proposta, medição e documento fiscal o CNPJ costuma ser obrigatório. O formato alfanumérico segue a IN RFB nº 2.229/2024; confira a norma antes de confiar no achado.
  valor: **.222.333/0001-**
proposta-sintetica.xlsx › Medicao › H2 › CNPJ › info
  CNPJ válido (numérico ou alfanumérico). Informativo: em proposta, medição e documento fiscal o CNPJ costuma ser obrigatório. O formato alfanumérico segue a IN RFB nº 2.229/2024; confira a norma antes de confiar no achado.
  valor: **.ABC.345/01DE-**
proposta-sintetica.xlsx › Proposta › C2 › constante › info
  Fórmula com constante numérica. Pode revelar o método de margem ou BDI (por exemplo um fator multiplicando o custo). É informativo: constante sozinha não prova vazamento.
  valor: Custos!B2*[n]
---
Resumo: 10 alto, 9 médio, 4 info (23 no total). 0 ignorado(s).
nenhum achado não significa arquivo limpo.
```

O código de saída foi 1, porque o padrão de `--fail-on` é `alto`.

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
- Valor mascarado em toda saída, salvo `--show` no texto do terminal.
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
