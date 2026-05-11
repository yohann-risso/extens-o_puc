# Organização Financeira na Prática

Aplicativo em Python e Streamlit para organização financeira pessoal com linguagem simples, visual moderno e uso contínuo.

O app foi pensado para pessoas com pouco conhecimento técnico. Ele ajuda a registrar entradas e gastos, marcar o que é fixo, acompanhar dívidas, montar metas, gerar relatórios e fazer simulações educativas sem recomendar investimentos.

## O que o app tem

- Aba **Início** com explicação simples.
- Aba **Lançamentos** para registrar entrada ou gasto, linha por linha.
- Campo **Fixo** para marcar valores que costumam repetir todo mês.
- Campos **Início** e **Fim** para repetir lançamentos fixos automaticamente nos relatórios anuais.
- Aba **Dívidas** para acompanhar parcelas sem registrar dados sensíveis.
- Aba **Painel** com resumo do mês: entrou, saiu, sobrou ou faltou.
- Gráficos por categoria e comparação entre entradas e gastos.
- Aba **Metas** para calcular quanto guardar por mês.
- Aba **Simulações** com CDI, poupança, Tesouro Selic, Tesouro Prefixado e Tesouro IPCA+.
- Aba **Relatórios** com prévia, Excel e TXT.
- Relatório anual de controle de gastos, com seleção de anos como 2026 e 2027.
- Tabelas anuais por mês, por categoria, por compras parceladas e por lançamentos usados no relatório.
- Aba **Oficina** com orientações genéricas para atividade educativa.

## Simulações educativas

A simulação possui caráter exclusivamente educativo e não representa recomendação de investimento.

O app busca, quando possível:

- Selic, TR e IPCA pela API SGS do Banco Central do Brasil.
- Taxas de títulos públicos pela base pública do Tesouro Transparente.

As simulações são simplificadas e servem para aprender como juros, tempo e descontos podem alterar o valor final. O app não indica bancos, corretoras, fundos, ações, carteiras ou produtos financeiros.

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

Esse arquivo instala as dependências, inicia o app e mostra o endereço para abrir no computador ou no celular conectado ao mesmo Wi-Fi.

## Como usar

1. Abra a aba Lançamentos.
2. Registre entradas e gastos.
3. Marque como fixo o que costuma repetir todo mês.
4. Para lançamentos fixos, informe **Início** e, se souber quando termina, **Fim**.
5. Use a aba Dívidas para controlar parcelas.
6. Veja o resultado na aba Painel.
7. Crie uma meta na aba Metas.
8. Use Simulações apenas como aprendizado.
9. Use Relatórios para baixar o resumo geral ou o controle anual.

## Segurança e ética

- Não informe CPF, senha, conta bancária, número de cartão ou contrato.
- Use descrições simples, como mercado, aluguel, transporte ou salário.
- O app é educativo e não recomenda investimentos.

## Uso em oficina

Use o botão **Carregar exemplo** para demonstrar o fluxo sem expor dados reais. Depois, cada participante pode preencher seus próprios lançamentos de forma individual.

## Justificativa acadêmica

O app responde à lacuna diagnosticada na Etapa 1 do projeto de extensão: dificuldade de controle de gastos, ausência de organização financeira estruturada e necessidade de uma ferramenta prática para planejar melhor o dinheiro do mês.
