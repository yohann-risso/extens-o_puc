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
CACHE_TAXAS_BCB = "bcb-parser-v2"
TESOURO_CSV_URL = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
    "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv"
)

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


def formatar_moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_decimal(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",")


def formatar_data(valor: object) -> str:
    data = pd.to_datetime(valor, errors="coerce")
    if pd.isna(data):
        return ""
    return data.strftime("%d/%m/%Y")


def formatar_tabela_lancamentos(lancamentos: pd.DataFrame) -> pd.DataFrame:
    tabela = lancamentos.copy()
    if tabela.empty:
        return tabela
    for coluna_data in ["Data", "Início", "Fim"]:
        if coluna_data in tabela.columns:
            tabela[coluna_data] = tabela[coluna_data].map(formatar_data)
    if "Valor" in tabela.columns:
        tabela["Valor"] = tabela["Valor"].map(formatar_moeda)
    return tabela


def formatar_tabela_dividas(dividas: pd.DataFrame) -> pd.DataFrame:
    tabela = dividas.copy()
    if tabela.empty:
        return tabela
    for coluna in ["Falta pagar", "Parcela do mês"]:
        if coluna in tabela.columns:
            tabela[coluna] = tabela[coluna].map(formatar_moeda)
    return tabela


def formatar_tabela_simulacao(tabela: pd.DataFrame) -> pd.DataFrame:
    tabela_formatada = tabela.copy()
    if tabela_formatada.empty:
        return tabela_formatada
    for coluna in tabela_formatada.columns:
        if coluna != "Mês":
            tabela_formatada[coluna] = tabela_formatada[coluna].map(formatar_moeda)
    return tabela_formatada


def formatar_tabela_resumo_anual(tabela: pd.DataFrame) -> pd.DataFrame:
    tabela_formatada = tabela.copy()
    if tabela_formatada.empty:
        return tabela_formatada
    for coluna in ["Entradas", "Gastos fixos", "Gastos não fixos", "Total de gastos", "Sobrou/Faltou"]:
        if coluna in tabela_formatada.columns:
            tabela_formatada[coluna] = tabela_formatada[coluna].map(formatar_moeda)
    return tabela_formatada


def formatar_tabela_categoria_anual(tabela: pd.DataFrame) -> pd.DataFrame:
    tabela_formatada = tabela.copy()
    if tabela_formatada.empty:
        return tabela_formatada
    if "Valor" in tabela_formatada.columns:
        tabela_formatada["Valor"] = tabela_formatada["Valor"].map(formatar_moeda)
    return tabela_formatada


def aplicar_eixo_moeda(fig) -> None:
    fig.update_yaxes(tickprefix="R$ ", separatethousands=True)


def dinheiro_input(rotulo: str, chave: str, valor: float = 0.0, ajuda: str | None = None) -> float:
    return st.number_input(rotulo, min_value=0.0, value=float(valor), step=50.0, format="%.2f", key=chave, help=ajuda)


def numero_br(valor: object) -> float:
    if pd.isna(valor):
        return 0.0
    texto = str(valor).strip().replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return 0.0


def numero_bcb(valor: object) -> float:
    if pd.isna(valor):
        return 0.0
    return float(str(valor).strip().replace(",", "."))


def normalizar_percentual_atual(valor: float) -> float:
    """Evita exibir valor inflado se algum cache antigo trouxe 14.50 como 1450."""
    return valor / 100 if valor > 100 else valor


def configurar_pagina() -> None:
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
        .main .block-container { max-width: 1220px; padding-top: 1.1rem; padding-bottom: 3rem; }
        h1, h2, h3 { color: var(--ink); letter-spacing: 0; }
        .hero {
            background: var(--panel);
            border: 1px solid var(--line);
            border-left: 7px solid var(--green);
            border-radius: 18px;
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
            border-radius: 14px;
            min-height: 124px;
            padding: .95rem;
            box-shadow: 0 8px 22px rgba(23, 32, 38, .055);
        }
        .metric-card.green { border-top: 5px solid var(--green); }
        .metric-card.blue { border-top: 5px solid var(--blue); }
        .metric-card.red { border-top: 5px solid var(--red); }
        .metric-card.gold { border-top: 5px solid var(--gold); }
        .metric-label { color: var(--muted); font-size: .86rem; margin-bottom: .35rem; }
        .metric-value { color: var(--ink); font-size: clamp(1.15rem, 2vw, 1.58rem); font-weight: 780; line-height: 1.15; }
        .metric-help { color: var(--muted); font-size: .82rem; margin-top: .42rem; }
        .note {
            color: var(--muted);
            font-size: .95rem;
            margin-top: -.25rem;
            margin-bottom: .75rem;
        }
        .panel {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 14px;
            padding: 1rem;
            margin: .55rem 0;
        }
        .total-line {
            background: #f0f6f8;
            border: 1px solid #d8e7ee;
            border-radius: 12px;
            color: #264653;
            font-weight: 740;
            margin-top: .65rem;
            padding: .7rem .85rem;
        }
        div[data-testid="stAlert"] { border-radius: 13px; }
        .stTabs [data-baseweb="tab-list"] { gap: .35rem; flex-wrap: wrap; }
        .stTabs [data-baseweb="tab"] {
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 999px;
            padding: .45rem .8rem;
        }
        @media (max-width: 760px) {
            .main .block-container { padding-left: .85rem; padding-right: .85rem; }
            .hero { padding: 1rem; }
            .metric-card { min-height: auto; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def card(rotulo: str, valor: str, ajuda: str = "", cor: str = "green") -> None:
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
    st.markdown(f'<div class="total-line">{texto}</div>', unsafe_allow_html=True)


def panel_html(titulo: str, texto: str) -> None:
    st.markdown(f'<div class="panel"><strong>{titulo}</strong><br>{texto}</div>', unsafe_allow_html=True)


def buscar_serie_bcb(codigo: int, ultimos: int = 1) -> list[dict[str, object]]:
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


def acumular_percentuais(valores: list[float]) -> float:
    fator = 1.0
    for valor in valores:
        fator *= 1 + valor / 100
    return (fator - 1) * 100


@st.cache_data(ttl=60 * 60)
def obter_taxas_bcb(_cache_version: str = CACHE_TAXAS_BCB) -> dict[str, object]:
    try:
        selic = buscar_serie_bcb(432)[-1]
        tr = buscar_serie_bcb(226)[-1]
        ipca_serie = buscar_serie_bcb(433, 12)
        selic_aa = normalizar_percentual_atual(float(selic["valor"]))
        tr_mensal = normalizar_percentual_atual(float(tr["valor"]))
        ipca_12m = normalizar_percentual_atual(acumular_percentuais([float(item["valor"]) for item in ipca_serie]))
        return {
            "ok": True,
            "selic_aa": selic_aa,
            "selic_data": selic["data"],
            "tr_mensal": tr_mensal,
            "tr_data": tr["data"],
            "ipca_12m": ipca_12m,
            "ipca_data": ipca_serie[-1]["data"],
        }
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as erro:
        return {
            "ok": False,
            "erro": str(erro),
            "selic_aa": 10.0,
            "selic_data": "manual",
            "tr_mensal": 0.0,
            "tr_data": "manual",
            "ipca_12m": 4.0,
            "ipca_data": "manual",
        }


@st.cache_data(ttl=60 * 60 * 6)
def obter_titulos_tesouro() -> dict[str, object]:
    try:
        df = pd.read_csv(TESOURO_CSV_URL, sep=";", encoding="latin1")
        df["Data Base Dt"] = pd.to_datetime(df["Data Base"], dayfirst=True, errors="coerce")
        df["Data Vencimento Dt"] = pd.to_datetime(df["Data Vencimento"], dayfirst=True, errors="coerce")
        data_base = df["Data Base Dt"].max()
        df = df[df["Data Base Dt"] == data_base].copy()
        df = df[df["Tipo Titulo"].isin(["Tesouro Selic", "Tesouro Prefixado", "Tesouro IPCA+"])]
        for coluna in ["Taxa Compra Manha", "Taxa Venda Manha", "PU Compra Manha", "PU Venda Manha"]:
            df[coluna] = df[coluna].map(numero_br)
        df = df.sort_values(["Tipo Titulo", "Data Vencimento Dt"])

        titulos = []
        for _, linha in df.iterrows():
            ano = int(linha["Data Vencimento Dt"].year) if pd.notna(linha["Data Vencimento Dt"]) else ""
            titulos.append(
                {
                    "tipo": linha["Tipo Titulo"],
                    "nome": f"{linha['Tipo Titulo']} {ano}",
                    "vencimento": linha["Data Vencimento"],
                    "taxa": float(linha["Taxa Compra Manha"]),
                    "preco": float(linha["PU Compra Manha"]),
                }
            )
        return {
            "ok": True,
            "data_base": data_base.strftime("%d/%m/%Y") if pd.notna(data_base) else "",
            "titulos": titulos,
            "url": TESOURO_CSV_URL,
        }
    except Exception as erro:
        return {"ok": False, "erro": str(erro), "data_base": "manual", "titulos": [], "url": TESOURO_CSV_URL}


def criar_lancamentos_padrao() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Data": date.today(),
                "Tipo": "Entrada",
                "Descrição": "Salário",
                "Categoria": "Salário",
                "Valor": 0.0,
                "Fixo": True,
                "Início": date(date.today().year, 1, 1),
                "Fim": None,
                "Parcelado": False,
                "Nº de parcelas": 1,
                "Parcelas pagas": 0,
                "Observação": "",
            },
            {
                "Data": date.today(),
                "Tipo": "Gasto",
                "Descrição": "Mercado",
                "Categoria": "Mercado e alimentação",
                "Valor": 0.0,
                "Fixo": False,
                "Início": None,
                "Fim": None,
                "Parcelado": False,
                "Nº de parcelas": 1,
                "Parcelas pagas": 0,
                "Observação": "",
            },
            {
                "Data": date.today(),
                "Tipo": "Gasto",
                "Descrição": "Conta de luz",
                "Categoria": "Água, luz e internet",
                "Valor": 0.0,
                "Fixo": True,
                "Início": date(date.today().year, 1, 1),
                "Fim": None,
                "Parcelado": False,
                "Nº de parcelas": 1,
                "Parcelas pagas": 0,
                "Observação": "",
            },
        ]
    )


def normalizar_lancamentos(df: pd.DataFrame) -> pd.DataFrame:
    colunas = [
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
    data_dt = pd.to_datetime(dados["Data"], errors="coerce")
    inicio_dt = pd.to_datetime(dados["Início"], errors="coerce").fillna(data_dt)
    fim_dt = pd.to_datetime(dados["Fim"], errors="coerce")
    dados["Início"] = inicio_dt.dt.date
    dados["Fim"] = fim_dt.dt.date
    dados.loc[fim_dt.isna(), "Fim"] = None
    dados.loc[~dados["Fixo"], "Início"] = None
    dados.loc[~dados["Fixo"], "Fim"] = None
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
    if lancamentos.empty:
        return 0.0
    return float(lancamentos.loc[lancamentos["Tipo"] == "Entrada", "Valor"].sum())


def calcular_gastos(lancamentos: pd.DataFrame) -> dict[str, float]:
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
    return pd.DataFrame(
        [{"Dívida": "", "Falta pagar": 0.0, "Parcela do mês": 0.0, "Parcelas restantes": 0, "Observação": ""}]
    )


def normalizar_dividas(df: pd.DataFrame) -> pd.DataFrame:
    colunas = ["Dívida", "Falta pagar", "Parcela do mês", "Parcelas restantes", "Observação"]
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


def calcular_dividas(dividas: pd.DataFrame) -> float:
    if dividas.empty:
        return 0.0
    return float(dividas["Parcela do mês"].sum())


def gerar_resumo(total_receitas: float, total_fixos: float, total_variaveis: float, total_dividas: float) -> dict[str, float]:
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
        "valor_usado_a_cada_100": min(usado, 999.0),
    }


def gerar_diagnostico(resumo: dict[str, float]) -> list[dict[str, str]]:
    total_receitas = resumo["total_receitas"]
    total_gastos = resumo["total_geral_gastos"]
    total_dividas = resumo["total_dividas"]
    saldo = resumo["saldo_final"]
    parte_dividas = total_dividas / total_receitas * 100 if total_receitas > 0 else 0.0

    if total_receitas == 0 and total_gastos == 0:
        return [{"tipo": "info", "titulo": "Comece pelos lançamentos", "texto": "Registre pelo menos uma entrada e um gasto.", "acao": "Use valores aproximados para começar."}]

    mensagens = []
    if saldo < 0:
        mensagens.append({"tipo": "erro", "titulo": "Saiu mais do que entrou", "texto": "O mês fechou no aperto.", "acao": "Escolha um gasto para reduzir antes do próximo pagamento."})
    elif saldo == 0:
        mensagens.append({"tipo": "aviso", "titulo": "O mês ficou no limite", "texto": "Tudo que entrou já tem destino.", "acao": "Tente criar uma folga pequena."})
    else:
        mensagens.append({"tipo": "sucesso", "titulo": "Terminou com dinheiro sobrando", "texto": "Sobrou dinheiro depois dos gastos.", "acao": "Separe uma parte antes de gastar sem perceber."})

    if parte_dividas >= 30:
        mensagens.append({"tipo": "aviso", "titulo": "Parcelas pesadas", "texto": "As dívidas estão levando uma parte importante do mês.", "acao": "Evite nova parcela antes de entender se cabe."})

    if saldo <= 0:
        mensagens.append({"tipo": "info", "titulo": "Primeiro organizar", "texto": "Antes de pensar em investir, o ideal é organizar o dinheiro do mês.", "acao": "O primeiro objetivo é parar de fechar no aperto."})
    else:
        mensagens.append({"tipo": "info", "titulo": "Próximo passo", "texto": "Você pode criar ou reforçar um dinheiro guardado para emergência.", "acao": "Comece com um valor pequeno e constante."})
    return mensagens


def gerar_plano_acao(resumo: dict[str, float], lancamentos: pd.DataFrame) -> list[str]:
    if resumo["total_receitas"] == 0:
        return ["Registrar o dinheiro que entra no mês.", "Registrar os gastos conforme eles acontecem.", "Voltar ao painel depois de preencher alguns lançamentos."]

    plano = []
    if resumo["saldo_final"] < 0:
        plano.extend(["Revisar os gastos não fixos primeiro.", "Evitar nova parcela até o mês fechar sem faltar dinheiro.", "Anotar gastos pequenos por 7 dias."])
    elif resumo["saldo_final"] == 0:
        plano.extend(["Tentar abrir uma pequena folga no mês.", "Rever assinaturas, delivery e compras não planejadas.", "Separar o dinheiro das contas fixas assim que receber."])
    else:
        plano.extend(["Separar uma parte do que sobrou.", "Guardar um valor para emergência.", "Acompanhar por 3 meses para perceber o padrão."])

    gastos = lancamentos[lancamentos["Tipo"] == "Gasto"] if not lancamentos.empty else pd.DataFrame()
    if not gastos.empty:
        maior = gastos.groupby("Categoria")["Valor"].sum().sort_values(ascending=False)
        if not maior.empty:
            plano.append(f"Olhar com carinho para a categoria que mais pesou: {maior.index[0]}.")
    return plano


def preparar_lancamentos_ano(lancamentos: pd.DataFrame) -> pd.DataFrame:
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
    data = pd.to_datetime(valor, errors="coerce")
    if pd.isna(data):
        return None
    return pd.Timestamp(year=int(data.year), month=int(data.month), day=1)


def data_repetida_no_mes(mes: pd.Timestamp, dia_preferido: int) -> date:
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


def exportar_relatorio_anual_excel(relatorio: dict[str, pd.DataFrame]) -> bytes:
    arquivo = BytesIO()
    with pd.ExcelWriter(arquivo, engine="openpyxl") as writer:
        relatorio["mensal"].to_excel(writer, index=False, sheet_name="Mes a mes")
        relatorio["totais_ano"].to_excel(writer, index=False, sheet_name="Totais por ano")
        relatorio["categorias"].to_excel(writer, index=False, sheet_name="Categorias")
        relatorio["parceladas"].to_excel(writer, index=False, sheet_name="Parceladas")
        relatorio["considerados"].to_excel(writer, index=False, sheet_name="Lancamentos usados")

        for planilha in writer.sheets.values():
            for coluna in planilha.columns:
                maior = max(len(str(celula.value)) if celula.value is not None else 0 for celula in coluna)
                planilha.column_dimensions[coluna[0].column_letter].width = min(maior + 3, 52)

        for nome_planilha in ["Mes a mes", "Totais por ano", "Categorias", "Parceladas", "Lancamentos usados"]:
            planilha = writer.sheets[nome_planilha]
            cabecalhos = {celula.value: celula.column_letter for celula in planilha[1]}
            for nome_coluna in ["Entradas", "Gastos fixos", "Gastos não fixos", "Total de gastos", "Sobrou/Faltou", "Valor"]:
                if nome_coluna in cabecalhos:
                    for celula in planilha[cabecalhos[nome_coluna]][1:]:
                        celula.number_format = '"R$" #,##0.00'
            for nome_coluna in ["Data", "Início", "Fim"]:
                if nome_coluna in cabecalhos:
                    for celula in planilha[cabecalhos[nome_coluna]][1:]:
                        celula.number_format = "DD/MM/YYYY"
    return arquivo.getvalue()


def aliquota_irrf(meses: int) -> float:
    dias = meses * 30
    if dias <= 180:
        return 0.225
    if dias <= 360:
        return 0.20
    if dias <= 720:
        return 0.175
    return 0.15


def texto_irrf(meses: int) -> str:
    dias = meses * 30
    aliquota = aliquota_irrf(meses)
    if dias <= 180:
        faixa = "até 180 dias"
    elif dias <= 360:
        faixa = "de 181 a 360 dias"
    elif dias <= 720:
        faixa = "de 361 a 720 dias"
    else:
        faixa = "acima de 720 dias"
    return f"{formatar_decimal(aliquota * 100)}% ({faixa})"


def taxa_mensal_anual(taxa_aa: float) -> float:
    return (1 + taxa_aa / 100) ** (1 / 12) - 1


def taxa_poupanca_mensal(selic_aa: float, tr_mensal: float) -> tuple[float, str]:
    if selic_aa <= 8.5:
        base = taxa_mensal_anual(selic_aa * 0.70)
        regra = "70% da Selic ao ano, em valor mensal, mais TR"
    else:
        base = 0.005
        regra = "0,5% ao mês mais TR"
    return base + tr_mensal / 100, regra


def aplicar_irrf(saldo: float, total_colocado: float, meses: int) -> tuple[float, float]:
    ganho = max(saldo - total_colocado, 0.0)
    desconto = ganho * aliquota_irrf(meses)
    return saldo - desconto, desconto


def simular_cenarios(
    valor_inicial: float,
    valor_mensal: float,
    meses: int,
    selic_aa: float,
    tr_mensal: float,
    ipca_12m: float,
    percentual_cdi: float,
    taxa_selic_tesouro: float,
    taxa_pre: float,
    taxa_ipca: float,
    taxa_extra_aa: float,
) -> dict[str, object]:
    taxa_cdi = taxa_mensal_anual(selic_aa * percentual_cdi / 100)
    taxa_poupanca, regra_poupanca = taxa_poupanca_mensal(selic_aa, tr_mensal)
    taxa_tesouro_selic = taxa_mensal_anual(max(selic_aa + taxa_selic_tesouro - taxa_extra_aa, 0))
    taxa_tesouro_pre = taxa_mensal_anual(max(taxa_pre - taxa_extra_aa, 0))
    taxa_ipca_total = ((1 + ipca_12m / 100) * (1 + taxa_ipca / 100) - 1) * 100
    taxa_tesouro_ipca = taxa_mensal_anual(max(taxa_ipca_total - taxa_extra_aa, 0))

    saldos = {
        "CDI depois do desconto": valor_inicial,
        "Poupança": valor_inicial,
        "Tesouro Selic depois do desconto": valor_inicial,
        "Tesouro Prefixado depois do desconto": valor_inicial,
        "Tesouro IPCA+ depois do desconto": valor_inicial,
    }
    taxas = {
        "CDI depois do desconto": taxa_cdi,
        "Poupança": taxa_poupanca,
        "Tesouro Selic depois do desconto": taxa_tesouro_selic,
        "Tesouro Prefixado depois do desconto": taxa_tesouro_pre,
        "Tesouro IPCA+ depois do desconto": taxa_tesouro_ipca,
    }

    total_colocado = valor_inicial
    linhas = []
    descontos_finais = {}
    for mes in range(1, meses + 1):
        total_colocado += valor_mensal
        linha = {
            "Mês": mes,
            "Total colocado": total_colocado,
            "Conta corrente sem rendimento": total_colocado,
        }
        for nome, taxa in taxas.items():
            saldos[nome] = (saldos[nome] + valor_mensal) * (1 + taxa)
            if nome == "Poupança":
                linha[nome] = saldos[nome]
                descontos_finais[nome] = 0.0
            else:
                liquido, desconto = aplicar_irrf(saldos[nome], total_colocado, mes)
                linha[nome] = liquido
                descontos_finais[nome] = desconto
        linhas.append(linha)

    tabela = pd.DataFrame(linhas)
    final = tabela.iloc[-1].to_dict() if not tabela.empty else {"Total colocado": valor_inicial}
    return {
        "tabela": tabela,
        "final": final,
        "descontos": descontos_finais,
        "valor_inicial": valor_inicial,
        "valor_mensal": valor_mensal,
        "meses": meses,
        "selic_aa": selic_aa,
        "tr_mensal": tr_mensal,
        "ipca_12m": ipca_12m,
        "percentual_cdi": percentual_cdi,
        "taxa_selic_tesouro": taxa_selic_tesouro,
        "taxa_pre": taxa_pre,
        "taxa_ipca": taxa_ipca,
        "taxa_extra_aa": taxa_extra_aa,
        "faixa_irrf": texto_irrf(meses),
        "regra_poupanca": regra_poupanca,
    }


def carregar_exemplo() -> None:
    st.session_state["lancamentos_df"] = pd.DataFrame(
        [
            {"Data": date.today(), "Tipo": "Entrada", "Descrição": "Salário", "Categoria": "Salário", "Valor": 2400.0, "Fixo": True, "Parcelado": False, "Nº de parcelas": 1, "Parcelas pagas": 0, "Observação": ""},
            {"Data": date.today(), "Tipo": "Entrada", "Descrição": "Horas extras", "Categoria": "Horas extras", "Valor": 250.0, "Fixo": False, "Parcelado": False, "Nº de parcelas": 1, "Parcelas pagas": 0, "Observação": ""},
            {"Data": date.today(), "Tipo": "Gasto", "Descrição": "Aluguel", "Categoria": "Moradia", "Valor": 750.0, "Fixo": True, "Parcelado": False, "Nº de parcelas": 1, "Parcelas pagas": 0, "Observação": ""},
            {"Data": date.today(), "Tipo": "Gasto", "Descrição": "Mercado", "Categoria": "Mercado e alimentação", "Valor": 620.0, "Fixo": True, "Parcelado": False, "Nº de parcelas": 1, "Parcelas pagas": 0, "Observação": ""},
            {"Data": date.today(), "Tipo": "Gasto", "Descrição": "Delivery", "Categoria": "Delivery ou lanche fora", "Valor": 160.0, "Fixo": False, "Parcelado": False, "Nº de parcelas": 1, "Parcelas pagas": 0, "Observação": ""},
            {"Data": date.today(), "Tipo": "Gasto", "Descrição": "Assinaturas", "Categoria": "Assinaturas", "Valor": 55.0, "Fixo": True, "Parcelado": False, "Nº de parcelas": 1, "Parcelas pagas": 0, "Observação": ""},
            {"Data": date.today(), "Tipo": "Gasto", "Descrição": "Tênis parcelado", "Categoria": "Compras", "Valor": 90.0, "Fixo": False, "Parcelado": True, "Nº de parcelas": 5, "Parcelas pagas": 2, "Observação": "Parcela atual"},
        ]
    )
    fixos = st.session_state["lancamentos_df"]["Fixo"] == True
    st.session_state["lancamentos_df"]["Início"] = None
    st.session_state["lancamentos_df"]["Fim"] = None
    st.session_state["lancamentos_df"].loc[fixos, "Início"] = date(2026, 1, 1)
    st.session_state["dividas_df"] = pd.DataFrame(
        [{"Dívida": "Cartão", "Falta pagar": 1200.0, "Parcela do mês": 300.0, "Parcelas restantes": 4, "Observação": "Vence dia 10"}]
    )
    st.session_state["somar_dividas"] = True
    st.session_state["meta_valor_total"] = 1000.0
    st.session_state["meta_objetivo"] = "Dinheiro guardado para emergência"
    st.session_state["meta_prazo_meses"] = 8
    st.session_state["sim_valor_inicial"] = 300.0
    st.session_state["sim_valor_mensal"] = 100.0
    st.session_state["sim_meses"] = 12


def tela_inicio() -> None:
    st.markdown(
        f"""
        <div class="hero">
            <h1>{DISPLAY_NAME}</h1>
            <p>Um app simples para registrar entradas e gastos, acompanhar o mês, planejar metas e comparar simulações educativas.</p>
            <p>Não pede dados sensíveis e não recomenda investimentos, bancos, corretoras ou produtos financeiros.</p>
            <div class="chip-row">
                <span class="chip">Lançamentos</span>
                <span class="chip">Painel do mês</span>
                <span class="chip">Dívidas</span>
                <span class="chip">Metas</span>
                <span class="chip">Simulações educativas</span>
                <span class="chip">Relatórios</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        card("Uso diário", "Gasto a gasto", "Registre cada entrada e saída quando acontecer.", "green")
    with c2:
        card("Leitura fácil", "Entrou x saiu", "Veja rapidamente se sobrou ou faltou dinheiro.", "blue")
    with c3:
        card("Educação", "Sem indicação", "Simulações servem para aprender, não para escolher produto.", "gold")
    st.info("Comece pela aba Lançamentos. Se quiser demonstrar em sala, use o botão Carregar exemplo na lateral.")


def aba_lancamentos() -> pd.DataFrame:
    st.subheader("Lançamentos")
    st.markdown(
        '<p class="note">Registre entradas e gastos na mesma tabela. Se algo se repete todo mês, marque Fixo e informe Início e Fim. Se não tiver fim, deixe o campo Fim em branco.</p>',
        unsafe_allow_html=True,
    )

    if "lancamentos_df" not in st.session_state:
        st.session_state["lancamentos_df"] = criar_lancamentos_padrao()

    if st.button("Adicionar linhas vazias", use_container_width=False):
        extra = pd.DataFrame(
            [
                {
                    "Data": date.today(),
                    "Tipo": "Gasto",
                    "Descrição": "",
                    "Categoria": "Outros gastos",
                    "Valor": 0.0,
                    "Fixo": False,
                    "Parcelado": False,
                    "Nº de parcelas": 1,
                    "Parcelas pagas": 0,
                    "Observação": "",
                }
                for _ in range(5)
            ]
        )
        st.session_state["lancamentos_df"] = pd.concat([st.session_state["lancamentos_df"], extra], ignore_index=True)
        st.rerun()

    editado = st.data_editor(
        st.session_state["lancamentos_df"],
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "Tipo": st.column_config.SelectboxColumn("Tipo", options=TIPOS_LANCAMENTO, required=True),
            "Descrição": st.column_config.TextColumn("Descrição", help="Exemplo: salário, mercado, ônibus"),
            "Categoria": st.column_config.SelectboxColumn("Categoria", options=CATEGORIAS_LANCAMENTO),
            "Valor": st.column_config.NumberColumn("Valor (R$)", min_value=0.0, step=1.0, format="%.2f"),
            "Fixo": st.column_config.CheckboxColumn("Fixo"),
            "Início": st.column_config.DateColumn("Início", format="DD/MM/YYYY", help="Use para entradas ou gastos fixos que se repetem todo mês."),
            "Fim": st.column_config.DateColumn("Fim", format="DD/MM/YYYY", help="Opcional. Se ficar vazio, repete até o fim do relatório."),
            "Parcelado": st.column_config.CheckboxColumn("Parcelado"),
            "Nº de parcelas": st.column_config.NumberColumn("Nº de parcelas", min_value=1, step=1),
            "Parcelas pagas": st.column_config.NumberColumn("Parcelas pagas", min_value=0, step=1),
            "Observação": st.column_config.TextColumn("Observação"),
        },
        key="editor_lancamentos",
    )
    st.session_state["lancamentos_df"] = editado

    lancamentos = normalizar_lancamentos(editado)
    entradas = calcular_receitas(lancamentos)
    gastos = calcular_gastos(lancamentos)
    total_gastos = gastos["total_fixos"] + gastos["total_variaveis"]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        card("Entradas registradas", formatar_moeda(entradas), "Dinheiro que entrou", "green")
    with c2:
        card("Gastos registrados", formatar_moeda(total_gastos), "Tudo que saiu nos lançamentos", "red")
    with c3:
        card("Gastos fixos", formatar_moeda(gastos["total_fixos"]), "Marcados como fixos", "gold")
    with c4:
        card("Gastos não fixos", formatar_moeda(gastos["total_variaveis"]), "Compras e gastos que variam", "blue")

    if not lancamentos.empty:
        st.markdown("#### Resumo por categoria")
        por_categoria = (
            lancamentos.groupby(["Tipo", "Categoria"], as_index=False)["Valor"].sum().sort_values(["Tipo", "Valor"], ascending=[True, False])
        )
        tabela = por_categoria.copy()
        tabela["Valor"] = tabela["Valor"].map(formatar_moeda)
        st.dataframe(tabela, hide_index=True, use_container_width=True)
    return lancamentos


def aba_dividas() -> tuple[pd.DataFrame, float]:
    st.subheader("Dívidas e parcelas")
    st.markdown('<p class="note">Use esta aba para acompanhar parcelas. Não informe contrato, CPF, banco ou dados pessoais.</p>', unsafe_allow_html=True)

    if "dividas_df" not in st.session_state:
        st.session_state["dividas_df"] = criar_dividas_padrao()

    somar = st.checkbox(
        "Somar parcelas cadastradas no resultado do mês",
        value=bool(st.session_state.get("somar_dividas", True)),
        key="somar_dividas",
        help="Se a mesma parcela já foi lançada na aba Lançamentos, deixe desmarcado para não contar duas vezes.",
    )
    editado = st.data_editor(
        st.session_state["dividas_df"],
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "Dívida": st.column_config.TextColumn("Dívida", help="Exemplo: cartão, loja, empréstimo"),
            "Falta pagar": st.column_config.NumberColumn("Falta pagar (R$)", min_value=0.0, step=50.0, format="%.2f"),
            "Parcela do mês": st.column_config.NumberColumn("Parcela do mês (R$)", min_value=0.0, step=10.0, format="%.2f"),
            "Parcelas restantes": st.column_config.NumberColumn("Parcelas restantes", min_value=0, step=1),
            "Observação": st.column_config.TextColumn("Observação"),
        },
        key="editor_dividas",
    )
    st.session_state["dividas_df"] = editado
    dividas = normalizar_dividas(editado)
    total = calcular_dividas(dividas) if somar else 0.0

    c1, c2, c3 = st.columns(3)
    with c1:
        card("Parcelas do mês", formatar_moeda(calcular_dividas(dividas)), "Soma das parcelas cadastradas", "red")
    with c2:
        card("Contando no painel", formatar_moeda(total), "Valor que entra no resultado", "gold")
    with c3:
        card("Dívidas cadastradas", str(len(dividas)), "Quantidade de linhas preenchidas", "blue")
    return dividas, total


def exibir_painel(resumo: dict[str, float], lancamentos: pd.DataFrame, diagnostico: list[dict[str, str]], plano: list[str]) -> None:
    st.subheader("Painel do mês")
    saldo = resumo["saldo_final"]
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        card("Entrou", formatar_moeda(resumo["total_receitas"]), "Entradas lançadas", "green")
    with c2:
        card("Saiu", formatar_moeda(resumo["total_geral_gastos"]), "Gastos e parcelas", "red")
    with c3:
        card("Sobrou" if saldo >= 0 else "Faltou", formatar_moeda(abs(saldo)), "Resultado do mês", "blue" if saldo >= 0 else "gold")
    with c4:
        card("De cada R$ 100", f"R$ {formatar_decimal(resumo['valor_usado_a_cada_100'])}", "Valor que já foi usado", "gold")

    progresso = min(max(resumo["percentual_comprometido"], 0), 100)
    st.progress(int(progresso), text=f"Uso do dinheiro que entrou: R$ {formatar_decimal(resumo['percentual_comprometido'])} de cada R$ 100.")

    st.markdown("#### Leitura rápida")
    for item in diagnostico:
        texto = f"**{item['titulo']}**\n\n{item['texto']}\n\nPróximo passo: {item['acao']}"
        if item["tipo"] == "erro":
            st.error(texto)
        elif item["tipo"] == "aviso":
            st.warning(texto)
        elif item["tipo"] == "sucesso":
            st.success(texto)
        else:
            st.info(texto)

    aba1, aba2, aba3 = st.tabs(["Para onde foi", "Entrou x saiu", "Plano de ação"])
    with aba1:
        gastos = lancamentos[lancamentos["Tipo"] == "Gasto"] if not lancamentos.empty else pd.DataFrame()
        if gastos.empty:
            st.info("Registre gastos para ver o gráfico.")
        else:
            dados = gastos.groupby("Categoria", as_index=False)["Valor"].sum().sort_values("Valor", ascending=False)
            dados["Texto"] = dados["Valor"].map(formatar_moeda)
            fig = px.bar(dados, x="Categoria", y="Valor", text="Texto", color="Categoria", color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_traces(textposition="outside", cliponaxis=False)
            fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Valor", margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            aplicar_eixo_moeda(fig)
            st.plotly_chart(fig, use_container_width=True)
    with aba2:
        dados = pd.DataFrame({"Tipo": ["Entrou", "Saiu"], "Valor": [resumo["total_receitas"], resumo["total_geral_gastos"]]})
        dados["Texto"] = dados["Valor"].map(formatar_moeda)
        fig = px.bar(dados, x="Tipo", y="Valor", text="Texto", color="Tipo", color_discrete_map={"Entrou": "#2f7d59", "Saiu": "#c45f4b"})
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Valor", margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        aplicar_eixo_moeda(fig)
        st.plotly_chart(fig, use_container_width=True)
    with aba3:
        for indice, passo in enumerate(plano, start=1):
            panel_html(f"Passo {indice}", passo)


def aba_metas(saldo: float) -> dict[str, object]:
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
    c4, c5, c6 = st.columns(3)
    with c4:
        card("Guardar por mês", formatar_moeda(mensal), "Valor necessário para chegar no prazo", "green")
    with c5:
        card("Sobrou no mês", formatar_moeda(max(saldo, 0)), "Valor disponível no painel", "blue" if saldo > 0 else "gold")
    with c6:
        card("Cabe agora?", "Sim" if cabe else "Ainda não", "Ajuste prazo ou valor se precisar", "blue" if cabe else "gold")

    if valor_total > 0 and not cabe:
        st.warning("A meta pode ficar mais leve aumentando o prazo ou criando uma folga maior no mês.")
    elif valor_total > 0 and cabe:
        st.success("A meta cabe no dinheiro que sobrou. O próximo passo é separar esse valor assim que receber.")

    if mensal > 0:
        dados = pd.DataFrame({"Mês": list(range(1, int(prazo) + 1)), "Dinheiro guardado": [mensal * mes for mes in range(1, int(prazo) + 1)]})
        fig = px.line(dados, x="Mês", y="Dinheiro guardado", markers=True)
        fig.update_traces(line_color="#2f6f9f")
        fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        aplicar_eixo_moeda(fig)
        st.plotly_chart(fig, use_container_width=True)

    return {"objetivo": objetivo, "valor_total": valor_total, "prazo_meses": int(prazo), "valor_mensal_necessario": mensal, "situacao": "Sim" if cabe else "Não"}


def selecionar_taxa_tesouro(titulos: list[dict[str, object]], tipo: str, padrao: float) -> tuple[str, float]:
    opcoes = [t for t in titulos if t["tipo"] == tipo]
    if not opcoes:
        taxa = st.number_input(f"Taxa anual para {tipo}", value=float(padrao), step=0.1, format="%.2f", key=f"manual_{tipo}")
        return "Taxa manual", taxa
    nomes = [f"{t['nome']} - taxa {formatar_decimal(t['taxa'])}% - venc. {t['vencimento']}" for t in opcoes]
    escolha = st.selectbox(tipo, nomes, key=f"select_{tipo}")
    indice = nomes.index(escolha)
    return opcoes[indice]["nome"], float(opcoes[indice]["taxa"])


def aba_simulacoes(meta: dict[str, object]) -> dict[str, object]:
    st.subheader("Simulações educativas")
    st.warning("A simulação abaixo possui caráter exclusivamente educativo e não representa recomendação de investimento.")

    taxas = obter_taxas_bcb()
    tesouro = obter_titulos_tesouro()
    if taxas["ok"]:
        st.success(f"Selic carregada do Banco Central: {formatar_decimal(taxas['selic_aa'])}% ao ano. Data: {taxas['selic_data']}.")
    else:
        st.warning("Não foi possível carregar as taxas do BCB. Use valores manuais para simular.")
    if tesouro["ok"]:
        st.caption(f"Taxas do Tesouro carregadas do Tesouro Transparente. Data base: {tesouro['data_base']}.")
    else:
        st.caption("Não foi possível carregar o Tesouro Transparente. Use taxas manuais para simular.")

    with st.expander("Taxas usadas na simulação", expanded=False):
        selic_aa = st.number_input("Selic ao ano", min_value=0.0, value=float(taxas["selic_aa"]), step=0.25, format="%.2f", key="sim_selic")
        tr_mensal = st.number_input("TR ao mês", min_value=0.0, value=float(taxas["tr_mensal"]), step=0.01, format="%.4f", key="sim_tr")
        ipca_12m = st.number_input("IPCA dos últimos 12 meses", min_value=0.0, value=float(taxas["ipca_12m"]), step=0.1, format="%.2f", key="sim_ipca")
        taxa_extra = st.number_input("Taxa anual extra opcional", min_value=0.0, value=0.0, step=0.05, format="%.2f", key="sim_taxa_extra", help="Use para testar custódia, serviço ou outro desconto anual. Pode deixar zero.")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        valor_inicial = dinheiro_input("Dinheiro já guardado", "sim_valor_inicial")
    with c2:
        valor_mensal = st.number_input("Guardar por mês", min_value=0.0, value=float(st.session_state.get("sim_valor_mensal", meta.get("valor_mensal_necessario", 0.0))), step=50.0, format="%.2f", key="sim_valor_mensal")
    with c3:
        meses = st.number_input("Por quantos meses", min_value=1, max_value=360, value=int(st.session_state.get("sim_meses", max(int(meta.get("prazo_meses", 12)), 1))), step=1, key="sim_meses")
    with c4:
        percentual_cdi = st.number_input("Percentual do CDI", min_value=0.0, max_value=200.0, value=100.0, step=5.0, format="%.2f", key="sim_percentual_cdi", help="100 significa 100% do CDI. O app não indica produto.")

    st.markdown("#### Títulos públicos para comparação")
    c5, c6, c7 = st.columns(3)
    with c5:
        _, taxa_selic_tesouro = selecionar_taxa_tesouro(tesouro["titulos"], "Tesouro Selic", 0.10)
    with c6:
        _, taxa_pre = selecionar_taxa_tesouro(tesouro["titulos"], "Tesouro Prefixado", 10.0)
    with c7:
        _, taxa_ipca = selecionar_taxa_tesouro(tesouro["titulos"], "Tesouro IPCA+", 5.0)

    simulacao = simular_cenarios(
        valor_inicial=float(valor_inicial),
        valor_mensal=float(valor_mensal),
        meses=int(meses),
        selic_aa=float(selic_aa),
        tr_mensal=float(tr_mensal),
        ipca_12m=float(ipca_12m),
        percentual_cdi=float(percentual_cdi),
        taxa_selic_tesouro=float(taxa_selic_tesouro),
        taxa_pre=float(taxa_pre),
        taxa_ipca=float(taxa_ipca),
        taxa_extra_aa=float(taxa_extra),
    )

    final = simulacao["final"]
    st.markdown("#### Resultado final estimado")
    cols = st.columns(3)
    with cols[0]:
        card("Conta corrente", formatar_moeda(final["Conta corrente sem rendimento"]), "Mesmo dinheiro sem rendimento", "green")
    with cols[1]:
        card("CDI depois do desconto", formatar_moeda(final["CDI depois do desconto"]), simulacao["faixa_irrf"], "blue")
    with cols[2]:
        card("Poupança", formatar_moeda(final["Poupança"]), "Sem IR nesta simulação", "green")
    cols2 = st.columns(3)
    with cols2[0]:
        card("Tesouro Selic", formatar_moeda(final["Tesouro Selic depois do desconto"]), "Com IRRF estimado", "blue")
    with cols2[1]:
        card("Tesouro Prefixado", formatar_moeda(final["Tesouro Prefixado depois do desconto"]), "Com IRRF estimado", "gold")
    with cols2[2]:
        card("Tesouro IPCA+", formatar_moeda(final["Tesouro IPCA+ depois do desconto"]), "Com IPCA informado e IRRF", "red")

    tabela = simulacao["tabela"]
    aba1, aba2, aba3 = st.tabs(["Gráfico", "Tabela mês a mês", "Como entender"])
    with aba1:
        dados = tabela.melt(id_vars="Mês", var_name="Cenário", value_name="Valor")
        dados = dados[dados["Cenário"] != "Total colocado"]
        fig = px.line(dados, x="Mês", y="Valor", color="Cenário", markers=True)
        fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend_title_text="")
        aplicar_eixo_moeda(fig)
        st.plotly_chart(fig, use_container_width=True)
    with aba2:
        st.dataframe(formatar_tabela_simulacao(tabela), hide_index=True, use_container_width=True)
    with aba3:
        panel_html("CDI", "Usa a Selic atual como aproximação educativa. O desconto de IRRF é estimado sobre o rendimento.")
        panel_html("Poupança", f"Usa a regra: {simulacao['regra_poupanca']}. Nesta simulação aparece sem desconto de IR.")
        panel_html("Tesouro Selic, Prefixado e IPCA+", "Usam taxas atuais do Tesouro Transparente quando disponíveis. A conta é simplificada e considera IRRF estimado.")
        panel_html("Atenção", "Preços do Tesouro mudam todos os dias. Venda antes do vencimento pode dar resultado diferente. Isto não é indicação de investimento.")

    return simulacao


def montar_relatorio(resumo: dict[str, float], meta: dict[str, object], simulacao: dict[str, object], diagnostico: list[dict[str, str]], plano: list[str]) -> str:
    linhas = [
        DISPLAY_NAME,
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
        "RESUMO DO MÊS",
        f"Entrou: {formatar_moeda(resumo['total_receitas'])}",
        f"Saiu: {formatar_moeda(resumo['total_geral_gastos'])}",
        f"Resultado: {formatar_moeda(resumo['saldo_final'])}",
        f"Gastos fixos: {formatar_moeda(resumo['total_fixos'])}",
        f"Gastos não fixos: {formatar_moeda(resumo['total_variaveis'])}",
        f"Parcelas cadastradas: {formatar_moeda(resumo['total_dividas'])}",
        "",
        "LEITURA RÁPIDA",
    ]
    linhas.extend([f"- {item['titulo']}: {item['texto']} Próximo passo: {item['acao']}" for item in diagnostico])
    linhas.extend(["", "PLANO DE AÇÃO"])
    linhas.extend([f"- {passo}" for passo in plano])
    linhas.extend(
        [
            "",
            "META",
            f"Objetivo: {meta['objetivo'] or 'Não informado'}",
            f"Valor desejado: {formatar_moeda(float(meta['valor_total']))}",
            f"Guardar por mês: {formatar_moeda(float(meta['valor_mensal_necessario']))}",
            f"Cabe agora? {meta['situacao']}",
            "",
            "SIMULAÇÃO EDUCATIVA",
            "A simulação possui caráter exclusivamente educativo e não representa recomendação de investimento.",
            f"Selic usada: {formatar_decimal(float(simulacao['selic_aa']))}% ao ano",
            f"IPCA usado: {formatar_decimal(float(simulacao['ipca_12m']))}% em 12 meses",
            f"Faixa de IRRF: {simulacao['faixa_irrf']}",
            f"Total colocado: {formatar_moeda(float(simulacao['final']['Total colocado']))}",
        ]
    )
    for chave, valor in simulacao["final"].items():
        if chave not in ["Mês", "Total colocado"]:
            linhas.append(f"{chave}: {formatar_moeda(float(valor))}")
    linhas.extend(["", "Aviso: este material não recomenda investimentos, bancos, corretoras ou produtos financeiros."])
    return "\n".join(linhas)


def exportar_excel(lancamentos: pd.DataFrame, dividas: pd.DataFrame, resumo: dict[str, float], meta: dict[str, object], simulacao: dict[str, object], diagnostico: list[dict[str, str]], plano: list[str]) -> bytes:
    arquivo = BytesIO()
    with pd.ExcelWriter(arquivo, engine="openpyxl") as writer:
        pd.DataFrame({"Gerado em": [datetime.now().strftime("%d/%m/%Y %H:%M")], "Material": [DISPLAY_NAME]}).to_excel(writer, index=False, sheet_name="Inicio")
        lancamentos.to_excel(writer, index=False, sheet_name="Lancamentos")
        dividas.to_excel(writer, index=False, sheet_name="Dividas")
        pd.DataFrame(list(resumo.items()), columns=["Item", "Valor"]).to_excel(writer, index=False, sheet_name="Resumo")
        pd.DataFrame([meta]).to_excel(writer, index=False, sheet_name="Meta")
        pd.DataFrame(diagnostico).to_excel(writer, index=False, sheet_name="Leitura")
        pd.DataFrame({"Passo": plano}).to_excel(writer, index=False, sheet_name="Plano")
        simulacao["tabela"].to_excel(writer, index=False, sheet_name="Simulacao")
        for planilha in writer.sheets.values():
            for coluna in planilha.columns:
                maior = max(len(str(celula.value)) if celula.value is not None else 0 for celula in coluna)
                planilha.column_dimensions[coluna[0].column_letter].width = min(maior + 3, 52)

        for nome_planilha in ["Lancamentos"]:
            planilha = writer.sheets[nome_planilha]
            cabecalhos = {celula.value: celula.column_letter for celula in planilha[1]}
            if "Data" in cabecalhos:
                for celula in planilha[cabecalhos["Data"]][1:]:
                    celula.number_format = "DD/MM/YYYY"
            if "Valor" in cabecalhos:
                for celula in planilha[cabecalhos["Valor"]][1:]:
                    celula.number_format = '"R$" #,##0.00'

        planilha_dividas = writer.sheets["Dividas"]
        cabecalhos_dividas = {celula.value: celula.column_letter for celula in planilha_dividas[1]}
        for nome_coluna in ["Falta pagar", "Parcela do mês"]:
            if nome_coluna in cabecalhos_dividas:
                for celula in planilha_dividas[cabecalhos_dividas[nome_coluna]][1:]:
                    celula.number_format = '"R$" #,##0.00'

        planilha_simulacao = writer.sheets["Simulacao"]
        cabecalhos_simulacao = {celula.value: celula.column_letter for celula in planilha_simulacao[1]}
        for nome_coluna, letra in cabecalhos_simulacao.items():
            if nome_coluna != "Mês":
                for celula in planilha_simulacao[letra][1:]:
                    celula.number_format = '"R$" #,##0.00'
    return arquivo.getvalue()


def aba_relatorios(lancamentos: pd.DataFrame, dividas: pd.DataFrame, resumo: dict[str, float], meta: dict[str, object], simulacao: dict[str, object], diagnostico: list[dict[str, str]], plano: list[str]) -> None:
    st.subheader("Relatórios")
    relatorio = montar_relatorio(resumo, meta, simulacao, diagnostico, plano)
    data_arquivo = datetime.now().strftime("%Y-%m-%d_%H-%M")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Baixar Excel", data=exportar_excel(lancamentos, dividas, resumo, meta, simulacao, diagnostico, plano), file_name=f"organizacao_financeira_{data_arquivo}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    with c2:
        st.download_button("Baixar TXT", data=relatorio.encode("utf-8"), file_name=f"relatorio_financeiro_{data_arquivo}.txt", mime="text/plain", use_container_width=True)

    st.info("Para salvar em PDF, use a prévia abaixo e escolha imprimir/salvar como PDF no navegador.")
    aba1, aba2, aba3, aba4 = st.tabs(["Prévia", "Lançamentos", "Dívidas", "Ano"])
    with aba1:
        st.text_area("Relatório", relatorio, height=520)
    with aba2:
        st.dataframe(formatar_tabela_lancamentos(lancamentos), hide_index=True, use_container_width=True)
    with aba3:
        st.dataframe(formatar_tabela_dividas(dividas), hide_index=True, use_container_width=True)
    with aba4:
        st.markdown("#### Controle anual de gastos")
        st.markdown(
            '<p class="note">Escolha um ou mais anos para acompanhar entradas, gastos fixos, gastos não fixos e compras parceladas. Lançamentos marcados como Fixo são repetidos mês a mês entre Início e Fim.</p>',
            unsafe_allow_html=True,
        )

        opcoes_anos = anos_disponiveis(lancamentos)
        padrao = [ano for ano in [2026, 2027] if ano in opcoes_anos] or opcoes_anos[:1]
        anos = st.multiselect("Anos do relatório", options=opcoes_anos, default=padrao)
        if not anos:
            st.info("Selecione pelo menos um ano.")
            return

        relatorio_anual = gerar_relatorio_anual(lancamentos, anos)
        totais_ano = relatorio_anual["totais_ano"]

        c1, c2, c3 = st.columns(3)
        with c1:
            card("Anos selecionados", ", ".join(str(ano) for ano in anos), "Período do relatório", "blue")
        with c2:
            card("Gastos no período", formatar_moeda(float(totais_ano["Total de gastos"].sum())), "Soma dos gastos lançados", "red")
        with c3:
            card("Saldo no período", formatar_moeda(float(totais_ano["Sobrou/Faltou"].sum())), "Entradas menos gastos", "green")

        st.download_button(
            "Baixar controle anual em Excel",
            data=exportar_relatorio_anual_excel(relatorio_anual),
            file_name=f"controle_gastos_anual_{data_arquivo}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        sub1, sub2, sub3, sub4, sub5 = st.tabs(["Mês a mês", "Totais por ano", "Categorias", "Parceladas", "Usados no relatório"])
        with sub1:
            tabela_mensal = relatorio_anual["mensal"].drop(columns=["Mês nº"])
            st.dataframe(formatar_tabela_resumo_anual(tabela_mensal), hide_index=True, use_container_width=True)

            dados_grafico = relatorio_anual["mensal"].copy()
            dados_grafico["Período"] = dados_grafico["Mês"].astype(str) + "/" + dados_grafico["Ano"].astype(str)
            dados_grafico = dados_grafico.melt(
                id_vars=["Ano", "Mês nº", "Período"],
                value_vars=["Gastos fixos", "Gastos não fixos"],
                var_name="Tipo de gasto",
                value_name="Valor",
            )
            fig = px.bar(
                dados_grafico,
                x="Período",
                y="Valor",
                color="Tipo de gasto",
                color_discrete_map={"Gastos fixos": "#b7791f", "Gastos não fixos": "#2f6f9f"},
            )
            fig.update_layout(xaxis_title="", yaxis_title="Valor", margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            aplicar_eixo_moeda(fig)
            st.plotly_chart(fig, use_container_width=True)

        with sub2:
            st.dataframe(formatar_tabela_resumo_anual(totais_ano), hide_index=True, use_container_width=True)
        with sub3:
            categorias = relatorio_anual["categorias"]
            st.dataframe(formatar_tabela_categoria_anual(categorias), hide_index=True, use_container_width=True)
            if not categorias.empty:
                categorias_grafico = categorias.copy()
                categorias_grafico["Ano"] = categorias_grafico["Ano"].astype(str)
                fig = px.bar(
                    categorias_grafico,
                    x="Categoria",
                    y="Valor",
                    color="Ano",
                    barmode="group",
                    color_discrete_sequence=["#2f6f9f", "#2f7d59", "#b7791f", "#c45f4b"],
                )
                fig.update_layout(xaxis_title="", yaxis_title="Valor", margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                aplicar_eixo_moeda(fig)
                st.plotly_chart(fig, use_container_width=True)
        with sub4:
            parceladas = relatorio_anual["parceladas"]
            if parceladas.empty:
                st.info("Nenhuma compra parcelada encontrada nos anos selecionados.")
            else:
                tabela_parceladas = parceladas.copy()
                tabela_parceladas["Valor"] = tabela_parceladas["Valor"].map(formatar_moeda)
                st.dataframe(tabela_parceladas, hide_index=True, use_container_width=True)
        with sub5:
            considerados = relatorio_anual["considerados"].copy()
            if considerados.empty:
                st.info("Nenhum lançamento encontrado no período selecionado.")
            else:
                for coluna_data in ["Data", "Início", "Fim"]:
                    if coluna_data in considerados.columns:
                        considerados[coluna_data] = considerados[coluna_data].map(formatar_data)
                if "Valor" in considerados.columns:
                    considerados["Valor"] = considerados["Valor"].map(formatar_moeda)
                colunas_visiveis = [
                    coluna
                    for coluna in [
                        "Ano",
                        "Mês",
                        "Data",
                        "Tipo",
                        "Descrição",
                        "Categoria",
                        "Valor",
                        "Fixo",
                        "Início",
                        "Fim",
                        "Origem no relatório",
                    ]
                    if coluna in considerados.columns
                ]
                st.dataframe(considerados[colunas_visiveis], hide_index=True, use_container_width=True)


def aba_oficina() -> None:
    st.subheader("Oficina")
    panel_html("Objetivo", "Ajudar participantes a entender o mês financeiro com linguagem simples: entrou, saiu, sobrou ou faltou.")
    panel_html("Como conduzir", "Comece com um exemplo fictício, depois peça que cada pessoa preencha seus próprios lançamentos sem expor dados pessoais.")
    panel_html("Perguntas para conversa", "Qual gasto mais surpreendeu? Quais gastos são fixos? Qual gasto não fixo poderia ser reduzido? Existe parcela pesando no mês?")
    panel_html("Cuidados", "Não peça CPF, banco, número de conta, senha, contrato ou dados de cartão. O foco é educação e organização.")
    panel_html("Justificativa acadêmica", "O app responde à dificuldade de controle de gastos, à falta de organização financeira estruturada e à necessidade de uma ferramenta prática para planejar melhor o dinheiro do mês.")


def barra_lateral() -> None:
    st.sidebar.title("Organização")
    st.sidebar.write("Registre entradas e gastos.")
    st.sidebar.write("Marque o que é fixo.")
    st.sidebar.write("Acompanhe o painel do mês.")
    st.sidebar.divider()
    if st.sidebar.button("Carregar exemplo", use_container_width=True):
        carregar_exemplo()
        st.rerun()
    if st.sidebar.button("Limpar tudo", use_container_width=True):
        st.session_state.clear()
        st.rerun()
    if st.sidebar.button("Atualizar taxas", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.sidebar.divider()
    st.sidebar.caption("Material educativo. Não recomenda produtos financeiros.")


def main() -> None:
    configurar_pagina()
    barra_lateral()

    abas = st.tabs(["Início", "Lançamentos", "Dívidas", "Painel", "Metas", "Simulações", "Relatórios", "Oficina"])

    with abas[0]:
        tela_inicio()

    with abas[1]:
        lancamentos = aba_lancamentos()

    with abas[2]:
        dividas, total_dividas = aba_dividas()

    totais_gastos = calcular_gastos(lancamentos)
    resumo = gerar_resumo(
        total_receitas=calcular_receitas(lancamentos),
        total_fixos=totais_gastos["total_fixos"],
        total_variaveis=totais_gastos["total_variaveis"],
        total_dividas=total_dividas,
    )
    diagnostico = gerar_diagnostico(resumo)
    plano = gerar_plano_acao(resumo, lancamentos)

    with abas[3]:
        exibir_painel(resumo, lancamentos, diagnostico, plano)

    with abas[4]:
        meta = aba_metas(resumo["saldo_final"])

    with abas[5]:
        simulacao = aba_simulacoes(meta)

    with abas[6]:
        aba_relatorios(lancamentos, dividas, resumo, meta, simulacao, diagnostico, plano)

    with abas[7]:
        aba_oficina()

    st.caption("Uso educativo. O app ajuda a organizar o mês, mas não recomenda investimentos nem produtos financeiros.")


if __name__ == "__main__":
    main()
