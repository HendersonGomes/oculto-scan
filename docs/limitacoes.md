# Limitações

[Voltar ao README](../README.md)

- Só OOXML (`.xlsx`/`.xlsm`). Um `.xls` ou `.csv` passado no comando é «não analisado» (código 3). Dentro de uma pasta, essas extensões continuam de fora. PDF, DOCX e imagem ficam para depois.
- Sem `pip install -e ".[macro]"`, a macro de um `.xlsm` não é lida (código 3). Com o extra, a leitura é estática: nada é executado. Projeto VBA ilegível também fica como não analisado, sem tentativa de senha.
- Aba oculta é risco alto porque o destinatário a revela com um clique. Linha e coluna oculta ficam em médio: planilha de engenharia esconde faixa o tempo todo. O que sobe para alto é a célula visível que **depende** dessa faixa.
- Fórmula compartilhada é deslocada pela referência relativa do mestre. `INDIRECT` não é avaliado. Validação de dados, cache de tabela dinâmica e objeto incorporado não são lidos.
- O cabeçalho de CPF e de dado bancário é a célula de texto mais próxima acima na coluna, mesmo que não seja a linha 1. Se a coluna não tem cabeçalho, vale o rótulo à esquerda. Cabeçalho Telefone, Código ou Quantidade não vira alerta de CPF.
- Salário em si não vira achado: quase toda coluna de preço é um número. Ele só ajuda o contexto do CPF.
- Entropia desligada por padrão.
- Um relatório limpo não é arquivo limpo.

<a id="copia-limpa"></a>

## Cópia limpa

- A limpeza não recalcula fórmula; usa o valor que já estava em cache. Sem cache, a célula fica vazia.
- Hiperlink de célula, conexão de dados, impressora e formato que esconde número continuam na cópia.
- Uma fórmula com `INDIRETO` pode não ser reconhecida como dependente da área oculta.
- O desenho legado do comentário sai junto; um controle de formulário nesse mesmo desenho também sai.
- A macro não é executada. Ela só sai com `--remover-macros`.
- A cópia passa de novo pelo limite de zip (tamanho, quantidade de partes e razão de compressão).

O uso do comando está em [Uso › Limpar uma cópia](uso.md#limpar-uma-copia).
