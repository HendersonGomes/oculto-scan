# Segurança da própria ferramenta

[Voltar ao README](../README.md)

Falha no programa (não um achado na planilha) segue o [SECURITY.md](../SECURITY.md). Não abra issue pública.

- Sem rede. Não há cliente HTTP no código, e a tarja não tem dependência de execução.
- Valor mascarado em toda saída, salvo `--show` no terminal e no HTML. O JSON continua mascarado.
- XML com defusedxml (sem entidade externa, sem expansão de DTD).
- Zip bomb continua recusado: razão de compressão, número de partes e membro criptografado. Tamanho acima do limite (64 MiB no total, 32 MiB por parte) é «não analisado», código 3, com o limite na mensagem. `--max-mb` sobe esse limite de propósito. A leitura de cada parte também é limitada.
- Relatório HTML e JSON no disco ficam com permissão restrita (só quem rodou) quando o sistema permite. A saída do terminal é UTF-8.
- Macro não é executada e a senha do editor VBA não é testada. Sem o extra `oletools`, o binário não é lido e a saída é 3. Com o extra, só o texto do VBA é lido (módulos, palavras suspeitas e indicadores). O binário não é vasculhado em busca de segredo.
- Vínculo externo não é resolvido, mesmo que o caminho exista na máquina.

A política de assinatura dos arquivos de Windows está em [code-signing-policy.md](code-signing-policy.md). Os arquivos publicados não são assinados.
