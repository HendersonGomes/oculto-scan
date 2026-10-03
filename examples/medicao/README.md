# Boletim de medição — exemplo fictício

Dois arquivos inventados para ver o modo Comparar. Não há obra, pessoa nem preço reais. Os códigos e os valores não são do SINAPI oficial.

- `medicao-03-enviada.xlsx` — a construtora enviou. Salvo por Engenheira Ana Exemplo, na pasta `C:/Users/construtora/Desktop`.
- `medicao-03-devolvida.xlsx` — o fiscal devolveu. Salvo por Fiscal João Exemplo, na pasta `C:/Users/fiscal/OneDrive - Prefeitura/Medicoes`.

Na planilha devolvida, de propósito:

- o concreto fck 25 passou de 48,5 para 42 m³, com uma nota do fiscal na quantidade
- o preço unitário do aço CA-50 mudou
- a fórmula do Total da forma virou o número fixo 5.000
- a linha do lastro de concreto magro foi ocultada

Na pasta destes arquivos:

```bash
oculto-scan diff medicao-03-enviada.xlsx medicao-03-devolvida.xlsx
```

Na janela, use **Comparar dois arquivos**. Sem «Mostrar valores reais», os números saem mascarados.
