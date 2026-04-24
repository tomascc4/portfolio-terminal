"""Nova Transação — com auto-detecção da moeda de cotação."""
from datetime import date

import pandas as pd
import streamlit as st

from utils.data import add_transaction, detect_quote_currency, load_portfolio
from utils.styling import apply_custom_css

st.set_page_config(page_title="Nova Transação", page_icon="➕", layout="wide")
apply_custom_css()

st.markdown("# Nova Transação")
st.caption(
    "Registar compras e vendas. O PM é recalculado automaticamente como média ponderada. "
    "A moeda de cotação do ticker é auto-detectada via Yahoo Finance."
)

portfolio_data = load_portfolio()
existing_tickers = [p["ticker"] for p in portfolio_data["positions"]]

st.markdown("## Registar Operação")

col_left, col_right = st.columns([1, 1])

with col_left:
    action = st.radio("Acção", ["COMPRA", "VENDA"], horizontal=True)
    action_code = "BUY" if action == "COMPRA" else "SELL"

    mode_options = ["Selecionar existente"]
    if action_code == "BUY":
        mode_options.append("Novo ticker")
    mode = st.radio("Ticker", mode_options, horizontal=True)

    if mode == "Selecionar existente" and existing_tickers:
        ticker = st.selectbox("Escolhe posição", existing_tickers)
        existing = next(p for p in portfolio_data["positions"] if p["ticker"] == ticker)
        name = existing["name"]
        currency = existing["currency"]
        sector = existing["sector"]
        classification = existing["class"]
        is_new = False
        st.markdown(
            f"""
            <div style='padding:10px 14px; background: var(--bg-card);
                 border:1px solid var(--border); border-radius:8px;
                 font-family: var(--font-mono); font-size:0.82rem;'>
            <b>{ticker}</b> · {name}<br>
            Quantidade atual: <b>{existing['qty']:.4f}</b><br>
            PM atual: <b>{existing['avg_price']:.2f} {currency}</b>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        ticker = st.text_input("Novo ticker", placeholder="ex: AMD, CSPX.L, SXR8.DE").upper()
        name = st.text_input("Nome completo", placeholder="ex: Advanced Micro Devices")
        currency = st.selectbox(
            "Moeda do teu PM", ["USD", "EUR", "GBP"],
            help="Em que moeda pagaste (o Revolut mostra em EUR tipicamente)"
        )
        sector = st.text_input("Sector", placeholder="ex: Semis")
        classification = st.selectbox("Classificação", ["Core", "Tática", "ETF"])

        # Auto-detect quote currency
        detected_quote = None
        if ticker:
            with st.spinner(f"A detectar moeda de cotação de {ticker}..."):
                detected_quote = detect_quote_currency(ticker)
            if detected_quote != currency:
                st.info(
                    f"ℹ️ O Yahoo Finance cota **{ticker}** em **{detected_quote}**. "
                    f"Se pagaste em {currency}, será feita conversão automática."
                )
        is_new = True

with col_right:
    tx_date = st.date_input("Data", value=date.today())
    qty = st.number_input("Quantidade", min_value=0.0, step=0.0001, format="%.4f")
    price = st.number_input(
        f"Preço ({currency})",
        min_value=0.0, step=0.01,
        help=f"Preço que pagaste por unidade, em {currency}",
    )

    st.markdown("### Parâmetros de Risco (opcional)")
    st.caption(f"Stop e TP são fixados na moeda de cotação (o que vês na plataforma)")
    set_stop = st.checkbox("Definir stop-loss", value=False)
    stop = st.number_input("Stop", min_value=0.0, step=0.01) if set_stop else None
    set_tp = st.checkbox("Definir take-profit", value=False)
    take_profit = st.number_input("Take profit", min_value=0.0, step=0.01) if set_tp else None

# Preview
if ticker and qty > 0 and price > 0:
    st.markdown("### Pré-visualização")
    total_value = qty * price
    st.markdown(
        f"""
        <div style='padding:14px 18px; background: var(--bg-card);
             border:1px solid var(--border); border-left:3px solid var(--gain);
             border-radius:8px; font-family: var(--font-mono); font-size:0.88rem;'>
        {action}: <b>{qty:.4f}</b> × <b>{ticker}</b> @ <b>{price:.2f} {currency}</b><br>
        Valor total: <b>{total_value:,.2f} {currency}</b><br>
        Data: <b>{tx_date.strftime('%d/%m/%Y')}</b>
        </div>
        """,
        unsafe_allow_html=True,
    )

if st.button("Registar Transação", type="primary"):
    if not ticker or qty <= 0 or price <= 0:
        st.error("Preenche ticker, quantidade e preço.")
    else:
        msg = add_transaction(
            ticker=ticker, action=action_code, qty=qty, price=price,
            currency=currency, date=tx_date.isoformat(),
            name=name, sector=sector, classification=classification,
            stop=stop, take_profit=take_profit,
        )
        if msg.startswith("✅"):
            st.success(msg)
            st.balloons()
        else:
            st.error(msg)

# History
st.markdown("## Histórico de Transações")

tx_log = portfolio_data.get("transactions", [])
if not tx_log:
    st.info("Sem transações registadas ainda. Todas as futuras ficam aqui.")
else:
    tx_df = pd.DataFrame(tx_log).sort_values("date", ascending=False)
    tx_df["total"] = tx_df["qty"] * tx_df["price"]
    tx_df = tx_df.rename(columns={
        "date": "Data", "ticker": "Ticker", "action": "Ação",
        "qty": "Qtd", "price": "Preço", "currency": "Moeda",
        "total": "Total",
    })
    st.dataframe(
        tx_df, use_container_width=True, hide_index=True,
        column_config={
            "Qtd": st.column_config.NumberColumn(format="%.4f"),
            "Preço": st.column_config.NumberColumn(format="%.2f"),
            "Total": st.column_config.NumberColumn(format="%.2f"),
        },
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Total de Operações", len(tx_df))
    buys = tx_df[tx_df["Ação"] == "BUY"]
    c2.metric("Compras", len(buys))
    sells = tx_df[tx_df["Ação"] == "SELL"]
    c3.metric("Vendas", len(sells))
