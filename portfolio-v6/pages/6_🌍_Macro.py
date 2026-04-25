"""Macro — indicadores de mercado e contexto."""
import plotly.graph_objects as go
import streamlit as st

from utils.data import fetch_historical, fetch_macro_indicators
from utils.styling import COLORS, PLOTLY_DARK_LAYOUT, apply_custom_css

st.set_page_config(page_title="Macro", page_icon="🌍", layout="wide")
apply_custom_css()

st.markdown("# Macro")
st.caption("Indicadores de mercado, câmbios, commodities e índices globais.")

with st.spinner("A carregar indicadores..."):
    macro = fetch_macro_indicators()

if not macro:
    st.warning("Não foi possível obter indicadores macro.")
    st.stop()

# ---------- Grid ----------
st.markdown("## Indicadores Atuais")
cols = st.columns(4)
for i, (label, data) in enumerate(macro.items()):
    with cols[i % 4]:
        st.metric(label, f"{data['price']:,.2f}", f"{data['change_pct']:+.2f}%")

# ---------- Charts ----------
st.markdown("## Evolução (1A)")

tickers = {
    "S&P 500": "^GSPC",
    "NASDAQ 100": "^NDX",
    "STOXX 600": "^STOXX",
    "VIX": "^VIX",
    "EUR/USD": "EURUSD=X",
    "Ouro": "GC=F",
}

choice = st.multiselect(
    "Escolhe indicadores",
    list(tickers.keys()),
    default=["S&P 500", "NASDAQ 100", "STOXX 600"],
)

if choice:
    with st.spinner("A carregar histórico..."):
        hist = fetch_historical(tuple(tickers[c] for c in choice), period="1y")
    if not hist.empty:
        normalized = hist / hist.iloc[0] * 100
        fig = go.Figure()
        palette = [COLORS["gain"], COLORS["accent"], COLORS["warn"],
                   "#ff7eb6", COLORS["purple"], COLORS["loss"]]
        for i, col in enumerate(normalized.columns):
            label = [k for k, v in tickers.items() if v == col][0]
            fig.add_trace(go.Scatter(
                x=normalized.index, y=normalized[col], name=label,
                line=dict(color=palette[i % len(palette)], width=2),
            ))
        fig.update_layout(
            **PLOTLY_DARK_LAYOUT, height=450, yaxis_title="Base 100",
            legend=dict(orientation="h", y=1.08, x=0),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.warning("Sem dados históricos.")

# ---------- Interpretação ----------
st.markdown("## Leitura Rápida")
vix_data = macro.get("VIX")
if vix_data:
    vix = vix_data["price"]
    if vix < 15:
        label, colour = "Complacência", COLORS["warn"]
    elif vix < 20:
        label, colour = "Normal", COLORS["gain"]
    elif vix < 30:
        label, colour = "Elevado", COLORS["warn"]
    else:
        label, colour = "Pânico", COLORS["loss"]
    st.markdown(
        f"""
        <div style='background: var(--bg-card); border: 1px solid var(--border);
             border-left: 3px solid {colour}; border-radius:8px;
             padding: 12px 16px; font-size: 0.88rem;'>
        <b>VIX: {vix:.2f}</b> — <span style='color:{colour}; font-weight:600;'>{label}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
