# Code signing policy

[Voltar ao README](../README.md)

A assinatura de código ainda **não está ativa**. O `oculto-scan.exe` publicado hoje **não é assinado** e não deve ser descrito como assinado. Esta seção deixa o projeto pronto para pedir a assinatura gratuita da SignPath Foundation. O passo de assinatura no GitHub Actions está desligado até existirem o token e os IDs.

Quando a assinatura for ligada, a atribuição exigida será: “Free code signing provided by SignPath.io, certificate by SignPath Foundation”. Essa frase **não** vale para os arquivos publicados agora.

- Author (autor): Henderson Gomes (@HendersonGomes)
- Reviewer (revisor): Henderson Gomes (@HendersonGomes)
- Approver (aprovador): Henderson Gomes (@HendersonGomes)

Cada release que venha a ser assinada precisa de aprovação manual do aprovador. O build roda só em runners hospedados pelo GitHub, a partir do código deste repositório, sem cache não verificado. O nome do produto no `.exe` é `oculto-scan` e a versão é a mesma em todos os campos do arquivo.

This program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it.

O oculto-scan não tem cliente de rede. Ele lê a planilha que você escolhe e grava o relatório neste computador. defusedxml, tarja e oletools não enviam dados. O programa é uma verificação de privacidade e de vazamento de dados antes do envio. Não explora falhas e não altera o sistema.
