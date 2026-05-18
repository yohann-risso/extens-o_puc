# Organização Financeira na Prática

Aplicativo feito em Python com Streamlit para organizar entradas, gastos, dívidas, metas e histórico financeiro. A proposta é ser uma ferramenta simples para visualizar o orçamento do mês, sem transformar o projeto em um sistema financeiro complexo.

## O que dá para fazer

- Registrar entradas e gastos do mês.
- Separar gastos fixos e variáveis.
- Marcar compras parceladas.
- Acompanhar dívidas e parcelas.
- Ver se o mês fechou com sobra ou falta.
- Criar uma meta e calcular quanto guardar por mês.
- Simular dinheiro parado, poupança e uma aplicação simples.
- Gerar histórico anual e exportar relatórios em Excel, PDF ou JSON.
- Consultar a Política de Privacidade e LGPD dentro do próprio app.

## Estrutura do código

O arquivo principal é o `app.py`. Ele foi deixado em um único arquivo porque o projeto é pequeno, mas está separado por funções:

- constantes e categorias usadas no app;
- funções de formatação de moeda, data, tabelas e gráficos;
- funções de limpeza dos dados digitados;
- cálculos de receitas, gastos, dívidas, metas e simulação;
- exportação para Excel, PDF e JSON;
- telas do Streamlit.

As funções possuem docstrings curtas para explicar a finalidade de cada parte. Nos trechos menos diretos, como repetição de gastos fixos no histórico e geração manual do PDF, também existem comentários no próprio código.

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

## Publicação no Streamlit Cloud

Para publicar na web, suba estes arquivos para um repositório no GitHub:

```text
app.py
requirements.txt
README.md
PRIVACIDADE_LGPD.md
```

Depois, acesse `https://share.streamlit.io`, conecte sua conta do GitHub, selecione o repositório e informe `app.py` como arquivo principal do aplicativo.

O app não usa banco de dados. No Streamlit Cloud, os dados preenchidos ficam apenas na sessão de uso. Para continuar depois, o usuário deve baixar Excel ou JSON na aba **Histórico** e salvar no próprio dispositivo. O JSON pode ser carregado novamente pelo próprio app.

## Privacidade

A política completa está no arquivo `PRIVACIDADE_LGPD.md` e também na aba **Privacidade e LGPD** do app.

## Fluxo de uso

1. Registre entradas e gastos em **Registrar**.
2. Acompanhe parcelas em **Dívidas**.
3. Veja o saldo em **Resultado do mês**.
4. Crie uma meta simples em **Metas**.
5. Compare formas de guardar em **Guardando dinheiro**.
6. Baixe Excel, PDF ou JSON em **Histórico**.
7. Consulte privacidade e LGPD na aba **Privacidade e LGPD**.

As simulações e comparações servem apenas como referência para estudo e organização pessoal.
