"""Portfolio Terminal — Dashboard principal."""
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data import (
    enrich_portfolio,
    fetch_eurusd,
    fetch_historical,
    fetch_sparkline_data,
    load_portfolio,
)
from utils.metrics import (
    daily_returns,
    full_risk_suite,
    herfindahl_index,
    interpret_hhi,
    portfolio_returns,
)
from utils.styling import (
    BRAND_COLORS,
    COLORS,
    PLOTLY_DARK_LAYOUT,
    apply_custom_css,
)

st.set_page_config(
    page_title="Portfolio Terminal", page_icon="📊",
    layout="wide", initial_sidebar_state="expanded",
)
apply_custom_css()

portfolio_data = load_portfolio()
profile = portfolio_data["profile"]

# ============================================================
# Sidebar
# ============================================================
with st.sidebar:
    st.markdown("# Terminal")
    st.caption(f"**Atualização:** {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    st.caption(f"**Moeda Base:** {portfolio_data['base_currency']}")

    if st.button("🔄 Forçar refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption(
        "<span style='font-size:0.7rem; color: var(--text-muted);'>"
        "Preços: cache 5min · Histórico: cache 1h · Notícias: cache 30min"
        "</span>", unsafe_allow_html=True,
    )
    st.markdown("---")
    st.markdown("### Perfil")
    st.markdown(
        f"""
        <div style='font-size:0.82rem; line-height:1.7; color: var(--text-dim);'>
        <b style='color: var(--text)'>Idade:</b> {profile['idade']}<br>
        <b style='color: var(--text)'>Horizonte:</b> {profile['horizonte']}<br>
        <b style='color: var(--text)'>Risco:</b> {profile['risco']}<br>
        <b style='color: var(--text)'>Broker:</b> {profile['broker']}<br>
        <b style='color: var(--text)'>Contrib./mês:</b> € {profile['contribuicao_mensal']:,.0f}<br>
        <b style='color: var(--text)'>Freq. DCA:</b> {profile['frequencia_dca']}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.caption("⚠️ Não é aconselhamento financeiro")

# ============================================================
# Load market data
# ============================================================
with st.spinner("A carregar cotações..."):
    df = enrich_portfolio(portfolio_data)
    eurusd = fetch_eurusd()

df_valid = df.dropna(subset=["current_price"]).copy()
if df_valid.empty:
    st.error("Não foi possível obter cotações. Verifica a tua ligação.")
    st.stop()

total_value = float(df_valid["value_eur"].sum())
total_cost = float(df_valid["cost_eur"].sum())
total_pl = total_value - total_cost
total_pl_pct = (total_pl / total_cost * 100) if total_cost else 0

# Today's move
df_valid["value_eur_yday"] = df_valid["value_eur"] / (1 + df_valid["change_pct"] / 100)
today_move_eur = (df_valid["value_eur"] - df_valid["value_eur_yday"]).sum()
yesterday_value = df_valid["value_eur_yday"].sum()
today_move_pct = (today_move_eur / yesterday_value * 100) if yesterday_value else 0

# ============================================================
# Hero
# ============================================================
st.markdown("# Portfolio Dashboard")

hero_col1, hero_col2, hero_col3 = st.columns([1.3, 1, 1])
with hero_col1:
    today_color = COLORS["gain"] if today_move_eur >= 0 else COLORS["loss"]
    arrow = "▲" if today_move_eur >= 0 else "▼"
    st.markdown(
        f"""
        <div class="hero-label">Valor Total</div>
        <div class="hero-number" style="font-family: var(--font-mono); color: var(--text);">
            € {total_value:,.2f}
        </div>
        <div style="margin-top:6px; font-family: var(--font-mono); color: {today_color}; font-size:1rem;">
            {arrow} € {abs(today_move_eur):,.2f} &nbsp;·&nbsp; {today_move_pct:+.2f}%
            <span class="dim-text" style="margin-left:8px; font-size:0.78rem;">HOJE</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

with hero_col2:
    pl_color = COLORS["gain"] if total_pl >= 0 else COLORS["loss"]
    st.markdown(
        f"""
        <div class="hero-label">P/L Total Acumulado</div>
        <div class="hero-number" style="font-family: var(--font-mono); color: {pl_color};">
            {'+' if total_pl >= 0 else ''}€ {total_pl:,.2f}
        </div>
        <div style="margin-top:6px; font-family: var(--font-mono); color: {pl_color}; font-size:1rem;">
            {total_pl_pct:+.2f}%
            <span class="dim-text" style="margin-left:8px; font-size:0.78rem;">
                sobre € {total_cost:,.2f} investido
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

with hero_col3:
    top = df_valid.nlargest(1, "change_pct").iloc[0]
    bot = df_valid.nsmallest(1, "change_pct").iloc[0]
    st.markdown(
        f"""
        <div class="hero-label">Movers de Hoje</div>
        <div style="margin-top:8px;">
            <div style="font-family: var(--font-mono); font-size: 1.1rem; line-height:1.6;">
                <span class="gain-text">▲ {top['ticker']}</span>
                <span class="dim-text" style="font-size:0.85rem;"> — {top['name'][:20]}</span>
                <span class="gain-text" style="float:right;">{top['change_pct']:+.2f}%</span>
            </div>
            <div style="font-family: var(--font-mono); font-size: 1.1rem; line-height:1.6;">
                <span class="loss-text">▼ {bot['ticker']}</span>
                <span class="dim-text" style="font-size:0.85rem;"> — {bot['name'][:20]}</span>
                <span class="loss-text" style="float:right;">{bot['change_pct']:+.2f}%</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)

# ============================================================
# Allocation donuts
# ============================================================
st.markdown("## Alocação")
col_class, col_sector, col_currency = st.columns(3)


def donut(df_grouped, label_col, value_col, title, colors=None):
    fig = go.Figure(go.Pie(
        labels=df_grouped[label_col], values=df_grouped[value_col],
        hole=0.62,
        marker=dict(colors=colors or BRAND_COLORS,
                    line=dict(color=COLORS["bg_card"], width=2)),
        textinfo="percent",
        textfont=dict(color="#ffffff", size=11, family="JetBrains Mono"),
        hovertemplate="<b>%{label}</b><br>€ %{value:,.2f}<br>%{percent}<extra></extra>",
    ))
    total = df_grouped[value_col].sum()
    fig.update_layout(
        **PLOTLY_DARK_LAYOUT,
        title=dict(text=title, font=dict(size=12, color=COLORS["text_dim"]),
                   x=0.03, xanchor="left"),
        showlegend=True,
        legend=dict(orientation="v", x=1.0, y=0.5, font=dict(size=10)),
        height=260,
        annotations=[dict(text=f"€ {total:,.0f}", showarrow=False,
                          font=dict(size=14, family="JetBrains Mono",
                                    color=COLORS["text"]))],
    )
    return fig


with col_class:
    by_class = df_valid.groupby("class", as_index=False)["value_eur"].sum()
    st.plotly_chart(donut(by_class, "class", "value_eur", "POR CLASSE"),
                    use_container_width=True, config={"displayModeBar": False})

with col_sector:
    by_sector = (df_valid.groupby("sector", as_index=False)["value_eur"]
                 .sum().sort_values("value_eur", ascending=False))
    st.plotly_chart(donut(by_sector, "sector", "value_eur", "POR SECTOR"),
                    use_container_width=True, config={"displayModeBar": False})

with col_currency:
    # Use quote_currency for exposure (real FX exposure)
    by_curr = df_valid.groupby("quote_currency", as_index=False)["value_eur"].sum()
    st.plotly_chart(
        donut(by_curr, "quote_currency", "value_eur", "EXPOSIÇÃO CAMBIAL",
              colors=[COLORS["gain"], COLORS["accent"], COLORS["warn"]]),
        use_container_width=True, config={"displayModeBar": False},
    )

# ============================================================
# Holdings with sparklines
# ============================================================
st.markdown("## Holdings")

tickers_tuple = tuple(df_valid["ticker"].tolist())
with st.spinner("A carregar sparklines..."):
    spark = fetch_sparkline_data(tickers_tuple, days=30)
df_valid["sparkline"] = df_valid["ticker"].map(lambda t: spark.get(t, []))

# Use current_price_display (in PM currency) — matches the Google sheet mental model
display = df_valid[[
    "ticker", "name", "class", "currency", "sector",
    "qty", "avg_price", "current_price_display",
    "sparkline", "change_pct",
    "value_eur", "cost_eur", "pl_eur", "pl_pct", "weight",
    "dist_stop_pct", "dist_tp_pct",
]].rename(columns={
    "ticker": "Ticker", "name": "Nome", "class": "Cls",
    "currency": "Moeda", "sector": "Sector",
    "qty": "Qtd", "avg_price": "PM",
    "current_price_display": "Preço",
    "sparkline": "30d", "change_pct": "Hoje %",
    "value_eur": "Valor €", "cost_eur": "Custo €",
    "pl_eur": "P/L €", "pl_pct": "P/L %", "weight": "% Cart.",
    "dist_stop_pct": "→ Stop %", "dist_tp_pct": "→ TP %",
})

st.dataframe(
    display, use_container_width=True, hide_index=True, height=580,
    column_config={
        "Ticker": st.column_config.TextColumn(width="small"),
        "Nome": st.column_config.TextColumn(width="medium"),
        "Cls": st.column_config.TextColumn(width="small"),
        "Moeda": st.column_config.TextColumn("Moeda", width="small",
                  help="Moeda do PM (o que pagaste)"),
        "Qtd": st.column_config.NumberColumn(format="%.4f", width="small"),
        "PM": st.column_config.NumberColumn(format="%.2f",
               help="Preço médio na tua moeda de custo"),
        "Preço": st.column_config.NumberColumn(format="%.2f",
                  help="Preço atual convertido para a mesma moeda do PM"),
        "30d": st.column_config.LineChartColumn("30d", width="medium"),
        "Hoje %": st.column_config.NumberColumn(format="%.2f%%"),
        "Valor €": st.column_config.NumberColumn(format="€ %.2f"),
        "Custo €": st.column_config.NumberColumn(format="€ %.2f"),
        "P/L €": st.column_config.NumberColumn(format="€ %.2f"),
        "P/L %": st.column_config.NumberColumn(format="%.2f%%"),
        "% Cart.": st.column_config.ProgressColumn(format="%.2f%%",
                    min_value=0, max_value=30),
        "→ Stop %": st.column_config.NumberColumn(format="%.1f%%"),
        "→ TP %": st.column_config.NumberColumn(format="%.1f%%"),
    },
)

st.caption(
    f"**Total:** € {total_value:,.2f} · **Investido:** € {total_cost:,.2f} "
    f"· **P/L:** € {total_pl:,.2f} ({total_pl_pct:+.2f}%) · {len(df_valid)} posições"
)

# ============================================================
# Historical analysis
# ============================================================
with st.spinner("A carregar séries históricas..."):
    hist = fetch_historical(tickers_tuple, period="1y")
    bench_hist = fetch_historical(("^GSPC",), period="1y")

weights = dict(zip(df_valid["ticker"], df_valid["weight"] / 100))
hist_avail = [t for t in weights if t in hist.columns]
hist = hist[hist_avail].dropna(how="all")

if not hist.empty and not bench_hist.empty:
    bench_ret = daily_returns(bench_hist.iloc[:, 0])
    port_ret = portfolio_returns(hist, {t: weights[t] for t in hist_avail})

    # Performance + risk metrics
    perf_col, risk_col = st.columns([1.7, 1])

    with perf_col:
        st.markdown("## Rentabilidade Acumulada")
        port_idx = (1 + port_ret).cumprod() * 100
        bench_idx = (1 + bench_ret).cumprod() * 100
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=port_idx.index, y=port_idx.values, name="Carteira",
            line=dict(color=COLORS["gain"], width=2.5),
            fill="tozeroy", fillcolor="rgba(0,212,170,0.08)",
        ))
        fig.add_trace(go.Scatter(
            x=bench_idx.index, y=bench_idx.values, name="S&P 500",
            line=dict(color=COLORS["accent"], width=1.8, dash="dot"),
        ))
        fig.add_hline(y=100, line_dash="dash",
                      line_color=COLORS["text_muted"], opacity=0.5)
        fig.update_layout(**PLOTLY_DARK_LAYOUT, height=340,
                          legend=dict(orientation="h", y=1.08, x=0,
                                      bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False})

    with risk_col:
        st.markdown("## Métricas (1A)")
        port_m = full_risk_suite(port_ret, bench_ret,
                                 portfolio_data["risk_free_rate"])
        bench_m = full_risk_suite(bench_ret, bench_ret,
                                  portfolio_data["risk_free_rate"])

        rows = [
            ("Retorno Anual.", port_m["annualized_return"], bench_m["annualized_return"], "pct"),
            ("Volatilidade", port_m["volatility"], bench_m["volatility"], "pct"),
            ("Sharpe", port_m["sharpe"], bench_m["sharpe"], "num"),
            ("Sortino", port_m["sortino"], bench_m["sortino"], "num"),
            ("Beta", port_m["beta"], 1.0, "num"),
            ("Alpha (CAPM)", port_m["alpha"], 0.0, "pct"),
            ("R²", port_m["r_squared"], 1.0, "num"),
            ("Max DD", port_m["max_drawdown"], bench_m["max_drawdown"], "pct"),
        ]
        for label, p, b, fmt in rows:
            diff = p - b
            col = COLORS["gain"] if diff >= 0 else COLORS["loss"]
            if fmt == "pct":
                p_s, b_s, d_s = f"{p * 100:.2f}%", f"{b * 100:.2f}%", f"{diff * 100:+.2f}%"
            else:
                p_s, b_s, d_s = f"{p:.2f}", f"{b:.2f}", f"{diff:+.2f}"
            st.markdown(
                f"""
                <div style="display:grid; grid-template-columns: 1.2fr 1fr 0.8fr 0.8fr;
                            gap:6px; padding:6px 8px; border-bottom:1px solid var(--border);
                            font-family: var(--font-mono); font-size:0.82rem;">
                    <span style="color: var(--text-dim);">{label}</span>
                    <span style="color: var(--text); text-align:right;">{p_s}</span>
                    <span style="color: var(--text-muted); text-align:right;">{b_s}</span>
                    <span style="color: {col}; text-align:right; font-weight:500;">{d_s}</span>
                </div>
                """, unsafe_allow_html=True,
            )
        st.caption(
            "<span style='font-size:0.7rem; color: var(--text-muted);'>"
            "métrica · carteira · benchmark · Δ"
            "</span>", unsafe_allow_html=True,
        )

    # Correlation + alerts
    corr_col, right_col = st.columns([1.7, 1])

    with corr_col:
        st.markdown("## Correlação (1A)")
        rets = daily_returns(hist)
        corr = rets.corr()
        fig = go.Figure(go.Heatmap(
            z=corr.values, x=corr.columns, y=corr.columns,
            colorscale=[[0.0, COLORS["loss"]],
                        [0.5, COLORS["bg_elevated"]],
                        [1.0, COLORS["gain"]]],
            zmin=-1, zmax=1,
            text=np.round(corr.values, 2),
            texttemplate="%{text}",
            textfont=dict(size=9, family="JetBrains Mono"),
            colorbar=dict(thickness=10, tickfont=dict(size=9)),
        ))
        fig.update_layout(**PLOTLY_DARK_LAYOUT, height=420)
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False})

    with right_col:
        st.markdown("## Concentração")
        hhi = herfindahl_index(df_valid["value_eur"].values)
        biggest = df_valid.loc[df_valid["value_eur"].idxmax()]
        k1, k2 = st.columns(2)
        k1.metric("Maior Posição", f"{biggest['ticker']}", f"{biggest['weight']:.2f}%")
        k2.metric("HHI", f"{hhi:.3f}", interpret_hhi(hhi), delta_color="off")

        st.markdown("## Alertas")
        alerts = []
        for _, r in df_valid[df_valid["weight"] > 20].iterrows():
            alerts.append(
                f"<div style='padding:6px 10px; border-left:3px solid {COLORS['loss']}; "
                f"background:rgba(255,92,122,0.06); margin-bottom:4px; font-size:0.8rem;'>"
                f"<b>{r['ticker']}</b> · concentração "
                f"<span class='loss-text'>{r['weight']:.1f}%</span></div>"
            )
        for _, r in df_valid[df_valid["pl_pct"] < -10].iterrows():
            alerts.append(
                f"<div style='padding:6px 10px; border-left:3px solid {COLORS['warn']}; "
                f"background:rgba(255,183,77,0.06); margin-bottom:4px; font-size:0.8rem;'>"
                f"<b>{r['ticker']}</b> · em prejuízo "
                f"<span class='warn-text'>{r['pl_pct']:.1f}%</span></div>"
            )
        for _, r in df_valid.iterrows():
            if r["dist_stop_pct"] is not None and -15 < r["dist_stop_pct"] < 0:
                alerts.append(
                    f"<div style='padding:6px 10px; border-left:3px solid {COLORS['warn']}; "
                    f"background:rgba(255,183,77,0.06); margin-bottom:4px; font-size:0.8rem;'>"
                    f"<b>{r['ticker']}</b> · a <span class='warn-text'>"
                    f"{abs(r['dist_stop_pct']):.1f}%</span> do stop</div>"
                )
        for _, r in df_valid.iterrows():
            if r["dist_tp_pct"] is not None and 0 < r["dist_tp_pct"] < 10:
                alerts.append(
                    f"<div style='padding:6px 10px; border-left:3px solid {COLORS['gain']}; "
                    f"background:rgba(0,212,170,0.06); margin-bottom:4px; font-size:0.8rem;'>"
                    f"<b>{r['ticker']}</b> · a <span class='gain-text'>"
                    f"{r['dist_tp_pct']:.1f}%</span> do take-profit</div>"
                )
        if not alerts:
            alerts.append(
                f"<div style='padding:8px 12px; border-left:3px solid {COLORS['gain']}; "
                f"background:rgba(0,212,170,0.06); font-size:0.82rem;'>"
                "✓ Sem alertas — tudo dentro dos parâmetros</div>"
            )
        for a in alerts[:8]:
            st.markdown(a, unsafe_allow_html=True)

    st.markdown("## Performance 12m por Ativo")
    perf = ((hist.iloc[-1] / hist.iloc[0]) - 1) * 100
    perf = perf.sort_values(ascending=True)
    colors_bar = [COLORS["gain"] if v >= 0 else COLORS["loss"] for v in perf.values]
    fig = go.Figure(go.Bar(
        y=perf.index, x=perf.values, orientation="h",
        marker=dict(color=colors_bar),
        text=[f"{v:+.1f}%" for v in perf.values],
        textposition="outside",
        textfont=dict(family="JetBrains Mono", size=10),
    ))
    fig.update_layout(**PLOTLY_DARK_LAYOUT,
                      height=max(300, 26 * len(perf)),
                      xaxis_title="Retorno (%)")
    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False})
else:
    st.warning("Sem séries históricas suficientes.")

st.markdown("---")
st.caption(
    f"💱 EUR/USD: {eurusd:.4f} · Yahoo Finance · "
    f"{datetime.now().strftime('%d/%m/%Y %H:%M')}"
)
