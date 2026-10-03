<p align="center">
  <img src="packaging/oculto-scan.png" alt="Ícone do oculto-scan" width="96">
</p>

<h1 align="center">oculto-scan</h1>

<p align="center"><strong>Ache o que vaza na planilha antes de enviar a proposta</strong></p>

<p align="center">
  <a href="https://github.com/HendersonGomes/oculto-scan/actions/workflows/ci.yml"><img src="https://github.com/HendersonGomes/oculto-scan/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/HendersonGomes/oculto-scan/releases/latest"><img src="https://img.shields.io/github/v/release/HendersonGomes/oculto-scan" alt="Release"></a>
  <a href="https://github.com/HendersonGomes/oculto-scan/blob/main/LICENSE"><img src="https://img.shields.io/github/license/HendersonGomes/oculto-scan" alt="Licença Apache-2.0"></a>
</p>

<p align="center">
  <a href="https://github.com/HendersonGomes/oculto-scan/releases/latest/download/oculto-scan-setup.exe"><img src="https://img.shields.io/badge/Baixar-oculto--scan--setup.exe-E6A317?style=for-the-badge&logo=windows&logoColor=0E2433" alt="Baixar oculto-scan-setup.exe"></a>
</p>

<a id="aviso-windows"></a>

> [!IMPORTANT]
> **O Windows pode avisar ou bloquear o download. Não é vírus.**
> O programa ainda não tem assinatura digital de código (certificado pago). O Windows SmartScreen e o navegador desconfiam de todo programa novo, sem assinatura e com poucos downloads; o aviso diminui conforme mais gente baixa e vai sumir quando a assinatura gratuita para open source (SignPath) for aprovada.
>
> No Edge ou no Chrome, se aparecer «não é baixado com frequência» ou «pode ser perigoso», clique nos três pontinhos ou na seta › **Manter** › **Manter assim mesmo**. Ao abrir, na tela azul «O Windows protegeu o computador», clique em **Mais informações** › **Executar assim mesmo**.
>
> Como ter certeza: o código é aberto e o arquivo é compilado pela GitHub Actions na [página de releases](https://github.com/HendersonGomes/oculto-scan/releases). Confira o SHA-256 com `Get-FileHash` no [guia para iniciantes](docs/guia-iniciante.md#conferir-o-sha-256). Se quiser, envie o arquivo ao [VirusTotal](https://www.virustotal.com/).

<p align="center"><strong>100% offline · grátis · open source</strong></p>

<p align="center">Quem prefere não instalar baixa o <a href="https://github.com/HendersonGomes/oculto-scan/releases/latest/download/oculto-scan.exe">oculto-scan.exe portátil</a>. Ele abre só a janela, sem a janela preta do terminal. O <a href="https://github.com/HendersonGomes/oculto-scan/releases/latest/download/oculto-scan-cli.exe">oculto-scan-cli.exe</a> é o mesmo programa na linha de comando.</p>

<p align="center">
  <img src="docs/img/janela.png" alt="Janela do oculto-scan v0.2 com o medidor de risco" width="760">
</p>

## Para que serve

- Enviou a planilha e ficou na dúvida do que foi alterado?
- Mandou um boletim de medição e não sabe o que o fiscal ou a empresa mudou?
- Vai enviar uma proposta sigilosa de licitação?
- Tem CPF, nome ou CNPJ que não deveria aparecer (LGPD)?

**Comparar dois arquivos** (`oculto-scan diff`) mostra valor, fórmula, estrutura (aba, linha, coluna ou vínculo) e metadado que mudaram, com a aba e a célula, e quem salvou por último. A análise aponta o que pode vazar, como CPF, CNPJ e autor. A cópia limpa tira comentário, autor e vínculo antes do envio; CPF dentro da célula fica para você revisar.

Isso ajuda a encontrar dado pessoal. Não é conformidade com a LGPD e não substitui revisão humana nem assessoria jurídica. Quem salvou é só o último que gravou o arquivo: esse nome pode ser editado, e abrir sem salvar não deixa rastro. O detalhe está em [Comparar o que voltou](docs/uso.md#comparar-o-que-voltou-diff).

Lê a planilha de proposta, medição, orçamento ou laudo (`.xlsx` e `.xlsm`) **antes** do envio e junta, num lugar só, o que um engenheiro olharia na pasta.

**nenhum achado não significa arquivo limpo.**

**Novidades da v0.2:** cópia limpa, pasta onde a planilha foi salva (com aviso de mesmo usuário ao comparar), planilhas pesadas mais rápidas com progresso e cancelar, e relatório agrupado e leve. Veja o [CHANGELOG](CHANGELOG.md) e as [Releases](https://github.com/HendersonGomes/oculto-scan/releases).

## O que ele encontra

| | |
| --- | --- |
| 🙈 | Abas, linhas e colunas ocultas, e a fórmula visível que puxa essa área |
| 💬 | Comentários e notas |
| 🪪 | CPF, CNPJ, PIS e dado bancário com contexto |
| 🗂️ | Caminho de rede, usuário do Windows, SharePoint e impressora |
| 📁 | Pasta onde a planilha foi salva (usuário, OneDrive ou UNC) |
| 👤 | Metadados: autor, empresa e último editor |
| 🔗 | Vínculos externos e hiperlinks (anotados, nunca abertos) |
| ⚙️ | Macros (lidas, nunca executadas) |
| 🔑 | Senha, token e chave |

A tabela de risco está em [Uso](docs/uso.md#o-que-a-ferramenta-detecta).

## Novo na v0.2: cópia limpa

**Gerar cópia limpa** grava outro arquivo (`proposta-limpa.xlsx`). O original não muda.

Saem comentários, autor, empresa, dado pessoal nos metadados e vínculos externos. Aba oculta e macro só saem se você marcar.

CPF e senha dentro da célula ficam para revisão humana. O medidor passa a mostrar o risco da cópia.

<p align="center">
  <img src="docs/img/limpar-antes.png" alt="Antes: medidor em Alto, na planilha original" width="49%">
  <img src="docs/img/limpar-depois.png" alt="Depois: medidor em Médio, na cópia limpa" width="49%">
</p>

Regras: [Limpar uma cópia](docs/uso.md#limpar-uma-copia).

## Como usar em 3 passos

1. **Baixe** o `oculto-scan-setup.exe` no botão acima.
2. **Abra** o instalador. O atalho do menu Iniciar abre a janela.
3. **Escolha** a planilha e clique em **Escanear**.

O aviso do Windows no download está no [bloco do topo](#aviso-windows). Para atualizar, baixe o setup novo e instale por cima.

Hash, desinstalar e o caminho sem terminal: [Guia para iniciantes](docs/guia-iniciante.md).

## Para quem usa terminal

```bash
python -m pip install -e ".[macro]"
oculto-scan proposta.xlsx
```

No Windows, `oculto-scan gui` usa o `pythonw` e não abre o console. Comandos, `diff`, ignore e códigos de saída: [Uso](docs/uso.md).

## Privacidade

Nada sai do computador. Não há telemetria nem cliente de rede: a planilha é lida aqui e o relatório fica neste disco.
A macro não é executada e o vínculo externo não é aberto.

## Feito com

<p align="center">
  <img alt="Cursor" src="https://img.shields.io/badge/Cursor-agentes_na_nuvem-000000?logo=cursor&logoColor=white">
  <img alt="Claude Code" src="https://img.shields.io/badge/Claude_Code-000000?logo=anthropic&logoColor=white">
  <img alt="Claude" src="https://img.shields.io/badge/Claude-d97757?logo=anthropic&logoColor=white">
  <img alt="Grok" src="https://img.shields.io/badge/Grok-000000?logo=x&logoColor=white">
  <br>
  <img alt="GitHub" src="https://img.shields.io/badge/GitHub-Actions_%C2%B7_Releases-181717?logo=github&logoColor=white">
  <img alt="Python e Tkinter" src="https://img.shields.io/badge/Python_+_Tkinter-3776AB?logo=python&logoColor=white">
  <img alt="PyInstaller" src="https://img.shields.io/badge/PyInstaller-3776AB?logo=python&logoColor=white">
  <img alt="Inno Setup" src="https://img.shields.io/badge/Inno_Setup-217346">
</p>

Desenvolvido por Henderson Gomes · NeoRise Technology, com auxílio de ferramentas de IA.

## Apoie

Checagem de arquivo antes do envio e apoio ao projeto: [GitHub Sponsors](https://github.com/sponsors/HendersonGomes). O contato também é pelo [perfil no GitHub](https://github.com/HendersonGomes) ou pelo perfil dele no LinkedIn.

Dúvidas: use o menu Ajuda > Contato da janela ou [abra uma issue](https://github.com/HendersonGomes/oculto-scan/issues).

## Comunidade

[Contribuir](CONTRIBUTING.md) · [Código de conduta](CODE_OF_CONDUCT.md) · [Segurança](SECURITY.md) · [Política de assinatura de código](docs/code-signing-policy.md)

## Licença e créditos

Apache-2.0. Veja [LICENSE](LICENSE) e [NOTICE](NOTICE).

- [tarja](https://github.com/macmaia/tarja), Maria Alice Maia — CPF, CNPJ (inclusive alfanumérico) e PIS/NIS. Apache-2.0.
- [defusedxml](https://github.com/tiran/defusedxml) — leitura de XML hostil.
- [gitleaks](https://github.com/gitleaks/gitleaks) — padrões de token sob MIT, com atribuição no `NOTICE`. A regra de `senha` é deste projeto.
- [oletools](https://github.com/decalage2/oletools) — leitura estática de macro. BSD. A macro não é executada.
- [PyInstaller](https://pyinstaller.org) — só para montar o `.exe` de Windows. O executável não usa UPX.

O oculto-scan não substitui revisão humana nem assessoria jurídica. Não publica pacote no PyPI. Não é ferramenta de invasão.

## Mais documentação

- [Guia para iniciantes](docs/guia-iniciante.md) — baixar, hash, passo a passo e planilha de demonstração
- [Uso](docs/uso.md) — instalação, atualizar, comandos, cópia limpa, diff, exemplo e ignore
- [Limitações](docs/limitacoes.md)
- [Segurança da ferramenta](docs/seguranca-da-ferramenta.md)
- [Roteiro](docs/roteiro.md)
