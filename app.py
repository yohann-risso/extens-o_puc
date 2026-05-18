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


def formatar_tabela_lancamentos(lancamentos: pd.DataFrame, colunas: list[str] | None = None) -> pd.DataFrame:
    tabela = lancamentos.copy()
    if tabela.empty:
        return tabela
    if colunas is not None:
        tabela = tabela[[coluna for coluna in colunas if coluna in tabela.columns]].copy()
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


def numero_bcb(valor: object) -> float:
    if pd.isna(valor):
        return 0.0
    return float(str(valor).strip().replace(",", "."))


def normalizar_percentual_atual(valor: float) -> float:
    """Evita exibir valor inflado se algum cache antigo trouxe 14.50 como 1450."""
    return valor / 100 if valor > 100 else valor


def icone_categoria(categoria: str) -> str:
    return ICONE_CATEGORIA.get(categoria, "•")


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
        div[data-testid="stAlert"] { border-radius: 8px; }
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


@st.cache_data(ttl=60 * 60)
def obter_taxas_bcb(_cache_version: str = CACHE_TAXAS_BCB) -> dict[str, object]:
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


def criar_lancamento_vazio(tipo: str = "Gasto") -> dict[str, object]:
    categoria = "Outros ganhos" if tipo == "Entrada" else "Outros gastos"
    return {
        "Data": date.today(),
        "Tipo": tipo,
        "Descrição": "",
        "Categoria": categoria,
        "Valor": 0.0,
        "Fixo": False,
        "Início": None,
        "Fim": None,
        "Parcelado": False,
        "Nº de parcelas": 1,
        "Parcelas pagas": 0,
        "Observação": "",
    }


def normalizar_lancamentos(df: pd.DataFrame) -> pd.DataFrame:
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
    }


def gerar_diagnostico(resumo: dict[str, float]) -> list[dict[str, str]]:
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
    gastos = lancamentos[lancamentos["Tipo"] == "Gasto"] if not lancamentos.empty else pd.DataFrame()
    if gastos.empty:
        return "Ainda não registrada", 0.0
    por_categoria = gastos.groupby("Categoria")["Valor"].sum().sort_values(ascending=False)
    if por_categoria.empty:
        return "Ainda não registrada", 0.0
    return str(por_categoria.index[0]), float(por_categoria.iloc[0])


def gerar_resumo_financeiro_mes(resumo: dict[str, float], lancamentos: pd.DataFrame) -> dict[str, object]:
    categoria, valor_categoria = principal_categoria_gasto(lancamentos)
    saldo = resumo["saldo_final"]
    total_receitas = resumo["total_receitas"]
    parte_dividas = resumo["total_dividas"] / total_receitas * 100 if total_receitas > 0 else 0.0

    if total_receitas == 0:
        recomendacao = "Comece registrando uma entrada, como salário, ajuda recebida ou venda feita no mês."
    elif saldo < 0:
        recomendacao = f"{categoria} foi a categoria que mais pesou. Procure uma redução pequena para o próximo mês."
    elif parte_dividas >= 20:
        recomendacao = "As parcelas estão ocupando uma parte importante do mês. Evite nova compra parcelada antes de reorganizar o orçamento."
    elif categoria in ["Delivery ou lanche fora", "Lazer", "Compras", "Assinaturas"]:
        recomendacao = f"Você gastou mais com {categoria.lower()}. Pequenas reduções podem ajudar a formar uma reserva financeira."
    elif saldo > 0:
        recomendacao = "O mês terminou com sobra. Separar uma parte logo ao receber ajuda a transformar sobra em hábito."
    else:
        recomendacao = "O mês ficou no limite. Tente criar uma folga pequena antes de assumir novos gastos."

    return {
        "entrou": resumo["total_receitas"],
        "saiu": resumo["total_geral_gastos"],
        "categoria": categoria,
        "valor_categoria": valor_categoria,
        "saldo": saldo,
        "recomendacao": recomendacao,
    }


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

        for planilha in writer.sheets.values():
            for coluna in planilha.columns:
                maior = max(len(str(celula.value)) if celula.value is not None else 0 for celula in coluna)
                planilha.column_dimensions[coluna[0].column_letter].width = min(maior + 3, 52)

        for nome_planilha in ["Mes a mes", "Totais por ano", "Categorias", "Parceladas"]:
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


def taxa_mensal_anual(taxa_aa: float) -> float:
    return (1 + taxa_aa / 100) ** (1 / 12) - 1


def taxa_poupanca_mensal(selic_aa: float, tr_mensal: float) -> tuple[float, str]:
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
            descricao = st.text_input("Descrição", placeholder="Exemplo: mercado")
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
                st.rerun()
            else:
                st.warning("Informe um valor maior que zero.")

    if st.button("Adicionar linha vazia", width="content"):
        st.session_state["lancamentos_df"] = pd.concat(
            [st.session_state["lancamentos_df"], pd.DataFrame([criar_lancamento_vazio()])],
            ignore_index=True,
        )
        st.rerun()

    mostrar_detalhes = st.toggle("Mostrar detalhes", value=False)
    colunas_editor = COLUNAS_LANCAMENTOS_BASICAS + (COLUNAS_LANCAMENTOS_DETALHES if mostrar_detalhes else [])

    editado = st.data_editor(
        st.session_state["lancamentos_df"],
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_order=colunas_editor,
        column_config={
            "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "Tipo": st.column_config.SelectboxColumn("Tipo", options=TIPOS_LANCAMENTO, required=True),
            "Descrição": st.column_config.TextColumn("Descrição", help="Exemplo: salário, mercado, ônibus"),
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
        key="editor_lancamentos",
    )
    st.session_state["lancamentos_df"] = editado

    lancamentos = normalizar_lancamentos(editado)
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
    editado = st.data_editor(
        st.session_state["dividas_df"],
        num_rows="dynamic",
        width="stretch",
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

    c1, c2 = st.columns(2)
    with c1:
        card("⚠️ Parcelas do mês", formatar_moeda(calcular_dividas(dividas)), "Soma das parcelas cadastradas.", "red")
    with c2:
        card("📌 No resultado", formatar_moeda(total), "Valor que entra no resultado do mês.", "gold")
    c3, _ = st.columns(2)
    with c3:
        card("🧾 Dívidas cadastradas", str(len(dividas)), "Quantidade de linhas preenchidas.", "blue")
    return dividas, total


def exibir_painel(resumo: dict[str, float], lancamentos: pd.DataFrame, diagnostico: list[dict[str, str]], sugestoes: list[str], resumo_final: dict[str, object]) -> None:
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
        card("⚠️ Parcelas", formatar_moeda(resumo["total_dividas"]), "Parcelas somadas ao mês.", "gold")

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
            fig = px.bar(dados, x="Valor", y="Categoria", text="Texto", orientation="h", color="Categoria", color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_traces(textposition="outside", cliponaxis=False)
            fig.update_layout(
                showlegend=False,
                xaxis_title="",
                yaxis_title="",
                yaxis={"categoryorder": "total ascending"},
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            fig.update_xaxes(showgrid=False, tickprefix="R$ ", separatethousands=True)
            fig.update_yaxes(showgrid=False)
            st.plotly_chart(fig, width="stretch")
            st.info(f"{resumo_final['categoria']} foi a categoria que mais pesou este mês.")
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
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="", margin=dict(l=10, r=10, t=15, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        aplicar_eixo_moeda(fig)
        st.plotly_chart(fig, width="stretch")

    panel_html("Insight do mês", str(resumo_final["recomendacao"]))


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
        fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        aplicar_eixo_moeda(fig)
        st.plotly_chart(fig, width="stretch")

    return {"objetivo": objetivo, "valor_total": valor_total, "prazo_meses": int(prazo), "valor_mensal_necessario": mensal, "situacao": "Sim" if cabe else "Não"}


def aba_guardando_dinheiro(meta: dict[str, object]) -> dict[str, object]:
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
    fig = px.bar(dados, x="Valor", y="Cenário", text="Texto", orientation="h", color="Cenário", color_discrete_sequence=["#2f7d59", "#2f6f9f", "#b7791f"])
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="", margin=dict(l=10, r=10, t=15, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    fig.update_xaxes(showgrid=False, tickprefix="R$ ", separatethousands=True)
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(fig, width="stretch")

    with st.expander("Ver evolução mês a mês"):
        st.dataframe(formatar_tabela_simulacao(tabela), hide_index=True, width="stretch")

    return simulacao


def montar_resumo_exportacao(resumo: dict[str, float], resumo_final: dict[str, object], meta: dict[str, object], simulacao: dict[str, object], sugestoes: list[str]) -> list[str]:
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
    texto = texto.encode("latin-1", "replace").decode("latin-1")
    return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def exportar_pdf(linhas: list[str]) -> bytes:
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


def exportar_excel(lancamentos: pd.DataFrame, dividas: pd.DataFrame, resumo: dict[str, float], resumo_final: dict[str, object], meta: dict[str, object], simulacao: dict[str, object], sugestoes: list[str]) -> bytes:
    arquivo = BytesIO()
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
        pd.DataFrame({"Sugestão": sugestoes}).to_excel(writer, index=False, sheet_name="Sugestoes")
        simulacao["tabela"].to_excel(writer, index=False, sheet_name="Guardando")
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

        planilha_simulacao = writer.sheets["Guardando"]
        cabecalhos_simulacao = {celula.value: celula.column_letter for celula in planilha_simulacao[1]}
        for nome_coluna, letra in cabecalhos_simulacao.items():
            if nome_coluna != "Mês":
                for celula in planilha_simulacao[letra][1:]:
                    celula.number_format = '"R$" #,##0.00'
    return arquivo.getvalue()


def aba_historico(lancamentos: pd.DataFrame, dividas: pd.DataFrame, resumo: dict[str, float], resumo_final: dict[str, object], meta: dict[str, object], simulacao: dict[str, object], sugestoes: list[str]) -> None:
    st.subheader("Histórico")
    linhas_pdf = montar_resumo_exportacao(resumo, resumo_final, meta, simulacao, sugestoes)
    data_arquivo = datetime.now().strftime("%Y-%m-%d_%H-%M")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "Baixar Excel",
            data=exportar_excel(lancamentos, dividas, resumo, resumo_final, meta, simulacao, sugestoes),
            file_name=f"organizacao_financeira_{data_arquivo}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
    with c2:
        st.download_button(
            "Baixar PDF",
            data=exportar_pdf(linhas_pdf),
            file_name=f"resumo_financeiro_{data_arquivo}.pdf",
            mime="application/pdf",
            width="stretch",
        )

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
        st.dataframe(formatar_tabela_lancamentos(lancamentos, ["Data", "Descrição", "Categoria", "Valor"]), hide_index=True, width="stretch")

    with st.expander("Ver dívidas"):
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
        file_name=f"historico_anual_{data_arquivo}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )

    dados_grafico = historico_anual["mensal"].copy()
    dados_grafico["Período"] = dados_grafico["Mês"].astype(str) + "/" + dados_grafico["Ano"].astype(str)
    fig = px.line(dados_grafico, x="Período", y="Sobrou/Faltou", markers=True)
    fig.update_traces(line_color="#2f6f9f")
    fig.update_layout(xaxis_title="", yaxis_title="", margin=dict(l=10, r=10, t=20, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    aplicar_eixo_moeda(fig)
    st.plotly_chart(fig, width="stretch")

    with st.expander("Resumo mês a mês"):
        tabela_mensal = historico_anual["mensal"].drop(columns=["Mês nº"])
        st.dataframe(formatar_tabela_resumo_anual(tabela_mensal), hide_index=True, width="stretch")

    with st.expander("Categorias principais"):
        categorias = historico_anual["categorias"]
        st.dataframe(formatar_tabela_categoria_anual(categorias), hide_index=True, width="stretch")
        if not categorias.empty:
            categorias_grafico = categorias.groupby("Categoria", as_index=False)["Valor"].sum().sort_values("Valor", ascending=False).head(8)
            categorias_grafico["Categoria"] = categorias_grafico["Categoria"].map(lambda item: f"{icone_categoria(item)} {item}")
            categorias_grafico["Texto"] = categorias_grafico["Valor"].map(formatar_moeda)
            fig = px.bar(
                categorias_grafico,
                x="Valor",
                y="Categoria",
                text="Texto",
                orientation="h",
                color="Categoria",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig.update_traces(textposition="outside", cliponaxis=False)
            fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="", yaxis={"categoryorder": "total ascending"}, margin=dict(l=10, r=10, t=15, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            fig.update_xaxes(showgrid=False, tickprefix="R$ ", separatethousands=True)
            fig.update_yaxes(showgrid=False)
            st.plotly_chart(fig, width="stretch")

    with st.expander("Compras parceladas"):
        parceladas = historico_anual["parceladas"]
        if parceladas.empty:
            st.info("Nenhuma compra parcelada encontrada nos anos selecionados.")
        else:
            tabela_parceladas = parceladas.copy()
            tabela_parceladas["Valor"] = tabela_parceladas["Valor"].map(formatar_moeda)
            st.dataframe(tabela_parceladas, hide_index=True, width="stretch")


def barra_lateral() -> None:
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
        st.rerun()
    if st.sidebar.button("Carregar exemplo", width="stretch"):
        carregar_exemplo()
        st.rerun()
    if st.sidebar.button("Limpar tudo", width="stretch"):
        st.session_state.clear()
        st.rerun()
    if st.sidebar.button("Atualizar referências", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    st.sidebar.divider()
    st.sidebar.caption("As comparações possuem caráter informativo.")


def main() -> None:
    configurar_pagina()
    barra_lateral()

    abas = st.tabs(["Início", "Registrar", "Resultado do mês", "Dívidas", "Metas", "Guardando dinheiro", "Histórico"])

    with abas[0]:
        tela_inicio()

    with abas[1]:
        lancamentos = aba_lancamentos()

    with abas[3]:
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

    with abas[2]:
        exibir_painel(resumo, lancamentos, diagnostico, sugestoes, resumo_final)

    with abas[4]:
        meta = aba_metas(resumo["saldo_final"])

    with abas[5]:
        simulacao = aba_guardando_dinheiro(meta)

    with abas[6]:
        aba_historico(lancamentos, dividas, resumo, resumo_final, meta, simulacao, sugestoes)

    st.caption("As comparações possuem caráter informativo.")


if __name__ == "__main__":
    main()
