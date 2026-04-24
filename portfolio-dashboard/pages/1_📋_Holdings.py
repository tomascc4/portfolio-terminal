"""Holdings — análise detalhada com gestão de moedas correcta."""
import plotly.graph_objects as go
import streamlit as st

from utils.data import enrich_portfolio, fetch_historical, load_portfolio
from utils.metrics import (
    annualized_return, annualized_volatility,
    daily_returns, max_drawdown, sharpe_ratio,
)
from utils.styling import COLORS, PLOTLY_DARK_LAYOUT, apply_custom_css

st.set_page_config(page_title="Holdings", page_icon="📋", layout="wide")
apply_custom_css()

st.markdown("# Holdings")
st.caption("Deep-dive por posição. Preços em moeda nativa; P/L sempre em EUR.")

portfolio_data = load_portfolio()
df = enrich_portfolio(portfolio_data).dropna(subset=["current_price"])

# Filters
c1, c2, c3 = st.columns(3)
with c1:
    sel_class = st.selectbox("Classificação", ["Todas"] + sorted(df["class"].unique().tolist()))
with c2:
    sel_sector = st.selectbox("Sector", ["Todos"] + sorted(df["sector"].unique().tolist()))
with c3:
    sel_curr = st.selectbox("Moeda PM", ["Todas"] + sorted(df["currency"].unique().tolist()))

filt = df.copy()
if sel_class != "Todas":
    filt = filt[filt["class"] == sel_class]
if sel_sector != "Todos":
    filt = filt[filt["sector"] == sel_sector]
if sel_curr != "Todas":
    filt = filt[filt["currency"] == sel_curr]

# Summary
total_val = filt["value_eur"].sum()
total_cost = filt["cost_eur"].sum()
total_pl = total_val - total_cost
total_pl_pct = (total_pl / total_cost * 100) if total_cost else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("Posições", f"{len(filt)}")
m2.metric("Valor", f"€ {total_val:,.2f}")
m3.metric("Custo", f"€ {total_cost:,.2f}")
m4.metric("P/L", f"€ {total_pl:,.2f}", f"{total_pl_pct:+.2f}%")

st.markdown("## Análise por Posição")
ticker = st.selectbox("Escolhe um ticker", filt["ticker"].tolist())

if ticker:
    row = filt[filt["ticker"] == ticker].iloc[0]

    # Show quote currency for native display (what trading platform shows)
    quote_ccy = row["quote_currency"]
    pm_ccy = row["currency"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Preço Atual",
        f"{row['current_price']:.2f} {quote_ccy}",
        f"{row['change_pct']:+.2f}% hoje",
    )
    c2.metric(
        "Preço Médio",
        f"{row['avg_price']:.2f} {pm_ccy}",
        help="Preço médio na moeda em que investiste"
    )
    c3.metric(
        "P/L da Posição",
        f"€ {row['pl_eur']:,.2f}",
        f"{row['pl_pct']:+.2f}%",
    )
    c4.metric("Peso na Carteira", f"{row['weight']:.2f}%")

    # Show currency info if different
    if quote_ccy != pm_ccy:
        st.info(
            f"ℹ️ **{ticker}** é cotado em **{quote_ccy}** na bolsa mas compraste em **{pm_ccy}**. "
            f"O preço actual convertido para {pm_ccy} é **{row['current_price_display']:.2f} {pm_ccy}**."
        )

    # Stop/TP (in quote currency, matching broker display)
    if row["stop"] is not None or row["take_profit"] is not None:
        sc1, sc2, sc3 = st.columns(3)
        if row["stop"] is not None:
            sc1.metric(
                f"Stop ({quote_ccy})",
                f"{row['stop']:.2f}",
                f"{row['dist_stop_pct']:+.1f}%" if row["dist_stop_pct"] is not None else "",
            )
        if row["take_profit"] is not None:
            sc2.metric(
                f"Take Profit ({quote_ccy})",
                f"{row['take_profit']:.2f}",
                f"{row['dist_tp_pct']:+.1f}%" if row["dist_tp_pct"] is not None else "",
            )
        if row["stop"] is not None and row["take_profit"] is not None:
            curr = row["current_price"]
            risk = abs(curr - row["stop"])
            reward = abs(row["take_profit"] - curr)
            rr = reward / risk if risk else None
            sc3.metric("Risk/Reward", f"{rr:.2f}" if rr else "—",
                       help="Rácio entre distância ao TP e distância ao stop")

    with st.spinner(f"A carregar histórico de {ticker}..."):
        hist = fetch_historical((ticker,), period="2y")

    if not hist.empty:
        prices = hist.iloc[:, 0].dropna()
        rets = daily_returns(prices)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=prices.index, y=prices.values, name=ticker,
            line=dict(color=COLORS["gain"], width=2),
            fill="tozeroy", fillcolor="rgba(0,212,170,0.06)",
        ))
        # PM line — convert to quote currency for the chart if needed
        pm_in_quote = (
            row["avg_price"] if pm_ccy == quote_ccy
            else row["avg_price"] / row["current_price_display"] * row["current_price"]
            if row["current_price_display"] else row["avg_price"]
        )
        fig.add_hline(y=pm_in_quote, line_dash="dash",
                      line_color=COLORS["text_muted"],
                      annotation_text=f"PM {pm_in_quote:.2f} {quote_ccy}",
                      annotation_position="right")
        if row["stop"] is not None:
            fig.add_hline(y=row["stop"], line_dash="dot",
                          line_color=COLORS["loss"],
                          annotation_text=f"Stop {row['stop']:.2f}",
                          annotation_position="right")
        if row["take_profit"] is not None:
            fig.add_hline(y=row["take_profit"], line_dash="dot",
                          line_color=COLORS["gain"],
                          annotation_text=f"TP {row['take_profit']:.2f}",
                          annotation_position="right")
        fig.update_layout(
            **PLOTLY_DARK_LAYOUT,
            title=f"{ticker} — {row['name']} · 2 anos ({quote_ccy})",
            height=420,
        )
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False})

        st.markdown("## Estatísticas (2A)")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Retorno Anualizado", f"{annualized_return(rets):.2%}")
        c2.metric("Volatilidade", f"{annualized_volatility(rets):.2%}")
        c3.metric("Sharpe", f"{sharpe_ratio(rets):.2f}")
        c4.metric("Máx. Drawdown", f"{max_drawdown(prices):.2%}")
    else:
        st.warning(f"Sem histórico disponível para {ticker}")
