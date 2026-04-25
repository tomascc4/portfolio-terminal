"""Watchlist — posições em monitorização com cálculo automático de sinal."""
import pandas as pd
import streamlit as st

from utils.data import (
    add_to_watchlist, enrich_watchlist, load_portfolio, remove_from_watchlist,
)
from utils.styling import COLORS, apply_custom_css

st.set_page_config(page_title="Watchlist", page_icon="👀", layout="wide")
apply_custom_css()

st.markdown("# Watchlist")
st.caption("Ativos em monitorização com entry/stop/TP — sinal calculado automaticamente.")

portfolio_data = load_portfolio()
df = enrich_watchlist(portfolio_data)

if df.empty:
    st.info("Watchlist vazia. Adiciona abaixo o primeiro ativo.")
else:
    # ---------- Summary counts ----------
    sig_counts = df["signal"].value_counts().to_dict()
    cols = st.columns(5)
    signals_order = ["Zona de compra", "Monitorizar", "Já correu",
                     "Abaixo entry", "Stop atingido"]
    for i, sig in enumerate(signals_order):
        count = sig_counts.get(sig, 0)
        with cols[i]:
            st.metric(sig, str(count))

    # ---------- Table ----------
    display = df[[
        "ticker", "name", "price", "change_pct", "entry_lo", "entry_hi",
        "stop", "tp1", "tp2", "dist_stop", "dist_tp1", "dist_tp2",
        "conviction", "signal",
    ]].rename(columns={
        "ticker": "Ticker", "name": "Nome", "price": "Preço",
        "change_pct": "Hoje %", "entry_lo": "Entry Lo", "entry_hi": "Entry Hi",
        "stop": "Stop", "tp1": "TP1", "tp2": "TP2",
        "dist_stop": "→ Stop %", "dist_tp1": "→ TP1 %", "dist_tp2": "→ TP2 %",
        "conviction": "Convicção", "signal": "Sinal",
    })

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        height=300,
        column_config={
            "Ticker": st.column_config.TextColumn(width="small"),
            "Preço": st.column_config.NumberColumn(format="%.2f"),
            "Hoje %": st.column_config.NumberColumn(format="%.2f%%"),
            "Entry Lo": st.column_config.NumberColumn(format="%.2f"),
            "Entry Hi": st.column_config.NumberColumn(format="%.2f"),
            "Stop": st.column_config.NumberColumn(format="%.2f"),
            "TP1": st.column_config.NumberColumn(format="%.2f"),
            "TP2": st.column_config.NumberColumn(format="%.2f"),
            "→ Stop %": st.column_config.NumberColumn(format="%.1f%%"),
            "→ TP1 %": st.column_config.NumberColumn(format="%.1f%%"),
            "→ TP2 %": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

    # ---------- Detailed cards ----------
    st.markdown("## Detalhe por Ativo")

    for _, row in df.iterrows():
        # Pick card color from signal
        sig = row["signal"]
        accent = {
            "Zona de compra": COLORS["gain"],
            "Monitorizar":    COLORS["warn"],
            "Já correu":      COLORS["warn"],
            "Abaixo entry":   COLORS["accent"],
            "Stop atingido":  COLORS["loss"],
        }.get(sig, COLORS["text_dim"])

        rr_1 = abs((row["tp1"] - row["price"]) / (row["price"] - row["stop"])) if row["price"] != row["stop"] else 0
        rr_2 = abs((row["tp2"] - row["price"]) / (row["price"] - row["stop"])) if row["price"] != row["stop"] else 0

        notes = row.get("notes", "") or ""

        st.markdown(
            f"""
            <div style="
                background: var(--bg-card);
                border: 1px solid var(--border);
                border-left: 3px solid {accent};
                border-radius: 10px;
                padding: 14px 18px;
                margin-bottom: 10px;
            ">
              <div style="display:flex; justify-content:space-between; align-items:baseline;">
                <div>
                  <span style="font-family: var(--font-mono); font-size:1.1rem; font-weight:600;">
                    {row['ticker']}
                  </span>
                  <span class="dim-text" style="font-size:0.85rem; margin-left:8px;">{row['name']}</span>
                </div>
                <div>
                  <span class="badge" style="background: rgba(0,212,170,0.15); color: {accent};">{sig}</span>
                  <span class="dim-text" style="font-size:0.75rem; margin-left:10px;">
                    Convicção: <b style="color: var(--text);">{row['conviction'] or '—'}</b>
                  </span>
                </div>
              </div>
              <div style="
                font-family: var(--font-mono);
                font-size: 0.85rem;
                margin-top:10px;
                display:grid;
                grid-template-columns: repeat(6, 1fr);
                gap:8px;
              ">
                <div><span class="dim-text" style="font-size:0.7rem;">PREÇO</span><br>
                  <b>{row['price']:.2f}</b> {row['currency']}
                </div>
                <div><span class="dim-text" style="font-size:0.7rem;">ENTRY</span><br>
                  {row['entry_lo']:.2f} – {row['entry_hi']:.2f}
                </div>
                <div><span class="dim-text" style="font-size:0.7rem;">STOP</span><br>
                  <span class="loss-text">{row['stop']:.2f}</span>
                  <span class="dim-text" style="font-size:0.7rem;"> ({row['dist_stop']:+.1f}%)</span>
                </div>
                <div><span class="dim-text" style="font-size:0.7rem;">TP1</span><br>
                  <span class="gain-text">{row['tp1']:.2f}</span>
                  <span class="dim-text" style="font-size:0.7rem;"> ({row['dist_tp1']:+.1f}%)</span>
                </div>
                <div><span class="dim-text" style="font-size:0.7rem;">TP2</span><br>
                  <span class="gain-text">{row['tp2']:.2f}</span>
                  <span class="dim-text" style="font-size:0.7rem;"> ({row['dist_tp2']:+.1f}%)</span>
                </div>
                <div><span class="dim-text" style="font-size:0.7rem;">R/R</span><br>
                  <b>{rr_1:.2f}</b> / {rr_2:.2f}
                </div>
              </div>
              {f'<div class="dim-text" style="font-size:0.78rem; margin-top:10px; font-style:italic;">{notes}</div>' if notes else ''}
            </div>
            """,
            unsafe_allow_html=True,
        )

# ============================================================
# Add / Remove
# ============================================================
st.markdown("## Gerir Watchlist")

tab_add, tab_remove = st.tabs(["➕ Adicionar", "➖ Remover"])

with tab_add:
    c1, c2, c3 = st.columns(3)
    with c1:
        ticker = st.text_input("Ticker", placeholder="ex: AMD, CRM")
        name = st.text_input("Nome completo", placeholder="ex: Advanced Micro Devices")
        currency = st.selectbox("Moeda", ["USD", "EUR", "GBP"])
    with c2:
        entry_lo = st.number_input("Entry Lo", min_value=0.0, step=0.01)
        entry_hi = st.number_input("Entry Hi", min_value=0.0, step=0.01)
        stop = st.number_input("Stop", min_value=0.0, step=0.01)
    with c3:
        tp1 = st.number_input("TP1", min_value=0.0, step=0.01)
        tp2 = st.number_input("TP2", min_value=0.0, step=0.01)
        conviction = st.selectbox("Convicção", ["Alta", "Média", "Baixa"])
    notes = st.text_area("Notas (opcional)", height=70)

    if st.button("Adicionar à Watchlist", type="primary"):
        if not ticker:
            st.error("Tens de indicar um ticker.")
        elif entry_hi <= entry_lo:
            st.error("Entry Hi tem de ser maior que Entry Lo.")
        elif tp1 <= entry_hi or tp2 <= tp1:
            st.error("TPs têm de ser progressivos: Entry Hi < TP1 < TP2.")
        elif stop >= entry_lo:
            st.error("Stop tem de estar abaixo do Entry Lo.")
        else:
            msg = add_to_watchlist({
                "ticker": ticker.upper(),
                "name": name,
                "currency": currency,
                "entry_lo": entry_lo,
                "entry_hi": entry_hi,
                "stop": stop,
                "tp1": tp1,
                "tp2": tp2,
                "conviction": conviction,
                "notes": notes,
            })
            st.success(msg)
            st.rerun()

with tab_remove:
    if not df.empty:
        remove_ticker = st.selectbox("Escolhe ticker a remover", df["ticker"].tolist())
        if st.button("Remover", type="primary"):
            msg = remove_from_watchlist(remove_ticker)
            st.success(msg)
            st.rerun()
    else:
        st.info("Watchlist vazia.")
