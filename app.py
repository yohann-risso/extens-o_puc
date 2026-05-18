"""Aplicativo simples de organização financeira feito com Streamlit.

A ideia do projeto é deixar a pessoa registrar entradas, gastos, dívidas,
metas e uma simulação básica de dinheiro guardado. O código fica em um único
arquivo porque o projeto é pequeno, mas as funções foram separadas por assunto
para facilitar manutenção e apresentação.
"""

from datetime import date, datetime, timedelta
from io import BytesIO
import base64
import hashlib
import json
from math import ceil
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components


DISPLAY_NAME = "Organização Financeira na Prática"
PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_ROOT / "assets"
LOGO_PATH = ASSETS_DIR / "logo-organizacao-financeira.svg"
FAVICON_PATH = ASSETS_DIR / "favicon-organizacao-financeira.png"
BRASAO_PUC_PATH = ASSETS_DIR / "brasao-pucminas-footer.png"
BCB_BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs"
CACHE_TAXAS_BCB = "bcb-parser-v3"
FORMATO_MOEDA_EXCEL = '"R$" #,##0.00'
FORMATO_DATA_EXCEL = "DD/MM/YYYY"
PREFIXO_ARQUIVO = "controle-financeiro"
MIME_EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MIME_JSON = "application/json"
LOCAL_STORAGE_KEY = "organizacao-financeira-na-pratica:v1"
LOCAL_STORAGE_SCHEMA = 1
LOCAL_STORAGE_COMPONENT_DIR = PROJECT_ROOT / "components" / "local_storage"
CORES_GRAFICO = {
    "verde": "#0f9f6e",
    "azul": "#2563eb",
    "vermelho": "#e5484d",
    "dourado": "#d97706",
    "ciano": "#0891b2",
    "roxo": "#7c3aed",
    "cinza": "#64748b",
    "linha": "#d9e2ec",
    "fundo": "#f6f8fb",
}
PALETA_GRAFICO = [
    CORES_GRAFICO["verde"],
    CORES_GRAFICO["azul"],
    CORES_GRAFICO["vermelho"],
    CORES_GRAFICO["dourado"],
    CORES_GRAFICO["ciano"],
    CORES_GRAFICO["roxo"],
    "#475569",
]
CONFIG_GRAFICO = {"displayModeBar": False, "responsive": True}

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
COLUNAS_METAS = ["Objetivo", "Valor total", "Já guardado", "Prazo (meses)", "Prioridade"]
PRIORIDADES_META = ["Alta", "Média", "Baixa"]
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

local_storage_bridge = components.declare_component(
    "local_storage_bridge",
    path=str(LOCAL_STORAGE_COMPONENT_DIR),
)


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


def formatar_tabela_metas(tabela: pd.DataFrame) -> pd.DataFrame:
    """Formata metas para leitura no painel."""
    dados = formatar_tabela(
        tabela,
        colunas=[
            "Objetivo",
            "Prioridade",
            "Valor total",
            "Já guardado",
            "Falta",
            "Prazo (meses)",
            "Guardar por mês",
            "Progresso",
            "Situação",
        ],
        colunas_moeda=["Valor total", "Já guardado", "Falta", "Guardar por mês"],
    )
    if "Progresso" in dados.columns:
        dados["Progresso"] = dados["Progresso"].map(lambda valor: f"{formatar_decimal(float(valor))}%")
    return dados


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


def imagem_data_uri(caminho: Path, mime_type: str) -> str:
    """Transforma um asset local em data URI para uso no HTML do Streamlit."""
    try:
        conteudo = caminho.read_bytes()
    except OSError:
        return ""
    return f"data:{mime_type};base64,{base64.b64encode(conteudo).decode('ascii')}"


def favicon_da_pagina() -> bytes | str:
    """Carrega o favicon do projeto, com fallback simples se o arquivo sumir."""
    try:
        return FAVICON_PATH.read_bytes()
    except OSError:
        return "R$"


def logo_html(classe: str) -> str:
    """Monta a tag do logo com fallback textual."""
    logo_uri = imagem_data_uri(LOGO_PATH, "image/svg+xml")
    if not logo_uri:
        return f'<strong class="{classe} logo-text-fallback">{DISPLAY_NAME}</strong>'
    return f'<img class="{classe}" src="{logo_uri}" alt="{DISPLAY_NAME}">'


def configurar_pagina() -> None:
    """Configura a página e o CSS básico do app."""
    st.set_page_config(page_title=DISPLAY_NAME, page_icon=favicon_da_pagina(), layout="wide", initial_sidebar_state="expanded")
    st.markdown(
        """
        <style>
        :root {
            --bg: #f6f8fb;
            --panel: #ffffff;
            --panel-alt: #eef2f7;
            --ink: #111827;
            --muted: #667085;
            --line: #d9e2ec;
            --green: #0f9f6e;
            --green-strong: #087f5b;
            --green-soft: #e8f8f1;
            --blue: #2563eb;
            --blue-soft: #edf4ff;
            --red: #e5484d;
            --red-soft: #fff1f1;
            --gold: #d97706;
            --gold-soft: #fff7e8;
            --shadow: 0 14px 34px rgba(15, 23, 42, .08);
            --shadow-soft: 0 8px 24px rgba(15, 23, 42, .055);
        }
        .stApp {
            background:
                linear-gradient(180deg, rgba(255,255,255,.78), rgba(255,255,255,0) 240px),
                var(--bg);
            color: var(--ink);
        }
        section[data-testid="stSidebar"] {
            background: var(--panel-alt);
            border-right: 1px solid var(--line);
        }
        .main .block-container { max-width: 1120px; padding-top: 1.1rem; padding-bottom: 3rem; }
        h1, h2, h3 { color: var(--ink); letter-spacing: 0; font-weight: 760; }
        .hero {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 8px;
            box-shadow: var(--shadow);
            margin-bottom: 1rem;
            overflow: hidden;
            padding: 1.25rem 1.35rem;
            position: relative;
        }
        .hero::before {
            background: linear-gradient(90deg, var(--green), var(--blue), var(--gold));
            content: "";
            height: 5px;
            inset: 0 0 auto 0;
            position: absolute;
        }
        .brand-logo {
            display: block;
            height: auto;
        }
        .hero-logo {
            margin-bottom: .85rem;
            width: min(100%, 520px);
        }
        .sidebar-logo {
            height: auto;
            margin: .1rem 0 .35rem 0;
            width: min(100%, 242px);
        }
        .logo-text-fallback {
            color: var(--ink);
            display: inline-block;
            font-size: 1.35rem;
            line-height: 1.2;
            margin-bottom: .75rem;
        }
        .visually-hidden {
            border: 0;
            clip: rect(0 0 0 0);
            height: 1px;
            margin: -1px;
            overflow: hidden;
            padding: 0;
            position: absolute;
            width: 1px;
        }
        .hero h1 { font-size: clamp(1.55rem, 3vw, 2.4rem); margin: 0 0 .4rem 0; }
        .hero p { color: var(--muted); margin: .15rem 0; max-width: 900px; }
        .chip-row { display: flex; flex-wrap: wrap; gap: .45rem; margin-top: .75rem; }
        .chip {
            border: 1px solid #ccebdd;
            background: var(--green-soft);
            color: #07543d;
            border-radius: 999px;
            padding: .34rem .62rem;
            font-size: .86rem;
            font-weight: 700;
        }
        .metric-card {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 8px;
            box-shadow: var(--shadow-soft);
            min-height: 148px;
            overflow: hidden;
            padding: 1.15rem;
            position: relative;
            transition: border-color .16s ease, box-shadow .16s ease, transform .16s ease;
        }
        .metric-card:hover {
            border-color: #b8c4d4;
            box-shadow: var(--shadow);
            transform: translateY(-1px);
        }
        .metric-card::before {
            content: "";
            height: 4px;
            inset: 0 0 auto 0;
            position: absolute;
        }
        .metric-card.green::before { background: var(--green); }
        .metric-card.blue::before { background: var(--blue); }
        .metric-card.red::before { background: var(--red); }
        .metric-card.gold::before { background: var(--gold); }
        .metric-label { color: var(--muted); font-size: .92rem; margin-bottom: .5rem; }
        .metric-value { color: var(--ink); font-size: clamp(1.22rem, 2vw, 1.72rem); font-weight: 780; line-height: 1.15; }
        .metric-help { color: var(--muted); font-size: .88rem; margin-top: .55rem; line-height: 1.35; }
        .panel {
            background: var(--panel);
            border: 1px solid var(--line);
            border-left: 4px solid var(--blue);
            border-radius: 8px;
            box-shadow: var(--shadow-soft);
            padding: 1.05rem 1.1rem;
            margin: .65rem 0;
        }
        .total-line {
            background: var(--blue-soft);
            border: 1px solid #c8dcff;
            border-radius: 8px;
            color: #173b8f;
            font-weight: 740;
            margin-top: .65rem;
            padding: .7rem .85rem;
        }
        .empty-state {
            background: var(--panel);
            border: 1px dashed #bdc8d6;
            border-radius: 8px;
            color: var(--muted);
            padding: 1rem 1.05rem;
            margin: .75rem 0;
        }
        .empty-state strong { color: var(--ink); }
        .app-footer {
            align-items: center;
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 8px;
            box-shadow: var(--shadow-soft);
            display: flex;
            gap: 1rem;
            justify-content: space-between;
            margin-top: 2rem;
            padding: .95rem 1rem;
        }
        .footer-copy {
            display: flex;
            flex-direction: column;
            gap: .12rem;
        }
        .footer-copy strong { color: var(--ink); font-size: .98rem; }
        .footer-copy span { color: var(--ink); font-weight: 650; }
        .footer-institution {
            align-items: center;
            color: #07543d;
            display: flex;
            flex-shrink: 0;
            font-weight: 750;
            gap: .65rem;
        }
        .footer-institution img {
            height: 64px;
            object-fit: contain;
            width: auto;
        }
        .stButton > button,
        .stDownloadButton > button {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 8px;
            color: var(--ink);
            font-weight: 650;
            transition: background .16s ease, border-color .16s ease, color .16s ease, transform .16s ease;
        }
        .stButton > button:hover,
        .stDownloadButton > button:hover {
            background: #f8fbff;
            border-color: #aebbd0;
            color: var(--blue);
            transform: translateY(-1px);
        }
        .stButton > button:focus:not(:active),
        .stDownloadButton > button:focus:not(:active) {
            border-color: var(--blue);
            box-shadow: 0 0 0 3px rgba(37, 99, 235, .14);
        }
        .stButton button[kind="primary"],
        .stDownloadButton button[kind="primary"],
        button[kind="primary"] {
            background: var(--green);
            border-color: var(--green);
            color: #ffffff;
        }
        .stButton button[kind="primary"]:hover,
        .stDownloadButton button[kind="primary"]:hover,
        button[kind="primary"]:hover {
            background: var(--green-strong);
            border-color: var(--green-strong);
            color: #ffffff;
        }
        div[data-testid="stAlert"] {
            border: 1px solid rgba(148, 163, 184, .24);
            border-radius: 8px;
            box-shadow: var(--shadow-soft);
        }
        div[data-testid="stDataFrame"],
        div[data-testid="stDataEditor"] {
            border-radius: 8px;
            overflow: hidden;
        }
        div[role="radiogroup"] label {
            border: 1px solid transparent;
            border-radius: 999px;
            padding: .16rem .34rem;
        }
        div[role="radiogroup"] label:hover {
            background: rgba(255, 255, 255, .82);
            border-color: var(--line);
        }
        .stTabs [data-baseweb="tab-list"] { gap: .35rem; flex-wrap: wrap; }
        .stTabs [data-baseweb="tab"] {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 999px;
            padding: .45rem .8rem;
        }
        @media (max-width: 680px) {
            .app-footer {
                align-items: flex-start;
                flex-direction: column;
            }
            .footer-institution img { height: 58px; }
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


def logo_barra_lateral() -> None:
    """Mostra o logo do app no topo da barra lateral."""
    st.sidebar.markdown(logo_html("brand-logo sidebar-logo"), unsafe_allow_html=True)


def rodape_institucional() -> None:
    """Mostra autoria e vínculo institucional no rodapé."""
    brasao_uri = imagem_data_uri(BRASAO_PUC_PATH, "image/png")
    brasao_html = ""
    if brasao_uri:
        brasao_html = f'<img src="{brasao_uri}" alt="Brasão da PUC Minas">'
    st.markdown(
        f"""
        <footer class="app-footer" aria-label="Rodapé">
            <div class="footer-copy">
                <strong>{DISPLAY_NAME}</strong>
                <span>desenvolvido por Yohann da Rocha Risso</span>
            </div>
            <div class="footer-institution">
                {brasao_html}
                <span>PUC Minas</span>
            </div>
        </footer>
        """,
        unsafe_allow_html=True,
    )


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


def limpar_grafico(
    fig,
    margem: dict[str, int] | None = None,
    mostrar_legenda: bool = False,
    altura: int | None = 320,
):
    """Deixa o gráfico com aparência mais limpa para caber no Streamlit."""
    fig.update_layout(
        showlegend=mostrar_legenda,
        xaxis_title="",
        yaxis_title="",
        margin=margem or dict(l=10, r=10, t=18, b=10),
        height=altura,
        font=dict(color="#111827", size=12),
        hoverlabel=dict(bgcolor="#ffffff", bordercolor=CORES_GRAFICO["linha"], font_size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        legend_title_text="",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        bargap=0.28,
    )
    fig.update_xaxes(showline=False, zeroline=False, gridcolor="rgba(100, 116, 139, .14)")
    fig.update_yaxes(showline=False, zeroline=False, gridcolor="rgba(100, 116, 139, .10)")
    return fig


def mostrar_grafico(fig) -> None:
    """Mostra gráficos Plotly sem barra de ferramentas visível."""
    st.plotly_chart(fig, width="stretch", config=CONFIG_GRAFICO)


def grafico_barras_horizontais(
    dados: pd.DataFrame,
    eixo_y: str,
    cores: list[str] | None = None,
):
    """Cria gráfico horizontal para comparações de valores."""
    sequencia_cores = cores if cores is not None else PALETA_GRAFICO
    altura = max(260, min(460, 90 + len(dados) * 42))
    fig = px.bar(
        dados,
        x="Valor",
        y=eixo_y,
        orientation="h",
        color=eixo_y,
        color_discrete_sequence=sequencia_cores,
        custom_data=["Texto"],
    )
    fig.update_traces(
        marker_line_width=0,
        hovertemplate="%{y}<br>%{customdata[0]}<extra></extra>",
    )
    limpar_grafico(fig, altura=altura)
    fig.update_xaxes(showgrid=True, tickprefix="R$ ", separatethousands=True)
    fig.update_yaxes(showgrid=False)
    return fig


def grafico_linha_moeda(dados: pd.DataFrame, eixo_x: str, eixo_y: str, cor: str = "#2563eb"):
    """Cria linha simples para evolução de valores em reais."""
    dados_grafico = dados.copy()
    dados_grafico["Texto"] = dados_grafico[eixo_y].map(formatar_moeda)
    fig = px.line(dados_grafico, x=eixo_x, y=eixo_y, markers=True, custom_data=["Texto"])
    fig.update_traces(
        line=dict(color=cor, width=3),
        marker=dict(size=7),
        hovertemplate="%{x}<br>%{customdata[0]}<extra></extra>",
    )
    limpar_grafico(fig, margem=dict(l=10, r=10, t=20, b=10), altura=340)
    aplicar_eixo_moeda(fig)
    return fig


def grafico_destino_do_mes(resumo: dict[str, float]):
    """Mostra em uma barra única para onde o dinheiro foi."""
    saldo = float(resumo["saldo_final"])
    linhas = [
        ("Fixos", float(resumo["total_fixos"]), CORES_GRAFICO["dourado"]),
        ("Variáveis", float(resumo["total_variaveis"]), CORES_GRAFICO["azul"]),
        ("Parcelas", float(resumo["total_dividas"]), CORES_GRAFICO["vermelho"]),
    ]
    if saldo > 0:
        linhas.append(("Sobra", saldo, CORES_GRAFICO["verde"]))

    dados = pd.DataFrame(linhas, columns=["Grupo", "Valor", "Cor"])
    dados = dados[dados["Valor"] > 0].copy()
    dados["Base"] = "Mês"
    dados["Texto"] = dados["Valor"].map(formatar_moeda)
    mapa_cores = dict(zip(dados["Grupo"], dados["Cor"]))
    fig = px.bar(
        dados,
        x="Valor",
        y="Base",
        color="Grupo",
        orientation="h",
        color_discrete_map=mapa_cores,
        custom_data=["Texto"],
    )
    fig.update_traces(
        marker_line_width=0,
        hovertemplate="%{fullData.name}<br>%{customdata[0]}<extra></extra>",
    )
    limpar_grafico(fig, margem=dict(l=10, r=10, t=25, b=10), mostrar_legenda=True, altura=230)
    fig.update_layout(barmode="stack")
    fig.update_xaxes(tickprefix="R$ ", separatethousands=True, showgrid=True)
    fig.update_yaxes(showticklabels=False, showgrid=False)
    return fig


def grafico_dividas_comparativo(dividas: pd.DataFrame):
    """Compara saldo em aberto e parcela do mês em um só gráfico."""
    dados = dividas[["Dívida", "Falta pagar", "Parcela do mês"]].copy()
    dados["Dívida"] = dados["Dívida"].replace("", "Sem nome")
    dados = dados.sort_values("Falta pagar", ascending=False).head(8)
    grafico = dados.melt(id_vars="Dívida", var_name="Indicador", value_name="Valor")
    grafico = grafico[grafico["Valor"] > 0].copy()
    grafico["Texto"] = grafico["Valor"].map(formatar_moeda)
    altura = max(300, min(520, 120 + dados["Dívida"].nunique() * 48))
    fig = px.bar(
        grafico,
        x="Valor",
        y="Dívida",
        color="Indicador",
        orientation="h",
        barmode="group",
        color_discrete_map={"Falta pagar": CORES_GRAFICO["dourado"], "Parcela do mês": CORES_GRAFICO["vermelho"]},
        custom_data=["Texto"],
    )
    fig.update_traces(
        marker_line_width=0,
        hovertemplate="%{y}<br>%{fullData.name}: %{customdata[0]}<extra></extra>",
    )
    limpar_grafico(fig, mostrar_legenda=True, altura=altura)
    fig.update_xaxes(tickprefix="R$ ", separatethousands=True, showgrid=True)
    fig.update_yaxes(showgrid=False)
    return fig


def grafico_progresso_metas(metas_calculadas: pd.DataFrame):
    """Mostra progresso individual das metas sem depender da tabela."""
    dados = metas_calculadas.copy().head(8)
    dados["Objetivo visual"] = dados["Objetivo"].replace("", "Meta sem nome")
    dados["Progresso"] = dados["Progresso"].clip(lower=0, upper=100)
    dados["Texto"] = dados["Progresso"].map(lambda valor: f"{formatar_decimal(float(valor))}%")
    dados = dados.iloc[::-1].copy()
    cores = dados["Situação"].map(
        {
            "Concluída": CORES_GRAFICO["verde"],
            "Cabe": CORES_GRAFICO["azul"],
            "Ajustar": CORES_GRAFICO["dourado"],
            "Planejar": CORES_GRAFICO["cinza"],
        }
    ).fillna(CORES_GRAFICO["azul"])
    altura = max(280, min(500, 120 + len(dados) * 42))
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=[100] * len(dados),
            y=dados["Objetivo visual"],
            orientation="h",
            marker_color="rgba(100, 116, 139, .16)",
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Bar(
            x=dados["Progresso"],
            y=dados["Objetivo visual"],
            orientation="h",
            text=dados["Texto"],
            textposition="inside",
            marker_color=cores,
            customdata=dados[["Falta", "Guardar por mês", "Situação"]].assign(
                Falta=dados["Falta"].map(formatar_moeda),
                **{"Guardar por mês": dados["Guardar por mês"].map(formatar_moeda)},
            ),
            hovertemplate="%{y}<br>%{x:.1f}% concluído<br>Falta: %{customdata[0]}<br>Por mês: %{customdata[1]}<br>%{customdata[2]}<extra></extra>",
            showlegend=False,
        )
    )
    limpar_grafico(fig, margem=dict(l=10, r=10, t=16, b=10), altura=altura)
    fig.update_layout(barmode="overlay")
    fig.update_xaxes(range=[0, 100], ticksuffix="%", showgrid=True)
    fig.update_yaxes(showgrid=False)
    return fig


def grafico_historico_mensal(dados_grafico: pd.DataFrame):
    """Combina entradas, gastos e saldo em um gráfico anual."""
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Entradas",
            x=dados_grafico["Período"],
            y=dados_grafico["Entradas"],
            marker_color=CORES_GRAFICO["verde"],
            customdata=dados_grafico["Entradas"].map(formatar_moeda),
            hovertemplate="%{x}<br>%{customdata}<extra>Entradas</extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Gastos",
            x=dados_grafico["Período"],
            y=dados_grafico["Total de gastos"],
            marker_color=CORES_GRAFICO["vermelho"],
            customdata=dados_grafico["Total de gastos"].map(formatar_moeda),
            hovertemplate="%{x}<br>%{customdata}<extra>Gastos</extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            name="Saldo",
            x=dados_grafico["Período"],
            y=dados_grafico["Sobrou/Faltou"],
            mode="lines+markers",
            line=dict(color=CORES_GRAFICO["azul"], width=3),
            marker=dict(size=7),
            customdata=dados_grafico["Sobrou/Faltou"].map(formatar_moeda),
            hovertemplate="%{x}<br>%{customdata}<extra>Saldo</extra>",
        )
    )
    limpar_grafico(fig, margem=dict(l=10, r=10, t=22, b=10), mostrar_legenda=True, altura=390)
    fig.update_layout(barmode="group", hovermode="x unified")
    aplicar_eixo_moeda(fig)
    fig.update_xaxes(tickangle=-35)
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


def criar_metas_padrao() -> pd.DataFrame:
    """Cria a tabela vazia para cadastro de metas."""
    return pd.DataFrame(columns=COLUNAS_METAS)


def normalizar_metas(df: object) -> pd.DataFrame:
    """Limpa a tabela de metas e aceita backups antigos com uma meta única."""
    if df is None:
        return criar_metas_padrao()

    dados = pd.DataFrame(df).copy()
    if dados.empty:
        return criar_metas_padrao()

    dados = dados.rename(
        columns={
            "objetivo": "Objetivo",
            "valor_total": "Valor total",
            "valor_guardado": "Já guardado",
            "prazo_meses": "Prazo (meses)",
            "prioridade": "Prioridade",
        }
    )
    for coluna in COLUNAS_METAS:
        if coluna not in dados.columns:
            if coluna == "Prazo (meses)":
                dados[coluna] = 6
            elif coluna == "Prioridade":
                dados[coluna] = "Média"
            elif coluna == "Objetivo":
                dados[coluna] = ""
            else:
                dados[coluna] = 0.0

    dados = dados[COLUNAS_METAS].copy()
    dados["Objetivo"] = dados["Objetivo"].fillna("").astype(str).str.strip()
    dados["Valor total"] = pd.to_numeric(dados["Valor total"], errors="coerce").fillna(0.0).clip(lower=0.0)
    dados["Já guardado"] = pd.to_numeric(dados["Já guardado"], errors="coerce").fillna(0.0).clip(lower=0.0)
    dados["Prazo (meses)"] = (
        pd.to_numeric(dados["Prazo (meses)"], errors="coerce")
        .fillna(6)
        .clip(lower=1, upper=240)
        .round()
        .astype(int)
    )
    dados["Prioridade"] = dados["Prioridade"].fillna("Média").astype(str)
    dados.loc[~dados["Prioridade"].isin(PRIORIDADES_META), "Prioridade"] = "Média"

    tem_conteudo = (
        (dados["Objetivo"] != "")
        | (dados["Valor total"] > 0)
        | (dados["Já guardado"] > 0)
    )
    return dados[tem_conteudo].reset_index(drop=True)


def metas_de_configuracoes(configuracoes: object) -> pd.DataFrame:
    """Converte a meta antiga da configuração para a tabela de metas."""
    dados = configuracoes if hasattr(configuracoes, "get") else {}
    objetivo = texto_configuracao(dados.get("meta_objetivo", ""))
    valor_total = numero_configuracao(dados.get("meta_valor_total", 0.0), 0.0)
    valor_guardado = numero_configuracao(dados.get("meta_valor_guardado", 0.0), 0.0)
    prazo = inteiro_configuracao(dados.get("meta_prazo_meses", 6), 6, 1, 240)
    if not objetivo.strip() and valor_total <= 0 and valor_guardado <= 0:
        return criar_metas_padrao()
    return normalizar_metas(
        [
            {
                "Objetivo": objetivo,
                "Valor total": valor_total,
                "Já guardado": valor_guardado,
                "Prazo (meses)": prazo,
                "Prioridade": "Alta",
            }
        ]
    )


def metas_atuais() -> pd.DataFrame:
    """Lê as metas da sessão e migra a meta única antiga quando necessário."""
    if "metas_df" not in st.session_state:
        st.session_state["metas_df"] = metas_de_configuracoes(st.session_state)
    metas = normalizar_metas(st.session_state.get("metas_df", criar_metas_padrao()))
    st.session_state["metas_df"] = metas
    return metas


def calcular_metas(metas: pd.DataFrame, saldo: float) -> pd.DataFrame:
    """Calcula progresso e esforço mensal para cada meta."""
    dados = normalizar_metas(metas)
    if dados.empty:
        return dados.assign(
            Falta=pd.Series(dtype=float),
            **{
                "Guardar por mês": pd.Series(dtype=float),
                "Progresso": pd.Series(dtype=float),
                "Folga após guardar": pd.Series(dtype=float),
                "Prazo sugerido": pd.Series(dtype=int),
                "Situação": pd.Series(dtype=str),
            },
        )

    dados["Falta"] = (dados["Valor total"] - dados["Já guardado"]).clip(lower=0.0)
    dados["Guardar por mês"] = dados["Falta"] / dados["Prazo (meses)"].clip(lower=1)
    dados["Progresso"] = dados.apply(
        lambda linha: min((linha["Já guardado"] / linha["Valor total"]) * 100, 100) if linha["Valor total"] > 0 else 0.0,
        axis=1,
    )
    dados["Folga após guardar"] = float(saldo) - dados["Guardar por mês"]
    dados["Prazo sugerido"] = dados["Falta"].map(lambda falta: ceil(falta / saldo) if saldo > 0 and falta > 0 else 0)

    def situacao(linha: pd.Series) -> str:
        if linha["Valor total"] <= 0:
            return "Planejar"
        if linha["Falta"] <= 0:
            return "Concluída"
        if saldo >= linha["Guardar por mês"]:
            return "Cabe"
        return "Ajustar"

    dados["Situação"] = dados.apply(situacao, axis=1)
    prioridade_ordem = {"Alta": 0, "Média": 1, "Baixa": 2}
    dados["Ordem prioridade"] = dados["Prioridade"].map(prioridade_ordem).fillna(1).astype(int)
    return dados.sort_values(["Ordem prioridade", "Situação", "Objetivo"]).drop(columns=["Ordem prioridade"]).reset_index(drop=True)


def indice_meta_foco(metas: pd.DataFrame) -> int | None:
    """Escolhe a meta em foco, respeitando a seleção anterior quando existir."""
    if metas.empty:
        return None
    indice = int(st.session_state.get("meta_foco_indice", 0) or 0)
    indice = max(0, min(indice, len(metas) - 1))
    st.session_state["meta_foco_indice"] = indice
    return indice


def meta_dict_de_linha(linha: pd.Series | None) -> dict[str, object]:
    """Converte uma linha calculada de meta para o formato usado pelo restante do app."""
    if linha is None:
        return {
            "objetivo": "",
            "valor_total": 0.0,
            "valor_guardado": 0.0,
            "faltante": 0.0,
            "prazo_meses": 6,
            "valor_mensal_necessario": 0.0,
            "progresso_percentual": 0.0,
            "situacao": "Não",
        }
    return {
        "objetivo": str(linha.get("Objetivo", "")),
        "valor_total": float(linha.get("Valor total", 0.0) or 0.0),
        "valor_guardado": float(linha.get("Já guardado", 0.0) or 0.0),
        "faltante": float(linha.get("Falta", 0.0) or 0.0),
        "prazo_meses": int(linha.get("Prazo (meses)", 6) or 6),
        "valor_mensal_necessario": float(linha.get("Guardar por mês", 0.0) or 0.0),
        "progresso_percentual": float(linha.get("Progresso", 0.0) or 0.0),
        "situacao": str(linha.get("Situação", "Não")),
    }


def sincronizar_meta_legada(metas: pd.DataFrame) -> None:
    """Mantém os campos antigos atualizados para backups e telas existentes."""
    metas_calculadas = calcular_metas(metas, 0.0)
    indice = indice_meta_foco(metas_calculadas)
    meta = meta_dict_de_linha(metas_calculadas.iloc[indice] if indice is not None else None)
    st.session_state["meta_objetivo"] = meta["objetivo"]
    st.session_state["meta_valor_total"] = meta["valor_total"]
    st.session_state["meta_valor_guardado"] = meta["valor_guardado"]
    st.session_state["meta_prazo_meses"] = meta["prazo_meses"]


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
        "meta_valor_guardado": numero_configuracao(dados.get("meta_valor_guardado", 0.0), 0.0),
        "meta_prazo_meses": inteiro_configuracao(dados.get("meta_prazo_meses", 6), 6, 1, 240),
        "sim_valor_inicial": numero_configuracao(dados.get("sim_valor_inicial", 300.0), 300.0),
        "sim_valor_mensal": numero_configuracao(dados.get("sim_valor_mensal", 100.0), 100.0),
        "sim_meses": inteiro_configuracao(dados.get("sim_meses", 12), 12, 1, 360),
    }


def obter_configuracoes_backup() -> dict[str, object]:
    """Reúne as configurações atuais para exportação e restauração local."""
    sincronizar_meta_legada(metas_atuais())
    return normalizar_configuracoes_backup(
        {
            "somar_dividas": st.session_state.get("somar_dividas", True),
            "meta_objetivo": st.session_state.get("meta_objetivo", ""),
            "meta_valor_total": st.session_state.get("meta_valor_total", 0.0),
            "meta_valor_guardado": st.session_state.get("meta_valor_guardado", 0.0),
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
    metas: pd.DataFrame | None = None,
) -> dict[str, object]:
    """Monta os dados visuais mostrados após uma restauração."""
    objetivo_meta = str(configuracoes.get("meta_objetivo", "")).strip()
    valor_meta = float(configuracoes.get("meta_valor_total", 0.0) or 0.0)
    metas_normalizadas = normalizar_metas(metas)
    quantidade_metas = len(metas_normalizadas)
    texto_meta = f"{quantidade_metas} meta(s) encontrada(s)" if quantidade_metas else "Meta ativa encontrada" if objetivo_meta or valor_meta > 0 else "Sem meta ativa"
    return {
        "lancamentos": int(len(lancamentos)),
        "dividas": int(len(dividas)),
        "meta": texto_meta,
        "periodo": periodo_resumo_backup(lancamentos),
    }


def mostrar_resumo_importacao(resumo_importacao: dict[str, object]) -> None:
    """Mostra um resumo amigável do arquivo restaurado."""
    st.markdown("#### Dados carregados")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        card("Lançamentos", str(resumo_importacao.get("lancamentos", 0)), "Registros restaurados.", "green")
    with c2:
        card("Dívidas", str(resumo_importacao.get("dividas", 0)), "Parcelas restauradas.", "gold")
    with c3:
        card("Meta", str(resumo_importacao.get("meta", "Sem meta ativa")), "Meta recuperada.", "blue")
    with c4:
        card("Período", str(resumo_importacao.get("periodo", "Sem período identificado")), "Datas encontradas.", "green")


def agendar_importacao(
    lancamentos: pd.DataFrame,
    dividas: pd.DataFrame,
    configuracoes: dict[str, object],
    mensagem: str,
    metas: pd.DataFrame | None = None,
) -> None:
    """Agenda a restauração para a próxima execução, antes da criação dos widgets."""
    lancamentos_normalizados = normalizar_lancamentos(lancamentos)
    dividas_normalizadas = normalizar_dividas(dividas)
    configuracoes_normalizadas = normalizar_configuracoes_backup(configuracoes)
    metas_normalizadas = normalizar_metas(metas)
    if metas_normalizadas.empty:
        metas_normalizadas = metas_de_configuracoes(configuracoes_normalizadas)
    st.session_state["importacao_pendente"] = {
        "lancamentos_df": lancamentos_normalizados,
        "dividas_df": dividas_normalizadas,
        "metas_df": metas_normalizadas,
        "configuracoes": configuracoes_normalizadas,
        "resumo": resumir_backup_importado(lancamentos_normalizados, dividas_normalizadas, configuracoes_normalizadas, metas_normalizadas),
        "mensagem": mensagem,
    }


def exportar_json(lancamentos: pd.DataFrame, dividas: pd.DataFrame) -> bytes:
    """Gera um backup JSON para o usuário salvar no próprio dispositivo."""
    dados = {
        "app": DISPLAY_NAME,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "observacao": "Cópia dos dados gerada pelo usuário. O app mantém uma cópia neste navegador para facilitar a continuidade do uso.",
        "lancamentos": dataframe_para_registros_json(lancamentos),
        "dividas": dataframe_para_registros_json(dividas),
        "metas": dataframe_para_registros_json(metas_atuais()),
        "configuracoes": {chave: valor_para_json(valor) for chave, valor in obter_configuracoes_backup().items()},
    }
    return json.dumps(dados, ensure_ascii=False, indent=2).encode("utf-8")


def importar_json(conteudo: bytes) -> None:
    """Carrega um backup JSON exportado pelo próprio app."""
    dados = json.loads(conteudo.decode("utf-8"))
    if not isinstance(dados, dict) or ("lancamentos" not in dados and "dividas" not in dados):
        raise ValueError("Não reconheci esse arquivo salvo.")

    agendar_importacao(
        pd.DataFrame(dados.get("lancamentos", [])),
        pd.DataFrame(dados.get("dividas", [])),
        dados.get("configuracoes", {}),
        "Dados salvos carregados. Suas informações foram restauradas.",
        pd.DataFrame(dados.get("metas", [])),
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
    metas_planilha = planilhas.get("Metas", pd.DataFrame())
    if not configuracoes:
        meta = primeira_linha_planilha(planilhas, "Meta")
        configuracoes = {
            "meta_objetivo": meta.get("objetivo", ""),
            "meta_valor_total": meta.get("valor_total", 0.0),
            "meta_valor_guardado": meta.get("valor_guardado", 0.0),
            "meta_prazo_meses": meta.get("prazo_meses", 6),
        }
        if metas_planilha.empty and meta:
            metas_planilha = pd.DataFrame(
                [
                    {
                        "Objetivo": meta.get("objetivo", ""),
                        "Valor total": meta.get("valor_total", 0.0),
                        "Já guardado": meta.get("valor_guardado", 0.0),
                        "Prazo (meses)": meta.get("prazo_meses", 6),
                        "Prioridade": "Alta",
                    }
                ]
            )

    agendar_importacao(
        planilhas.get("Lancamentos", pd.DataFrame()),
        planilhas.get("Dividas", pd.DataFrame()),
        configuracoes,
        "Planilha carregada. Suas informações foram restauradas.",
        metas_planilha,
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
    raise ValueError("Use um arquivo salvo anteriormente por este app.")


def controle_importacao_local(container, prefixo: str) -> None:
    """Mostra o campo de importação reaproveitado na sidebar e no histórico."""
    arquivo = container.file_uploader(
        "Selecionar dados salvos",
        type=["json", "xlsx"],
        key=f"{prefixo}_arquivo_local",
        label_visibility="collapsed",
    )
    if container.button("Carregar dados", width="stretch", key=f"{prefixo}_importar_local"):
        if arquivo is None:
            container.warning("Selecione um arquivo salvo anteriormente pelo app.")
        else:
            try:
                importar_arquivo_local(arquivo.getvalue(), arquivo.name)
                rerun_preservando_tela()
            except ValueError as erro:
                container.error(f"Não foi possível carregar os dados: {erro}")
            except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
                container.error("Não consegui ler esse arquivo. Tente usar um arquivo salvo pelo próprio app.")


def aplicar_importacao_pendente() -> None:
    """Aplica importação antes dos widgets serem criados na execução atual."""
    importacao = st.session_state.pop("importacao_pendente", None)
    if not importacao:
        return

    st.session_state["lancamentos_df"] = importacao["lancamentos_df"]
    st.session_state["dividas_df"] = importacao["dividas_df"]
    st.session_state["metas_df"] = importacao.get("metas_df", criar_metas_padrao())
    for chave, valor in importacao.get("configuracoes", {}).items():
        st.session_state[chave] = valor
    st.session_state["editor_versao"] = int(st.session_state.get("editor_versao", 0)) + 1
    st.session_state["metas_editor_versao"] = int(st.session_state.get("metas_editor_versao", 0)) + 1
    st.session_state["mensagem_importacao"] = importacao.get(
        "mensagem",
        "Dados carregados. Suas informações foram restauradas.",
    )
    st.session_state["resumo_importacao"] = importacao.get("resumo")
    st.session_state["mensagem_feedback"] = "Dados restaurados com segurança."


def acionar_localstorage(acao: str, request_id: str, payload: dict[str, object] | None = None, chave: str | None = None) -> dict[str, object] | None:
    """Aciona a ponte JavaScript que lê e grava no localStorage do navegador."""
    return local_storage_bridge(
        action=acao,
        storageKey=LOCAL_STORAGE_KEY,
        requestId=request_id,
        payload=payload,
        key=chave or f"localstorage_{acao}",
        default=None,
    )


def montar_snapshot_localstorage(lancamentos: pd.DataFrame, dividas: pd.DataFrame) -> dict[str, object]:
    """Monta o estado mínimo do app para sobreviver a F5 e queda de conexão."""
    return {
        "schema": LOCAL_STORAGE_SCHEMA,
        "app": DISPLAY_NAME,
        "lancamentos": dataframe_para_registros_json(normalizar_lancamentos(lancamentos)),
        "dividas": dataframe_para_registros_json(normalizar_dividas(dividas)),
        "metas": dataframe_para_registros_json(metas_atuais()),
        "configuracoes": {chave: valor_para_json(valor) for chave, valor in obter_configuracoes_backup().items()},
    }


def assinatura_snapshot_localstorage(snapshot: dict[str, object]) -> str:
    """Gera uma assinatura estável para evitar reruns infinitos ao salvar."""
    conteudo = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(conteudo.encode("utf-8")).hexdigest()


def restaurar_snapshot_localstorage(raw: object) -> None:
    """Restaura o snapshot salvo no navegador usando a rotina de importação."""
    dados = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(dados, dict):
        raise ValueError("dados locais em formato inválido")
    if not any(chave in dados for chave in ["lancamentos", "dividas", "metas", "configuracoes"]):
        raise ValueError("dados locais não pertencem a este app")
    schema = int(dados.get("schema", 1) or 1)
    if schema > LOCAL_STORAGE_SCHEMA:
        raise ValueError("dados locais foram criados por uma versão mais nova do app")

    agendar_importacao(
        pd.DataFrame(dados.get("lancamentos", [])),
        pd.DataFrame(dados.get("dividas", [])),
        dados.get("configuracoes", {}),
        "Dados recuperados automaticamente deste navegador.",
        pd.DataFrame(dados.get("metas", [])),
    )


def inicializar_armazenamento_local() -> None:
    """Carrega o localStorage antes de criar widgets, quando a sessão é nova."""
    if st.session_state.pop("localstorage_limpar_pendente", False):
        st.session_state["localstorage_pronto"] = True
        st.session_state["localstorage_limpar_agora"] = True
        return

    if st.session_state.get("localstorage_pronto"):
        return

    resposta = acionar_localstorage("load", f"load-{LOCAL_STORAGE_SCHEMA}", chave="localstorage_load")
    if resposta is None:
        st.markdown("Recuperando dados salvos neste navegador...")
        st.stop()

    if not isinstance(resposta, dict):
        st.session_state["localstorage_pronto"] = True
        return

    if resposta.get("status") == "error":
        st.warning("Não foi possível verificar os dados salvos neste navegador.")
        st.session_state["localstorage_pronto"] = True
        return

    raw = resposta.get("raw")
    if raw:
        try:
            restaurar_snapshot_localstorage(raw)
            st.session_state["localstorage_restaurado"] = True
        except (json.JSONDecodeError, TypeError, ValueError):
            st.warning("Não foi possível recuperar os dados salvos neste navegador.")
            st.session_state["localstorage_limpar_agora"] = True

    st.session_state["localstorage_pronto"] = True


def sincronizar_armazenamento_local(lancamentos: pd.DataFrame, dividas: pd.DataFrame) -> None:
    """Salva o estado atual no localStorage depois que a tela é calculada."""
    if not st.session_state.get("localstorage_pronto"):
        return

    if st.session_state.pop("localstorage_limpar_agora", False):
        acionar_localstorage(
            "clear",
            f"clear-{datetime.now().isoformat(timespec='microseconds')}",
            chave="localstorage_clear",
        )

    snapshot = montar_snapshot_localstorage(lancamentos, dividas)
    assinatura = assinatura_snapshot_localstorage(snapshot)
    resposta = acionar_localstorage("save", assinatura, payload=snapshot, chave="localstorage_save")
    if isinstance(resposta, dict) and resposta.get("status") == "error" and resposta.get("requestId") == assinatura:
        if st.session_state.get("localstorage_erro_salvar") != assinatura:
            st.warning(f"Não foi possível salvar os dados neste navegador: {resposta.get('message', 'erro desconhecido')}")
            st.session_state["localstorage_erro_salvar"] = assinatura


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
    st.session_state["metas_df"] = normalizar_metas(
        [
            {"Objetivo": "Reserva de emergência", "Valor total": 3000.0, "Já guardado": 600.0, "Prazo (meses)": 12, "Prioridade": "Alta"},
            {"Objetivo": "Curso de especialização", "Valor total": 900.0, "Já guardado": 150.0, "Prazo (meses)": 5, "Prioridade": "Média"},
            {"Objetivo": "Viagem curta", "Valor total": 1200.0, "Já guardado": 0.0, "Prazo (meses)": 10, "Prioridade": "Baixa"},
        ]
    )
    st.session_state["meta_foco_indice"] = 0
    sincronizar_meta_legada(st.session_state["metas_df"])
    st.session_state["sim_valor_inicial"] = 300.0
    st.session_state["sim_valor_mensal"] = 100.0
    st.session_state["sim_meses"] = 12
    st.session_state["metas_editor_versao"] = int(st.session_state.get("metas_editor_versao", 0)) + 1
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
    """Monta a meta em foco sem precisar renderizar a tela de metas."""
    metas = calcular_metas(metas_atuais(), saldo)
    indice = indice_meta_foco(metas)
    linha = metas.iloc[indice] if indice is not None else None
    return meta_dict_de_linha(linha)


def simulacao_atual(meta: dict[str, object]) -> dict[str, object]:
    """Monta a simulação atual sem precisar renderizar a tela Guardando dinheiro."""
    taxas = obter_taxas_bcb()
    referencia_aa = float(taxas["selic_aa"])
    tr_mensal = float(taxas["tr_mensal"])
    meses_padrao = max(int(meta.get("prazo_meses", 12)), 1)
    return simular_cenarios(
        valor_inicial=float(st.session_state.get("sim_valor_inicial", meta.get("valor_guardado", 300.0)) or 0.0),
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
            <h1 class="visually-hidden">{DISPLAY_NAME}</h1>
            {logo_html("brand-logo hero-logo")}
            <p>Organize entradas, gastos, parcelas e metas em poucos minutos.</p>
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

    st.markdown("#### Gastos por categoria")
    por_categoria = (
        lancamentos.groupby(["Tipo", "Categoria"], as_index=False)["Valor"].sum().sort_values(["Tipo", "Valor"], ascending=[True, False])
    )
    por_categoria["Categoria"] = por_categoria["Categoria"].map(lambda item: f"{icone_categoria(item)} {item}")
    gastos_categoria = por_categoria[por_categoria["Tipo"] == "Gasto"].copy().head(8)
    if not gastos_categoria.empty:
        gastos_categoria["Texto"] = gastos_categoria["Valor"].map(formatar_moeda)
        fig = grafico_barras_horizontais(gastos_categoria, "Categoria")
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        mostrar_grafico(fig)

    with st.expander("Ver resumo por categoria"):
        tabela = por_categoria.copy()
        tabela["Valor"] = tabela["Valor"].map(formatar_moeda)
        st.dataframe(tabela, hide_index=True, width="stretch")
    return lancamentos


def aba_dividas() -> tuple[pd.DataFrame, float]:
    """Cuida das dívidas e parcelas cadastradas separadamente."""
    st.subheader("Dívidas e parcelas")

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

    if not dividas.empty:
        st.markdown("#### Comparativo das dívidas")
        if float(dividas[["Falta pagar", "Parcela do mês"]].sum().sum()) > 0:
            fig = grafico_dividas_comparativo(dividas)
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            mostrar_grafico(fig)
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

    st.markdown("#### Mapa do mês")
    if resumo["total_receitas"] != 0 or resumo["total_geral_gastos"] != 0:
        mostrar_grafico(grafico_destino_do_mes(resumo))

    dividas_backup = dividas if dividas is not None else pd.DataFrame(columns=COLUNAS_DIVIDAS)
    st.download_button(
        "💾 Salvar meus dados",
        data=exportar_json(lancamentos, dividas_backup),
        file_name=nome_arquivo_exportacao("json"),
        mime=MIME_JSON,
        width="stretch",
        type="primary",
        key="resultado_backup_json",
        on_click=registrar_feedback,
        args=("Seus dados estão prontos para salvar.",),
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
                panel_html(item["titulo"], f"{item['texto']} Ação: {item['acao']}")

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
            if not gastos.empty:
                dados = gastos.groupby("Categoria", as_index=False)["Valor"].sum().sort_values("Valor", ascending=False).head(8)
                dados["Categoria"] = dados["Categoria"].map(lambda item: f"{icone_categoria(item)} {item}")
                dados["Texto"] = dados["Valor"].map(formatar_moeda)
                fig = grafico_barras_horizontais(dados, "Categoria")
                fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin=dict(l=10, r=10, t=10, b=10))
                mostrar_grafico(fig)
        with col_sugestoes:
            st.markdown("#### Sugestões rápidas")
            for sugestao in sugestoes[:4]:
                panel_html("Ação rápida", sugestao)

def aba_metas(saldo: float) -> dict[str, object]:
    """Permite acompanhar várias metas de dinheiro guardado."""
    st.subheader("Metas para guardar dinheiro")

    if "metas_editor_versao" not in st.session_state:
        st.session_state["metas_editor_versao"] = 0

    metas_base = metas_atuais()
    st.markdown("#### Cadastro de metas")
    metas_editadas = st.data_editor(
        metas_base,
        hide_index=True,
        num_rows="dynamic",
        width="stretch",
        key=f"metas_editor_{st.session_state['metas_editor_versao']}",
        column_config={
            "Objetivo": st.column_config.TextColumn("Objetivo", width="large"),
            "Valor total": st.column_config.NumberColumn("Valor total", min_value=0.0, step=50.0, format="R$ %.2f"),
            "Já guardado": st.column_config.NumberColumn("Já guardado", min_value=0.0, step=50.0, format="R$ %.2f"),
            "Prazo (meses)": st.column_config.NumberColumn("Prazo", min_value=1, max_value=240, step=1),
            "Prioridade": st.column_config.SelectboxColumn("Prioridade", options=PRIORIDADES_META, required=True),
        },
    )
    metas = normalizar_metas(metas_editadas)
    st.session_state["metas_df"] = metas
    sincronizar_meta_legada(metas)

    metas_calculadas = calcular_metas(metas, saldo)
    if metas_calculadas.empty:
        empty_state("Sem metas", "Adicione uma linha na tabela para acompanhar reserva de emergência, curso, viagem, compra planejada ou outro objetivo.")
        return meta_dict_de_linha(None)

    total_alvo = float(metas_calculadas["Valor total"].sum())
    total_faltante = float(metas_calculadas["Falta"].sum())
    total_guardado = float((metas_calculadas["Valor total"] - metas_calculadas["Falta"]).clip(lower=0.0).sum())
    mensal_total = float(metas_calculadas["Guardar por mês"].sum())
    progresso_total = min((total_guardado / total_alvo) * 100, 100) if total_alvo > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        card("Metas ativas", str(len(metas_calculadas)), "Objetivos cadastrados.", "blue")
    with c2:
        card("Já guardado", formatar_moeda(total_guardado), "Soma do progresso.", "green")
    with c3:
        card("Falta juntar", formatar_moeda(total_faltante), "Valor restante.", "gold" if total_faltante > 0 else "green")
    with c4:
        cor_mensal = "blue" if saldo >= mensal_total and mensal_total > 0 else "gold"
        card("Total por mês", formatar_moeda(mensal_total), "Para cumprir todos os prazos.", cor_mensal)

    st.progress(int(progresso_total), text=f"{formatar_decimal(progresso_total)}% do valor total das metas já foi guardado.")
    if total_faltante <= 0 and total_alvo > 0:
        st.success("Todas as metas cadastradas já foram alcançadas.")
    elif saldo <= 0:
        st.warning("O mês ainda não tem sobra para financiar as metas. Primeiro tente fechar o resultado no positivo.")
    elif mensal_total > saldo:
        st.warning(f"Para cumprir todos os prazos ao mesmo tempo, faltam {formatar_moeda(mensal_total - saldo)} por mês.")
    else:
        st.success("As metas cabem na sobra do mês considerando os prazos informados.")

    st.markdown("#### Progresso das metas")
    mostrar_grafico(grafico_progresso_metas(metas_calculadas))

    st.markdown("#### Meta em foco")
    opcoes = list(metas_calculadas.index)
    indice_atual = indice_meta_foco(metas_calculadas) or 0
    if int(st.session_state.get("meta_foco_select", indice_atual) or 0) not in opcoes:
        st.session_state["meta_foco_select"] = indice_atual
    indice_foco = st.selectbox(
        "Meta em foco",
        options=opcoes,
        index=indice_atual,
        format_func=lambda indice: f"{metas_calculadas.loc[indice, 'Objetivo'] or 'Sem nome'} · {metas_calculadas.loc[indice, 'Prioridade']}",
        label_visibility="collapsed",
        key="meta_foco_select",
    )
    st.session_state["meta_foco_indice"] = int(indice_foco)
    sincronizar_meta_legada(metas)
    linha = metas_calculadas.iloc[int(indice_foco)]
    meta = meta_dict_de_linha(linha)

    foco1, foco2, foco3 = st.columns(3)
    with foco1:
        card("Falta nessa meta", formatar_moeda(float(linha["Falta"])), "Valor restante do objetivo.", "gold" if linha["Falta"] > 0 else "green")
    with foco2:
        card("Guardar por mês", formatar_moeda(float(linha["Guardar por mês"])), "Ritmo para o prazo escolhido.", "blue")
    with foco3:
        card("Situação", str(linha["Situação"]), f"{formatar_decimal(float(linha['Progresso']))}% concluída.", "green" if linha["Situação"] in ["Cabe", "Concluída"] else "gold")

    if linha["Situação"] == "Ajustar" and int(linha["Prazo sugerido"]) > int(linha["Prazo (meses)"]):
        panel_html("Prazo sugerido", f"Com a sobra atual, essa meta fica mais realista em cerca de {int(linha['Prazo sugerido'])} meses.")

    st.markdown("#### Caminho da meta em foco")
    prazo = int(linha["Prazo (meses)"])
    mensal = float(linha["Guardar por mês"])
    valor_total = float(linha["Valor total"])
    valor_guardado = float(linha["Já guardado"])
    dados_evolucao = pd.DataFrame(
        {
            "Mês": list(range(0, prazo + 1)),
            "Dinheiro guardado": [min(valor_guardado + mensal * mes, valor_total) for mes in range(0, prazo + 1)],
        }
    )
    fig = grafico_linha_moeda(dados_evolucao, "Mês", "Dinheiro guardado")
    if valor_total > 0:
        fig.add_hline(y=valor_total, line_dash="dash", line_color=CORES_GRAFICO["dourado"])
    mostrar_grafico(fig)

    with st.expander("Ver todas as metas calculadas"):
        st.dataframe(formatar_tabela_metas(metas_calculadas), hide_index=True, width="stretch")

    return meta


def aba_guardando_dinheiro(meta: dict[str, object]) -> dict[str, object]:
    """Mostra a simulação de dinheiro guardado ao longo do tempo."""
    st.subheader("Guardando dinheiro")

    taxas = obter_taxas_bcb()
    if not taxas["ok"]:
        st.warning("Referências atuais indisponíveis; usando valores padrão.")

    referencia_aa = float(taxas["selic_aa"])
    tr_mensal = float(taxas["tr_mensal"])

    if "sim_valor_inicial" not in st.session_state:
        st.session_state["sim_valor_inicial"] = float(meta.get("valor_guardado", 0.0) or 0.0)
    if "sim_valor_mensal" not in st.session_state:
        st.session_state["sim_valor_mensal"] = float(meta.get("valor_mensal_necessario", 0.0) or 0.0)
    if meta.get("objetivo"):
        panel_html("Meta em foco", f"{meta['objetivo']} · falta {formatar_moeda(float(meta.get('faltante', 0.0)))}")

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

    if not tabela.empty:
        st.markdown("#### Evolução comparada")
        evolucao = tabela.melt(
            id_vars="Mês",
            value_vars=["Dinheiro parado", "Poupança", "Aplicação simples"],
            var_name="Cenário",
            value_name="Valor",
        )
        evolucao["Texto"] = evolucao["Valor"].map(formatar_moeda)
        fig = px.line(
            evolucao,
            x="Mês",
            y="Valor",
            color="Cenário",
            markers=True,
            color_discrete_map={
                "Dinheiro parado": CORES_GRAFICO["verde"],
                "Poupança": CORES_GRAFICO["azul"],
                "Aplicação simples": CORES_GRAFICO["dourado"],
            },
            custom_data=["Texto"],
        )
        fig.update_traces(line=dict(width=3), marker=dict(size=6), hovertemplate="Mês %{x}<br>%{customdata[0]}<extra>%{fullData.name}</extra>")
        limpar_grafico(fig, margem=dict(l=10, r=10, t=22, b=10), mostrar_legenda=True, altura=380)
        fig.update_layout(hovermode="x unified")
        aplicar_eixo_moeda(fig)
        mostrar_grafico(fig)

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
            f"Já guardado: {formatar_moeda(float(meta.get('valor_guardado', 0.0)))}",
            f"Falta juntar: {formatar_moeda(float(meta.get('faltante', 0.0)))}",
            f"Guardar por mês: {formatar_moeda(float(meta['valor_mensal_necessario']))}",
            f"Situação: {meta['situacao']}",
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
    comandos.append(comando_retangulo_pdf(0, 0, 595, 842, (0.96, 0.97, 0.98)))
    comandos.append(comando_retangulo_pdf(36, 730, 523, 74, (1.00, 1.00, 1.00)))
    comandos.append(comando_texto_pdf(DISPLAY_NAME, 50, 780, 17))
    comandos.append(comando_texto_pdf(f"Resumo gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", 50, 758, 10))
    comandos.append(comando_texto_pdf("Dados armazenados no navegador e nos arquivos salvos pelo usuário.", 50, 742, 9))

    valores = [
        ("Entrou", float(resumo["total_receitas"]), (0.06, 0.62, 0.43)),
        ("Saiu", float(resumo["total_geral_gastos"]), (0.90, 0.28, 0.30)),
        ("Resultado", float(resumo["saldo_final"]), (0.15, 0.39, 0.92) if resumo["saldo_final"] >= 0 else (0.85, 0.47, 0.02)),
    ]
    maior = max(max(abs(valor) for _, valor, _ in valores), 1.0)
    y_barra = 690
    comandos.append(comando_texto_pdf("Gráfico simples do mês", 50, y_barra + 28, 13))
    for rotulo, valor, cor in valores:
        largura = int((abs(valor) / maior) * 290)
        comandos.append(comando_texto_pdf(rotulo, 50, y_barra + 3, 10))
        comandos.append(comando_retangulo_pdf(130, y_barra, 300, 14, (0.85, 0.89, 0.93)))
        comandos.append(comando_retangulo_pdf(130, y_barra, max(largura, 4), 14, cor))
        comandos.append(comando_texto_pdf(formatar_moeda(valor), 445, y_barra + 3, 10))
        y_barra -= 32

    linhas = [
        f"Principal gasto: {resumo_final['categoria']} ({formatar_moeda(float(resumo_final['valor_categoria']))})",
        f"Insight: {resumo_final['recomendacao']}",
        "",
        "Meta",
        f"Objetivo: {meta['objetivo'] or 'Não informado'}",
        f"Falta juntar: {formatar_moeda(float(meta.get('faltante', 0.0)))}",
        f"Guardar por mês: {formatar_moeda(float(meta['valor_mensal_necessario']))}",
        f"Situação: {meta['situacao']}",
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
    metas_exportacao = calcular_metas(metas_atuais(), resumo["saldo_final"])
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
        metas_exportacao.to_excel(writer, index=False, sheet_name="Metas")
        pd.DataFrame([obter_configuracoes_backup()]).to_excel(writer, index=False, sheet_name="Configuracoes")
        historico_simples.to_excel(writer, index=False, sheet_name="Historico")
        pd.DataFrame({"Sugestão": sugestoes}).to_excel(writer, index=False, sheet_name="Sugestoes")
        simulacao["tabela"].to_excel(writer, index=False, sheet_name="Guardando")

        ajustar_largura_colunas_excel(writer)
        aplicar_formato_excel(writer, "Lancamentos", ["Valor"], FORMATO_MOEDA_EXCEL)
        aplicar_formato_excel(writer, "Lancamentos", ["Data"], FORMATO_DATA_EXCEL)
        aplicar_formato_excel(writer, "Dividas", ["Falta pagar", "Parcela do mês"], FORMATO_MOEDA_EXCEL)
        aplicar_formato_excel(writer, "Meta", ["valor_total", "valor_guardado", "faltante", "valor_mensal_necessario"], FORMATO_MOEDA_EXCEL)
        aplicar_formato_excel(writer, "Metas", ["Valor total", "Já guardado", "Falta", "Guardar por mês", "Folga após guardar"], FORMATO_MOEDA_EXCEL)
        aplicar_formato_excel(writer, "Configuracoes", ["meta_valor_total", "meta_valor_guardado", "sim_valor_inicial", "sim_valor_mensal"], FORMATO_MOEDA_EXCEL)
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
            "Baixar planilha",
            data=exportar_excel(lancamentos, dividas, resumo, resumo_final, meta, simulacao, sugestoes),
            file_name=nome_arquivo_exportacao("xlsx"),
            mime=MIME_EXCEL,
            width="stretch",
            key="historico_exportar_excel",
            on_click=registrar_feedback,
            args=("Planilha pronta para salvar.",),
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
            "💾 Salvar meus dados",
            data=exportar_json(lancamentos, dividas),
            file_name=nome_arquivo_exportacao("json"),
            mime=MIME_JSON,
            width="stretch",
            type="primary",
            key="historico_backup_json",
            on_click=registrar_feedback,
            args=("Seus dados estão prontos para salvar.",),
        )

    with st.expander("Carregar dados salvos"):
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
        st.warning("Selecione pelo menos um ano.")
        return

    historico_anual = gerar_relatorio_anual(lancamentos, anos)
    totais_ano = historico_anual["totais_ano"]

    c7, c8 = st.columns(2)
    with c7:
        card("📉 Gastos no período", formatar_moeda(float(totais_ano["Total de gastos"].sum())), "Soma dos gastos lançados.", "red")
    with c8:
        card("💰 Saldo no período", formatar_moeda(float(totais_ano["Sobrou/Faltou"].sum())), "Entradas menos gastos.", "green")

    st.download_button(
        "Baixar histórico anual",
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
    st.markdown("#### Evolução do período")
    mostrar_grafico(grafico_historico_mensal(dados_grafico))

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
            mostrar_grafico(fig)

    with st.expander("Compras parceladas"):
        parceladas = historico_anual["parceladas"]
        if parceladas.empty:
            empty_state("Sem compras parceladas", "Nenhuma compra parcelada encontrada nos anos selecionados.")
        else:
            parceladas_grafico = parceladas.copy()
            parceladas_grafico["Item"] = parceladas_grafico["Descrição"].replace("", pd.NA).fillna(parceladas_grafico["Categoria"]).astype(str)
            parceladas_grafico = parceladas_grafico.groupby("Item", as_index=False)["Valor"].sum().sort_values("Valor", ascending=False).head(8)
            parceladas_grafico["Texto"] = parceladas_grafico["Valor"].map(formatar_moeda)
            fig = grafico_barras_horizontais(parceladas_grafico, "Item", [CORES_GRAFICO["dourado"], CORES_GRAFICO["azul"], CORES_GRAFICO["vermelho"], CORES_GRAFICO["verde"]])
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            mostrar_grafico(fig)
            tabela_parceladas = parceladas.copy()
            tabela_parceladas["Valor"] = tabela_parceladas["Valor"].map(formatar_moeda)
            st.dataframe(tabela_parceladas, hide_index=True, width="stretch")


def tela_privacidade() -> None:
    """Mostra a política de privacidade e LGPD dentro do app."""
    st.subheader("Política de Privacidade e LGPD")

    st.markdown(
        """
### 1. Sobre o aplicativo

O aplicativo **Organização Financeira na Prática** foi desenvolvido como uma ferramenta simples de organização financeira pessoal, permitindo o registro de receitas, despesas, metas e acompanhamento financeiro básico.

O sistema possui caráter educativo e informativo, com foco em auxiliar usuários na organização do orçamento mensal e no desenvolvimento de hábitos financeiros mais saudáveis.

### 2. Coleta de dados

O aplicativo não solicita CPF, RG, senha, dados bancários, cartão de crédito, informações de conta bancária, localização, biometria ou documentos pessoais.

As informações inseridas pelo usuário são preenchidas voluntariamente apenas para uso pessoal dentro da ferramenta.

### 3. Uso na versão publicada

Na versão publicada na internet, os dados digitados são usados apenas para mostrar os resultados na tela. Uma cópia automática pode ficar no próprio navegador para ajudar a recuperar o preenchimento após atualizar a página ou perder a conexão.

O aplicativo não exige cadastro, senha, anúncios ou conexão com banco, cartão ou conta financeira. Ao limpar os dados no aplicativo, a cópia do navegador também é removida. Para guardar as informações fora do navegador, o usuário pode baixar uma cópia e salvá-la no próprio dispositivo.

### 4. Armazenamento das informações

O aplicativo não guarda permanentemente os dados financeiros em uma área própria na internet.

As informações preenchidas ficam durante o uso e, quando houver recuperação automática, em uma cópia no próprio navegador. Elas não são vendidas, não são usadas para fins comerciais e não são compartilhadas voluntariamente com terceiros pelo responsável do projeto.

### 5. Controle local dos dados

Os arquivos baixados pelo aplicativo e a cópia automática do navegador ficam no computador, celular, tablet ou navegador escolhido pelo usuário.

O aplicativo não acessa depois os arquivos que o usuário salvou fora do navegador. O usuário pode baixar uma cópia dos dados ou uma planilha para continuar usando o app em outro momento.

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
    logo_barra_lateral()
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
        st.session_state["localstorage_limpar_pendente"] = True
        st.session_state["mensagem_feedback"] = "Dados limpos."
        rerun_preservando_tela()
    if st.sidebar.button("Atualizar taxas", width="stretch"):
        st.cache_data.clear()
        st.session_state["mensagem_feedback"] = "Taxas atualizadas."
        rerun_preservando_tela()
    st.sidebar.divider()
    st.sidebar.subheader("Salvar dados")
    st.sidebar.download_button(
        "💾 Salvar meus dados",
        data=exportar_json(lancamentos, dividas),
        file_name=nome_arquivo_exportacao("json"),
        mime=MIME_JSON,
        width="stretch",
        type="primary",
        key="sidebar_backup_json",
        on_click=registrar_feedback,
        args=("Seus dados estão prontos para salvar.",),
    )
    st.sidebar.download_button(
        "Baixar planilha",
        data=exportar_excel(lancamentos, dividas, resumo, resumo_final, meta, simulacao, sugestoes),
        file_name=nome_arquivo_exportacao("xlsx"),
        mime=MIME_EXCEL,
        width="stretch",
        key="sidebar_exportar_excel",
        on_click=registrar_feedback,
        args=("Planilha pronta para salvar.",),
    )
    with st.sidebar.expander("Carregar dados salvos"):
        controle_importacao_local(st, "sidebar")


def main() -> None:
    """Executa o app e organiza as abas principais."""
    configurar_pagina()
    inicializar_armazenamento_local()
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
    sincronizar_armazenamento_local(lancamentos, dividas)

    rodape_institucional()


if __name__ == "__main__":
    main()
