"""Projeções — cenários de crescimento composto com DCA."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data import enrich_portfolio, load_portfolio
from utils.styling import COLORS, PLOTLY_DARK_LAYOUT, apply_custom_css

st.set_page_config(page_title="Projeções", page_icon="📈", layout="wide")
apply_custom_css()

st.markdown("# Projeções")
st.caption("Cenários de crescimento composto com contribuição mensal (DCA).")

portfolio_data = load_portfolio()
df = enrich_portfolio(portfolio_data).dropna(subset=["current_price"])
initial = df["value_eur"].sum()

c1, c2, c3, c4 = st.columns(4)
with c1:
    valor_inicial = st.number_input("Valor Inicial (€)", value=float(initial), step=100.0)
with c2:
    contrib = st.number_input("Contribuição Mensal (€)",
                              value=float(portfolio_data["profile"]["contribuicao_mensal"]),
                              step=50.0)
with c3:
    anos = st.slider("Anos", 5, 40, 30)
with c4:
    inflacao = st.slider("Inflação (%)", 0.0, 6.0, 2.0, step=0.25)

cenarios = {
    "Pessimista (4% a.a.)": (0.04, COLORS["loss"]),
    "Base (8% a.a.)":       (0.08, COLORS["gain"]),
    "Otimista (11% a.a.)":  (0.11, COLORS["accent"]),
}

meses = anos * 12
mes_idx = np.arange(meses + 1)

fig = go.Figure()
results = []
for nome, (r_anual, cor) in cenarios.items():
    r_mensal = (1 + r_anual) ** (1 / 12) - 1
    values = np.zeros(meses + 1)
    values[0] = valor_inicial
    invested = np.zeros(meses + 1)
    invested[0] = valor_inicial
    for m in range(1, meses + 1):
        values[m] = values[m - 1] * (1 + r_mensal) + contrib
        invested[m] = invested[m - 1] + contrib

    final = values[-1]
    total_invested = invested[-1]
    real_final = final / ((1 + inflacao / 100) ** anos)
    results.append({
        "Cenário": nome,
        "Valor Nominal Final": final,
        "Valor Real (hoje)": real_final,
        "Total Investido": total_invested,
        "Ganhos": final - total_invested,
        "Multiplicador": final / total_invested if total_invested else 0,
    })
    fig.add_trace(go.Scatter(
        x=mes_idx / 12, y=values, name=nome,
        line=dict(color=cor, width=2.5),
    ))

invested_line = valor_inicial + contrib * mes_idx
fig.add_trace(go.Scatter(
    x=mes_idx / 12, y=invested_line,
    name="Investido (sem retorno)",
    line=dict(color=COLORS["text_muted"], width=2, dash="dash"),
))

fig.update_layout(
    **PLOTLY_DARK_LAYOUT, height=500,
    xaxis_title="Anos", yaxis_title="Valor (€)",
    legend=dict(orientation="h", y=1.08, x=0),
)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

st.markdown("## Resumo por Cenário")
st.dataframe(
    pd.DataFrame(results),
    hide_index=True, use_container_width=True,
    column_config={
        "Valor Nominal Final": st.column_config.NumberColumn(format="€ %.0f"),
        "Valor Real (hoje)":   st.column_config.NumberColumn(format="€ %.0f"),
        "Total Investido":     st.column_config.NumberColumn(format="€ %.0f"),
        "Ganhos":              st.column_config.NumberColumn(format="€ %.0f"),
        "Multiplicador":       st.column_config.NumberColumn(format="%.2fx"),
    },
)

st.caption(
    "Projeções determinísticas. Para ver o impacto da volatilidade, ver página **⚠️ Risco** (Monte Carlo)."
)
