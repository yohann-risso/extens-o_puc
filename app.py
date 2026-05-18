"""Aplicativo simples de organização financeira feito com Streamlit.

A ideia do projeto é deixar a pessoa registrar entradas, gastos, dívidas,
metas e uma simulação básica de dinheiro guardado. O código fica em um único
arquivo porque o projeto é pequeno, mas as funções foram separadas por assunto
para facilitar manutenção e apresentação.
"""

from datetime import date, datetime, timedelta
from io import BytesIO
import json
from urllib.error import URLError
from urllib.request import urlopen

import pandas as pd
import plotly.express as px
import streamlit as st


DISPLAY_NAME = "Organização Financeira na Prática"
BCB_BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs"
CACHE_TAXAS_BCB = "bcb-parser-v3"
FORMATO_MOEDA_EXCEL = '"R$" #,##0.00'
FORMATO_DATA_EXCEL = "DD/MM/YYYY"
PREFIXO_ARQUIVO = "controle-financeiro"
MIME_EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MIME_JSON = "application/json"

TIPOS_LANCAMENTO = ["Entrada", "Gasto"]
CATEGORIAS_ENTRADA = ["Salário", "Horas extras", "Benefícios", "Venda ou bico", "Ajuda recebida", "Outros ganhos"]
CATEGORIAS_GASTO = [
    "Moradia",
    "Mercado e alimentação",
    "Água, luz e internet",
    "Transporte",
    "Saúde",
    "Educação",
    "Lazer",
    "Delivery ou lanche fora",
    "Compras",
    "Cartão de crédito",
    "Assinaturas",
    "Dívidas",
    "Imprevistos",
    "Outros gastos",
]
CATEGORIAS_LANCAMENTO = CATEGORIAS_ENTRADA + CATEGORIAS_GASTO
COLUNAS_LANCAMENTOS = [
    "Data",
    "Tipo",
    "Descrição",
    "Categoria",
    "Valor",
    "Fixo",
    "Início",
    "Fim",
    "Parcelado",
    "Nº de parcelas",
    "Parcelas pagas",
    "Observação",
]
COLUNAS_LANCAMENTOS_BASICAS = ["Data", "Tipo", "Descrição", "Categoria", "Valor"]
COLUNAS_LANCAMENTOS_DETALHES = ["Fixo", "Início", "Fim", "Parcelado", "Nº de parcelas", "Parcelas pagas", "Observação"]
COLUNAS_DIVIDAS = ["Dívida", "Falta pagar", "Parcela do mês", "Parcelas restantes", "Observação"]
COLUNAS_DATA = ["Data", "Início", "Fim"]
COLUNAS_RESUMO_ANUAL = ["Entradas", "Gastos fixos", "Gastos não fixos", "Total de gastos", "Sobrou/Faltou"]
COLUNAS_MOEDA_RELATORIO = COLUNAS_RESUMO_ANUAL + ["Valor", "Falta pagar", "Parcela do mês"]
ICONE_CATEGORIA = {
    "Salário": "💰",
    "Horas extras": "💰",
    "Benefícios": "💰",
    "Venda ou bico": "💰",
    "Ajuda recebida": "💰",
    "Moradia": "🏠",
    "Mercado e alimentação": "🛒",
    "Água, luz e internet": "💡",
    "Transporte": "🚌",
    "Saúde": "🩺",
    "Educação": "📚",
    "Lazer": "🎟️",
    "Delivery ou lanche fora": "🍔",
    "Compras": "🛍️",
    "Cartão de crédito": "💳",
    "Assinaturas": "🔁",
    "Dívidas": "⚠️",
    "Imprevistos": "⚠️",
}

BASE_LANCAMENTO = {
    "Data": None,
    "Tipo": "Gasto",
    "Descrição": "",
    "Categoria": "Outros gastos",
    "Valor": 0.0,
    "Fixo": False,
    "Início": None,
    "Fim": None,
    "Parcelado": False,
    "Nº de parcelas": 1,
    "Parcelas pagas": 0,
    "Observação": "",
}
MESES_PT = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}
ABAS_APP = [
    "Início",
    "Registrar",
    "Resultado do mês",
    "Dívidas",
    "Metas",
    "Guardando dinheiro",
    "Histórico",
    "Privacidade e LGPD",
]


def formatar_moeda(valor: float) -> str:
    """Mostra número no formato usado no Brasil."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_decimal(valor: float) -> str:
    """Mostra percentual com vírgula em vez de ponto."""
    return f"{valor:.2f}".replace(".", ",")


def formatar_data(valor: object) -> str:
    """Converte datas para dia/mês/ano quando o valor é válido."""
    data = pd.to_datetime(valor, errors="coerce")
    if pd.isna(data):
        return ""
    return data.strftime("%d/%m/%Y")


def formatar_tabela(
    tabela_original: pd.DataFrame,
    colunas: list[str] | None = None,
    colunas_moeda: list[str] | None = None,
    colunas_data: list[str] | None = None,
) -> pd.DataFrame:
    """Prepara tabelas para aparecer na tela, sem mexer nos dados originais."""
    tabela = tabela_original.copy()
    if tabela.empty:
        return tabela
    if colunas is not None:
        tabela = tabela[[coluna for coluna in colunas if coluna in tabela.columns]].copy()
    for coluna_data in colunas_data or []:
        if coluna_data in tabela.columns:
            tabela[coluna_data] = tabela[coluna_data].map(formatar_data)
    for coluna_moeda in colunas_moeda or []:
        if coluna_moeda in tabela.columns:
            tabela[coluna_moeda] = tabela[coluna_moeda].map(formatar_moeda)
    return tabela


def formatar_tabela_lancamentos(lancamentos: pd.DataFrame, colunas: list[str] | None = None) -> pd.DataFrame:
    """Formata lançamentos para consulta visual."""
    return formatar_tabela(lancamentos, colunas=colunas, colunas_moeda=["Valor"], colunas_data=COLUNAS_DATA)


def formatar_tabela_dividas(dividas: pd.DataFrame) -> pd.DataFrame:
    """Formata a tabela de dívidas para leitura."""
    return formatar_tabela(dividas, colunas_moeda=["Falta pagar", "Parcela do mês"])


def formatar_tabela_simulacao(tabela: pd.DataFrame) -> pd.DataFrame:
    """Formata a evolução mensal da simulação."""
    colunas_moeda = [coluna for coluna in tabela.columns if coluna != "Mês"]
    return formatar_tabela(tabela, colunas_moeda=colunas_moeda)


def formatar_tabela_resumo_anual(tabela: pd.DataFrame) -> pd.DataFrame:
    """Formata o resumo anual mês a mês."""
    return formatar_tabela(tabela, colunas_moeda=COLUNAS_RESUMO_ANUAL)


def formatar_tabela_categoria_anual(tabela: pd.DataFrame) -> pd.DataFrame:
    """Formata o resumo anual por categoria."""
    return formatar_tabela(tabela, colunas_moeda=["Valor"])


def aplicar_eixo_moeda(fig) -> None:
    """Coloca prefixo de real nos eixos dos gráficos."""
    fig.update_yaxes(tickprefix="R$ ", separatethousands=True)


def dinheiro_input(rotulo: str, chave: str, valor: float = 0.0, ajuda: str | None = None) -> float:
    """Evita repetir a mesma configuração nos campos de dinheiro."""
    return st.number_input(rotulo, min_value=0.0, value=float(valor), step=50.0, format="%.2f", key=chave, help=ajuda)


def numero_bcb(valor: object) -> float:
    """Converte número vindo do Banco Central, que chega como texto."""
    if pd.isna(valor):
        return 0.0
    return float(str(valor).strip().replace(",", "."))


def normalizar_percentual_atual(valor: float) -> float:
    """Evita exibir valor inflado se algum cache antigo trouxe 14.50 como 1450."""
    return valor / 100 if valor > 100 else valor


def icone_categoria(categoria: str) -> str:
    """Escolhe um ícone simples para a categoria."""
    return ICONE_CATEGORIA.get(categoria, "•")


def configurar_pagina() -> None:
    """Configura a página e o CSS básico do app."""
    st.set_page_config(page_title=DISPLAY_NAME, layout="wide", initial_sidebar_state="expanded")
    st.markdown(
        """
        <style>
        :root {
            --bg: #f4f6f2;
            --panel: #ffffff;
            --ink: #172026;
            --muted: #64717c;
            --line: #dfe6de;
            --green: #2f7d59;
            --blue: #2f6f9f;
            --red: #c45f4b;
            --gold: #b7791f;
        }
        .stApp { background: var(--bg); }
        .main .block-container { max-width: 1120px; padding-top: 1.1rem; padding-bottom: 3rem; }
        h1, h2, h3 { color: var(--ink); letter-spacing: 0; }
        .hero {
            background: var(--panel);
            border: 1px solid var(--line);
            border-left: 7px solid var(--green);
            border-radius: 8px;
            padding: 1.25rem 1.35rem;
            box-shadow: 0 12px 30px rgba(23, 32, 38, .06);
            margin-bottom: 1rem;
        }
        .hero h1 { font-size: clamp(1.55rem, 3vw, 2.4rem); margin: 0 0 .4rem 0; }
        .hero p { color: var(--muted); margin: .15rem 0; max-width: 900px; }
        .chip-row { display: flex; flex-wrap: wrap; gap: .45rem; margin-top: .75rem; }
        .chip {
            border: 1px solid #d8e7dc;
            background: #edf6ef;
            color: #244b38;
            border-radius: 999px;
            padding: .34rem .62rem;
            font-size: .86rem;
            font-weight: 650;
        }
        .metric-card {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 8px;
            min-height: 148px;
            padding: 1.15rem;
            box-shadow: 0 8px 22px rgba(23, 32, 38, .055);
        }
        .metric-card.green { border-top: 5px solid var(--green); }
        .metric-card.blue { border-top: 5px solid var(--blue); }
        .metric-card.red { border-top: 5px solid var(--red); }
        .metric-card.gold { border-top: 5px solid var(--gold); }
        .metric-label { color: var(--muted); font-size: .92rem; margin-bottom: .5rem; }
        .metric-value { color: var(--ink); font-size: clamp(1.22rem, 2vw, 1.72rem); font-weight: 780; line-height: 1.15; }
        .metric-help { color: var(--muted); font-size: .88rem; margin-top: .55rem; line-height: 1.35; }
        .note {
            color: var(--muted);
            font-size: .95rem;
            margin-top: -.25rem;
            margin-bottom: .75rem;
        }
        .panel {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 1.05rem 1.1rem;
            margin: .65rem 0;
        }
        .total-line {
            background: #f0f6f8;
            border: 1px solid #d8e7ee;
            border-radius: 8px;
            color: #264653;
            font-weight: 740;
            margin-top: .65rem;
            padding: .7rem .85rem;
        }
        .empty-state {
            background: #ffffff;
            border: 1px dashed #cfd9cf;
            border-radius: 8px;
            color: var(--muted);
            padding: 1rem 1.05rem;
            margin: .75rem 0;
        }
        .empty-state strong { color: var(--ink); }
        .backup-hint {
            background: #edf6ef;
            border: 1px solid #cfe3d4;
            border-radius: 8px;
            color: #244b38;
            font-weight: 650;
            padding: .7rem .8rem;
            margin: .5rem 0 .75rem 0;
        }
        div[data-testid="stAlert"] { border-radius: 8px; }
        .stTabs [data-baseweb="tab-list"] { gap: .35rem; flex-wrap: wrap; }
        .stTabs [data-baseweb="tab"] {
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 999px;
            padding: .45rem .8rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def card(rotulo: str, valor: str, ajuda: str = "", cor: str = "green") -> None:
    """Mostra um card simples de indicador financeiro."""
    st.markdown(
        f"""
        <div class="metric-card {cor}">
            <div class="metric-label">{rotulo}</div>
            <div class="metric-value">{valor}</div>
            <div class="metric-help">{ajuda}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def total_line(texto: str) -> None:
    """Mostra uma linha de total com destaque."""
    st.markdown(f'<div class="total-line">{texto}</div>', unsafe_allow_html=True)


def empty_state(titulo: str, texto: str) -> None:
    """Mostra uma orientação curta quando ainda não há dados."""
    st.markdown(f'<div class="empty-state"><strong>{titulo}</strong><br>{texto}</div>', unsafe_allow_html=True)


def panel_html(titulo: str, texto: str) -> None:
    """Mostra um bloco curto de texto dentro do layout."""
    st.markdown(f'<div class="panel"><strong>{titulo}</strong><br>{texto}</div>', unsafe_allow_html=True)


def backup_hint(texto: str) -> None:
    """Reforça que o backup é local e depende do download do usuário."""
    st.markdown(f'<div class="backup-hint">{texto}</div>', unsafe_allow_html=True)


def nome_arquivo_exportacao(extensao: str, prefixo: str = PREFIXO_ARQUIVO, incluir_hora: bool = False) -> str:
    """Cria nomes profissionais para os arquivos baixados."""
    agora = datetime.now()
    sufixo = agora.strftime("%Y-%m-%d_%H-%M") if incluir_hora else agora.strftime("%Y-%m")
    return f"{prefixo}-{sufixo}.{extensao}"


def registrar_feedback(mensagem: str) -> None:
    """Guarda uma mensagem curta para aparecer após ações com rerun."""
    st.session_state["mensagem_feedback"] = mensagem


def mostrar_feedback_pendente() -> None:
    """Mostra feedback visual de ações concluídas."""
    mensagem = st.session_state.pop("mensagem_feedback", None)
    if mensagem:
        st.success(mensagem)
        st.toast(mensagem, icon="✅")


def rerun_preservando_tela() -> None:
    """Atualiza a execução sem voltar para a tela inicial."""
    if st.session_state.get("aba_atual") not in ABAS_APP:
        st.session_state["aba_atual"] = "Início"
    st.rerun()


def limpar_grafico(fig, margem: dict[str, int] | None = None):
    """Deixa o gráfico com aparência mais limpa para caber no Streamlit."""
    fig.update_layout(
        showlegend=False,
        xaxis_title="",
        yaxis_title="",
        margin=margem or dict(l=10, r=10, t=15, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def grafico_barras_horizontais(
    dados: pd.DataFrame,
    eixo_y: str,
    cores: list[str] | None = None,
):
    """Cria gráfico horizontal para comparações de valores."""
    sequencia_cores = cores if cores is not None else px.colors.qualitative.Set2
    fig = px.bar(
        dados,
        x="Valor",
        y=eixo_y,
        text="Texto",
        orientation="h",
        color=eixo_y,
        color_discrete_sequence=sequencia_cores,
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    limpar_grafico(fig)
    fig.update_xaxes(showgrid=False, tickprefix="R$ ", separatethousands=True)
    fig.update_yaxes(showgrid=False)
    return fig


def buscar_serie_bcb(codigo: int, ultimos: int = 1) -> list[dict[str, object]]:
    """Busca uma série histórica simples na API do Banco Central."""
    data_final = date.today()
    data_inicial = data_final - timedelta(days=900)
    url = (
        f"{BCB_BASE_URL}.{codigo}/dados?formato=json"
        f"&dataInicial={data_inicial.strftime('%d/%m/%Y')}"
        f"&dataFinal={data_final.strftime('%d/%m/%Y')}"
    )
    with urlopen(url, timeout=10) as resposta:
        dados = json.loads(resposta.read().decode("utf-8"))
    if not dados:
        raise ValueError("BCB não retornou dados.")
    dados = dados[-ultimos:]
    return [{"data": item["data"], "valor": numero_bcb(item["valor"]), "url": url} for item in dados]


@st.cache_data(ttl=60 * 60)
def obter_taxas_bcb(_cache_version: str = CACHE_TAXAS_BCB) -> dict[str, object]:
    """Obtém Selic e TR para a simulação de dinheiro guardado."""
    try:
        selic = buscar_serie_bcb(432)[-1]
        tr = buscar_serie_bcb(226)[-1]
        selic_aa = normalizar_percentual_atual(float(selic["valor"]))
        tr_mensal = normalizar_percentual_atual(float(tr["valor"]))
        return {
            "ok": True,
            "selic_aa": selic_aa,
            "selic_data": selic["data"],
            "tr_mensal": tr_mensal,
            "tr_data": tr["data"],
        }
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as erro:
        return {
            "ok": False,
            "erro": str(erro),
            "selic_aa": 10.0,
            "selic_data": "manual",
            "tr_mensal": 0.0,
            "tr_data": "manual",
        }


def montar_lancamento(**campos: object) -> dict[str, object]:
    """Monta um lançamento usando valores padrão e sobrescrevendo o necessário."""
    lancamento = BASE_LANCAMENTO.copy()
    lancamento["Data"] = date.today()
    lancamento.update(campos)
    return lancamento


def criar_lancamentos_padrao() -> pd.DataFrame:
    """Cria a tabela vazia de lançamentos."""
    return pd.DataFrame(columns=COLUNAS_LANCAMENTOS)


def criar_lancamento_vazio(tipo: str = "Gasto") -> dict[str, object]:
    """Cria uma linha vazia para o editor do Streamlit."""
    categoria = "Outros ganhos" if tipo == "Entrada" else "Outros gastos"
    return montar_lancamento(**{"Tipo": tipo, "Categoria": categoria})


def normalizar_lancamentos(df: pd.DataFrame) -> pd.DataFrame:
    """Limpa os lançamentos antes de calcular ou exportar."""
    colunas = COLUNAS_LANCAMENTOS
    if df is None or df.empty:
        return pd.DataFrame(columns=colunas)
    dados = df.copy()
    for coluna in colunas:
        if coluna not in dados.columns:
            if coluna in ["Fixo", "Parcelado"]:
                dados[coluna] = False
            elif coluna == "Valor":
                dados[coluna] = 0.0
            elif coluna in ["Início", "Fim"]:
                dados[coluna] = None
            elif coluna == "Nº de parcelas":
                dados[coluna] = 1
            elif coluna == "Parcelas pagas":
                dados[coluna] = 0
            else:
                dados[coluna] = ""
    dados = dados[colunas]
    dados["Data"] = pd.to_datetime(dados["Data"], errors="coerce").dt.date
    dados["Tipo"] = dados["Tipo"].where(dados["Tipo"].isin(TIPOS_LANCAMENTO), "Gasto")
    dados["Categoria"] = dados["Categoria"].fillna("Outros gastos").astype(str)
    dados["Descrição"] = dados["Descrição"].fillna("").astype(str)
    dados["Observação"] = dados["Observação"].fillna("").astype(str)
    dados["Valor"] = pd.to_numeric(dados["Valor"], errors="coerce").fillna(0.0)
    dados["Fixo"] = dados["Fixo"].fillna(False).astype(bool)

    # Para gastos fixos, a data de início controla a repetição no histórico anual.
    data_dt = pd.to_datetime(dados["Data"], errors="coerce")
    inicio_dt = pd.to_datetime(dados["Início"], errors="coerce").fillna(data_dt)
    fim_dt = pd.to_datetime(dados["Fim"], errors="coerce")
    dados["Início"] = inicio_dt.dt.date
    dados["Fim"] = fim_dt.dt.date
    dados.loc[fim_dt.isna(), "Fim"] = None
    dados.loc[~dados["Fixo"], "Início"] = None
    dados.loc[~dados["Fixo"], "Fim"] = None

    # Parcelas são guardadas separadas porque ajudam no relatório, mesmo sem mudar o cálculo do mês.
    dados["Parcelado"] = dados["Parcelado"].fillna(False).astype(bool)
    dados["Nº de parcelas"] = pd.to_numeric(dados["Nº de parcelas"], errors="coerce").fillna(1).astype(int)
    dados["Parcelas pagas"] = pd.to_numeric(dados["Parcelas pagas"], errors="coerce").fillna(0).astype(int)
    dados.loc[~dados["Parcelado"], "Nº de parcelas"] = 1
    dados.loc[~dados["Parcelado"], "Parcelas pagas"] = 0
    dados["Nº de parcelas"] = dados["Nº de parcelas"].clip(lower=1)
    dados["Parcelas pagas"] = dados["Parcelas pagas"].clip(lower=0)
    dados["Parcelas pagas"] = dados[["Parcelas pagas", "Nº de parcelas"]].min(axis=1)
    dados = dados[(dados["Valor"] > 0) | (dados["Descrição"].str.strip() != "")]
    return dados.reset_index(drop=True)


def calcular_receitas(lancamentos: pd.DataFrame) -> float:
    """Soma tudo que entrou no mês."""
    if lancamentos.empty:
        return 0.0
    return float(lancamentos.loc[lancamentos["Tipo"] == "Entrada", "Valor"].sum())


def calcular_gastos(lancamentos: pd.DataFrame) -> dict[str, float]:
    """Separa gastos fixos e variáveis."""
    if lancamentos.empty:
        return {"total_fixos": 0.0, "total_variaveis": 0.0, "total_gastos_sem_dividas": 0.0}
    gastos = lancamentos[lancamentos["Tipo"] == "Gasto"]
    total_fixos = float(gastos.loc[gastos["Fixo"], "Valor"].sum())
    total_variaveis = float(gastos.loc[~gastos["Fixo"], "Valor"].sum())
    return {
        "total_fixos": total_fixos,
        "total_variaveis": total_variaveis,
        "total_gastos_sem_dividas": total_fixos + total_variaveis,
    }


def criar_dividas_padrao() -> pd.DataFrame:
    """Cria a tabela vazia para cadastro de dívidas."""
    return pd.DataFrame(columns=COLUNAS_DIVIDAS)


def normalizar_dividas(df: pd.DataFrame) -> pd.DataFrame:
    """Limpa a tabela de dívidas antes de somar."""
    colunas = COLUNAS_DIVIDAS
    if df is None or df.empty:
        return pd.DataFrame(columns=colunas)
    dados = df.copy()
    for coluna in colunas:
        if coluna not in dados.columns:
            dados[coluna] = 0.0 if coluna in ["Falta pagar", "Parcela do mês", "Parcelas restantes"] else ""
    dados = dados[colunas]
    dados["Dívida"] = dados["Dívida"].fillna("").astype(str)
    dados["Observação"] = dados["Observação"].fillna("").astype(str)
    dados["Falta pagar"] = pd.to_numeric(dados["Falta pagar"], errors="coerce").fillna(0.0)
    dados["Parcela do mês"] = pd.to_numeric(dados["Parcela do mês"], errors="coerce").fillna(0.0)
    dados["Parcelas restantes"] = pd.to_numeric(dados["Parcelas restantes"], errors="coerce").fillna(0).astype(int)
    dados = dados[(dados["Dívida"].str.strip() != "") | (dados["Parcela do mês"] > 0) | (dados["Falta pagar"] > 0)]
    return dados.reset_index(drop=True)


def valor_para_json(valor: object) -> object:
    """Converte valores de tabela para um formato seguro no arquivo JSON."""
    if isinstance(valor, pd.Timestamp):
        if pd.isna(valor):
            return None
        return valor.date().isoformat()
    if isinstance(valor, datetime):
        return valor.isoformat(timespec="seconds")
    if isinstance(valor, date):
        return valor.isoformat()
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    return valor


def dataframe_para_registros_json(df: pd.DataFrame) -> list[dict[str, object]]:
    """Transforma uma tabela em registros simples para backup no dispositivo."""
    if df is None or df.empty:
        return []
    registros = []
    for linha in df.to_dict("records"):
        registros.append({coluna: valor_para_json(valor) for coluna, valor in linha.items()})
    return registros


def numero_configuracao(valor: object, padrao: float, minimo: float = 0.0) -> float:
    """Lê números vindos de JSON/Excel sem quebrar os widgets do Streamlit."""
    try:
        if pd.isna(valor):
            return padrao
    except (TypeError, ValueError):
        pass
    try:
        numero = float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        numero = padrao
    return max(minimo, numero)


def inteiro_configuracao(valor: object, padrao: int, minimo: int, maximo: int) -> int:
    """Lê inteiros importados respeitando os limites dos campos do app."""
    numero = int(numero_configuracao(valor, float(padrao), float(minimo)))
    return min(max(numero, minimo), maximo)


def booleano_configuracao(valor: object, padrao: bool = True) -> bool:
    """Converte valores booleanos vindos de arquivo local."""
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, str):
        texto = valor.strip().lower()
        if texto in {"1", "true", "sim", "s", "yes"}:
            return True
        if texto in {"0", "false", "não", "nao", "n", "no"}:
            return False
    try:
        if pd.isna(valor):
            return padrao
    except (TypeError, ValueError):
        pass
    return bool(valor)


def texto_configuracao(valor: object, padrao: str = "") -> str:
    """Normaliza campos de texto vindos de backup."""
    try:
        if pd.isna(valor):
            return padrao
    except (TypeError, ValueError):
        pass
    return str(valor)


def normalizar_configuracoes_backup(configuracoes: object) -> dict[str, object]:
    """Garante que as configurações importadas cabem nos campos da sessão."""
    dados = configuracoes if isinstance(configuracoes, dict) else {}
    return {
        "somar_dividas": booleano_configuracao(dados.get("somar_dividas", True), True),
        "meta_objetivo": texto_configuracao(dados.get("meta_objetivo", "")),
        "meta_valor_total": numero_configuracao(dados.get("meta_valor_total", 0.0), 0.0),
        "meta_prazo_meses": inteiro_configuracao(dados.get("meta_prazo_meses", 6), 6, 1, 240),
        "sim_valor_inicial": numero_configuracao(dados.get("sim_valor_inicial", 300.0), 300.0),
        "sim_valor_mensal": numero_configuracao(dados.get("sim_valor_mensal", 100.0), 100.0),
        "sim_meses": inteiro_configuracao(dados.get("sim_meses", 12), 12, 1, 360),
    }


def obter_configuracoes_backup() -> dict[str, object]:
    """Reúne as configurações atuais para exportação e restauração local."""
    return normalizar_configuracoes_backup(
        {
            "somar_dividas": st.session_state.get("somar_dividas", True),
            "meta_objetivo": st.session_state.get("meta_objetivo", ""),
            "meta_valor_total": st.session_state.get("meta_valor_total", 0.0),
            "meta_prazo_meses": st.session_state.get("meta_prazo_meses", 6),
            "sim_valor_inicial": st.session_state.get("sim_valor_inicial", 300.0),
            "sim_valor_mensal": st.session_state.get("sim_valor_mensal", 100.0),
            "sim_meses": st.session_state.get("sim_meses", 12),
        }
    )


def periodo_resumo_backup(lancamentos: pd.DataFrame) -> str:
    """Resume o período encontrado no backup importado."""
    if lancamentos.empty or "Data" not in lancamentos.columns:
        return "Sem período identificado"
    datas = pd.to_datetime(lancamentos["Data"], errors="coerce").dropna()
    if datas.empty:
        return "Sem período identificado"

    primeira = datas.min()
    ultima = datas.max()
    inicio = f"{MESES_PT[int(primeira.month)]}/{int(primeira.year)}"
    fim = f"{MESES_PT[int(ultima.month)]}/{int(ultima.year)}"
    if inicio == fim:
        return f"Dados de {fim}"
    return f"Dados de {inicio} a {fim}"


def resumir_backup_importado(
    lancamentos: pd.DataFrame,
    dividas: pd.DataFrame,
    configuracoes: dict[str, object],
) -> dict[str, object]:
    """Monta os dados visuais mostrados após uma restauração."""
    objetivo_meta = str(configuracoes.get("meta_objetivo", "")).strip()
    valor_meta = float(configuracoes.get("meta_valor_total", 0.0) or 0.0)
    return {
        "lancamentos": int(len(lancamentos)),
        "dividas": int(len(dividas)),
        "meta": "Meta ativa encontrada" if objetivo_meta or valor_meta > 0 else "Sem meta ativa",
        "periodo": periodo_resumo_backup(lancamentos),
    }


def mostrar_resumo_importacao(resumo_importacao: dict[str, object]) -> None:
    """Mostra um resumo amigável do arquivo restaurado."""
    st.markdown("#### Backup carregado")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        card("Lançamentos", str(resumo_importacao.get("lancamentos", 0)), "Registros restaurados.", "green")
    with c2:
        card("Dívidas", str(resumo_importacao.get("dividas", 0)), "Parcelas restauradas.", "gold")
    with c3:
        card("Meta", str(resumo_importacao.get("meta", "Sem meta ativa")), "Configuração importada.", "blue")
    with c4:
        card("Período", str(resumo_importacao.get("periodo", "Sem período identificado")), "Datas do arquivo.", "green")


def agendar_importacao(
    lancamentos: pd.DataFrame,
    dividas: pd.DataFrame,
    configuracoes: dict[str, object],
    mensagem: str,
) -> None:
    """Agenda a restauração para a próxima execução, antes da criação dos widgets."""
    lancamentos_normalizados = normalizar_lancamentos(lancamentos)
    dividas_normalizadas = normalizar_dividas(dividas)
    configuracoes_normalizadas = normalizar_configuracoes_backup(configuracoes)
    st.session_state["importacao_pendente"] = {
        "lancamentos_df": lancamentos_normalizados,
        "dividas_df": dividas_normalizadas,
        "configuracoes": configuracoes_normalizadas,
        "resumo": resumir_backup_importado(lancamentos_normalizados, dividas_normalizadas, configuracoes_normalizadas),
        "mensagem": mensagem,
    }


def exportar_json(lancamentos: pd.DataFrame, dividas: pd.DataFrame) -> bytes:
    """Gera um backup JSON para o usuário salvar no próprio dispositivo."""
    dados = {
        "app": DISPLAY_NAME,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "observacao": "Backup local gerado pelo usuário. O app não mantém armazenamento permanente.",
        "lancamentos": dataframe_para_registros_json(lancamentos),
        "dividas": dataframe_para_registros_json(dividas),
        "configuracoes": {chave: valor_para_json(valor) for chave, valor in obter_configuracoes_backup().items()},
    }
    return json.dumps(dados, ensure_ascii=False, indent=2).encode("utf-8")


def importar_json(conteudo: bytes) -> None:
    """Carrega um backup JSON exportado pelo próprio app."""
    dados = json.loads(conteudo.decode("utf-8"))
    if not isinstance(dados, dict) or ("lancamentos" not in dados and "dividas" not in dados):
        raise ValueError("Arquivo JSON incompatível com este app.")

    agendar_importacao(
        pd.DataFrame(dados.get("lancamentos", [])),
        pd.DataFrame(dados.get("dividas", [])),
        dados.get("configuracoes", {}),
        "Arquivo JSON carregado. Os dados foram restaurados nesta sessão.",
    )


def primeira_linha_planilha(planilhas: dict[str, pd.DataFrame], nome: str) -> dict[str, object]:
    """Lê a primeira linha de uma aba do Excel, quando ela existir."""
    tabela = planilhas.get(nome)
    if tabela is None or tabela.empty:
        return {}
    return tabela.iloc[0].to_dict()


def importar_excel(conteudo: bytes) -> None:
    """Carrega uma planilha Excel exportada pelo app."""
    planilhas = pd.read_excel(BytesIO(conteudo), sheet_name=None)
    if "Lancamentos" not in planilhas and "Dividas" not in planilhas:
        raise ValueError("Planilha incompatível com este app.")

    configuracoes = primeira_linha_planilha(planilhas, "Configuracoes")
    if not configuracoes:
        meta = primeira_linha_planilha(planilhas, "Meta")
        configuracoes = {
            "meta_objetivo": meta.get("objetivo", ""),
            "meta_valor_total": meta.get("valor_total", 0.0),
            "meta_prazo_meses": meta.get("prazo_meses", 6),
        }

    agendar_importacao(
        planilhas.get("Lancamentos", pd.DataFrame()),
        planilhas.get("Dividas", pd.DataFrame()),
        configuracoes,
        "Planilha Excel carregada. Os dados foram restaurados nesta sessão.",
    )


def importar_arquivo_local(conteudo: bytes, nome_arquivo: str) -> None:
    """Importa JSON ou Excel salvo no dispositivo do usuário."""
    nome = nome_arquivo.lower()
    if nome.endswith(".json"):
        importar_json(conteudo)
        return
    if nome.endswith(".xlsx"):
        importar_excel(conteudo)
        return
    raise ValueError("Use um arquivo JSON ou Excel exportado por este app.")


def controle_importacao_local(container, prefixo: str) -> None:
    """Mostra o campo de importação reaproveitado na sidebar e no histórico."""
    arquivo = container.file_uploader(
        "Selecionar arquivo JSON ou Excel",
        type=["json", "xlsx"],
        key=f"{prefixo}_arquivo_local",
        label_visibility="collapsed",
    )
    if container.button("Importar arquivo", width="stretch", key=f"{prefixo}_importar_local"):
        if arquivo is None:
            container.warning("Selecione um arquivo JSON ou Excel exportado pelo app.")
        else:
            try:
                importar_arquivo_local(arquivo.getvalue(), arquivo.name)
                rerun_preservando_tela()
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError) as erro:
                container.error(f"Não foi possível carregar o arquivo: {erro}")


def aplicar_importacao_pendente() -> None:
    """Aplica importação antes dos widgets serem criados na execução atual."""
    importacao = st.session_state.pop("importacao_pendente", None)
    if not importacao:
        return

    st.session_state["lancamentos_df"] = importacao["lancamentos_df"]
    st.session_state["dividas_df"] = importacao["dividas_df"]
    for chave, valor in importacao.get("configuracoes", {}).items():
        st.session_state[chave] = valor
    st.session_state["editor_versao"] = int(st.session_state.get("editor_versao", 0)) + 1
    st.session_state["mensagem_importacao"] = importacao.get(
        "mensagem",
        "Arquivo carregado. Os dados foram restaurados nesta sessão.",
    )
    st.session_state["resumo_importacao"] = importacao.get("resumo")
    st.session_state["mensagem_feedback"] = "Dados restaurados com segurança nesta sessão."


def calcular_dividas(dividas: pd.DataFrame) -> float:
    """Soma as parcelas que entram no resultado do mês."""
    if dividas.empty:
        return 0.0
    return float(dividas["Parcela do mês"].sum())


def gerar_resumo(total_receitas: float, total_fixos: float, total_variaveis: float, total_dividas: float) -> dict[str, float]:
    """Junta os totais principais em um resumo do mês."""
    total_gastos = total_fixos + total_variaveis + total_dividas
    saldo = total_receitas - total_gastos
    usado = total_gastos / total_receitas * 100 if total_receitas > 0 else 0.0
    sobrou = saldo / total_receitas * 100 if total_receitas > 0 and saldo > 0 else 0.0
    return {
        "total_receitas": total_receitas,
        "total_fixos": total_fixos,
        "total_variaveis": total_variaveis,
        "total_dividas": total_dividas,
        "total_geral_gastos": total_gastos,
        "saldo_final": saldo,
        "percentual_comprometido": usado,
        "percentual_sobrou": sobrou,
    }


def gerar_diagnostico(resumo: dict[str, float]) -> list[dict[str, str]]:
    """Gera alertas curtos a partir do resultado do mês."""
    total_receitas = resumo["total_receitas"]
    total_gastos = resumo["total_geral_gastos"]
    total_dividas = resumo["total_dividas"]
    saldo = resumo["saldo_final"]
    parte_dividas = total_dividas / total_receitas * 100 if total_receitas > 0 else 0.0

    if total_receitas == 0 and total_gastos == 0:
        return [{"tipo": "info", "titulo": "Comece registrando", "texto": "Inclua uma entrada e os principais gastos.", "acao": "Valores aproximados já ajudam."}]

    mensagens = []
    if saldo < 0:
        mensagens.append({"tipo": "erro", "titulo": "Saiu mais do que entrou", "texto": "O mês fechou negativo.", "acao": "Reduza uma categoria antes do próximo pagamento."})
    elif saldo == 0:
        mensagens.append({"tipo": "aviso", "titulo": "Mês no limite", "texto": "Tudo que entrou já tem destino.", "acao": "Crie uma folga pequena."})
    else:
        mensagens.append({"tipo": "sucesso", "titulo": "Sobrou dinheiro", "texto": "O mês terminou positivo.", "acao": "Separe uma parte da sobra."})

    if parte_dividas >= 30:
        mensagens.append({"tipo": "aviso", "titulo": "Parcelas altas", "texto": "As parcelas pesaram este mês.", "acao": "Evite novas compras parceladas."})

    if saldo <= 0:
        mensagens.append({"tipo": "info", "titulo": "Prioridade do mês", "texto": "Ajuste gastos antes de criar novas metas.", "acao": "Busque fechar sem faltar dinheiro."})
    else:
        mensagens.append({"tipo": "info", "titulo": "Próximo passo", "texto": "A sobra pode virar dinheiro guardado.", "acao": "Comece com um valor pequeno."})
    return mensagens


def gerar_sugestoes_rapidas(resumo: dict[str, float], lancamentos: pd.DataFrame) -> list[str]:
    """Cria sugestões simples de ação para a pessoa testar."""
    if resumo["total_receitas"] == 0:
        return ["Registre o dinheiro que entra no mês.", "Adicione os principais gastos.", "Volte ao resultado depois dos primeiros lançamentos."]

    sugestoes = []
    if resumo["saldo_final"] < 0:
        sugestoes.extend(["Revise os gastos não fixos primeiro.", "Evite nova parcela até o mês fechar positivo.", "Anote gastos pequenos por 7 dias."])
    elif resumo["saldo_final"] == 0:
        sugestoes.extend(["Abra uma pequena folga no mês.", "Reveja assinaturas, delivery e compras não planejadas.", "Separe o dinheiro das contas fixas ao receber."])
    else:
        sugestoes.extend(["Separe uma parte do que sobrou.", "Guarde um valor para emergência.", "Acompanhe por 3 meses para perceber o padrão."])

    gastos = lancamentos[lancamentos["Tipo"] == "Gasto"] if not lancamentos.empty else pd.DataFrame()
    if not gastos.empty:
        maior = gastos.groupby("Categoria")["Valor"].sum().sort_values(ascending=False)
        if not maior.empty:
            sugestoes.append(f"Revise {maior.index[0].lower()}, a categoria que mais pesou.")
    return sugestoes


def principal_categoria_gasto(lancamentos: pd.DataFrame) -> tuple[str, float]:
    """Encontra a categoria de gasto com maior valor."""
    gastos = lancamentos[lancamentos["Tipo"] == "Gasto"] if not lancamentos.empty else pd.DataFrame()
    if gastos.empty:
        return "Ainda não registrada", 0.0
    por_categoria = gastos.groupby("Categoria")["Valor"].sum().sort_values(ascending=False)
    if por_categoria.empty:
        return "Ainda não registrada", 0.0
    return str(por_categoria.index[0]), float(por_categoria.iloc[0])


def nome_curto_categoria(categoria: str) -> str:
    """Deixa alguns nomes mais naturais nas mensagens."""
    nomes = {
        "Mercado e alimentação": "Mercado",
        "Delivery ou lanche fora": "Delivery",
        "Água, luz e internet": "Contas da casa",
        "Cartão de crédito": "Cartão de crédito",
        "Outros gastos": "Outros gastos",
    }
    return nomes.get(categoria, categoria)


def mes_referencia_lancamentos(lancamentos: pd.DataFrame) -> pd.Timestamp:
    """Escolhe o mês mais recente dos lançamentos ou o mês atual."""
    if lancamentos.empty or "Data" not in lancamentos.columns:
        hoje = pd.Timestamp(date.today())
        return pd.Timestamp(year=int(hoje.year), month=int(hoje.month), day=1)
    datas = pd.to_datetime(lancamentos["Data"], errors="coerce").dropna()
    if datas.empty:
        hoje = pd.Timestamp(date.today())
        return pd.Timestamp(year=int(hoje.year), month=int(hoje.month), day=1)
    ultima = datas.max()
    return pd.Timestamp(year=int(ultima.year), month=int(ultima.month), day=1)


def comparar_categorias_mes_anterior(lancamentos: pd.DataFrame) -> pd.DataFrame:
    """Compara gastos por categoria com o mês anterior."""
    dados_base = normalizar_lancamentos(lancamentos)
    if dados_base.empty:
        return pd.DataFrame(columns=["Categoria", "Atual", "Anterior", "Diferença", "Tendência", "Texto"])

    referencia = mes_referencia_lancamentos(dados_base)
    anterior = referencia - pd.DateOffset(months=1)
    considerados = expandir_fixos_para_relatorio(dados_base, sorted({int(anterior.year), int(referencia.year)}))
    dados = preparar_lancamentos_ano(considerados)
    if dados.empty:
        return pd.DataFrame(columns=["Categoria", "Atual", "Anterior", "Diferença", "Tendência", "Texto"])

    gastos = dados[dados["Tipo"] == "Gasto"].copy()
    if gastos.empty:
        return pd.DataFrame(columns=["Categoria", "Atual", "Anterior", "Diferença", "Tendência", "Texto"])

    atual = gastos[(gastos["Ano"] == int(referencia.year)) & (gastos["Mês nº"] == int(referencia.month))]
    mes_anterior = gastos[(gastos["Ano"] == int(anterior.year)) & (gastos["Mês nº"] == int(anterior.month))]
    atual_cat = atual.groupby("Categoria")["Valor"].sum()
    anterior_cat = mes_anterior.groupby("Categoria")["Valor"].sum()
    categorias = sorted(set(atual_cat.index).union(set(anterior_cat.index)))

    linhas = []
    for categoria in categorias:
        valor_atual = float(atual_cat.get(categoria, 0.0))
        valor_anterior = float(anterior_cat.get(categoria, 0.0))
        diferenca = valor_atual - valor_anterior
        if abs(diferenca) < 0.01:
            continue
        tendencia = "aumentou" if diferenca > 0 else "reduziu"
        linhas.append(
            {
                "Categoria": str(categoria),
                "Atual": valor_atual,
                "Anterior": valor_anterior,
                "Diferença": diferenca,
                "Tendência": tendencia,
                "Texto": f"{icone_categoria(str(categoria))} {nome_curto_categoria(str(categoria))} {tendencia} {formatar_moeda(abs(diferenca))} em relação ao mês anterior.",
            }
        )

    if not linhas:
        return pd.DataFrame(columns=["Categoria", "Atual", "Anterior", "Diferença", "Tendência", "Texto"])
    return pd.DataFrame(linhas).sort_values("Diferença", key=lambda serie: serie.abs(), ascending=False).reset_index(drop=True)


def gerar_resumo_financeiro_mes(resumo: dict[str, float], lancamentos: pd.DataFrame) -> dict[str, object]:
    """Monta o texto final do mês usando os principais indicadores."""
    categoria, valor_categoria = principal_categoria_gasto(lancamentos)
    saldo = resumo["saldo_final"]
    total_receitas = resumo["total_receitas"]
    parte_dividas = resumo["total_dividas"] / total_receitas * 100 if total_receitas > 0 else 0.0
    tendencias = comparar_categorias_mes_anterior(lancamentos)

    if total_receitas == 0:
        recomendacao = "Comece registrando uma entrada, como salário, ajuda recebida ou venda feita no mês."
    elif valor_categoria == 0:
        recomendacao = "Entradas registradas. Adicione os principais gastos para entender para onde o dinheiro está indo."
    elif saldo < 0:
        recomendacao = f"{nome_curto_categoria(categoria)} foi a categoria que mais pesou. Procure uma redução pequena para o próximo mês."
    elif parte_dividas >= 20:
        recomendacao = "Cartão de crédito e parcelas estão pesando no orçamento deste mês."
    elif not tendencias.empty and tendencias.iloc[0]["Tendência"] == "aumentou":
        recomendacao = str(tendencias.iloc[0]["Texto"])
    elif categoria in ["Delivery ou lanche fora", "Lazer", "Compras", "Assinaturas"]:
        recomendacao = f"{nome_curto_categoria(categoria)} foi a principal categoria de gasto. Pequenas reduções podem ajudar a formar uma reserva financeira."
    elif saldo > 0:
        recomendacao = f"{nome_curto_categoria(categoria)} foi a principal categoria, e o mês terminou com sobra."
    else:
        recomendacao = "O mês ficou no limite. Tente criar uma folga pequena antes de assumir novos gastos."

    return {
        "entrou": resumo["total_receitas"],
        "saiu": resumo["total_geral_gastos"],
        "categoria": categoria,
        "valor_categoria": valor_categoria,
        "saldo": saldo,
        "recomendacao": recomendacao,
        "tendencias": tendencias,
    }


def preparar_lancamentos_ano(lancamentos: pd.DataFrame) -> pd.DataFrame:
    """Adiciona ano e mês para relatórios anuais."""
    dados = lancamentos.copy()
    if dados.empty:
        return dados
    dados["Data_dt"] = pd.to_datetime(dados["Data"], errors="coerce")
    dados = dados.dropna(subset=["Data_dt"]).copy()
    dados["Ano"] = dados["Data_dt"].dt.year
    dados["Mês nº"] = dados["Data_dt"].dt.month
    dados["Mês"] = dados["Mês nº"].map(MESES_PT)
    return dados


def inicio_do_mes(valor: object) -> pd.Timestamp | None:
    """Transforma uma data no primeiro dia do mês."""
    data = pd.to_datetime(valor, errors="coerce")
    if pd.isna(data):
        return None
    return pd.Timestamp(year=int(data.year), month=int(data.month), day=1)


def data_repetida_no_mes(mes: pd.Timestamp, dia_preferido: int) -> date:
    """Repete uma data no mês respeitando meses com menos dias."""
    ultimo_dia = int((mes + pd.offsets.MonthEnd(0)).day)
    return date(int(mes.year), int(mes.month), min(max(dia_preferido, 1), ultimo_dia))


def expandir_fixos_para_relatorio(lancamentos: pd.DataFrame, anos: list[int]) -> pd.DataFrame:
    """Repete lançamentos fixos mês a mês dentro do período selecionado."""
    dados = normalizar_lancamentos(lancamentos)
    if dados.empty or not anos:
        return dados

    periodo_inicio = pd.Timestamp(year=min(anos), month=1, day=1)
    periodo_fim = pd.Timestamp(year=max(anos), month=12, day=1)
    linhas = []

    for _, linha in dados.iterrows():
        linha_dict = linha.to_dict()
        data_lancamento = pd.to_datetime(linha_dict.get("Data"), errors="coerce")
        if pd.isna(data_lancamento):
            continue

        if bool(linha_dict.get("Fixo", False)):
            inicio = inicio_do_mes(linha_dict.get("Início")) or inicio_do_mes(linha_dict.get("Data"))
            fim = inicio_do_mes(linha_dict.get("Fim")) or periodo_fim
            if inicio is None:
                continue
            if fim < inicio:
                fim = inicio

            mes_atual = max(inicio, periodo_inicio)
            mes_limite = min(fim, periodo_fim)
            dia_preferido = int(data_lancamento.day)

            # Aqui cada lançamento fixo vira uma linha por mês dentro do período selecionado.
            while mes_atual <= mes_limite:
                repetido = linha_dict.copy()
                repetido["Data"] = data_repetida_no_mes(mes_atual, dia_preferido)
                repetido["Origem no relatório"] = "Fixo repetido"
                linhas.append(repetido)
                mes_atual = mes_atual + pd.DateOffset(months=1)
        else:
            data_mes = inicio_do_mes(linha_dict.get("Data"))
            if data_mes is not None and periodo_inicio <= data_mes <= periodo_fim:
                linha_dict["Origem no relatório"] = "Lançamento único"
                linhas.append(linha_dict)

    if not linhas:
        colunas = list(dados.columns) + ["Origem no relatório"]
        return pd.DataFrame(columns=colunas)

    return pd.DataFrame(linhas)


def anos_disponiveis(lancamentos: pd.DataFrame) -> list[int]:
    """Lista anos possíveis para montar o histórico."""
    dados = preparar_lancamentos_ano(lancamentos)
    anos = set([2026, 2027])
    if not dados.empty:
        anos.update(int(ano) for ano in dados["Ano"].dropna().unique())
        inicio = pd.to_datetime(dados.get("Início"), errors="coerce")
        fim = pd.to_datetime(dados.get("Fim"), errors="coerce")
        anos.update(int(ano) for ano in inicio.dropna().dt.year.unique())
        anos.update(int(ano) for ano in fim.dropna().dt.year.unique())
    return sorted(anos)


def gerar_relatorio_anual(lancamentos: pd.DataFrame, anos: list[int]) -> dict[str, pd.DataFrame]:
    """Gera tabelas usadas no histórico anual."""
    considerados = expandir_fixos_para_relatorio(lancamentos, anos)
    dados = preparar_lancamentos_ano(considerados)
    linhas = []

    for ano in anos:
        for mes_numero in range(1, 13):
            mes = dados[(dados["Ano"] == ano) & (dados["Mês nº"] == mes_numero)] if not dados.empty else pd.DataFrame()
            entradas = float(mes.loc[mes["Tipo"] == "Entrada", "Valor"].sum()) if not mes.empty else 0.0
            gastos = mes[mes["Tipo"] == "Gasto"] if not mes.empty else pd.DataFrame()
            gastos_fixos = float(gastos.loc[gastos["Fixo"], "Valor"].sum()) if not gastos.empty else 0.0
            gastos_nao_fixos = float(gastos.loc[~gastos["Fixo"], "Valor"].sum()) if not gastos.empty else 0.0
            total_gastos = gastos_fixos + gastos_nao_fixos
            linhas.append(
                {
                    "Ano": ano,
                    "Mês nº": mes_numero,
                    "Mês": MESES_PT[mes_numero],
                    "Entradas": entradas,
                    "Gastos fixos": gastos_fixos,
                    "Gastos não fixos": gastos_nao_fixos,
                    "Total de gastos": total_gastos,
                    "Sobrou/Faltou": entradas - total_gastos,
                }
            )

    resumo_mensal = pd.DataFrame(linhas)

    if dados.empty:
        categorias = pd.DataFrame(columns=["Ano", "Categoria", "Valor"])
        parceladas = pd.DataFrame(columns=lancamentos.columns)
    else:
        gastos_filtrados = dados[(dados["Ano"].isin(anos)) & (dados["Tipo"] == "Gasto")].copy()
        categorias = (
            gastos_filtrados.groupby(["Ano", "Categoria"], as_index=False)["Valor"].sum().sort_values(["Ano", "Valor"], ascending=[True, False])
            if not gastos_filtrados.empty
            else pd.DataFrame(columns=["Ano", "Categoria", "Valor"])
        )
        parceladas = gastos_filtrados[gastos_filtrados["Parcelado"]].copy() if not gastos_filtrados.empty else pd.DataFrame()
        if not parceladas.empty:
            parceladas["Data"] = parceladas["Data"].map(formatar_data)
            parceladas["Parcelas restantes"] = parceladas["Nº de parcelas"] - parceladas["Parcelas pagas"]
            parceladas = parceladas[
                [
                    "Ano",
                    "Data",
                    "Descrição",
                    "Categoria",
                    "Valor",
                    "Nº de parcelas",
                    "Parcelas pagas",
                    "Parcelas restantes",
                    "Observação",
                ]
            ]

    totais_ano = (
        resumo_mensal.groupby("Ano", as_index=False)[["Entradas", "Gastos fixos", "Gastos não fixos", "Total de gastos", "Sobrou/Faltou"]]
        .sum()
        .sort_values("Ano")
    )
    return {
        "mensal": resumo_mensal,
        "categorias": categorias,
        "parceladas": parceladas,
        "totais_ano": totais_ano,
        "considerados": dados,
    }


def ajustar_largura_colunas_excel(writer) -> None:
    """Ajusta a largura das colunas das planilhas exportadas."""
    for planilha in writer.sheets.values():
        for coluna in planilha.columns:
            maior = max(len(str(celula.value)) if celula.value is not None else 0 for celula in coluna)
            planilha.column_dimensions[coluna[0].column_letter].width = min(maior + 3, 52)


def cabecalhos_excel(planilha) -> dict[str, str]:
    """Mapeia nome da coluna para letra da coluna no Excel."""
    return {celula.value: celula.column_letter for celula in planilha[1] if celula.value is not None}


def aplicar_formato_excel(writer, nome_planilha: str, nomes_colunas: list[str], formato: str) -> None:
    """Aplica formato numérico em colunas específicas, se elas existirem."""
    planilha = writer.sheets[nome_planilha]
    cabecalhos = cabecalhos_excel(planilha)
    for nome_coluna in nomes_colunas:
        if nome_coluna in cabecalhos:
            for celula in planilha[cabecalhos[nome_coluna]][1:]:
                celula.number_format = formato


def exportar_relatorio_anual_excel(relatorio: dict[str, pd.DataFrame]) -> bytes:
    """Exporta as tabelas anuais para Excel."""
    arquivo = BytesIO()
    with pd.ExcelWriter(arquivo, engine="openpyxl") as writer:
        relatorio["mensal"].to_excel(writer, index=False, sheet_name="Mes a mes")
        relatorio["totais_ano"].to_excel(writer, index=False, sheet_name="Totais por ano")
        relatorio["categorias"].to_excel(writer, index=False, sheet_name="Categorias")
        relatorio["parceladas"].to_excel(writer, index=False, sheet_name="Parceladas")

        ajustar_largura_colunas_excel(writer)
        for nome_planilha in ["Mes a mes", "Totais por ano", "Categorias", "Parceladas"]:
            aplicar_formato_excel(writer, nome_planilha, COLUNAS_MOEDA_RELATORIO, FORMATO_MOEDA_EXCEL)
            aplicar_formato_excel(writer, nome_planilha, COLUNAS_DATA, FORMATO_DATA_EXCEL)
    return arquivo.getvalue()


def taxa_mensal_anual(taxa_aa: float) -> float:
    """Converte taxa anual em taxa mensal composta."""
    return (1 + taxa_aa / 100) ** (1 / 12) - 1


def taxa_poupanca_mensal(selic_aa: float, tr_mensal: float) -> tuple[float, str]:
    """Calcula uma referência simplificada para poupança."""
    if selic_aa <= 8.5:
        base = taxa_mensal_anual(selic_aa * 0.70)
        regra = "referência simples da poupança"
    else:
        base = 0.005
        regra = "referência simples da poupança"
    return base + tr_mensal / 100, regra


def simular_cenarios(
    valor_inicial: float,
    valor_mensal: float,
    meses: int,
    selic_aa: float,
    tr_mensal: float,
) -> dict[str, object]:
    """Simula dinheiro parado, poupança e uma aplicação simples."""
    taxa_poupanca, regra_poupanca = taxa_poupanca_mensal(selic_aa, tr_mensal)
    taxa_aplicacao_simples = taxa_mensal_anual(max(selic_aa, 0))

    saldos = {
        "Poupança": valor_inicial,
        "Aplicação simples": valor_inicial,
    }
    taxas = {
        "Poupança": taxa_poupanca,
        "Aplicação simples": taxa_aplicacao_simples,
    }

    total_colocado = valor_inicial
    linhas = []
    for mes in range(1, meses + 1):
        total_colocado += valor_mensal
        linha = {
            "Mês": mes,
            "Total guardado": total_colocado,
            "Dinheiro parado": total_colocado,
        }
        for nome, taxa in taxas.items():
            saldos[nome] = (saldos[nome] + valor_mensal) * (1 + taxa)
            linha[nome] = saldos[nome]
        linhas.append(linha)

    tabela = pd.DataFrame(linhas)
    final = tabela.iloc[-1].to_dict() if not tabela.empty else {"Total guardado": valor_inicial}
    return {
        "tabela": tabela,
        "final": final,
        "valor_inicial": valor_inicial,
        "valor_mensal": valor_mensal,
        "meses": meses,
        "referencia_aa": selic_aa,
        "regra_poupanca": regra_poupanca,
    }


def carregar_exemplo() -> None:
    """Preenche o app com dados fictícios para demonstração."""
    hoje = date.today()
    mes_atual = date(hoje.year, hoje.month, 1)
    mes_anterior = (pd.Timestamp(mes_atual) - pd.DateOffset(months=1)).date()
    inicio_padrao = date(hoje.year, 1, 1)
    lancamentos_exemplo = [
        {"Data": mes_atual, "Tipo": "Entrada", "Descrição": "Salário", "Categoria": "Salário", "Valor": 2600.0, "Fixo": True, "Início": inicio_padrao},
        {"Data": mes_atual.replace(day=5), "Tipo": "Entrada", "Descrição": "Horas extras", "Categoria": "Horas extras", "Valor": 280.0},
        {"Data": mes_atual.replace(day=3), "Descrição": "Aluguel", "Categoria": "Moradia", "Valor": 780.0, "Fixo": True, "Início": inicio_padrao},
        {"Data": mes_atual.replace(day=8), "Descrição": "Mercado Extra", "Categoria": "Mercado e alimentação", "Valor": 690.0},
        {"Data": mes_atual.replace(day=12), "Descrição": "iFood", "Categoria": "Delivery ou lanche fora", "Valor": 210.0},
        {"Data": mes_atual.replace(day=14), "Descrição": "Uber", "Categoria": "Transporte", "Valor": 135.0},
        {"Data": mes_atual.replace(day=15), "Descrição": "Netflix", "Categoria": "Assinaturas", "Valor": 59.90, "Fixo": True, "Início": inicio_padrao},
        {"Data": mes_atual.replace(day=17), "Descrição": "Shopee", "Categoria": "Compras", "Valor": 180.0},
        {"Data": mes_atual.replace(day=18), "Descrição": "Farmácia", "Categoria": "Saúde", "Valor": 96.0},
        {"Data": mes_atual.replace(day=10), "Descrição": "Internet", "Categoria": "Água, luz e internet", "Valor": 109.90, "Fixo": True, "Início": inicio_padrao},
        {"Data": mes_atual.replace(day=20), "Descrição": "Conta de luz", "Categoria": "Água, luz e internet", "Valor": 148.0, "Fixo": True, "Início": inicio_padrao},
        {"Data": mes_anterior.replace(day=8), "Descrição": "Mercado Extra", "Categoria": "Mercado e alimentação", "Valor": 510.0},
        {"Data": mes_anterior.replace(day=12), "Descrição": "iFood", "Categoria": "Delivery ou lanche fora", "Valor": 120.0},
        {"Data": mes_anterior.replace(day=14), "Descrição": "Uber", "Categoria": "Transporte", "Valor": 90.0},
        {"Data": mes_anterior.replace(day=17), "Descrição": "Shopee", "Categoria": "Compras", "Valor": 95.0},
        {
            "Data": mes_atual.replace(day=16),
            "Descrição": "Tênis parcelado",
            "Categoria": "Compras",
            "Valor": 90.0,
            "Parcelado": True,
            "Nº de parcelas": 5,
            "Parcelas pagas": 2,
            "Observação": "Parcela atual",
        },
    ]
    st.session_state["lancamentos_df"] = pd.DataFrame(
        [montar_lancamento(**item) for item in lancamentos_exemplo]
    )
    st.session_state["dividas_df"] = pd.DataFrame(
        [
            {"Dívida": "Cartão de crédito", "Falta pagar": 1200.0, "Parcela do mês": 300.0, "Parcelas restantes": 4, "Observação": "Vence dia 10"},
            {"Dívida": "Notebook parcelado", "Falta pagar": 720.0, "Parcela do mês": 180.0, "Parcelas restantes": 4, "Observação": "Loja online"},
        ]
    )
    st.session_state["somar_dividas"] = True
    st.session_state["meta_valor_total"] = 1000.0
    st.session_state["meta_objetivo"] = "Dinheiro guardado para emergência"
    st.session_state["meta_prazo_meses"] = 8
    st.session_state["sim_valor_inicial"] = 300.0
    st.session_state["sim_valor_mensal"] = 100.0
    st.session_state["sim_meses"] = 12
    st.session_state["mensagem_feedback"] = "Exemplo carregado com dados próximos do cotidiano."


def aplicar_exemplo_pendente() -> None:
    """Carrega o exemplo antes dos widgets serem criados."""
    if st.session_state.pop("carregar_exemplo_pendente", False):
        carregar_exemplo()


def lancamentos_atuais() -> pd.DataFrame:
    """Lê os lançamentos da sessão mesmo quando a tela Registrar não está aberta."""
    if "lancamentos_df" not in st.session_state:
        st.session_state["lancamentos_df"] = criar_lancamentos_padrao()
    return normalizar_lancamentos(st.session_state["lancamentos_df"])


def dividas_atuais() -> tuple[pd.DataFrame, float]:
    """Lê as dívidas da sessão mesmo quando a tela Dívidas não está aberta."""
    if "dividas_df" not in st.session_state:
        st.session_state["dividas_df"] = criar_dividas_padrao()
    dividas = normalizar_dividas(st.session_state["dividas_df"])
    somar = bool(st.session_state.get("somar_dividas", True))
    return dividas, calcular_dividas(dividas) if somar else 0.0


def meta_atual(saldo: float) -> dict[str, object]:
    """Monta a meta atual sem precisar renderizar a tela de metas."""
    objetivo = str(st.session_state.get("meta_objetivo", "") or "")
    valor_total = float(st.session_state.get("meta_valor_total", 0.0) or 0.0)
    prazo = int(st.session_state.get("meta_prazo_meses", 6) or 6)
    prazo = max(1, min(prazo, 240))
    mensal = valor_total / prazo if prazo else 0.0
    cabe = saldo >= mensal and mensal > 0
    return {
        "objetivo": objetivo,
        "valor_total": valor_total,
        "prazo_meses": prazo,
        "valor_mensal_necessario": mensal,
        "situacao": "Sim" if cabe else "Não",
    }


def simulacao_atual(meta: dict[str, object]) -> dict[str, object]:
    """Monta a simulação atual sem precisar renderizar a tela Guardando dinheiro."""
    taxas = obter_taxas_bcb()
    referencia_aa = float(taxas["selic_aa"])
    tr_mensal = float(taxas["tr_mensal"])
    meses_padrao = max(int(meta.get("prazo_meses", 12)), 1)
    return simular_cenarios(
        valor_inicial=float(st.session_state.get("sim_valor_inicial", 300.0) or 0.0),
        valor_mensal=float(st.session_state.get("sim_valor_mensal", meta.get("valor_mensal_necessario", 0.0)) or 0.0),
        meses=int(st.session_state.get("sim_meses", meses_padrao) or meses_padrao),
        selic_aa=referencia_aa,
        tr_mensal=tr_mensal,
    )


def seletor_tela() -> str:
    """Mantém a tela atual mesmo quando alguma ação chama st.rerun()."""
    if st.session_state.get("aba_atual") not in ABAS_APP:
        st.session_state["aba_atual"] = "Início"
    return st.radio("Navegação", ABAS_APP, horizontal=True, label_visibility="collapsed", key="aba_atual")


def tela_inicio() -> None:
    """Monta a primeira tela com o resumo do app."""
    st.markdown(
        f"""
        <div class="hero">
            <h1>{DISPLAY_NAME}</h1>
            <p>Organize entradas, gastos, parcelas e metas em poucos minutos.</p>
            <p>As comparações possuem caráter informativo.</p>
            <div class="chip-row">
                <span class="chip">Registrar</span>
                <span class="chip">Resultado do mês</span>
                <span class="chip">Metas</span>
                <span class="chip">Histórico</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.info(
        "Seus dados não ficam salvos no servidor. Para continuar utilizando depois, exporte sua planilha ou arquivo JSON."
    )
    st.caption("Os arquivos exportados ficam armazenados apenas no seu dispositivo.")
    c1, c2 = st.columns(2)
    with c1:
        card("💰 Entradas", "Anote o que entrou", "Salário, benefício, venda, bico ou ajuda recebida.", "green")
    with c2:
        card("📉 Gastos", "Veja para onde foi", "Mercado, moradia, delivery, transporte e compras.", "red")
    c3, c4 = st.columns(2)
    with c3:
        card("⚠️ Parcelas", "Controle o mês", "Acompanhe dívidas e compras parceladas sem misturar tudo.", "gold")
    with c4:
        card("🎯 Metas", "Guarde com clareza", "Defina um objetivo e veja quanto precisa separar.", "blue")


def aba_lancamentos() -> pd.DataFrame:
    """Cuida do cadastro e edição de entradas e gastos."""
    st.subheader("Registrar")
    st.markdown(
        '<p class="note">Adicione entradas e gastos do mês. Use detalhes apenas quando precisar marcar fixos ou parcelas.</p>',
        unsafe_allow_html=True,
    )

    if "lancamentos_df" not in st.session_state:
        st.session_state["lancamentos_df"] = criar_lancamentos_padrao()

    with st.form("lancamento_rapido", clear_on_submit=True):
        c1, c2, c3, c4, c5 = st.columns([.9, 1.1, 1.6, 1.4, 1])
        with c1:
            data_lancamento = st.date_input("Data", value=date.today())
        with c2:
            tipo = st.selectbox("Tipo", TIPOS_LANCAMENTO)
        categorias = CATEGORIAS_ENTRADA if tipo == "Entrada" else CATEGORIAS_GASTO
        with c3:
            descricao = st.text_input("Descrição", placeholder="Exemplo: Mercado Extra, iFood, Uber")
        with c4:
            categoria = st.selectbox("Categoria", categorias, format_func=lambda item: f"{icone_categoria(item)} {item}")
        with c5:
            valor = st.number_input("Valor", min_value=0.0, step=10.0, format="%.2f")

        if st.form_submit_button("Adicionar", width="stretch"):
            if valor > 0:
                novo = criar_lancamento_vazio(tipo)
                novo.update(
                    {
                        "Data": data_lancamento,
                        "Descrição": descricao.strip() or categoria,
                        "Categoria": categoria,
                        "Valor": float(valor),
                    }
                )
                st.session_state["lancamentos_df"] = pd.concat([st.session_state["lancamentos_df"], pd.DataFrame([novo])], ignore_index=True)
                st.success("Lançamento adicionado.")
            else:
                st.warning("Informe um valor maior que zero.")

    if st.button("Adicionar linha vazia", width="content"):
        st.session_state["lancamentos_df"] = pd.concat(
            [st.session_state["lancamentos_df"], pd.DataFrame([criar_lancamento_vazio()])],
            ignore_index=True,
        )
        st.success("Linha vazia adicionada.")

    mostrar_detalhes = st.toggle("Mostrar detalhes", value=False)
    colunas_editor = COLUNAS_LANCAMENTOS_BASICAS + (COLUNAS_LANCAMENTOS_DETALHES if mostrar_detalhes else [])

    versao_editor = int(st.session_state.get("editor_versao", 0))
    editado = st.data_editor(
        st.session_state["lancamentos_df"],
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_order=colunas_editor,
        column_config={
            "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "Tipo": st.column_config.SelectboxColumn("Tipo", options=TIPOS_LANCAMENTO, required=True),
            "Descrição": st.column_config.TextColumn("Descrição", help="Exemplo: Salário, Mercado Extra, iFood, Uber"),
            "Categoria": st.column_config.SelectboxColumn("Categoria", options=CATEGORIAS_LANCAMENTO, help="Escolha uma categoria simples."),
            "Valor": st.column_config.NumberColumn("Valor (R$)", min_value=0.0, step=1.0, format="%.2f"),
            "Fixo": st.column_config.CheckboxColumn("Fixo"),
            "Início": st.column_config.DateColumn("Início", format="DD/MM/YYYY", help="Use para entradas ou gastos fixos que se repetem todo mês."),
            "Fim": st.column_config.DateColumn("Fim", format="DD/MM/YYYY", help="Opcional. Se ficar vazio, repete até o fim do relatório."),
            "Parcelado": st.column_config.CheckboxColumn("Parcelado"),
            "Nº de parcelas": st.column_config.NumberColumn("Nº de parcelas", min_value=1, step=1),
            "Parcelas pagas": st.column_config.NumberColumn("Parcelas pagas", min_value=0, step=1),
            "Observação": st.column_config.TextColumn("Observação"),
        },
        key=f"editor_lancamentos_{versao_editor}",
    )
    st.session_state["lancamentos_df"] = editado

    lancamentos = normalizar_lancamentos(editado)
    if lancamentos.empty:
        empty_state("Sem lançamentos", "Comece registrando sua primeira entrada ou gasto. Um valor aproximado já ajuda a visualizar o mês.")
        return lancamentos

    entradas = calcular_receitas(lancamentos)
    gastos = calcular_gastos(lancamentos)
    total_gastos = gastos["total_fixos"] + gastos["total_variaveis"]

    c1, c2 = st.columns(2)
    with c1:
        card("💰 Entradas registradas", formatar_moeda(entradas), "Dinheiro que entrou.", "green")
    with c2:
        card("📉 Gastos registrados", formatar_moeda(total_gastos), "Tudo que saiu nos lançamentos.", "red")
    c3, c4 = st.columns(2)
    with c3:
        card("🏠 Fixos", formatar_moeda(gastos["total_fixos"]), "Marcados como fixos.", "gold")
    with c4:
        card("🛍️ Variáveis", formatar_moeda(gastos["total_variaveis"]), "Compras e gastos que variam.", "blue")

    if not lancamentos.empty:
        st.markdown("#### Resumo por categoria")
        por_categoria = (
            lancamentos.groupby(["Tipo", "Categoria"], as_index=False)["Valor"].sum().sort_values(["Tipo", "Valor"], ascending=[True, False])
        )
        por_categoria["Categoria"] = por_categoria["Categoria"].map(lambda item: f"{icone_categoria(item)} {item}")
        tabela = por_categoria.copy()
        tabela["Valor"] = tabela["Valor"].map(formatar_moeda)
        st.dataframe(tabela, hide_index=True, width="stretch")
    return lancamentos


def aba_dividas() -> tuple[pd.DataFrame, float]:
    """Cuida das dívidas e parcelas cadastradas separadamente."""
    st.subheader("Dívidas e parcelas")
    st.markdown('<p class="note">Acompanhe parcelas do mês usando nomes simples, sem dados pessoais.</p>', unsafe_allow_html=True)

    if "dividas_df" not in st.session_state:
        st.session_state["dividas_df"] = criar_dividas_padrao()

    somar = st.checkbox(
        "Somar parcelas cadastradas no resultado do mês",
        value=bool(st.session_state.get("somar_dividas", True)),
        key="somar_dividas",
        help="Se a mesma parcela já foi lançada em Registrar, deixe desmarcado para não contar duas vezes.",
    )
    versao_editor = int(st.session_state.get("editor_versao", 0))
    editado = st.data_editor(
        st.session_state["dividas_df"],
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_config={
            "Dívida": st.column_config.TextColumn("Dívida", help="Exemplo: cartão de crédito, notebook parcelado, loja"),
            "Falta pagar": st.column_config.NumberColumn("Falta pagar (R$)", min_value=0.0, step=50.0, format="%.2f"),
            "Parcela do mês": st.column_config.NumberColumn("Parcela do mês (R$)", min_value=0.0, step=10.0, format="%.2f"),
            "Parcelas restantes": st.column_config.NumberColumn("Parcelas restantes", min_value=0, step=1),
            "Observação": st.column_config.TextColumn("Observação"),
        },
        key=f"editor_dividas_{versao_editor}",
    )
    st.session_state["dividas_df"] = editado
    dividas = normalizar_dividas(editado)
    total = calcular_dividas(dividas) if somar else 0.0
    total_restante = float(dividas["Falta pagar"].sum()) if not dividas.empty else 0.0
    parcelas_restantes = int(dividas["Parcelas restantes"].sum()) if not dividas.empty else 0

    if dividas.empty:
        empty_state("Sem dívidas cadastradas", "Adicione apenas parcelas que ainda pesam no mês. Se já lançou em Registrar, deixe a soma desmarcada para não contar duas vezes.")

    c1, c2, c3 = st.columns(3)
    with c1:
        card("⚠️ Parcelas do mês", formatar_moeda(calcular_dividas(dividas)), "Soma das parcelas cadastradas.", "red")
    with c2:
        card("💳 Total restante", formatar_moeda(total_restante), "Valor ainda em aberto.", "gold")
    with c3:
        card("📦 Parcelas restantes", str(parcelas_restantes), "Quantidade total de parcelas.", "blue")
    c4, _ = st.columns(2)
    with c4:
        card("📌 No resultado", formatar_moeda(total), "Peso mensal considerado no mês.", "green" if total == 0 else "red")
    return dividas, total


def exibir_painel(
    resumo: dict[str, float],
    lancamentos: pd.DataFrame,
    diagnostico: list[dict[str, str]],
    sugestoes: list[str],
    resumo_final: dict[str, object],
    dividas: pd.DataFrame | None = None,
) -> None:
    """Mostra o resultado do mês com cards, alertas e gráficos."""
    st.subheader("Resultado do mês")
    saldo = resumo["saldo_final"]
    c1, c2 = st.columns(2)
    with c1:
        card("💰 Entrou", formatar_moeda(resumo["total_receitas"]), "Entradas lançadas.", "green")
    with c2:
        card("📉 Saiu", formatar_moeda(resumo["total_geral_gastos"]), "Gastos e parcelas.", "red")
    c3, c4 = st.columns(2)
    with c3:
        card("✅ Sobrou" if saldo >= 0 else "⚠️ Faltou", formatar_moeda(abs(saldo)), "Entrou menos saiu.", "blue" if saldo >= 0 else "gold")
    with c4:
        card("Principal categoria", str(resumo_final["categoria"]), formatar_moeda(float(resumo_final["valor_categoria"])), "gold")

    if resumo["total_receitas"] == 0 and resumo["total_geral_gastos"] == 0:
        empty_state("Sem resultado ainda", "Registre uma entrada e um gasto para o app mostrar o mês com mais clareza.")

    panel_html("Insight do mês", str(resumo_final["recomendacao"]))

    tendencias = resumo_final.get("tendencias", pd.DataFrame())
    if isinstance(tendencias, pd.DataFrame) and not tendencias.empty:
        panel_html("Tendência", str(tendencias.iloc[0]["Texto"]))

    dividas_backup = dividas if dividas is not None else pd.DataFrame(columns=COLUNAS_DIVIDAS)
    st.download_button(
        "💾 Salvar backup JSON",
        data=exportar_json(lancamentos, dividas_backup),
        file_name=nome_arquivo_exportacao("json"),
        mime=MIME_JSON,
        width="stretch",
        type="primary",
        key="resultado_backup_json",
        on_click=registrar_feedback,
        args=("Backup JSON pronto para salvar no dispositivo.",),
    )

    with st.expander("Ver mais"):
        progresso = min(max(resumo["percentual_comprometido"], 0), 100)
        st.progress(int(progresso), text=f"{formatar_decimal(resumo['percentual_comprometido'])}% do dinheiro que entrou já foi usado.")

        st.markdown("#### Alertas rápidos")
        for item in diagnostico:
            texto = f"**{item['titulo']}**  \n{item['texto']} Ação: {item['acao']}"
            if item["tipo"] == "erro":
                st.error(texto)
            elif item["tipo"] == "aviso":
                st.warning(texto)
            elif item["tipo"] == "sucesso":
                st.success(texto)
            else:
                st.info(texto)

        if isinstance(tendencias, pd.DataFrame) and not tendencias.empty:
            st.markdown("#### Comparação com mês anterior")
            tabela_tendencias = tendencias[["Categoria", "Atual", "Anterior", "Diferença", "Tendência"]].copy()
            tabela_tendencias["Atual"] = tabela_tendencias["Atual"].map(formatar_moeda)
            tabela_tendencias["Anterior"] = tabela_tendencias["Anterior"].map(formatar_moeda)
            tabela_tendencias["Diferença"] = tabela_tendencias["Diferença"].map(formatar_moeda)
            st.dataframe(tabela_tendencias, hide_index=True, width="stretch")

        col_grafico, col_sugestoes = st.columns([1.25, 1])
        with col_grafico:
            st.markdown("#### Categorias que mais pesaram")
            gastos = lancamentos[lancamentos["Tipo"] == "Gasto"] if not lancamentos.empty else pd.DataFrame()
            if gastos.empty:
                st.info("Registre gastos para ver o gráfico.")
            else:
                dados = gastos.groupby("Categoria", as_index=False)["Valor"].sum().sort_values("Valor", ascending=False).head(8)
                dados["Categoria"] = dados["Categoria"].map(lambda item: f"{icone_categoria(item)} {item}")
                dados["Texto"] = dados["Valor"].map(formatar_moeda)
                fig = grafico_barras_horizontais(dados, "Categoria")
                fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig, width="stretch")
        with col_sugestoes:
            st.markdown("#### Sugestões rápidas")
            for sugestao in sugestoes[:4]:
                panel_html("Ação rápida", sugestao)

        st.markdown("#### Entrou x saiu")
        if resumo["total_receitas"] == 0 and resumo["total_geral_gastos"] == 0:
            st.info("Registre entradas e gastos para comparar o mês.")
        else:
            dados = pd.DataFrame({"Tipo": ["Entrou", "Saiu"], "Valor": [resumo["total_receitas"], resumo["total_geral_gastos"]]})
            dados["Texto"] = dados["Valor"].map(formatar_moeda)
            fig = px.bar(dados, x="Tipo", y="Valor", text="Texto", color="Tipo", color_discrete_map={"Entrou": "#2f7d59", "Saiu": "#c45f4b"})
            fig.update_traces(textposition="outside", cliponaxis=False)
            limpar_grafico(fig)
            aplicar_eixo_moeda(fig)
            st.plotly_chart(fig, width="stretch")

def aba_metas(saldo: float) -> dict[str, object]:
    """Calcula quanto guardar por mês para uma meta."""
    st.subheader("Meta para guardar dinheiro")
    st.markdown('<p class="note">Defina um objetivo simples e veja se cabe no dinheiro que sobrou.</p>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.4, 1])
    with c1:
        valor_total = dinheiro_input("Quanto quer juntar?", "meta_valor_total")
    with c2:
        objetivo = st.text_input("Para quê?", key="meta_objetivo", placeholder="Exemplo: emergência, curso, compra planejada")
    with c3:
        prazo = st.number_input("Em quantos meses?", min_value=1, max_value=240, value=int(st.session_state.get("meta_prazo_meses", 6)), step=1, key="meta_prazo_meses")

    mensal = valor_total / prazo if prazo else 0.0
    cabe = saldo >= mensal and mensal > 0

    if valor_total <= 0 and not objetivo.strip():
        empty_state("Sem metas", "Crie uma meta simples para acompanhar seu progresso, como reserva de emergência, curso ou compra planejada.")

    if st.button("Salvar meta", width="content"):
        st.success("Meta salva.")

    c4, c5 = st.columns(2)
    with c4:
        card("🎯 Guardar por mês", formatar_moeda(mensal), "Valor necessário para chegar no prazo.", "green")
    with c5:
        card("💰 Sobra do mês", formatar_moeda(max(saldo, 0)), "Valor disponível no resultado.", "blue" if saldo > 0 else "gold")

    if valor_total > 0 and not cabe:
        st.warning("A meta pode ficar mais leve aumentando o prazo ou criando uma folga maior no mês.")
    elif valor_total > 0 and cabe:
        st.success("A meta cabe no dinheiro que sobrou. O próximo passo é separar esse valor assim que receber.")

    if mensal > 0:
        dados = pd.DataFrame({"Mês": list(range(1, int(prazo) + 1)), "Dinheiro guardado": [mensal * mes for mes in range(1, int(prazo) + 1)]})
        fig = px.line(dados, x="Mês", y="Dinheiro guardado", markers=True)
        fig.update_traces(line_color="#2f6f9f")
        limpar_grafico(fig, margem=dict(l=10, r=10, t=30, b=10))
        aplicar_eixo_moeda(fig)
        st.plotly_chart(fig, width="stretch")

    return {"objetivo": objetivo, "valor_total": valor_total, "prazo_meses": int(prazo), "valor_mensal_necessario": mensal, "situacao": "Sim" if cabe else "Não"}


def aba_guardando_dinheiro(meta: dict[str, object]) -> dict[str, object]:
    """Mostra a simulação de dinheiro guardado ao longo do tempo."""
    st.subheader("Guardando dinheiro")
    st.markdown('<p class="note">Compare caminhos simples para visualizar a diferença de guardar todo mês.</p>', unsafe_allow_html=True)
    st.info("As comparações possuem caráter informativo.")

    taxas = obter_taxas_bcb()
    if not taxas["ok"]:
        st.caption("Usando uma referência padrão porque não foi possível atualizar os valores agora.")

    referencia_aa = float(taxas["selic_aa"])
    tr_mensal = float(taxas["tr_mensal"])

    c1, c2, c3 = st.columns(3)
    with c1:
        valor_inicial = dinheiro_input("Dinheiro já guardado", "sim_valor_inicial")
    with c2:
        valor_mensal = st.number_input("Guardar por mês", min_value=0.0, value=float(st.session_state.get("sim_valor_mensal", meta.get("valor_mensal_necessario", 0.0))), step=50.0, format="%.2f", key="sim_valor_mensal")
    with c3:
        meses = st.number_input("Por quantos meses", min_value=1, max_value=360, value=int(st.session_state.get("sim_meses", max(int(meta.get("prazo_meses", 12)), 1))), step=1, key="sim_meses")

    simulacao = simular_cenarios(
        valor_inicial=float(valor_inicial),
        valor_mensal=float(valor_mensal),
        meses=int(meses),
        selic_aa=float(referencia_aa),
        tr_mensal=float(tr_mensal),
    )

    final = simulacao["final"]
    st.markdown("#### Resultado aproximado")
    cols = st.columns(2)
    with cols[0]:
        card("💵 Dinheiro parado", formatar_moeda(final["Dinheiro parado"]), "Mesmo dinheiro sem render.", "green")
    with cols[1]:
        card("🏦 Poupança", formatar_moeda(final["Poupança"]), "Comparação simples e conhecida.", "blue")
    col3, _ = st.columns(2)
    with col3:
        card("📈 Aplicação simples", formatar_moeda(final["Aplicação simples"]), "Estimativa para comparar com dinheiro parado.", "gold")

    tabela = simulacao["tabela"]
    diferenca = float(final["Aplicação simples"]) - float(final["Dinheiro parado"])
    if diferenca > 0:
        st.success(f"A diferença estimada entre deixar parado e aplicar de forma simples é de {formatar_moeda(diferenca)} no período.")

    dados = pd.DataFrame(
        {
            "Cenário": ["Dinheiro parado", "Poupança", "Aplicação simples"],
            "Valor": [final["Dinheiro parado"], final["Poupança"], final["Aplicação simples"]],
        }
    )
    dados["Texto"] = dados["Valor"].map(formatar_moeda)
    fig = grafico_barras_horizontais(dados, "Cenário", ["#2f7d59", "#2f6f9f", "#b7791f"])
    st.plotly_chart(fig, width="stretch")

    with st.expander("Ver evolução mês a mês"):
        st.dataframe(formatar_tabela_simulacao(tabela), hide_index=True, width="stretch")

    return simulacao


def montar_resumo_exportacao(resumo: dict[str, float], resumo_final: dict[str, object], meta: dict[str, object], simulacao: dict[str, object], sugestoes: list[str]) -> list[str]:
    """Monta as linhas usadas no PDF e no resumo exportado."""
    linhas = [
        DISPLAY_NAME,
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
        "Resumo mensal",
        f"Entrou: {formatar_moeda(resumo['total_receitas'])}",
        f"Saiu: {formatar_moeda(resumo['total_geral_gastos'])}",
        f"Resultado: {formatar_moeda(resumo['saldo_final'])}",
        f"Parcelas: {formatar_moeda(resumo['total_dividas'])}",
        f"Categoria principal: {resumo_final['categoria']} ({formatar_moeda(float(resumo_final['valor_categoria']))})",
        f"Insight: {resumo_final['recomendacao']}",
        "",
        "Sugestões rápidas",
    ]
    linhas.extend([f"- {sugestao}" for sugestao in sugestoes[:5]])
    linhas.extend(
        [
            "",
            "Meta",
            f"Objetivo: {meta['objetivo'] or 'Não informado'}",
            f"Valor desejado: {formatar_moeda(float(meta['valor_total']))}",
            f"Guardar por mês: {formatar_moeda(float(meta['valor_mensal_necessario']))}",
            f"Cabe agora? {meta['situacao']}",
            "",
            "Guardando dinheiro",
            f"Total guardado: {formatar_moeda(float(simulacao['final']['Total guardado']))}",
        ]
    )
    for chave, valor in simulacao["final"].items():
        if chave not in ["Mês", "Total guardado"]:
            linhas.append(f"{chave}: {formatar_moeda(float(valor))}")
    linhas.extend(["", "As comparações possuem caráter informativo."])
    return linhas


def quebrar_texto(texto: str, limite: int = 92) -> list[str]:
    """Quebra textos longos para caber melhor no PDF."""
    if not texto:
        return [""]
    palavras = texto.split()
    linhas: list[str] = []
    atual = ""
    for palavra in palavras:
        tentativa = palavra if not atual else f"{atual} {palavra}"
        if len(tentativa) <= limite:
            atual = tentativa
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def escapar_pdf(texto: str) -> str:
    """Escapa caracteres que têm significado dentro do PDF."""
    texto = texto.encode("latin-1", "replace").decode("latin-1")
    return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def exportar_pdf(linhas: list[str]) -> bytes:
    """Gera um PDF simples sem depender de biblioteca externa."""
    linhas_pdf: list[str] = []
    for linha in linhas:
        linhas_pdf.extend(quebrar_texto(linha))

    paginas: list[list[str]] = []
    linhas_por_pagina = 48
    for indice in range(0, len(linhas_pdf), linhas_por_pagina):
        paginas.append(linhas_pdf[indice : indice + linhas_por_pagina])
    if not paginas:
        paginas = [[""]]

    objetos: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    ids_paginas = []
    for indice, pagina in enumerate(paginas):
        # O PDF é montado "na mão" para evitar mais uma dependência no projeto.
        conteudo_id = 4 + indice * 2
        pagina_id = conteudo_id + 1
        ids_paginas.append(pagina_id)

        comandos = ["BT", "/F1 11 Tf", "50 790 Td", "14 TL"]
        for linha_indice, linha in enumerate(pagina):
            prefixo = "" if linha_indice == 0 else "T* "
            comandos.append(f"{prefixo}({escapar_pdf(linha)}) Tj")
        comandos.append("ET")
        conteudo = "\n".join(comandos).encode("latin-1", "replace")
        objetos[conteudo_id] = b"<< /Length " + str(len(conteudo)).encode("ascii") + b" >>\nstream\n" + conteudo + b"\nendstream"
        objetos[pagina_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {conteudo_id} 0 R >>"
        ).encode("ascii")

    kids = " ".join(f"{pagina_id} 0 R" for pagina_id in ids_paginas)
    objetos[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(ids_paginas)} >>".encode("ascii")

    maior_id = max(objetos)
    saida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * (maior_id + 1)
    for objeto_id in range(1, maior_id + 1):
        offsets[objeto_id] = len(saida)
        saida.extend(f"{objeto_id} 0 obj\n".encode("ascii"))
        saida.extend(objetos[objeto_id])
        saida.extend(b"\nendobj\n")

    xref_pos = len(saida)
    saida.extend(f"xref\n0 {maior_id + 1}\n".encode("ascii"))
    saida.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        saida.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    saida.extend(f"trailer\n<< /Size {maior_id + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii"))
    return bytes(saida)


def comando_texto_pdf(texto: str, x: int, y: int, tamanho: int = 11) -> str:
    """Monta um comando de texto para o PDF manual."""
    return f"BT /F1 {tamanho} Tf {x} {y} Td ({escapar_pdf(texto)}) Tj ET"


def comando_retangulo_pdf(x: int, y: int, largura: int, altura: int, cor: tuple[float, float, float]) -> str:
    """Monta um retângulo colorido para o PDF manual."""
    r, g, b = cor
    return f"{r:.2f} {g:.2f} {b:.2f} rg {x} {y} {largura} {altura} re f"


def exportar_pdf_resumo(
    resumo: dict[str, float],
    resumo_final: dict[str, object],
    meta: dict[str, object],
    simulacao: dict[str, object],
    sugestoes: list[str],
) -> bytes:
    """Gera um PDF visual de uma página com o resumo essencial."""
    comandos: list[str] = []
    comandos.append(comando_retangulo_pdf(0, 0, 595, 842, (0.96, 0.97, 0.95)))
    comandos.append(comando_retangulo_pdf(36, 730, 523, 74, (1.00, 1.00, 1.00)))
    comandos.append(comando_texto_pdf(DISPLAY_NAME, 50, 780, 17))
    comandos.append(comando_texto_pdf(f"Resumo gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", 50, 758, 10))
    comandos.append(comando_texto_pdf("Dados armazenados apenas na sessão e nos arquivos salvos pelo usuário.", 50, 742, 9))

    valores = [
        ("Entrou", float(resumo["total_receitas"]), (0.18, 0.49, 0.35)),
        ("Saiu", float(resumo["total_geral_gastos"]), (0.77, 0.37, 0.29)),
        ("Resultado", float(resumo["saldo_final"]), (0.18, 0.44, 0.62) if resumo["saldo_final"] >= 0 else (0.72, 0.47, 0.12)),
    ]
    maior = max(max(abs(valor) for _, valor, _ in valores), 1.0)
    y_barra = 690
    comandos.append(comando_texto_pdf("Gráfico simples do mês", 50, y_barra + 28, 13))
    for rotulo, valor, cor in valores:
        largura = int((abs(valor) / maior) * 290)
        comandos.append(comando_texto_pdf(rotulo, 50, y_barra + 3, 10))
        comandos.append(comando_retangulo_pdf(130, y_barra, 300, 14, (0.88, 0.91, 0.88)))
        comandos.append(comando_retangulo_pdf(130, y_barra, max(largura, 4), 14, cor))
        comandos.append(comando_texto_pdf(formatar_moeda(valor), 445, y_barra + 3, 10))
        y_barra -= 32

    linhas = [
        f"Principal gasto: {resumo_final['categoria']} ({formatar_moeda(float(resumo_final['valor_categoria']))})",
        f"Insight: {resumo_final['recomendacao']}",
        "",
        "Meta",
        f"Objetivo: {meta['objetivo'] or 'Não informado'}",
        f"Guardar por mês: {formatar_moeda(float(meta['valor_mensal_necessario']))}",
        f"Cabe agora? {meta['situacao']}",
        "",
        "Guardando dinheiro",
        f"Total guardado previsto: {formatar_moeda(float(simulacao['final']['Total guardado']))}",
        "",
        "Sugestões rápidas",
    ]
    linhas.extend([f"- {sugestao}" for sugestao in sugestoes[:4]])
    linhas.append("As comparações possuem caráter informativo.")

    y_texto = 555
    for linha in linhas:
        if y_texto < 54:
            break
        if linha == "":
            y_texto -= 14
            continue
        tamanho = 12 if linha in ["Meta", "Guardando dinheiro", "Sugestões rápidas"] else 10
        for parte in quebrar_texto(linha, 78):
            comandos.append(comando_texto_pdf(parte, 50, y_texto, tamanho))
            y_texto -= 15

    conteudo = "\n".join(comandos).encode("latin-1", "replace")
    objetos: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [5 0 R] /Count 1 >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        4: b"<< /Length " + str(len(conteudo)).encode("ascii") + b" >>\nstream\n" + conteudo + b"\nendstream",
        5: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents 4 0 R >>",
    }

    saida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * 6
    for objeto_id in range(1, 6):
        offsets[objeto_id] = len(saida)
        saida.extend(f"{objeto_id} 0 obj\n".encode("ascii"))
        saida.extend(objetos[objeto_id])
        saida.extend(b"\nendobj\n")

    xref_pos = len(saida)
    saida.extend(b"xref\n0 6\n")
    saida.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        saida.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    saida.extend(f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii"))
    return bytes(saida)


def anos_historico_exportacao(lancamentos: pd.DataFrame) -> list[int]:
    """Seleciona anos úteis para o histórico simples exportado no Excel."""
    anos = {date.today().year}
    if lancamentos is None or lancamentos.empty:
        return sorted(anos)
    for coluna in ["Data", "Início", "Fim"]:
        if coluna in lancamentos.columns:
            datas = pd.to_datetime(lancamentos[coluna], errors="coerce").dropna()
            anos.update(int(ano) for ano in datas.dt.year.unique())
    return sorted(anos)


def exportar_excel(lancamentos: pd.DataFrame, dividas: pd.DataFrame, resumo: dict[str, float], resumo_final: dict[str, object], meta: dict[str, object], simulacao: dict[str, object], sugestoes: list[str]) -> bytes:
    """Exporta o resumo geral do app para Excel."""
    arquivo = BytesIO()
    historico = gerar_relatorio_anual(lancamentos, anos_historico_exportacao(lancamentos))
    historico_simples = historico["mensal"].drop(columns=["Mês nº"], errors="ignore")
    with pd.ExcelWriter(arquivo, engine="openpyxl") as writer:
        pd.DataFrame({"Gerado em": [datetime.now().strftime("%d/%m/%Y %H:%M")], "App": [DISPLAY_NAME]}).to_excel(writer, index=False, sheet_name="Inicio")
        lancamentos.to_excel(writer, index=False, sheet_name="Lancamentos")
        dividas.to_excel(writer, index=False, sheet_name="Dividas")
        pd.DataFrame(
            [
                {"Item": "Entrou", "Valor": resumo["total_receitas"]},
                {"Item": "Saiu", "Valor": resumo["total_geral_gastos"]},
                {"Item": "Resultado", "Valor": resumo["saldo_final"]},
                {"Item": "Parcelas", "Valor": resumo["total_dividas"]},
                {"Item": "Categoria principal", "Valor": resumo_final["categoria"]},
                {"Item": "Insight", "Valor": resumo_final["recomendacao"]},
            ]
        ).to_excel(writer, index=False, sheet_name="Resumo")
        pd.DataFrame([meta]).to_excel(writer, index=False, sheet_name="Meta")
        pd.DataFrame([obter_configuracoes_backup()]).to_excel(writer, index=False, sheet_name="Configuracoes")
        historico_simples.to_excel(writer, index=False, sheet_name="Historico")
        pd.DataFrame({"Sugestão": sugestoes}).to_excel(writer, index=False, sheet_name="Sugestoes")
        simulacao["tabela"].to_excel(writer, index=False, sheet_name="Guardando")

        ajustar_largura_colunas_excel(writer)
        aplicar_formato_excel(writer, "Lancamentos", ["Valor"], FORMATO_MOEDA_EXCEL)
        aplicar_formato_excel(writer, "Lancamentos", ["Data"], FORMATO_DATA_EXCEL)
        aplicar_formato_excel(writer, "Dividas", ["Falta pagar", "Parcela do mês"], FORMATO_MOEDA_EXCEL)
        aplicar_formato_excel(writer, "Meta", ["valor_total", "valor_mensal_necessario"], FORMATO_MOEDA_EXCEL)
        aplicar_formato_excel(writer, "Configuracoes", ["meta_valor_total", "sim_valor_inicial", "sim_valor_mensal"], FORMATO_MOEDA_EXCEL)
        aplicar_formato_excel(writer, "Historico", COLUNAS_RESUMO_ANUAL, FORMATO_MOEDA_EXCEL)
        colunas_guardando = [coluna for coluna in simulacao["tabela"].columns if coluna != "Mês"]
        aplicar_formato_excel(writer, "Guardando", colunas_guardando, FORMATO_MOEDA_EXCEL)
    return arquivo.getvalue()


def aba_historico(lancamentos: pd.DataFrame, dividas: pd.DataFrame, resumo: dict[str, float], resumo_final: dict[str, object], meta: dict[str, object], simulacao: dict[str, object], sugestoes: list[str]) -> None:
    """Mostra histórico, tabelas de apoio e botões de exportação."""
    st.subheader("Histórico")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button(
            "Baixar Excel",
            data=exportar_excel(lancamentos, dividas, resumo, resumo_final, meta, simulacao, sugestoes),
            file_name=nome_arquivo_exportacao("xlsx"),
            mime=MIME_EXCEL,
            width="stretch",
            key="historico_exportar_excel",
            on_click=registrar_feedback,
            args=("Planilha Excel pronta para salvar.",),
        )
    with c2:
        st.download_button(
            "Baixar PDF",
            data=exportar_pdf_resumo(resumo, resumo_final, meta, simulacao, sugestoes),
            file_name=nome_arquivo_exportacao("pdf"),
            mime="application/pdf",
            width="stretch",
            key="historico_exportar_pdf",
            on_click=registrar_feedback,
            args=("Resumo PDF pronto para salvar.",),
        )
    with c3:
        st.download_button(
            "💾 Salvar backup JSON",
            data=exportar_json(lancamentos, dividas),
            file_name=nome_arquivo_exportacao("json"),
            mime=MIME_JSON,
            width="stretch",
            type="primary",
            key="historico_backup_json",
            on_click=registrar_feedback,
            args=("Backup JSON pronto para salvar no dispositivo.",),
        )

    with st.expander("Importar arquivo salvo no dispositivo"):
        st.markdown('<p class="note">Use apenas arquivos JSON ou Excel exportados por este app.</p>', unsafe_allow_html=True)
        controle_importacao_local(st, "historico")

    st.markdown("#### Resumo mensal")
    c3, c4 = st.columns(2)
    with c3:
        card("💰 Entrou", formatar_moeda(resumo["total_receitas"]), "Entradas do mês.", "green")
    with c4:
        card("📉 Saiu", formatar_moeda(resumo["total_geral_gastos"]), "Gastos e parcelas.", "red")
    c5, c6 = st.columns(2)
    with c5:
        card("Resultado", formatar_moeda(resumo["saldo_final"]), "Entrou menos saiu.", "blue" if resumo["saldo_final"] >= 0 else "gold")
    with c6:
        card("Categoria principal", str(resumo_final["categoria"]), formatar_moeda(float(resumo_final["valor_categoria"])), "gold")

    with st.expander("Ver lançamentos"):
        if lancamentos.empty:
            empty_state("Sem lançamentos", "Quando você registrar entradas ou gastos, eles aparecerão aqui.")
        else:
            st.dataframe(formatar_tabela_lancamentos(lancamentos, ["Data", "Descrição", "Categoria", "Valor"]), hide_index=True, width="stretch")

    with st.expander("Ver dívidas"):
        if dividas.empty:
            empty_state("Sem dívidas", "Parcelas cadastradas aparecerão neste histórico.")
        else:
            st.dataframe(formatar_tabela_dividas(dividas), hide_index=True, width="stretch")

    st.markdown("#### Evolução anual")
    opcoes_anos = anos_disponiveis(lancamentos)
    padrao = [ano for ano in [date.today().year] if ano in opcoes_anos] or opcoes_anos[:1]
    anos = st.multiselect("Anos", options=opcoes_anos, default=padrao)
    if not anos:
        st.info("Selecione pelo menos um ano.")
        return

    historico_anual = gerar_relatorio_anual(lancamentos, anos)
    totais_ano = historico_anual["totais_ano"]

    c7, c8 = st.columns(2)
    with c7:
        card("📉 Gastos no período", formatar_moeda(float(totais_ano["Total de gastos"].sum())), "Soma dos gastos lançados.", "red")
    with c8:
        card("💰 Saldo no período", formatar_moeda(float(totais_ano["Sobrou/Faltou"].sum())), "Entradas menos gastos.", "green")

    st.download_button(
        "Baixar histórico anual em Excel",
        data=exportar_relatorio_anual_excel(historico_anual),
        file_name=nome_arquivo_exportacao("xlsx", "historico-financeiro", incluir_hora=True),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
        key="historico_anual_excel",
        on_click=registrar_feedback,
        args=("Histórico anual pronto para salvar.",),
    )

    dados_grafico = historico_anual["mensal"].copy()
    dados_grafico["Período"] = dados_grafico["Mês"].astype(str) + "/" + dados_grafico["Ano"].astype(str)
    fig = px.line(dados_grafico, x="Período", y="Sobrou/Faltou", markers=True)
    fig.update_traces(line_color="#2f6f9f")
    limpar_grafico(fig, margem=dict(l=10, r=10, t=20, b=10))
    aplicar_eixo_moeda(fig)
    st.plotly_chart(fig, width="stretch")

    with st.expander("Resumo mês a mês"):
        tabela_mensal = historico_anual["mensal"].drop(columns=["Mês nº"])
        st.dataframe(formatar_tabela_resumo_anual(tabela_mensal), hide_index=True, width="stretch")

    with st.expander("Categorias principais"):
        categorias = historico_anual["categorias"]
        if categorias.empty:
            empty_state("Sem categorias", "Registre gastos para ver quais categorias mais pesaram no período.")
        else:
            st.dataframe(formatar_tabela_categoria_anual(categorias), hide_index=True, width="stretch")
            categorias_grafico = categorias.groupby("Categoria", as_index=False)["Valor"].sum().sort_values("Valor", ascending=False).head(8)
            categorias_grafico["Categoria"] = categorias_grafico["Categoria"].map(lambda item: f"{icone_categoria(item)} {item}")
            categorias_grafico["Texto"] = categorias_grafico["Valor"].map(formatar_moeda)
            fig = grafico_barras_horizontais(categorias_grafico, "Categoria")
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, width="stretch")

    with st.expander("Compras parceladas"):
        parceladas = historico_anual["parceladas"]
        if parceladas.empty:
            st.info("Nenhuma compra parcelada encontrada nos anos selecionados.")
        else:
            tabela_parceladas = parceladas.copy()
            tabela_parceladas["Valor"] = tabela_parceladas["Valor"].map(formatar_moeda)
            st.dataframe(tabela_parceladas, hide_index=True, width="stretch")


def tela_privacidade() -> None:
    """Mostra a política de privacidade e LGPD dentro do app."""
    st.subheader("Política de Privacidade e LGPD")
    st.caption("Organização Financeira na Prática - última atualização: Maio de 2026")

    st.markdown(
        """
### 1. Sobre o aplicativo

O aplicativo **Organização Financeira na Prática** foi desenvolvido como uma ferramenta simples de organização financeira pessoal, permitindo o registro de receitas, despesas, metas e acompanhamento financeiro básico.

O sistema possui caráter educativo e informativo, com foco em auxiliar usuários na organização do orçamento mensal e no desenvolvimento de hábitos financeiros mais saudáveis.

### 2. Coleta de dados

O aplicativo não solicita CPF, RG, senha, dados bancários, cartão de crédito, informações de conta bancária, localização, biometria ou documentos pessoais.

As informações inseridas pelo usuário são preenchidas voluntariamente apenas para uso pessoal dentro da ferramenta.

### 3. Uso no Streamlit Cloud

Na versão publicada no Streamlit Cloud, os dados digitados são processados temporariamente na sessão do aplicativo para que a interface funcione. O projeto não usa banco de dados, login, armazenamento permanente em servidor, publicidade ou ferramentas próprias de rastreamento.

Ao encerrar ou reiniciar a sessão, as informações preenchidas podem ser perdidas. Para guardar os dados, o usuário deve baixar os arquivos Excel ou JSON e salvá-los no próprio dispositivo.

### 4. Armazenamento das informações

O aplicativo não realiza armazenamento permanente de dados financeiros em servidores externos do projeto.

Os dados preenchidos permanecem apenas durante a sessão de uso, não são vendidos, não são utilizados para fins comerciais e não são compartilhados voluntariamente com terceiros pelo responsável do projeto.

### 5. Controle local dos dados

Os arquivos exportados pelo aplicativo são armazenados exclusivamente no computador ou dispositivo pessoal escolhido pelo usuário.

O aplicativo não possui acesso posterior aos arquivos salvos localmente. O usuário pode baixar um backup em JSON ou uma planilha Excel para carregar novamente no próprio app em outro momento.

### 6. Segurança

O aplicativo foi desenvolvido buscando reduzir a coleta de informações pessoais e minimizar riscos relacionados à privacidade dos usuários.

Recomenda-se que o usuário mantenha seus arquivos em local seguro, não compartilhe relatórios financeiros com terceiros e utilize dispositivos pessoais protegidos por senha.

### 7. Base legal (LGPD)

O tratamento das informações inseridas pelo usuário ocorre com base no consentimento do próprio usuário, na utilização voluntária da ferramenta e na finalidade exclusiva de organização financeira pessoal.

O aplicativo busca seguir os princípios da Lei Geral de Proteção de Dados (Lei nº 13.709/2018), especialmente minimização de dados, transparência, finalidade, segurança e necessidade.

### 8. Limitação de responsabilidade

O aplicativo possui finalidade exclusivamente educativa, organizacional e informativa.

O sistema não oferece consultoria financeira, não recomenda investimentos, não realiza aconselhamento financeiro e não substitui orientação profissional especializada.

### 9. Alterações desta política

Esta Política de Privacidade poderá ser atualizada futuramente para melhorias de transparência, segurança e adequação legal.

### 10. Contato

Em caso de dúvidas relacionadas ao funcionamento do aplicativo ou privacidade das informações, o usuário poderá entrar em contato com o responsável pelo projeto.

- **Responsável:** Yohann da Rocha Risso
- **Projeto:** Organização Financeira na Prática
- **Instituição:** PUC Minas - Ciências Econômicas EaD
        """
    )


def barra_lateral(lancamentos: pd.DataFrame, dividas: pd.DataFrame, resumo: dict[str, float], resumo_final: dict[str, object], meta: dict[str, object], simulacao: dict[str, object], sugestoes: list[str]) -> None:
    """Monta os botões fixos da barra lateral."""
    st.sidebar.title("Organização")
    st.sidebar.caption("Controle simples do mês.")
    st.sidebar.divider()
    if st.sidebar.button("Novo lançamento", width="stretch"):
        if "lancamentos_df" not in st.session_state:
            st.session_state["lancamentos_df"] = criar_lancamentos_padrao()
        st.session_state["lancamentos_df"] = pd.concat(
            [st.session_state["lancamentos_df"], pd.DataFrame([criar_lancamento_vazio()])],
            ignore_index=True,
        )
        st.session_state["mensagem_feedback"] = "Linha vazia adicionada."
        rerun_preservando_tela()
    if st.sidebar.button("Carregar exemplo", width="stretch"):
        st.session_state["carregar_exemplo_pendente"] = True
        rerun_preservando_tela()
    if st.sidebar.button("Limpar tudo", width="stretch"):
        tela_atual = st.session_state.get("aba_atual", "Início")
        st.session_state.clear()
        st.session_state["aba_atual"] = tela_atual if tela_atual in ABAS_APP else "Início"
        st.session_state["mensagem_feedback"] = "Dados limpos."
        rerun_preservando_tela()
    if st.sidebar.button("Atualizar referências", width="stretch"):
        st.cache_data.clear()
        st.session_state["mensagem_feedback"] = "Referências atualizadas."
        rerun_preservando_tela()
    st.sidebar.divider()
    st.sidebar.subheader("Salvar dados")
    backup_hint("Salve um backup JSON sempre que terminar uma atualização importante.")
    st.sidebar.download_button(
        "💾 Salvar backup JSON",
        data=exportar_json(lancamentos, dividas),
        file_name=nome_arquivo_exportacao("json"),
        mime=MIME_JSON,
        width="stretch",
        type="primary",
        key="sidebar_backup_json",
        on_click=registrar_feedback,
        args=("Backup JSON pronto para salvar no dispositivo.",),
    )
    st.sidebar.download_button(
        "Exportar Excel",
        data=exportar_excel(lancamentos, dividas, resumo, resumo_final, meta, simulacao, sugestoes),
        file_name=nome_arquivo_exportacao("xlsx"),
        mime=MIME_EXCEL,
        width="stretch",
        key="sidebar_exportar_excel",
        on_click=registrar_feedback,
        args=("Planilha Excel pronta para salvar.",),
    )
    with st.sidebar.expander("Importar arquivo"):
        st.caption("Carregue JSON ou Excel salvo no seu dispositivo.")
        controle_importacao_local(st, "sidebar")
    st.sidebar.caption("Os arquivos exportados ficam armazenados apenas no seu dispositivo.")
    st.sidebar.caption("As comparações possuem caráter informativo.")


def main() -> None:
    """Executa o app e organiza as abas principais."""
    configurar_pagina()
    aplicar_importacao_pendente()
    aplicar_exemplo_pendente()
    mensagem_importacao = st.session_state.pop("mensagem_importacao", None)
    if mensagem_importacao:
        st.success(mensagem_importacao)
    resumo_importacao = st.session_state.pop("resumo_importacao", None)
    if resumo_importacao:
        mostrar_resumo_importacao(resumo_importacao)
    mostrar_feedback_pendente()

    tela = seletor_tela()

    lancamentos = lancamentos_atuais()
    dividas, total_dividas = dividas_atuais()

    if tela == "Início":
        tela_inicio()

    if tela == "Registrar":
        lancamentos = aba_lancamentos()

    if tela == "Dívidas":
        dividas, total_dividas = aba_dividas()

    totais_gastos = calcular_gastos(lancamentos)
    resumo = gerar_resumo(
        total_receitas=calcular_receitas(lancamentos),
        total_fixos=totais_gastos["total_fixos"],
        total_variaveis=totais_gastos["total_variaveis"],
        total_dividas=total_dividas,
    )
    diagnostico = gerar_diagnostico(resumo)
    sugestoes = gerar_sugestoes_rapidas(resumo, lancamentos)
    resumo_final = gerar_resumo_financeiro_mes(resumo, lancamentos)
    meta = meta_atual(resumo["saldo_final"])
    simulacao = simulacao_atual(meta)

    if tela == "Resultado do mês":
        exibir_painel(resumo, lancamentos, diagnostico, sugestoes, resumo_final, dividas)

    if tela == "Metas":
        meta = aba_metas(resumo["saldo_final"])
        simulacao = simulacao_atual(meta)

    if tela == "Guardando dinheiro":
        simulacao = aba_guardando_dinheiro(meta)

    if tela == "Histórico":
        aba_historico(lancamentos, dividas, resumo, resumo_final, meta, simulacao, sugestoes)

    if tela == "Privacidade e LGPD":
        tela_privacidade()

    barra_lateral(lancamentos, dividas, resumo, resumo_final, meta, simulacao, sugestoes)

    st.caption("As comparações possuem caráter informativo.")


if __name__ == "__main__":
    main()
