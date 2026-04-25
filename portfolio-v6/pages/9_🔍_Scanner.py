"""Scanner — aplica filtros ao universo e devolve candidatos qualificados."""
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.scanner import (
    FilterConfig,
    close_to_passing,
    filter_passed,
    load_universe,
    results_to_dataframe,
    run_scan,
)
from utils.styling import COLORS, PLOTLY_DARK_LAYOUT, apply_custom_css

st.set_page_config(page_title="Scanner", page_icon="🔍", layout="wide")
apply_custom_css()

st.markdown("# Scanner")
st.caption(
    "Filtros aplicados ao universo de S&P 500 + NASDAQ. "
    "Primeira scan demora 3-5 min (depois é instantâneo graças à cache de 6h)."
)

universe = load_universe()

# ============================================================
# Filter controls
# ============================================================
st.markdown("## Filtros")

tab_val, tab_growth, tab_profit, tab_other = st.tabs(
    ["Valuation", "Crescimento", "Margens & Qualidade", "Risco & Size"]
)

cfg = FilterConfig()

with tab_val:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        cfg.max_trailing_pe = st.number_input("P/E trailing máx.", value=50.0, step=5.0,
                                               help="P/E (preço/earnings) histórico. Vazio = sem filtro.")
    with c2:
        cfg.max_forward_pe = st.number_input("P/E forward máx.", value=35.0, step=5.0)
    with c3:
        cfg.max_peg = st.number_input(
            "PEG máx.", value=1.5, step=0.1,
            help="P/E dividido por crescimento. <1 barato vs crescimento, >2 caro."
        )
    with c4:
        cfg.max_price_to_sales = st.number_input("P/S máx.", value=15.0, step=1.0)

with tab_growth:
    c1, c2 = st.columns(2)
    with c1:
        cfg.min_revenue_growth = st.slider(
            "Revenue Growth mín. (YoY)", 0.0, 0.50, 0.12, step=0.01,
            help="Crescimento de receitas anualizado. 12% é o teu default.",
            format="%.0f%%",
        )
    with c2:
        cfg.min_earnings_growth = st.slider(
            "Earnings Growth mín. (YoY)", 0.0, 0.50, 0.10, step=0.01,
            format="%.0f%%",
        )

with tab_profit:
    c1, c2 = st.columns(2)
    with c1:
        cfg.min_gross_margin = st.slider(
            "Gross Margin mín.", 0.0, 0.80, 0.30, step=0.05, format="%.0f%%",
        )
    with c2:
        cfg.min_operating_margin = st.slider(
            "Operating Margin mín.", -0.10, 0.40, 0.05, step=0.01, format="%.0f%%",
        )

with tab_other:
    c1, c2, c3 = st.columns(3)
    with c1:
        mcap_min_b = st.slider("Market Cap mín. ($B)", 0.5, 100.0, 2.0, step=0.5)
        cfg.min_market_cap = mcap_min_b * 1e9
    with c2:
        cfg.min_analyst_upside = st.slider(
            "Analyst Upside mín.", -0.10, 0.60, 0.15, step=0.05,
            help="Upside ao price target médio.", format="%.0f%%",
        )
    with c3:
        cfg.max_debt_to_equity = st.number_input(
            "Debt/Equity máx.", value=200.0, step=25.0,
        )

    c1, c2, c3 = st.columns(3)
    with c1:
        cfg.min_num_analysts = st.number_input("Nº analistas mín.", value=5, step=1)
    with c2:
        cfg.max_recommendation_mean = st.slider(
            "Rec. Score máx.", 1.0, 3.5, 2.5, step=0.1,
            help="1=Strong Buy, 3=Hold. Menor = melhor.",
        )
    with c3:
        cfg.max_beta = st.slider("Beta máx.", 0.5, 3.0, 2.0, step=0.1)

# ============================================================
# Run scan
# ============================================================
scan_c1, scan_c2, scan_c3 = st.columns([1, 1, 3])
with scan_c1:
    scan_limit_options = ["Top 100", "Top 250", "Universo completo (~500)"]
    scan_limit_label = st.selectbox("Abrangência", scan_limit_options, index=0)
    limit_map = {"Top 100": 100, "Top 250": 250, "Universo completo (~500)": None}
    limit = limit_map[scan_limit_label]

with scan_c2:
    run_button = st.button("🚀 Correr Scanner", type="primary", use_container_width=True)

with scan_c3:
    st.caption(
        f"<div style='padding-top: 24px; color: var(--text-dim); font-size: 0.8rem;'>"
        f"Universo total: {len(universe)} tickers. Cache de 6h por ticker — primeira scan "
        f"completa demora mais, depois é muito rápida.</div>",
        unsafe_allow_html=True,
    )

if run_button:
    progress_bar = st.progress(0.0, text="A preparar...")
    status_text = st.empty()
    start_time = time.time()

    def on_progress(i, total, ticker):
        progress_bar.progress(i / total, text=f"A analisar {ticker} ({i}/{total})")

    with st.spinner("A correr scanner..."):
        results = run_scan(universe, cfg, progress_callback=on_progress, limit=limit)

    progress_bar.empty()
    elapsed = time.time() - start_time
    st.session_state["scan_results"] = results
    st.session_state["scan_time"] = elapsed
    st.success(f"✓ Scan completo — {len(results)} tickers analisados em {elapsed:.1f}s")

# ============================================================
# Display results
# ============================================================
results = st.session_state.get("scan_results", [])

if results:
    passed = filter_passed(results)
    near_miss = close_to_passing(results, max_failures=2)

    st.markdown("## Resultados")

    # Summary metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Analisados", f"{len(results)}")
    c2.metric("✅ Passaram", f"{len(passed)}",
              f"{len(passed)/len(results)*100:.1f}% do universo")
    c3.metric("🟡 Perto (≤2 falhas)", f"{len(near_miss)}")
    avg_score = sum(r.score for r in passed) / len(passed) if passed else 0
    c4.metric("Score Médio (passaram)", f"{avg_score:.1f}")

    # Sector breakdown of passers
    if passed:
        st.markdown("### Distribuição Sectorial dos Qualificados")
        sectors = pd.Series([r.info.get("sector", "?") for r in passed]).value_counts()
        fig = go.Figure(go.Bar(
            x=sectors.values, y=sectors.index, orientation="h",
            marker_color=COLORS["gain"],
            text=sectors.values, textposition="outside",
            textfont=dict(family="JetBrains Mono", size=10),
        ))
        fig.update_layout(
            **PLOTLY_DARK_LAYOUT,
            height=max(200, 30 * len(sectors)),
            xaxis_title="Nº de empresas qualificadas",
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Tabs: passaram / perto / todos
    tab1, tab2, tab3 = st.tabs([
        f"✅ Passaram ({len(passed)})",
        f"🟡 Perto ({len(near_miss)})",
        f"📊 Todos ({len(results)})",
    ])

    def render_table(rs, show_failures=False):
        df = results_to_dataframe(rs)
        if df.empty:
            st.info("Sem resultados nesta categoria.")
            return
        cols_config = {
            "Ticker": st.column_config.TextColumn(width="small"),
            "Nome": st.column_config.TextColumn(width="medium"),
            "Preço": st.column_config.NumberColumn(format="%.2f"),
            "Market Cap": st.column_config.NumberColumn(
                format="%.0f", help="Em USD"),
            "P/E fwd": st.column_config.NumberColumn(format="%.1f"),
            "PEG": st.column_config.NumberColumn(format="%.2f"),
            "P/S": st.column_config.NumberColumn(format="%.1f"),
            "Rev Growth": st.column_config.NumberColumn(format="%.1f%%"),
            "EPS Growth": st.column_config.NumberColumn(format="%.1f%%"),
            "Op Margin": st.column_config.NumberColumn(format="%.1f%%"),
            "ROE": st.column_config.NumberColumn(format="%.1f%%"),
            "Upside %": st.column_config.NumberColumn(format="%.1f%%"),
            "Rec Score": st.column_config.NumberColumn(format="%.2f"),
            "Beta": st.column_config.NumberColumn(format="%.2f"),
            "Score": st.column_config.ProgressColumn(
                format="%.1f", min_value=0, max_value=100,
            ),
        }
        if not show_failures:
            df = df.drop(columns=["Falhas", "Razões"])
        else:
            cols_config["Falhas"] = st.column_config.NumberColumn(width="small")
            cols_config["Razões"] = st.column_config.TextColumn(width="large")

        # Make market cap human-readable
        if "Market Cap" in df.columns:
            df["Market Cap"] = df["Market Cap"].apply(
                lambda x: f"${x/1e9:.1f}B" if pd.notna(x) else "—"
            )
            cols_config["Market Cap"] = st.column_config.TextColumn(width="small")

        st.dataframe(
            df, use_container_width=True, hide_index=True,
            column_config=cols_config, height=500,
        )

    with tab1:
        st.caption("Empresas que passaram todos os filtros, ordenadas por score composto.")
        render_table(passed)
        if passed:
            csv = results_to_dataframe(passed).to_csv(index=False)
            st.download_button(
                "📥 Download CSV dos qualificados", csv,
                file_name="scanner_qualificados.csv", mime="text/csv",
            )

    with tab2:
        st.caption(
            "Empresas que quase passaram (≤2 filtros falharam). "
            "Úteis para afinar a tese ou considerar excepções manuais."
        )
        render_table(near_miss, show_failures=True)

    with tab3:
        st.caption("Todas as empresas analisadas, com detalhe de falhas.")
        render_table(results, show_failures=True)

else:
    st.info(
        "👆 Configura os filtros acima e clica em **Correr Scanner**. "
        "A primeira vez demora — depois fica em cache 6h e as scans seguintes são instantâneas."
    )
