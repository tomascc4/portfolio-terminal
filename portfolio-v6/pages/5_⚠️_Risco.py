"""Risco — análise aprofundada com Monte Carlo e stress tests."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data import enrich_portfolio, fetch_historical, load_portfolio
from utils.metrics import daily_returns, full_risk_suite, portfolio_returns
from utils.styling import COLORS, PLOTLY_DARK_LAYOUT, apply_custom_css

st.set_page_config(page_title="Risco", page_icon="⚠️", layout="wide")
apply_custom_css()

st.markdown("# Risco")
st.caption("Drawdowns, volatilidade rolling e simulações Monte Carlo.")

portfolio_data = load_portfolio()
df = enrich_portfolio(portfolio_data).dropna(subset=["current_price"])
tickers = tuple(df["ticker"].tolist())

with st.spinner("A carregar histórico..."):
    hist = fetch_historical(tickers, period="2y")
    bench = fetch_historical(("^GSPC",), period="2y")

weights = dict(zip(df["ticker"], df["weight"] / 100))
hist_avail = [t for t in weights if t in hist.columns]
hist = hist[hist_avail]
port_ret = portfolio_returns(hist, {t: weights[t] for t in hist_avail})
bench_ret = daily_returns(bench.iloc[:, 0])

# ============================================================
# Risk suite
# ============================================================
metrics = full_risk_suite(port_ret, bench_ret, portfolio_data["risk_free_rate"])

st.markdown("## Métricas (2A)")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Retorno Anualizado", f"{metrics['annualized_return']:.2%}")
c2.metric("Volatilidade", f"{metrics['volatility']:.2%}")
c3.metric("Sharpe", f"{metrics['sharpe']:.2f}")
c4.metric("Sortino", f"{metrics['sortino']:.2f}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Beta vs S&P 500", f"{metrics['beta']:.2f}")
c2.metric("Alpha (CAPM)", f"{metrics['alpha']:.2%}")
c3.metric("R²", f"{metrics['r_squared']:.2f}")
c4.metric("Máx. Drawdown", f"{metrics['max_drawdown']:.2%}")

# ============================================================
# Drawdown
# ============================================================
st.markdown("## Drawdown Histórico")
cum = (1 + port_ret).cumprod()
dd = (cum - cum.cummax()) / cum.cummax()
fig = go.Figure(go.Scatter(
    x=dd.index, y=dd.values * 100,
    line=dict(color=COLORS["loss"], width=1.5),
    fill="tozeroy", fillcolor="rgba(255,92,122,0.15)",
))
fig.update_layout(
    **PLOTLY_DARK_LAYOUT, height=300,
    yaxis_title="Drawdown (%)",
)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ============================================================
# Rolling volatility
# ============================================================
st.markdown("## Volatilidade Rolling (30d anualizada)")
rolling_vol = port_ret.rolling(30).std() * np.sqrt(252) * 100
rolling_bench = bench_ret.rolling(30).std() * np.sqrt(252) * 100
fig = go.Figure()
fig.add_trace(go.Scatter(x=rolling_vol.index, y=rolling_vol.values,
                         name="Carteira", line=dict(color=COLORS["gain"], width=2)))
fig.add_trace(go.Scatter(x=rolling_bench.index, y=rolling_bench.values,
                         name="S&P 500", line=dict(color=COLORS["accent"], width=2, dash="dot")))
fig.update_layout(**PLOTLY_DARK_LAYOUT, height=300,
                  yaxis_title="Volatilidade (%)",
                  legend=dict(orientation="h", y=1.08, x=0))
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ============================================================
# Monte Carlo
# ============================================================
st.markdown("## Monte Carlo (1A)")

c1, c2 = st.columns(2)
with c1:
    n_sims = st.slider("Número de simulações", 100, 5000, 1000, step=100)
with c2:
    horizon_days = st.slider("Horizonte (dias úteis)", 60, 504, 252, step=21)

mu = port_ret.mean()
sigma = port_ret.std()
initial = df["value_eur"].sum()

np.random.seed(42)
sims = np.zeros((horizon_days, n_sims))
for i in range(n_sims):
    daily = np.random.normal(mu, sigma, horizon_days)
    sims[:, i] = initial * (1 + daily).cumprod()

final_values = sims[-1, :]
p5, p25, p50, p75, p95 = np.percentile(final_values, [5, 25, 50, 75, 95])

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("P5 (pior)", f"€ {p5:,.0f}", f"{((p5/initial)-1)*100:+.1f}%")
c2.metric("P25", f"€ {p25:,.0f}", f"{((p25/initial)-1)*100:+.1f}%")
c3.metric("Mediano", f"€ {p50:,.0f}", f"{((p50/initial)-1)*100:+.1f}%")
c4.metric("P75", f"€ {p75:,.0f}", f"{((p75/initial)-1)*100:+.1f}%")
c5.metric("P95 (melhor)", f"€ {p95:,.0f}", f"{((p95/initial)-1)*100:+.1f}%")

fig = go.Figure()
for i in range(min(200, n_sims)):
    fig.add_trace(go.Scatter(
        y=sims[:, i], mode="lines",
        line=dict(color="rgba(0,212,170,0.04)", width=0.5),
        showlegend=False, hoverinfo="skip",
    ))
pct_5 = np.percentile(sims, 5, axis=1)
pct_50 = np.percentile(sims, 50, axis=1)
pct_95 = np.percentile(sims, 95, axis=1)
fig.add_trace(go.Scatter(y=pct_95, name="P95", line=dict(color=COLORS["gain"], width=2)))
fig.add_trace(go.Scatter(y=pct_50, name="Mediana", line=dict(color=COLORS["text"], width=2)))
fig.add_trace(go.Scatter(y=pct_5, name="P5", line=dict(color=COLORS["loss"], width=2)))
fig.update_layout(**PLOTLY_DARK_LAYOUT, height=400,
                  xaxis_title="Dias úteis", yaxis_title="Valor (€)")
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

st.caption(
    f"Assume retornos diários normalmente distribuídos (μ={mu*100:.3f}%, σ={sigma*100:.2f}%). "
    "Não captura caudas gordas nem mudanças de regime."
)
