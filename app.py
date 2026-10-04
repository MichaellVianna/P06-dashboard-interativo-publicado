from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

st.set_page_config(page_title="Processo contínuo", layout="wide")

# Paleta do P05 (validada para daltonismo). Cada máquina mantém sempre a mesma cor.
AZUL, LARANJA, VERDE_AGUA = "#2a78d6", "#eb6834", "#1baf7a"
TINTA, TINTA_2, TINTA_3 = "#0b0b0b", "#52514e", "#898781"
GRADE, CRITICO, AZUL_FAIXA = "#e1e0d9", "#d03b3b", "#cde2fb"
COR_MAQUINA = {1: AZUL, 2: LARANJA, 3: VERDE_AGUA}

CAMINHO = Path(__file__).parent / "data" / "processo_app.csv"
CONFIG_GRAFICO = {"displaylogo": False, "modeBarButtonsToRemove": ["select2d", "lasso2d"]}


def num(x, casas=2):
    """Número no formato brasileiro (vírgula decimal, ponto de milhar, sinal de menos)."""
    texto = f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return texto.replace("-", "−")


def aplica_layout(fig, altura):
    """Aparência comum a todos os gráficos: fundo da página, grade discreta, hover unificado."""
    fig.update_layout(
        height=altura,
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode="x unified",
        separators=",.",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TINTA_2, size=13),
        hoverlabel=dict(bgcolor="white", font_color=TINTA),
        legend=dict(orientation="h", x=0, y=1.12, yanchor="bottom"),
    )
    fig.update_xaxes(showgrid=False, tickformat="%H:%M", hoverformat="%H:%M:%S",
                     linecolor=GRADE, tickfont=dict(color=TINTA_3))
    fig.update_yaxes(gridcolor=GRADE, zeroline=False, tickfont=dict(color=TINTA_3))
    return fig


@st.cache_data
def carrega_dados():
    return pd.read_csv(CAMINHO, parse_dates=["time_stamp"])


df = carrega_dados()

# ---------- Cabeçalho ----------
st.title("Processo de manufatura contínua")
st.write(
    f"Corrida de {df['time_stamp'].min():%d/%m/%Y, %H:%M} a {df['time_stamp'].max():%H:%M}, "
    f"uma leitura por segundo ({num(len(df), 0)} leituras). "
    "Etapa 1 de uma linha de produção de duas etapas."
)

# ---------- Filtros (barra lateral) ----------
st.sidebar.header("Filtros")

ponto = st.sidebar.selectbox("Ponto de medição", range(15))

inicio = df["time_stamp"].min().to_pydatetime()
fim = df["time_stamp"].max().to_pydatetime()
periodo = st.sidebar.slider("Período", min_value=inicio, max_value=fim,
                            value=(inicio, fim), step=timedelta(seconds=1),
                            format="HH:mm")

sem_zeros = st.sidebar.checkbox("Remover leituras iguais a zero", value=True)

st.sidebar.divider()
maquinas = st.sidebar.multiselect("Máquinas", [1, 2, 3], default=[1, 2, 3])

st.sidebar.divider()
modo = st.sidebar.radio("Limites da carta", ["Todos os dados do período", "Trecho de referência"])
if modo == "Trecho de referência":
    ref_ini, ref_fim = st.sidebar.slider(
        "Trecho de referência", min_value=inicio, max_value=fim,
        value=(datetime(2019, 3, 6, 12, 10), datetime(2019, 3, 6, 13, 20)),
        step=timedelta(seconds=1), format="HH:mm")

# ---------- Dados filtrados ----------
medido = f"Stage1.Output.Measurement{ponto}.U.Actual"
alvo = f"Stage1.Output.Measurement{ponto}.U.Setpoint"

recorte = df[df["time_stamp"].between(*periodo)]
dados = recorte[recorte[medido] != 0] if sem_zeros else recorte

if dados.empty:
    st.warning("Nenhuma leitura neste período e ponto de medição. Ajuste os filtros.")
    st.stop()

tempo = dados["time_stamp"]
erro = dados[medido] - dados[alvo]

# ---------- Resumo ----------
minutos = round((periodo[1] - periodo[0]).total_seconds() / 60)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Leituras no período", num(len(recorte), 0), border=True)
k2.metric("Duração", f"{num(minutos, 0)} min", border=True)
k3.metric(f"Alvo do ponto {ponto}", f"{num(dados[alvo].median())} mm", border=True)
k4.metric("Erro médio (medido − alvo)", f"{num(erro.mean())} mm", border=True)

aba_alvo, aba_carta, aba_maquinas = st.tabs(
    ["Medido contra alvo", "Carta de controle", "Temperatura e pressão"])

# ---------- Aba 1: medido contra alvo ----------
with aba_alvo:
    fig = go.Figure()
    fig.add_scatter(x=tempo, y=dados[medido], name="medido", mode="lines",
                    line=dict(color=AZUL, width=1),
                    hovertemplate="%{y:,.2f} mm<extra></extra>")
    fig.add_scatter(x=tempo, y=dados[alvo], name="alvo", mode="lines",
                    line=dict(color=TINTA, width=1.5),
                    hovertemplate="%{y:,.2f} mm<extra></extra>")
    fig.update_yaxes(title_text="mm")
    st.plotly_chart(aplica_layout(fig, 430), width="stretch", config=CONFIG_GRAFICO)
    st.caption("Arraste sobre o gráfico para dar zoom e dê duplo clique para voltar à escala inteira. "
               "A caixa da barra lateral remove só as leituras exatamente iguais a zero.")

# ---------- Aba 2: carta de controle ----------
with aba_carta:
    if modo == "Trecho de referência":
        referencia = erro[tempo.between(ref_ini, ref_fim)]
    else:
        referencia = erro

    if len(referencia) < 2:
        st.warning("Poucas leituras no trecho de referência para calcular os limites.")
    else:
        centro, sigma = referencia.mean(), referencia.std()
        lic, lsc = centro - 3 * sigma, centro + 3 * sigma
        fora = (erro > lsc) | (erro < lic)

        c1, c2, c3, c4 = st.columns([0.8, 0.8, 1.4, 1.6])
        c1.metric("Centro (mm)", num(centro), border=True)
        c2.metric("Sigma (mm)", num(sigma, 3), border=True)
        c3.metric("Limites ±3σ (mm)", f"{num(lic)} a {num(lsc)}", border=True)
        c4.metric("Leituras fora dos limites", f"{num(fora.sum(), 0)} de {num(len(erro), 0)}",
                  border=True)

        fig = go.Figure()
        if modo == "Trecho de referência":
            fig.add_vrect(x0=ref_ini, x1=ref_fim, fillcolor=AZUL_FAIXA, opacity=0.6,
                          line_width=0, layer="below")
        fig.add_scatter(x=tempo, y=erro, name="erro", mode="lines",
                        line=dict(color=AZUL, width=1),
                        hovertemplate="%{y:,.2f} mm<extra></extra>")
        fig.add_scatter(x=tempo[fora], y=erro[fora], name="fora dos limites", mode="markers",
                        marker=dict(color=CRITICO, size=5),
                        hovertemplate="%{y:,.2f} mm<extra></extra>")
        extremos = [tempo.min(), tempo.max()]
        fig.add_scatter(x=extremos, y=[centro, centro], name="centro", mode="lines",
                        line=dict(color=TINTA, width=1.2), hoverinfo="skip")
        fig.add_scatter(x=extremos, y=[lsc, lsc], name="limites ±3σ", legendgroup="limites",
                        mode="lines", line=dict(color=TINTA_2, width=1, dash="dash"),
                        hoverinfo="skip")
        fig.add_scatter(x=extremos, y=[lic, lic], name="limites ±3σ", legendgroup="limites",
                        showlegend=False, mode="lines",
                        line=dict(color=TINTA_2, width=1, dash="dash"), hoverinfo="skip")
        fig.update_yaxes(title_text="erro: medido − alvo (mm)")
        st.plotly_chart(aplica_layout(fig, 430), width="stretch", config=CONFIG_GRAFICO)
        st.caption("Os limites vêm do centro e do desvio padrão do trecho escolhido e valem para o "
                   "período inteiro. A carta mostra quando o erro muda, não a causa.")

# ---------- Aba 3: temperatura e pressão ----------
with aba_maquinas:
    if maquinas:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08)
        for m in maquinas:
            for linha, coluna in [(1, f"Machine{m}.MaterialTemperature.U.Actual"),
                                  (2, f"Machine{m}.MaterialPressure.U.Actual")]:
                fig.add_scatter(x=recorte["time_stamp"], y=recorte[coluna], mode="lines",
                                name=f"máquina {m}", legendgroup=f"m{m}",
                                showlegend=(linha == 1),
                                line=dict(color=COR_MAQUINA[m], width=1),
                                hovertemplate="%{y:,.1f}<extra></extra>",
                                row=linha, col=1)
        fig.update_yaxes(title_text="temperatura do material", row=1, col=1)
        fig.update_yaxes(title_text="pressão do material", row=2, col=1)
        st.plotly_chart(aplica_layout(fig, 620), width="stretch", config=CONFIG_GRAFICO)
        st.caption("Temperatura e pressão do material nas máquinas da Etapa 1, no período escolhido. "
                   "Clique numa máquina da legenda para ocultá-la.")
    else:
        st.info("Marque pelo menos uma máquina na barra lateral.")

st.divider()
st.caption("Dados: Multi-stage continuous-flow manufacturing process (Kaggle, supergus). "
           "Uma corrida de cerca de 4 horas, anonimizada pelo fornecedor.")
