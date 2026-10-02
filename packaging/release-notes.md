# oculto-scan para Windows

`oculto-scan-setup.exe` instala a janela offline que verifica se uma planilha (`.xlsx` ou `.xlsm`) pode vazar dados antes do envio. O atalho abre só a janela, sem a janela preta do terminal. `oculto-scan.exe` é o mesmo programa, sem instalador. `oculto-scan-cli.exe` é a linha de comando. Não é uma ferramenta de invasão. Não instala serviço e não envia o arquivo para lugar nenhum.

A assinatura de código ainda **não está ativa**. Estes arquivos **não são assinados**. O aviso do SmartScreen aparece por isso: em “Mais informações”, escolha “Executar assim mesmo”.

Para conferir, compare o SHA-256 abaixo com `Get-FileHash -Algorithm SHA256` no PowerShell.

Para desinstalar o instalador, use Adicionar ou remover programas. O portátil sai ao apagar o `.exe`.

## Code signing policy

A assinatura ainda não está ativa. Nenhum arquivo desta release é assinado pela SignPath Foundation. O passo `signpath/github-action-submit-signing-request` no GitHub Actions está desligado até existirem `SIGNPATH_API_TOKEN` e os IDs do projeto.

Quando a assinatura for ligada, o certificado pretendido é o da SignPath Foundation: “Free code signing provided by SignPath.io, certificate by SignPath Foundation”. Essa frase não descreve o arquivo publicado agora.

- Author (autor): Henderson Gomes (@HendersonGomes)
- Reviewer (revisor): Henderson Gomes (@HendersonGomes)
- Approver (aprovador): Henderson Gomes (@HendersonGomes)

Cada release que venha a ser assinada precisa de aprovação manual do aprovador. O build usa apenas runners hospedados pelo GitHub, a partir do código deste repositório, sem cache não verificado.

This program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it.

O programa só lê a planilha escolhida e grava o relatório neste computador. defusedxml, tarja e oletools não enviam dados.
