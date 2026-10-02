# Guia para iniciantes (Windows)

[Voltar ao README](../README.md)

Este caminho é para quem nunca abriu um terminal. O atalho mais curto é o instalador: baixe o `oculto-scan-setup.exe`, abra e escolha a planilha. Os blocos abaixo servem para quem vai usar o código ou o terminal. Cada bloco é um comando: copie, cole e aperte Enter. Espere a resposta antes do próximo.

## Baixar o programa para Windows

Quem não quer instalar Python usa o instalador. O arquivo é `oculto-scan-setup.exe`:

https://github.com/HendersonGomes/oculto-scan/releases/latest

O botão no [README](../README.md) baixa esse instalador. O atalho do menu Iniciar abre só a janela. O `oculto-scan.exe` portátil faz o mesmo, sem console. O `oculto-scan-cli.exe`, na mesma página, é para o terminal. Os arquivos ainda **não são assinados**. A macro já vem dentro do programa. Nada é enviado para a internet.

### Aviso do SmartScreen

O Windows pode dizer que o aplicativo não é reconhecido. Isso acontece porque a assinatura ainda não está ativa, não porque o arquivo foi alterado no caminho.

1. Na janela azul, clique em **Mais informações**.
2. Clique em **Executar assim mesmo**.

Se o botão não aparecer, confira o SHA-256 antes de seguir. A política de assinatura está em [code-signing-policy.md](code-signing-policy.md).

### Conferir o SHA-256

Cada release traz o hash ao lado do arquivo (`.sha256` e a mesma linha nas notas). No PowerShell, na pasta onde o arquivo foi salvo:

```powershell
Get-FileHash -Algorithm SHA256 .\oculto-scan-setup.exe
```

```powershell
Get-FileHash -Algorithm SHA256 .\oculto-scan.exe
```

```powershell
Get-FileHash -Algorithm SHA256 .\oculto-scan-cli.exe
```

O hash tem de ser igual ao da release. Se for diferente, apague o arquivo e baixe de novo.

### Desinstalar

Se usou o instalador, abra **Adicionar ou remover programas**, procure `oculto-scan` e escolha Desinstalar. Não há serviço. Se baixou o portátil, apague o `oculto-scan.exe` e, se estiver na pasta, o `oculto-scan-cli.exe`.

### Abrir a janela com Python

Na pasta do projeto, com o ambiente virtual ativado:

```powershell
python -m pip install -e ".[macro]"
oculto-scan gui
```

O mesmo comando é `oculto-scan-gui`. No Windows, esse atalho do `pip` usa o `pythonw` e não abre o console. `oculto-scan` continua no terminal. A opção de macro é necessária para ler VBA. O `.exe` já inclui essa parte. A janela mostra um medidor (Limpo, Baixo, Médio ou Alto) e cartões curtos. O relatório completo continua no HTML. O arquivo entra pelo botão **Escolher**, e **Escanear** roda a análise neste computador. Depois do scan, **Gerar cópia limpa** grava outro arquivo e o medidor passa a mostrar o risco dessa cópia. Arrastar e soltar ficou de fora: no Windows isso exige um gancho na janela, e esse tipo de gancho é o que o antivírus costuma marcar.

## Passo a passo

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

Planilha `.xlsm` pode ter macro. A ferramenta não executa a macro e não tenta senha. Para ler o código VBA, instale o extra (veja [Uso](uso.md#instalação-técnica)). Sem ele, o relatório diz que a macro não foi analisada e o programa termina com código 3.

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

Se `oculto-scan` não for reconhecido, troque por `python -m oculto_scan diff`. O relatório diz o que mudou e quem salvou por último. Ele não mostra IP: o arquivo não guarda isso. Quem só abriu e não salvou não deixa rastro. O detalhe está em [Uso › Comparar o que voltou](uso.md#comparar-o-que-voltou-diff).

### 8. Atualizar para uma versão nova

A seção [Como atualizar](uso.md#como-atualizar) tem os caminhos: instalar o setup por cima, baixar o `.exe` portátil de novo, ou `git pull` na pasta do clone. O programa não procura versão nova sozinho.

## Monte uma planilha de demonstração

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
