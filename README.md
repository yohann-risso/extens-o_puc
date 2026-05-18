# Organização Financeira na Prática

Aplicativo em Python e Streamlit para organizar entradas, gastos, parcelas, metas e histórico financeiro de forma simples.

## O que o app tem

- **Início** com resumo visual do app.
- **Registrar** para adicionar entradas e gastos rapidamente.
- Tabela principal com data, tipo, descrição, categoria e valor.
- Opção **Mostrar detalhes** para fixos, datas, parcelas e observações.
- **Resultado do mês** com entrou, saiu, sobrou ou faltou.
- Alertas curtos e sugestões rápidas baseadas nos lançamentos.
- **Dívidas** para acompanhar parcelas do mês.
- **Metas** para calcular quanto guardar por mês.
- **Guardando dinheiro** para comparar dinheiro parado, poupança e aplicação simples.
- **Histórico** com resumo mensal, evolução anual, Excel e PDF.

## Instalação

Abra o terminal na pasta do projeto e execute:

```bash
pip install -r requirements.txt
```

## Como executar

Use:

```bash
streamlit run app.py
```

Normalmente o app abre em:

```text
http://localhost:8501
```

No Windows, também é possível dar dois cliques em:

```text
executar_app.bat
```

## Fluxo de uso

1. Registre entradas e gastos em **Registrar**.
2. Acompanhe parcelas em **Dívidas**.
3. Veja o saldo em **Resultado do mês**.
4. Crie uma meta simples em **Metas**.
5. Compare formas de guardar em **Guardando dinheiro**.
6. Baixe Excel ou PDF em **Histórico**.

As comparações possuem caráter informativo.
