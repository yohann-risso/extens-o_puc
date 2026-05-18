# Resumo Detalhado do App

## Nome do app

**Organização Financeira na Prática**

## Visão geral

O app **Organização Financeira na Prática** é uma aplicação web feita em **Python** com **Streamlit**, voltada para educação financeira pessoal. Seu objetivo é ajudar pessoas a registrarem entradas, gastos, dívidas, parcelas e metas de forma simples, visual e acessível.

A proposta principal é transformar o controle financeiro em uma atividade prática, compreensível e segura, especialmente para pessoas com pouco conhecimento técnico ou pouca familiaridade com planilhas e ferramentas financeiras mais complexas.

O app não pede dados sensíveis, não exige login, não solicita informações bancárias e não recomenda investimentos, bancos, corretoras ou produtos financeiros. As simulações existentes têm finalidade exclusivamente educativa.

## Objetivo geral

Auxiliar o usuário a organizar o dinheiro do mês, entendendo quanto entrou, quanto saiu, quanto foi gasto em despesas fixas e variáveis, quanto está comprometido com parcelas ou dívidas e se existe sobra para criar metas ou guardar dinheiro.

## Objetivos específicos

- Facilitar o registro de entradas e gastos em uma interface simples.
- Separar gastos fixos de gastos não fixos.
- Permitir o acompanhamento de dívidas e parcelas sem exposição de dados pessoais.
- Mostrar de forma visual se o mês fechou com sobra ou falta de dinheiro.
- Gerar diagnósticos automáticos com linguagem simples.
- Sugerir passos práticos para melhorar a organização financeira.
- Ajudar o usuário a criar metas realistas de economia.
- Simular cenários educativos simples envolvendo dinheiro parado, poupança, CDI e Tesouro Selic.
- Gerar relatórios em TXT e Excel.
- Criar um controle anual de gastos, incluindo lançamentos fixos repetidos por mês.
- Apoiar oficinas, aulas ou atividades de extensão sobre educação financeira.

## Público-alvo

O app foi pensado para:

- Pessoas que querem começar a organizar a vida financeira.
- Participantes de oficinas de educação financeira.
- Estudantes e comunidades atendidas por projetos de extensão.
- Usuários que não têm familiaridade com planilhas complexas.
- Pessoas que precisam visualizar de forma simples o resultado do mês.

## Tecnologias utilizadas

- **Python**: linguagem principal do app.
- **Streamlit**: criação da interface web.
- **Pandas**: organização, tratamento e análise dos dados.
- **Plotly**: criação de gráficos interativos.
- **OpenPyXL**: exportação de relatórios em Excel.
- **APIs públicas**: consulta de taxas do Banco Central do Brasil e do Tesouro Transparente, quando disponíveis.

## Estrutura principal do app

O app é organizado em nove abas principais:

1. **Início**
2. **Primeiros Passos**
3. **Lançamentos**
4. **Dívidas**
5. **Painel**
6. **Metas**
7. **Simulações**
8. **Relatórios**
9. **Oficina**

Além das abas, existe uma barra lateral com ações rápidas para carregar dados de exemplo, limpar tudo e atualizar taxas.

## Funcionalidades detalhadas

### 1. Aba Início

A aba inicial apresenta o propósito do app de maneira simples. Ela explica que a ferramenta é educativa e serve para registrar entradas e gastos, acompanhar o mês, planejar metas e comparar simulações básicas.

Também reforça que o app:

- Não solicita dados sensíveis.
- Não recomenda investimentos.
- Não indica bancos, corretoras ou produtos financeiros.
- Deve ser usado como apoio à organização financeira e à educação.

Na tela inicial, o usuário vê cartões resumindo os principais usos:

- Uso diário, com registro de entrada e saída.
- Leitura rápida de quanto entrou e quanto saiu.
- Educação financeira sem indicação de produtos.

### 2. Aba Primeiros Passos

A aba **Primeiros Passos** apresenta um roteiro simples para começar a organização financeira:

- Anotar quanto ganha.
- Registrar gastos fixos.
- Registrar gastos do dia a dia.
- Ver para onde o dinheiro está indo.
- Identificar excessos.
- Criar uma pequena meta.
- Começar a reserva de emergência.

Ela também usa exemplos próximos da rotina dos participantes, como cartão de crédito, mercado, delivery e transporte.

### 3. Aba Lançamentos

A aba **Lançamentos** é a base do app. Nela o usuário registra tudo que entra e tudo que sai do orçamento.

Cada lançamento pode conter:

- Data.
- Tipo: entrada ou gasto.
- Descrição.
- Categoria.
- Valor.
- Marcação de gasto ou entrada fixa.
- Data de início para lançamentos fixos.
- Data de fim para lançamentos fixos.
- Marcação de compra parcelada.
- Número de parcelas.
- Parcelas pagas.
- Observação.

As entradas possuem categorias como:

- Salário.
- Horas extras.
- Benefícios.
- Venda ou bico.
- Ajuda recebida.
- Outros ganhos.

Os gastos possuem categorias como:

- Moradia.
- Mercado e alimentação.
- Água, luz e internet.
- Transporte.
- Saúde.
- Educação.
- Lazer.
- Delivery ou lanche fora.
- Compras.
- Cartão de crédito.
- Assinaturas.
- Dívidas.
- Imprevistos.
- Outros gastos.

A aba também permite adicionar linhas vazias rapidamente, facilitando o preenchimento de vários gastos de uma vez.

Depois do preenchimento, o app calcula automaticamente:

- Total de entradas registradas.
- Total de gastos registrados.
- Total de gastos fixos.
- Total de gastos não fixos.
- Resumo por categoria.

### 4. Lançamentos fixos

O app permite marcar entradas e gastos como fixos. Essa funcionalidade é importante para contas que se repetem todos os meses, como aluguel, salário, internet, assinaturas e contas recorrentes.

Para lançamentos fixos, o usuário pode informar:

- Data de início.
- Data de fim.

Se o campo de fim ficar vazio, o app considera que o lançamento continua até o fim do período escolhido no relatório anual.

Essa lógica é usada principalmente nos relatórios anuais, em que os lançamentos fixos são repetidos automaticamente mês a mês dentro do período selecionado.

### 5. Compras parceladas

Na aba de lançamentos, o usuário também pode marcar um gasto como parcelado. Para isso, pode informar:

- Número total de parcelas.
- Quantidade de parcelas já pagas.
- Observação sobre a compra.

Essa informação aparece no controle anual, permitindo identificar compras parceladas que impactam o orçamento ao longo do tempo.

### 6. Aba Dívidas

A aba **Dívidas e parcelas** permite acompanhar compromissos financeiros sem registrar dados sensíveis.

Cada dívida pode conter:

- Nome simples da dívida.
- Valor que falta pagar.
- Valor da parcela do mês.
- Quantidade de parcelas restantes.
- Observação.

O app orienta o usuário a não informar CPF, banco, contrato, conta, senha ou dados de cartão.

Existe também uma opção para decidir se as parcelas cadastradas devem entrar no resultado do mês. Isso evita duplicidade quando a mesma parcela já foi registrada na aba Lançamentos.

A aba calcula:

- Soma das parcelas do mês.
- Valor que será contado no painel.
- Quantidade de dívidas cadastradas.

### 7. Aba Painel

A aba **Painel do mês** apresenta a leitura central da situação financeira do usuário.

Ela mostra cartões com:

- Quanto entrou no mês.
- Quanto saiu no mês.
- Quanto sobrou ou faltou.
- Quanto foi usado a cada R$ 100 recebidos.

O painel também exibe uma barra de progresso indicando o percentual do dinheiro comprometido.

Além dos números, o app gera uma **leitura rápida automática**, com mensagens como:

- Comece pelos lançamentos.
- Saiu mais do que entrou.
- O mês ficou no limite.
- Terminou com dinheiro sobrando.
- Parcelas pesadas.
- Primeiro organizar.
- Próximo passo.

Essas mensagens são acompanhadas de uma ação sugerida, sempre com linguagem simples e prática.

O painel também possui o **Resumo Financeiro do Mês**, com:

- Quanto entrou.
- Quanto saiu.
- Principal categoria de gasto.
- Saldo final.
- Recomendação simples.
- Próxima meta sugerida.

### 8. Diagnóstico automático

O diagnóstico é calculado a partir das entradas, gastos, dívidas e saldo final.

O app identifica situações como:

- Ausência de dados.
- Saldo negativo.
- Saldo zerado.
- Saldo positivo.
- Dívidas consumindo parte relevante da renda.

Com base nisso, o app mostra alertas, avisos, mensagens de sucesso ou orientações informativas.

### 9. Plano de ação

O app cria um plano de ação personalizado conforme o resultado do mês.

Se não houver entradas registradas, ele sugere:

- Registrar o dinheiro que entra no mês.
- Registrar os gastos conforme acontecem.
- Voltar ao painel depois de preencher alguns lançamentos.

Se o saldo for negativo, ele sugere:

- Revisar gastos não fixos.
- Evitar novas parcelas.
- Anotar gastos pequenos por alguns dias.

Se o saldo estiver zerado, ele sugere:

- Criar uma pequena folga.
- Rever assinaturas, delivery e compras não planejadas.
- Separar dinheiro das contas fixas ao receber.

Se houver sobra, ele sugere:

- Separar parte do dinheiro.
- Guardar valor para emergência.
- Acompanhar o padrão por alguns meses.

O app também identifica a categoria de gasto que mais pesou e recomenda atenção especial a ela.

### 10. Gráficos do painel

O painel possui gráficos para facilitar a visualização:

- Gráfico de gastos por categoria.
- Comparação entre entradas e saídas.
- Lista do plano de ação.

Esses gráficos ajudam o usuário a perceber rapidamente para onde o dinheiro está indo.

### 11. Aba Metas

A aba **Metas** permite criar um objetivo financeiro.

O usuário informa:

- Quanto deseja juntar.
- Para qual finalidade.
- Em quantos meses pretende alcançar a meta.

O app calcula:

- Quanto precisa guardar por mês.
- Quanto sobrou no mês atual.
- Se a meta cabe ou não no dinheiro disponível.

Quando a meta não cabe, o app sugere aumentar o prazo ou criar mais folga no orçamento. Quando cabe, ele incentiva separar o valor assim que receber.

A aba também gera um gráfico de evolução mês a mês da meta.

### 12. Aba Simulações

A aba **Simulações educativas** permite comparar cenários básicos de acúmulo de dinheiro ao longo do tempo.

Ela começa com o bloco **Antes de investir**, reforçando que o participante deve organizar gastos, reduzir dívidas caras, criar reserva de emergência e entender o orçamento mensal antes de buscar investimentos.

O usuário pode informar:

- Dinheiro já guardado.
- Valor que pretende guardar por mês.
- Quantidade de meses.

O app compara:

- Dinheiro parado.
- Poupança.
- CDI.
- Tesouro Selic.

As simulações consideram valores guardados mensalmente e mostram resultado aproximado ao final do período, com linguagem simples e poucos números técnicos.

### 13. Uso de taxas públicas

Quando há internet disponível, o app tenta buscar dados públicos para deixar as simulações mais próximas da realidade:

- Taxa básica e dados auxiliares pela API SGS do Banco Central do Brasil.
- Tesouro Selic pela base pública do Tesouro Transparente.

Se essas consultas falharem, o app usa valores educativos de referência, sem exigir preenchimento manual de taxas complexas.

### 14. Cuidados nas simulações

O app deixa claro que as simulações:

- São simplificadas.
- Têm finalidade educativa.
- Não representam recomendação de investimento.
- Não indicam produtos financeiros.
- Não substituem análise profissional.

O aviso principal é que controlar gastos, reduzir dívidas e formar reserva de emergência vem antes de investir.

### 15. Aba Relatórios

A aba **Relatórios** permite gerar e baixar materiais com os dados preenchidos.

O app oferece:

- Download em Excel.
- Download em TXT.
- Prévia do relatório em texto.
- Tabela de lançamentos.
- Tabela de dívidas.
- Controle anual de gastos.

O relatório em texto inclui:

- Data e hora de geração.
- Resumo do mês.
- Entradas.
- Gastos.
- Resultado.
- Gastos fixos.
- Gastos não fixos.
- Parcelas cadastradas.
- Leitura rápida.
- Plano de ação.
- Meta.
- Simulação educativa.
- Aviso de que não há recomendação de investimento.

### 16. Exportação em Excel

O app exporta os dados em planilhas organizadas.

O relatório geral em Excel possui abas como:

- Início.
- Lançamentos.
- Dívidas.
- Resumo.
- Meta.
- Leitura.
- Plano.
- Simulação.

As colunas são formatadas para facilitar a leitura, incluindo valores em reais e datas no formato brasileiro.

### 17. Controle anual de gastos

Dentro da aba Relatórios, existe um módulo de controle anual.

O usuário pode selecionar um ou mais anos para acompanhar:

- Entradas por mês.
- Gastos fixos por mês.
- Gastos não fixos por mês.
- Total de gastos por mês.
- Saldo mensal.
- Totais por ano.
- Gastos por categoria.
- Compras parceladas.
- Lançamentos considerados no relatório.

Por padrão, o app inclui anos como 2026 e 2027, além dos anos identificados nos lançamentos.

### 18. Repetição automática de lançamentos fixos no relatório anual

Uma das funções mais importantes do controle anual é repetir automaticamente os lançamentos marcados como fixos.

Exemplo:

- Um aluguel marcado como fixo com início em janeiro será considerado em todos os meses seguintes do relatório.
- Se houver uma data de fim, ele será considerado apenas até aquele mês.
- Se não houver fim, será repetido até o fim do período selecionado.

Isso permite criar uma visão anual mais realista do orçamento, sem precisar lançar manualmente o mesmo gasto todos os meses.

### 19. Aba Oficina

A aba **Oficina** foi transformada em um roteiro guiado para a atividade educativa.

Ela organiza a condução em seis momentos:

- Entendendo os gastos.
- Registrando receitas.
- Registrando despesas.
- Analisando o painel.
- Criando metas.
- Reflexão final: "O que posso melhorar este mês?"

O app sugere começar com um exemplo fictício e depois permitir que cada participante registre seus próprios dados individualmente. A aba também mantém perguntas para conversa, cuidados com dados pessoais e justificativa acadêmica.

### 20. Barra lateral

A barra lateral possui botões importantes:

- **Carregar exemplo**: preenche o app com dados fictícios para demonstração.
- **Limpar tudo**: apaga os dados da sessão atual.
- **Atualizar taxas**: limpa o cache e tenta buscar novamente as taxas usadas nas simulações.

Ela também reforça que o material é educativo e não recomenda produtos financeiros.

### 21. Dados de exemplo

O app possui uma base fictícia para demonstração, contendo:

- Salário.
- Horas extras.
- Aluguel.
- Mercado.
- Delivery.
- Assinaturas.
- Compra parcelada.
- Dívida de cartão.
- Meta de emergência.
- Valores iniciais para simulação.

Esse recurso é útil para apresentar o app em sala, oficina ou banca sem expor dados reais.

## Segurança e privacidade

O app foi construído com foco em uso educativo e preservação de dados pessoais.

Ele orienta o usuário a não informar:

- CPF.
- Senhas.
- Número de conta.
- Banco.
- Contratos.
- Cartões.
- Dados financeiros sensíveis.

As descrições devem ser simples, como mercado, aluguel, transporte, salário, cartão ou curso.

## Valor educacional

O app contribui para a educação financeira porque ajuda o usuário a transformar informações soltas em uma visão organizada do mês.

Ele ensina, na prática, conceitos como:

- Receita.
- Despesa.
- Gasto fixo.
- Gasto variável.
- Parcela.
- Dívida.
- Saldo.
- Meta.
- Planejamento mensal.
- Planejamento anual.
- Juros e rendimento em simulações.

O foco não é apenas calcular valores, mas ajudar o usuário a entender sua própria situação financeira e tomar decisões mais conscientes.

## Justificativa acadêmica

O app responde a uma dificuldade comum identificada em atividades de educação financeira: muitas pessoas não acompanham seus gastos de maneira estruturada e acabam sem clareza sobre quanto entra, quanto sai e quais despesas mais pesam no orçamento.

Como ferramenta de projeto de extensão, o app funciona como apoio prático para diagnóstico, orientação e reflexão. Ele permite que os participantes visualizem sua realidade financeira de forma simples, sem exposição pública de dados sensíveis, e construam um plano inicial de organização.

## Resultado esperado

Ao usar o app, espera-se que o usuário consiga:

- Registrar melhor o dinheiro que entra e sai.
- Entender quais categorias mais consomem sua renda.
- Identificar se o mês fecha com sobra ou falta.
- Perceber o peso de dívidas e parcelas.
- Planejar uma meta possível.
- Comparar cenários de forma educativa.
- Gerar relatórios para acompanhar a evolução.
- Desenvolver hábitos de controle financeiro.

## Síntese final

O **Organização Financeira na Prática** é uma ferramenta educativa de controle financeiro pessoal. Ele une registro de gastos, diagnóstico automático, visualização por gráficos, planejamento de metas, simulações educativas e relatórios em uma interface simples.

Seu principal objetivo é tornar a organização financeira mais acessível, ajudando o usuário a compreender o próprio orçamento e a planejar melhor o uso do dinheiro, sem depender de conhecimento técnico avançado e sem exposição de dados sensíveis.
