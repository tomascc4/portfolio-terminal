"""Config — editor visual do portfolio.json com quote_currency."""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.data import save_portfolio
from utils.styling import apply_custom_css

st.set_page_config(page_title="Config", page_icon="⚙️", layout="wide")
apply_custom_css()

st.markdown("# Config")
st.caption("Editor visual do portfolio.json.")

PORTFOLIO_PATH = Path(__file__).parent.parent / "data" / "portfolio.json"
with open(PORTFOLIO_PATH, encoding="utf-8") as f:
    data = json.load(f)

# ---------- Perfil ----------
st.markdown("## Perfil")
profile = data["profile"]
c1, c2, c3 = st.columns(3)
with c1:
    profile["idade"] = st.number_input("Idade", value=profile["idade"])
    profile["horizonte"] = st.text_input("Horizonte", value=profile["horizonte"])
with c2:
    profile["risco"] = st.text_input("Risco", value=profile["risco"])
    profile["broker"] = st.text_input("Broker", value=profile["broker"])
with c3:
    profile["contribuicao_mensal"] = st.number_input(
        "Contribuição mensal (€)", value=float(profile["contribuicao_mensal"])
    )
    profile["frequencia_dca"] = st.text_input("Freq. DCA", value=profile["frequencia_dca"])

# ---------- Positions ----------
st.markdown("## Posições")
st.caption(
    "• **Moeda:** em que moeda pagaste (normalmente EUR via Revolut) — "
    "esta é a moeda do teu PM.\n"
    "• **Quote Curr.:** em que moeda o yfinance devolve o preço "
    "(para UCITS ETFs LSE é tipicamente USD mesmo que pagues em EUR). "
    "Deixa vazio para assumir igual à Moeda."
)

pos_df = pd.DataFrame(data["positions"])
for col in ("stop", "take_profit", "quote_currency"):
    if col not in pos_df.columns:
        pos_df[col] = None

# Reorder columns for clarity
column_order = ["ticker", "name", "qty", "avg_price", "class", "sector",
                "currency", "quote_currency", "stop", "take_profit"]
pos_df = pos_df[column_order]

edited_pos = st.data_editor(
    pos_df, num_rows="dynamic", use_container_width=True,
    column_config={
        "ticker": st.column_config.TextColumn("Ticker", required=True),
        "name": st.column_config.TextColumn("Nome"),
        "qty": st.column_config.NumberColumn("Qtd", format="%.4f"),
        "avg_price": st.column_config.NumberColumn("PM", format="%.2f",
                      help="Na moeda indicada em 'Moeda'"),
        "class": st.column_config.SelectboxColumn("Cls",
                  options=["ETF", "Core", "Tática"]),
        "sector": st.column_config.TextColumn("Sector"),
        "currency": st.column_config.SelectboxColumn(
            "Moeda", options=["EUR", "USD", "GBP"],
            help="Moeda do PM (o que pagaste)"
        ),
        "quote_currency": st.column_config.SelectboxColumn(
            "Quote Curr.", options=[None, "USD", "EUR", "GBP"],
            help="Moeda que o Yahoo Finance devolve. Deixa vazio para igual à Moeda.",
        ),
        "stop": st.column_config.NumberColumn("Stop", format="%.2f",
                 help="Na moeda de cotação (Quote Curr.)"),
        "take_profit": st.column_config.NumberColumn("TP", format="%.2f",
                        help="Na moeda de cotação (Quote Curr.)"),
    },
    key="pos_editor",
)

# ---------- Watchlist ----------
st.markdown("## Watchlist")

wl_df = pd.DataFrame(data.get("watchlist", []))
edited_wl = st.data_editor(
    wl_df, num_rows="dynamic", use_container_width=True,
    column_config={
        "ticker": st.column_config.TextColumn("Ticker", required=True),
        "name": st.column_config.TextColumn("Nome"),
        "currency": st.column_config.SelectboxColumn("Cur", options=["USD", "EUR", "GBP"]),
        "entry_lo": st.column_config.NumberColumn("Entry Lo", format="%.2f"),
        "entry_hi": st.column_config.NumberColumn("Entry Hi", format="%.2f"),
        "stop": st.column_config.NumberColumn("Stop", format="%.2f"),
        "tp1": st.column_config.NumberColumn("TP1", format="%.2f"),
        "tp2": st.column_config.NumberColumn("TP2", format="%.2f"),
        "conviction": st.column_config.SelectboxColumn("Convicção",
                        options=["Alta", "Média", "Baixa"]),
        "notes": st.column_config.TextColumn("Notas"),
    },
    key="wl_editor",
)

# Save
col1, col2 = st.columns([1, 5])
with col1:
    if st.button("💾 Guardar", type="primary"):
        data["profile"] = profile
        # Remove None quote_currency to keep JSON clean
        positions_clean = edited_pos.to_dict(orient="records")
        for p in positions_clean:
            if p.get("quote_currency") in (None, "", pd.NA):
                p.pop("quote_currency", None)
        data["positions"] = positions_clean
        data["watchlist"] = edited_wl.to_dict(orient="records")
        save_portfolio(data)
        st.success("Guardado! Cache limpa.")

with col2:
    st.download_button(
        "📥 Download portfolio.json",
        data=json.dumps(data, indent=2, ensure_ascii=False),
        file_name="portfolio.json", mime="application/json",
    )

st.markdown("---")
st.markdown("### Guia Rápido de Moedas")
st.markdown("""
**Caso comum — stocks EUA:** Moeda=`USD`, Quote Curr.=vazio (= USD). Exemplo: MSFT, NVDA.

**Caso especial — ETFs UCITS no LSE:** Moeda=`EUR` (pagaste em EUR), Quote Curr.=`USD` (yfinance dá USD). Exemplos:
- `EXUS.L` — iShares MSCI ACWI ex-US
- `VUAA.L` — Vanguard S&P 500 UCITS Acc
- `CSPX.L` — iShares Core S&P 500 UCITS

**Alternativa:** usar tickers EUR-nativos (`.DE` Xetra, `.AS` Amesterdão) para evitar o FX:
- `SXR8.DE` — iShares Core S&P 500 UCITS (EUR)
- `IWDA.AS` — iShares Core MSCI World (EUR)

Neste caso, Moeda=`EUR`, Quote Curr.=vazio.
""")
