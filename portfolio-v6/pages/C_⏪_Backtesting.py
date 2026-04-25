"""Backtesting — simula estratégias retroactivamente."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.backtest import (
    CRISIS_PERIODS,
    backtest_buy_the_dip,
    backtest_dca,
    backtest_lump_sum,
    rolling_returns,
    stress_test,
)
from utils.data import enrich_portfolio, fetch_historical, load_portfolio
from utils.styling import COLORS, PLOTLY_DARK_LAYOUT, apply_custom_css

st.set_page_config(page_title="Backtesting", page_icon="⏪", layout="wide")
apply_custom_css()

st.markdown("# Backtesting")
st.caption(
    "Simula como teria sido a tua carteira no passado. "
    "Compara estratégias, testa cenários e vê rolling returns."
)

portfolio_data = load_portfolio()
df = enrich_portfolio(portfolio_data).dropna(subset=["current_price"])

if df.empty:
    st.info("Sem posições.")
    st.stop()

# ============================================================
# Tabs
# ============================================================
tab_dca, tab_compare, tab_rolling, tab_stress = st.tabs([
    "💰 Backtest DCA",
    "🔀 Comparar Estratégias",
    "📊 Rolling Returns",
    "⛈️ Stress Tests",
])

# Common configuration
@st.cache_data(ttl=3600)
def get_historical_for_portfolio(tickers: tuple, period: str) -> pd.DataFrame:
    return fetch_historical(tickers, period=period)


# ============================================================
# TAB 1 — Backtest DCA
# ============================================================
with tab_dca:
    st.markdown("### Simulador de DCA")
    st.caption(
        "E se tivesses começado com a tua alocação actual há X anos, com a "
        "contribuição mensal Y, qual seria o valor hoje?"
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        period = st.selectbox("Período histórico", ["1y", "2y", "5y", "10y", "max"], index=2)
    with c2:
        monthly = st.number_input(
            "Contribuição mensal (€)", min_value=0.0,
            value=float(portfolio_data["profile"]["contribuicao_mensal"]),
            step=50.0,
        )
    with c3:
        freq_days = st.selectbox(
            "Frequência",
            options=[7, 14, 21, 30],
            format_func=lambda x: {7: "Semanal", 14: "Quinzenal",
                                    21: "3 semanas (DCA actual)",
                                    30: "Mensal"}[x],
            index=2,
        )

    # Allocation: use current weights or custom
    use_current = st.checkbox(
        "Usar alocação actual da carteira", value=True,
        help="Se desligado, podes definir pesos manualmente.",
    )

    weights = {}
    if use_current:
        for _, r in df.iterrows():
            weights[r["ticker"]] = r["weight"] / 100
    else:
        st.markdown("#### Pesos personalizados (devem somar ~100%)")
        wcols = st.columns(4)
        for i, (_, r) in enumerate(df.iterrows()):
            with wcols[i % 4]:
                w = st.slider(
                    r["ticker"], min_value=0.0, max_value=50.0,
                    value=float(r["weight"]), step=1.0, format="%.0f%%",
                    key=f"w_{r['ticker']}",
                )
                if w > 0:
                    weights[r["ticker"]] = w / 100

    if st.button("⏪ Correr Backtest", type="primary"):
        if not weights:
            st.error("Define pelo menos uma posição com peso > 0.")
        else:
            with st.spinner("A carregar histórico e simular..."):
                tickers = tuple(weights.keys())
                hist = get_historical_for_portfolio(tickers, period)

                if hist.empty:
                    st.error("Sem dados históricos.")
                else:
                    # Filter to available
                    available = [t for t in weights if t in hist.columns]
                    if len(available) < len(weights):
                        missing = set(weights) - set(available)
                        st.warning(f"Sem histórico para: {', '.join(missing)}. "
                                    f"Estes serão excluídos da simulação.")
                    weights_avail = {t: weights[t] for t in available}

                    # Drop initial NaN
                    hist = hist[available].dropna(how="any")

                    result = backtest_dca(hist, weights_avail, monthly,
                                           frequency_days=freq_days)

                    # KPIs
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Investido", f"€ {result.total_invested:,.0f}")
                    c2.metric("Valor Final", f"€ {result.final_value:,.0f}",
                              f"€ {result.profit:+,.0f}")
                    c3.metric("IRR Anualizado", f"{result.irr_annual*100:.2f}%")
                    c4.metric("Max Drawdown", f"{result.max_drawdown*100:.2f}%")

                    c1, c2, c3 = st.columns(3)
                    c1.metric("Sharpe Ratio", f"{result.sharpe_ratio:.2f}")
                    c2.metric("Nº de Compras", result.n_purchases)
                    c3.metric("Multiplicador",
                              f"{result.final_value/result.total_invested:.2f}x"
                              if result.total_invested > 0 else "—")

                    # Chart
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=result.dates, y=result.portfolio_value,
                        name="Valor da Carteira",
                        line=dict(color=COLORS["gain"], width=2.5),
                        fill="tozeroy", fillcolor="rgba(0,212,170,0.08)",
                    ))
                    fig.add_trace(go.Scatter(
                        x=result.dates, y=result.invested_cumulative,
                        name="Investido (sem retorno)",
                        line=dict(color=COLORS["text_muted"], width=2, dash="dash"),
                    ))
                    fig.update_layout(
                        **PLOTLY_DARK_LAYOUT, height=420,
                        legend=dict(orientation="h", y=1.08, x=0),
                        yaxis_title="Valor (€)",
                    )
                    st.plotly_chart(fig, use_container_width=True,
                                    config={"displayModeBar": False})

# ============================================================
# TAB 2 — Comparar Estratégias
# ============================================================
with tab_compare:
    st.markdown("### DCA vs Lump Sum vs Buy-the-Dip")
    st.caption(
        "Mesma cápita total disponível, três estratégias diferentes. "
        "Vês qual teria ganho no período histórico escolhido."
    )

    c1, c2 = st.columns(2)
    with c1:
        cmp_period = st.selectbox(
            "Período", ["1y", "2y", "5y", "10y", "max"],
            index=2, key="cmp_period",
        )
    with c2:
        cmp_monthly = st.number_input(
            "Contribuição mensal (€)", min_value=50.0,
            value=400.0, step=50.0, key="cmp_monthly",
        )

    dip_threshold = st.slider(
        "Threshold Buy-the-Dip", -0.30, -0.05, -0.10, step=0.01,
        format="%.0f%%",
        help="Comprar quando a basket cai mais que isto desde o pico.",
    )

    if st.button("🔀 Comparar", type="primary", key="run_compare"):
        # Use current allocation
        weights = {r["ticker"]: r["weight"] / 100 for _, r in df.iterrows()}
        tickers = tuple(weights.keys())

        with st.spinner("A correr 3 simulações..."):
            hist = get_historical_for_portfolio(tickers, cmp_period)
            if hist.empty:
                st.error("Sem dados.")
            else:
                available = [t for t in weights if t in hist.columns]
                weights_avail = {t: weights[t] for t in available}
                hist = hist[available].dropna(how="any")

                # Run all 3
                r_dca = backtest_dca(hist, weights_avail, cmp_monthly)
                lump_capital = r_dca.total_invested  # match total invested
                r_lump = backtest_lump_sum(hist, weights_avail, lump_capital)
                r_btd = backtest_buy_the_dip(hist, weights_avail, cmp_monthly,
                                              drawdown_threshold=dip_threshold)

                # Comparison table
                results = [r_dca, r_lump, r_btd]
                comparison = pd.DataFrame([
                    {
                        "Estratégia": r.strategy_name,
                        "Investido": r.total_invested,
                        "Valor Final": r.final_value,
                        "Lucro": r.profit,
                        "IRR": r.irr_annual,
                        "Multiplicador": r.final_value / r.total_invested if r.total_invested else 0,
                        "Max Drawdown": r.max_drawdown,
                        "Sharpe": r.sharpe_ratio,
                        "Compras": r.n_purchases,
                    } for r in results
                ])

                # Highlight winner
                winner_idx = comparison["IRR"].idxmax()
                winner_name = comparison.loc[winner_idx, "Estratégia"]

                st.success(f"🏆 **{winner_name}** ganhou neste período "
                           f"({comparison.loc[winner_idx, 'IRR']*100:.2f}% IRR)")

                st.dataframe(
                    comparison, use_container_width=True, hide_index=True,
                    column_config={
                        "Investido": st.column_config.NumberColumn(format="€ %.0f"),
                        "Valor Final": st.column_config.NumberColumn(format="€ %.0f"),
                        "Lucro": st.column_config.NumberColumn(format="€ %.0f"),
                        "IRR": st.column_config.NumberColumn(format="%.2f%%"),
                        "Multiplicador": st.column_config.NumberColumn(format="%.2fx"),
                        "Max Drawdown": st.column_config.NumberColumn(format="%.2f%%"),
                        "Sharpe": st.column_config.NumberColumn(format="%.2f"),
                    },
                )

                # Chart
                fig = go.Figure()
                colors_strat = [COLORS["gain"], COLORS["accent"], COLORS["warn"]]
                for r, color in zip(results, colors_strat):
                    fig.add_trace(go.Scatter(
                        x=r.dates, y=r.portfolio_value,
                        name=r.strategy_name,
                        line=dict(color=color, width=2),
                    ))
                fig.update_layout(
                    **PLOTLY_DARK_LAYOUT, height=420,
                    legend=dict(orientation="h", y=1.08, x=0),
                    yaxis_title="Valor (€)",
                )
                st.plotly_chart(fig, use_container_width=True,
                                config={"displayModeBar": False})

                st.caption(
                    "💡 **Lembra-te:** lump sum costuma ganhar em mercados em "
                    "subida sustentada (porque deploya mais cedo), DCA reduz "
                    "regret e volatilidade emocional, BTD requer disciplina e "
                    "pode under-perform em bull markets."
                )

# ============================================================
# TAB 3 — Rolling Returns
# ============================================================
with tab_rolling:
    st.markdown("### Rolling Returns")
    st.caption(
        "Em vez do retorno único desde X, mostra a distribuição de todos os "
        "retornos N-anuais possíveis no histórico. Calibra expectativas."
    )

    c1, c2 = st.columns(2)
    with c1:
        roll_ticker = st.selectbox(
            "Activo", df["ticker"].tolist() + ["^GSPC (S&P 500)"],
            index=len(df), key="roll_ticker",
        )
    with c2:
        roll_window = st.slider("Janela (anos)", 1, 10, 3)

    actual_ticker = roll_ticker.split(" ")[0] if "(" in roll_ticker else roll_ticker

    if st.button("📊 Calcular Rolling", key="run_roll"):
        with st.spinner("A processar..."):
            hist = get_historical_for_portfolio((actual_ticker,), "max")
            if hist.empty:
                st.error("Sem dados.")
            else:
                prices = hist.iloc[:, 0].dropna()
                roll = rolling_returns(prices, window_years=roll_window)

                if roll.empty:
                    st.warning(f"Histórico insuficiente para janela de {roll_window}a.")
                else:
                    # Stats
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Mediana", f"{roll.median()*100:.2f}%")
                    c2.metric("Mínimo", f"{roll.min()*100:.2f}%",
                              delta="pior cenário", delta_color="off")
                    c3.metric("Máximo", f"{roll.max()*100:.2f}%",
                              delta="melhor cenário", delta_color="off")
                    pct_negative = (roll < 0).sum() / len(roll) * 100
                    c4.metric("% janelas negativas", f"{pct_negative:.1f}%")

                    # Distribution histogram
                    fig = go.Figure()
                    fig.add_trace(go.Histogram(
                        x=roll * 100, nbinsx=40,
                        marker_color=COLORS["accent"],
                        opacity=0.8,
                    ))
                    fig.add_vline(x=roll.median()*100, line_dash="dash",
                                  line_color=COLORS["gain"],
                                  annotation_text=f"Mediana {roll.median()*100:.1f}%")
                    fig.add_vline(x=0, line_color=COLORS["loss"], line_width=1)
                    fig.update_layout(
                        **PLOTLY_DARK_LAYOUT, height=380,
                        xaxis_title=f"Retorno anualizado (%) em janelas de {roll_window}a",
                        yaxis_title="Frequência",
                    )
                    st.plotly_chart(fig, use_container_width=True,
                                    config={"displayModeBar": False})

                    # Time series of rolling returns
                    st.markdown("#### Evolução temporal das janelas")
                    fig2 = go.Figure(go.Scatter(
                        x=roll.index, y=roll * 100,
                        line=dict(color=COLORS["gain"], width=1.5),
                        fill="tozeroy", fillcolor="rgba(0,212,170,0.06)",
                    ))
                    fig2.add_hline(y=0, line_color=COLORS["text_muted"], line_dash="dot")
                    fig2.update_layout(
                        **PLOTLY_DARK_LAYOUT, height=280,
                        yaxis_title=f"Retorno {roll_window}a anualizado (%)",
                    )
                    st.plotly_chart(fig2, use_container_width=True,
                                    config={"displayModeBar": False})

# ============================================================
# TAB 4 — Stress Tests
# ============================================================
with tab_stress:
    st.markdown("### Stress Tests Históricos")
    st.caption(
        "Como teria sido a tua carteira nos piores momentos da história recente? "
        "(Para posições recentes que não existiam, usa-se o histórico disponível.)"
    )

    weights = {r["ticker"]: r["weight"] / 100 for _, r in df.iterrows()}
    tickers = tuple(weights.keys())

    if st.button("⛈️ Correr Stress Tests", type="primary"):
        with st.spinner("A carregar 25 anos de histórico..."):
            hist = get_historical_for_portfolio(tickers, "max")

            if hist.empty:
                st.error("Sem dados históricos.")
            else:
                results = []
                for crisis_name, (start, end) in CRISIS_PERIODS.items():
                    result = stress_test(hist, weights, start, end)
                    if result["available"]:
                        results.append({
                            "Crise": crisis_name,
                            "Drawdown": result["max_drawdown_pct"],
                            "Retorno": result["total_return_pct"],
                            "Dias": result["n_days"],
                            "Cobertura": f"{result['tickers_available']}/{result['tickers_total']}",
                        })

                if not results:
                    st.warning(
                        "Nenhuma crise tem dados suficientes para a tua carteira. "
                        "Posições muito recentes — a maioria foi listada após 2020."
                    )
                else:
                    res_df = pd.DataFrame(results)
                    st.dataframe(
                        res_df, use_container_width=True, hide_index=True,
                        column_config={
                            "Drawdown": st.column_config.NumberColumn(format="%.2f%%"),
                            "Retorno": st.column_config.NumberColumn(format="%.2f%%"),
                            "Dias": st.column_config.NumberColumn(format="%d"),
                        },
                    )

                    # Bar chart
                    fig = go.Figure(go.Bar(
                        y=res_df["Crise"], x=res_df["Drawdown"], orientation="h",
                        marker_color=COLORS["loss"],
                        text=[f"{v:.1f}%" for v in res_df["Drawdown"]],
                        textposition="outside",
                        textfont=dict(family="JetBrains Mono"),
                    ))
                    fig.update_layout(
                        **PLOTLY_DARK_LAYOUT, height=max(300, 50 * len(res_df)),
                        xaxis_title="Drawdown (%)",
                    )
                    st.plotly_chart(fig, use_container_width=True,
                                    config={"displayModeBar": False})

                    worst = res_df.loc[res_df["Drawdown"].idxmin()]
                    st.warning(
                        f"📉 Pior cenário: **{worst['Crise']}** com drawdown de "
                        f"**{worst['Drawdown']:.1f}%** ao longo de {worst['Dias']} dias."
                    )
                    st.caption(
                        "💡 A cobertura indica quantas das tuas posições já existiam "
                        "no período. Quanto menor, mais o resultado deve ser interpretado "
                        "como aproximação (a carteira é mais recente do que a crise)."
                    )

st.markdown("---")
st.caption(
    "⏪ Backtests baseados em histórico Yahoo Finance. "
    "Performance passada não garante resultados futuros."
)
