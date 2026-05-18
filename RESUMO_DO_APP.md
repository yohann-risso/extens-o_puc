# Resumo do App

## Nome

**Organização Financeira na Prática**

## Ideia principal

O app foi feito em Python com Streamlit para ajudar no controle financeiro pessoal de um jeito simples. Ele serve para registrar entradas, gastos, dívidas, metas e acompanhar o resultado do mês.

A proposta é educativa. O aplicativo não pede login, não usa dados bancários e não faz recomendação de investimento. As comparações de dinheiro guardado são apenas uma referência para estudo e planejamento.

## Público pensado

- Pessoas começando a organizar a vida financeira.
- Participantes de oficinas ou projetos de extensão.
- Estudantes que querem visualizar melhor receitas, gastos e metas.
- Usuários que preferem uma ferramenta mais simples do que uma planilha grande.

## Tecnologias

- **Python** para a lógica principal.
- **Streamlit** para a interface web.
- **Pandas** para tratar tabelas e cálculos.
- **Plotly** para os gráficos.
- **OpenPyXL** para gerar arquivos Excel.
- API pública do **Banco Central do Brasil** para buscar referências como Selic e TR.
- **Streamlit Cloud** como opção de publicação web.

## Abas do app

1. **Início**: apresenta o app e os principais usos.
2. **Registrar**: cadastro de entradas e gastos.
3. **Resultado do mês**: mostra entrou, saiu, sobrou ou faltou.
4. **Dívidas**: acompanha parcelas e compromissos do mês.
5. **Metas**: calcula quanto guardar por mês.
6. **Guardando dinheiro**: compara dinheiro parado, poupança e aplicação simples.
7. **Histórico**: mostra evolução anual, exporta Excel/PDF/JSON e carrega backup JSON salvo pelo usuário.
8. **Privacidade e LGPD**: apresenta a política de privacidade do projeto.

## Como os dados são tratados

Os lançamentos passam por uma etapa de normalização antes dos cálculos. Essa etapa evita erro com data vazia, valor inválido, categoria sem preenchimento e campos de parcela incompletos.

Os gastos fixos possuem data de início e, se necessário, data de fim. No histórico anual, esses gastos são repetidos mês a mês dentro do período escolhido. Isso ajuda a simular melhor contas recorrentes como aluguel, internet, salário e assinaturas.

## Principais cálculos

- Total de entradas.
- Total de gastos fixos.
- Total de gastos variáveis.
- Total de parcelas cadastradas.
- Saldo final do mês.
- Percentual do dinheiro comprometido.
- Categoria de gasto que mais pesou.
- Valor mensal necessário para atingir uma meta.
- Evolução aproximada de dinheiro guardado ao longo do tempo.

## Exportações

O app gera:

- Excel geral com lançamentos, dívidas, resumo, meta, sugestões e simulação.
- PDF simples com o resumo financeiro.
- JSON com backup dos lançamentos, dívidas e configurações principais para o usuário salvar no próprio dispositivo.
- Excel anual com resumo mês a mês, totais por ano, categorias e compras parceladas.

## Privacidade e Streamlit Cloud

O app não usa login nem banco de dados. No Streamlit Cloud, as informações digitadas ficam na sessão de uso e não são armazenadas permanentemente pelo projeto.

Para continuar depois, o usuário deve baixar Excel ou JSON e salvar o arquivo no próprio computador ou dispositivo pessoal. O JSON pode ser carregado novamente no app.

## Observação

O projeto foi mantido em um arquivo principal porque ainda é pequeno. Mesmo assim, as funções foram separadas por assunto para deixar o código mais fácil de ler, alterar e apresentar.
