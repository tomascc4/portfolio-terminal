"""Empresa — deep-dive fundamental, valuation, earnings, analysts."""
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data import (
    fetch_analyst_recommendations,
    fetch_company_info,
    fetch_earnings_calendar,
    fetch_financials_history,
    fetch_historical,
    fetch_institutional_holders,
    format_large_number,
    format_percent,
    format_ratio,
    load_portfolio,
    recommendation_label,
)
from utils.styling import COLORS, PLOTLY_DARK_LAYOUT, apply_custom_css

st.set_page_config(page_title="Empresa", page_icon="🏢", layout="wide")
apply_custom_css()

# ============================================================
# Ticker selector
# ============================================================
portfolio_data = load_portfolio()
holdings = [p["ticker"] for p in portfolio_data["positions"]]
watchlist = [w["ticker"] for w in portfolio_data.get("watchlist", [])]
suggested = sorted(set(holdings + watchlist))

st.markdown("# Empresa")
st.caption("Perfil completo — fundamentais, valuation, crescimento, analistas.")

c1, c2 = st.columns([3, 1])
with c1:
    # Default to first holding
    ticker = st.selectbox(
        "Ticker",
        suggested + ["— outro —"],
        index=0,
        label_visibility="collapsed",
    )
with c2:
    if ticker == "— outro —":
        ticker = st.text_input("Inserir ticker", "AAPL").upper()

if not ticker or ticker == "— outro —":
    st.info("Escolhe um ticker para começar.")
    st.stop()

# ============================================================
# Fetch everything
# ============================================================
with st.spinner(f"A carregar dados de {ticker}..."):
    info = fetch_company_info(ticker)

if not info or not info.get("name"):
    st.error(
        f"Não foi possível obter dados para **{ticker}**. "
        "Verifica se o ticker está correcto no formato Yahoo Finance."
    )
    st.stop()

currency = info.get("currency", "USD")

# ============================================================
# HERO — Company header
# ============================================================
price = info.get("current_price")
prev = info.get("previous_close")
change = ((price / prev) - 1) * 100 if price and prev else 0
change_color = COLORS["gain"] if change >= 0 else COLORS["loss"]
arrow = "▲" if change >= 0 else "▼"

website = info.get("website", "")
website_display = website.replace("https://", "").replace("http://", "").rstrip("/") if website else ""

employees_str = f"{info['employees']:,}".replace(",", " ") if info.get("employees") else "—"

location_parts = [p for p in [info.get("city"), info.get("state"), info.get("country")] if p]
location = ", ".join(location_parts) if location_parts else "—"

hero_left, hero_right = st.columns([2, 1])

with hero_left:
    st.markdown(
        f"""
        <div style="margin-bottom: 12px;">
            <div class="hero-label">{info.get('exchange', '')} · {ticker}</div>
            <div style="font-family: var(--font-serif); font-size: 2.6rem;
                 font-weight: 400; letter-spacing: -0.01em; line-height: 1.1;
                 color: var(--text); margin-top: 4px;">
                {info['name']}
            </div>
            <div style="color: var(--text-dim); font-size: 0.88rem; margin-top: 6px;">
                {info.get('sector', '—')} &nbsp;·&nbsp; {info.get('industry', '—')}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with hero_right:
    if price:
        st.markdown(
            f"""
            <div style="text-align: right;">
                <div class="hero-label">Preço Atual</div>
                <div class="hero-number" style="font-family: var(--font-mono); color: var(--text);">
                    {currency} {price:,.2f}
                </div>
                <div style="margin-top:4px; font-family: var(--font-mono);
                     color: {change_color}; font-size:1rem;">
                    {arrow} {change:+.2f}%
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# Quick facts row
facts_html = f"""
<div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
     margin: 16px 0; padding: 14px 18px; background: var(--bg-card);
     border: 1px solid var(--border); border-radius: 10px;
     font-family: var(--font-mono); font-size: 0.85rem;">
  <div>
    <div class="dim-text" style="font-size: 0.7rem; text-transform: uppercase;
         letter-spacing: 0.1em;">Market Cap</div>
    <div style="font-size: 1rem; margin-top: 4px;">
        {format_large_number(info.get('market_cap'), '$')}
    </div>
  </div>
  <div>
    <div class="dim-text" style="font-size: 0.7rem; text-transform: uppercase;
         letter-spacing: 0.1em;">Funcionários</div>
    <div style="font-size: 1rem; margin-top: 4px;">{employees_str}</div>
  </div>
  <div>
    <div class="dim-text" style="font-size: 0.7rem; text-transform: uppercase;
         letter-spacing: 0.1em;">Sede</div>
    <div style="font-size: 0.88rem; margin-top: 4px;">{location}</div>
  </div>
  <div>
    <div class="dim-text" style="font-size: 0.7rem; text-transform: uppercase;
         letter-spacing: 0.1em;">Website</div>
    <div style="font-size: 0.88rem; margin-top: 4px;">
        {f'<a href="{website}" target="_blank" style="color: var(--accent);">{website_display}</a>' if website else '—'}
    </div>
  </div>
</div>
"""
st.markdown(facts_html, unsafe_allow_html=True)

# ============================================================
# About + CEO/Leadership
# ============================================================
about_col, officers_col = st.columns([2, 1])

with about_col:
    st.markdown("## Sobre")
    summary = info.get("summary", "")
    if summary:
        st.markdown(
            f"""
            <div style="color: var(--text-dim); font-size: 0.88rem; line-height: 1.6;
                 text-align: justify; padding: 4px 0;">
                {summary}
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.caption("Sem descrição disponível.")

with officers_col:
    st.markdown("## Liderança")
    officers = info.get("officers", [])
    if officers:
        # Find CEO first
        ceo = next((o for o in officers if "CEO" in (o.get("title", "") or "").upper()
                    or "Chief Executive" in (o.get("title", "") or "")), None)
        top_officers = [ceo] if ceo else []
        top_officers += [o for o in officers if o != ceo][:5]
        for o in top_officers[:6]:
            if not o:
                continue
            name = o.get("name", "—")
            title = o.get("title", "—")
            age = f" · {o['age']}a" if o.get("age") else ""
            pay = o.get("totalPay")
            pay_str = f"{format_large_number(pay, '$')}" if pay else ""
            is_ceo = "CEO" in title.upper() or "Chief Executive" in title
            border_color = COLORS["gain"] if is_ceo else COLORS["border"]
            st.markdown(
                f"""
                <div style="padding: 8px 12px; border-left: 2px solid {border_color};
                     background: var(--bg-card); border-radius: 4px;
                     margin-bottom: 6px; font-size: 0.82rem;">
                    <div style="font-weight: 500; color: var(--text);">{name}{age}</div>
                    <div class="dim-text" style="font-size: 0.78rem; margin-top: 2px;">
                        {title}
                    </div>
                    {f'<div class="dim-text" style="font-size: 0.72rem; margin-top: 2px; font-family: var(--font-mono);">Comp: {pay_str}</div>' if pay_str else ''}
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.caption("Dados de liderança não disponíveis.")

# ============================================================
# Valuation metrics
# ============================================================
st.markdown("## Valuation")

val_cols = st.columns(5)
val_metrics = [
    ("P/E (trailing)", info.get("trailing_pe"), "ratio"),
    ("P/E (forward)", info.get("forward_pe"), "ratio"),
    ("PEG", info.get("peg_ratio"), "ratio"),
    ("P/B", info.get("price_to_book"), "ratio"),
    ("P/S", info.get("price_to_sales"), "ratio"),
]
for i, (label, val, fmt) in enumerate(val_metrics):
    val_cols[i].metric(label, format_ratio(val) if fmt == "ratio" else val)

val_cols2 = st.columns(5)
val_metrics2 = [
    ("EV", format_large_number(info.get("enterprise_value"), "$")),
    ("EV/Revenue", format_ratio(info.get("ev_revenue"))),
    ("EV/EBITDA", format_ratio(info.get("ev_ebitda"))),
    ("Beta", format_ratio(info.get("beta"))),
    ("52w Range", f"{info.get('52w_low', 0):.0f}–{info.get('52w_high', 0):.0f}" if info.get("52w_low") else "—"),
]
for i, (label, val) in enumerate(val_metrics2):
    val_cols2[i].metric(label, val)

# PEG interpretation
peg = info.get("peg_ratio")
if peg is not None:
    if peg < 1:
        peg_msg = f"**PEG {peg:.2f}** — *subvalorizada vs crescimento*"
        peg_color = COLORS["gain"]
    elif peg < 1.5:
        peg_msg = f"**PEG {peg:.2f}** — *preço justo face ao crescimento*"
        peg_color = COLORS["warn"]
    elif peg < 2:
        peg_msg = f"**PEG {peg:.2f}** — *premium vs crescimento*"
        peg_color = COLORS["warn"]
    else:
        peg_msg = f"**PEG {peg:.2f}** — *caro face ao crescimento*"
        peg_color = COLORS["loss"]
    st.markdown(
        f"""
        <div style="padding: 8px 14px; background: var(--bg-card);
             border-left: 3px solid {peg_color}; border-radius: 6px;
             font-size: 0.82rem; margin-top: 8px;">{peg_msg}</div>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# Margins & profitability
# ============================================================
st.markdown("## Margens & Rentabilidade")

m_cols = st.columns(5)
m_cols[0].metric("Gross Margin", format_percent(info.get("gross_margin")))
m_cols[1].metric("Operating Margin", format_percent(info.get("operating_margin")))
m_cols[2].metric("Net Margin", format_percent(info.get("profit_margin")))
m_cols[3].metric("ROE", format_percent(info.get("roe")))
m_cols[4].metric("ROA", format_percent(info.get("roa")))

# ============================================================
# Growth
# ============================================================
st.markdown("## Crescimento")

g_cols = st.columns(4)
rev_g = info.get("revenue_growth")
eps_g = info.get("earnings_growth")
eps_q = info.get("earnings_qoq")

g_cols[0].metric(
    "Revenue Growth (YoY)",
    format_percent(rev_g),
    delta="vs meta 12%" if rev_g else None,
    delta_color="off",
)
g_cols[1].metric("Earnings Growth (YoY)", format_percent(eps_g))
g_cols[2].metric("Earnings Growth (QoQ)", format_percent(eps_q))
g_cols[3].metric(
    "Revenue TTM", format_large_number(info.get("revenue_ttm"), "$"),
)

# Revenue/earnings history chart (quarterly)
with st.spinner("A carregar histórico financeiro..."):
    financials = fetch_financials_history(ticker)

qi = financials.get("quarterly_income")
if qi is not None and not qi.empty:
    # Find key rows
    candidate_rows = {
        "revenue": ["Total Revenue", "Revenue"],
        "gross_profit": ["Gross Profit"],
        "operating_income": ["Operating Income"],
        "net_income": ["Net Income", "Net Income Common Stockholders"],
    }

    def find_row(df, candidates):
        for c in candidates:
            if c in df.index:
                return df.loc[c]
        return None

    revenue = find_row(qi, candidate_rows["revenue"])
    net_income = find_row(qi, candidate_rows["net_income"])
    gross_profit = find_row(qi, candidate_rows["gross_profit"])

    if revenue is not None:
        # Columns are timestamps (most recent first). Reverse for chart.
        dates = pd.to_datetime(revenue.index)[::-1]
        rev_vals = revenue.values[::-1]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=dates, y=rev_vals, name="Revenue",
            marker_color=COLORS["accent"],
            hovertemplate="%{x|%b %Y}<br>Revenue: $%{y:,.0f}<extra></extra>",
        ))
        if net_income is not None:
            ni_vals = net_income.values[::-1]
            fig.add_trace(go.Bar(
                x=dates, y=ni_vals, name="Net Income",
                marker_color=COLORS["gain"],
                hovertemplate="%{x|%b %Y}<br>Net Income: $%{y:,.0f}<extra></extra>",
            ))
        if gross_profit is not None:
            gp_vals = gross_profit.values[::-1]
            fig.add_trace(go.Scatter(
                x=dates, y=gp_vals, name="Gross Profit",
                line=dict(color=COLORS["warn"], width=2),
                mode="lines+markers",
                hovertemplate="%{x|%b %Y}<br>Gross Profit: $%{y:,.0f}<extra></extra>",
            ))
        fig.update_layout(
            **PLOTLY_DARK_LAYOUT,
            height=320,
            barmode="group",
            title=dict(text="Receitas & Lucro — Trimestral",
                       font=dict(size=12, color=COLORS["text_dim"]),
                       x=0.02, xanchor="left"),
            legend=dict(orientation="h", y=1.1, x=0),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ============================================================
# Balance sheet health
# ============================================================
st.markdown("## Balanço")
bs_cols = st.columns(5)
bs_cols[0].metric("Total Cash", format_large_number(info.get("total_cash"), "$"))
bs_cols[1].metric("Total Debt", format_large_number(info.get("total_debt"), "$"))
bs_cols[2].metric("Debt/Equity", format_ratio(info.get("debt_to_equity")))
bs_cols[3].metric("Current Ratio", format_ratio(info.get("current_ratio")))
bs_cols[4].metric("FCF (TTM)", format_large_number(info.get("free_cashflow"), "$"))

# ============================================================
# Analyst consensus
# ============================================================
st.markdown("## Consenso de Analistas")

num_analysts = info.get("num_analysts")
if num_analysts:
    rec_key = info.get("recommendation", "") or ""
    rec_label, rec_color = recommendation_label(rec_key)
    rec_mean = info.get("recommendation_mean")

    target_mean = info.get("target_mean")
    target_high = info.get("target_high")
    target_low = info.get("target_low")

    an_col1, an_col2, an_col3 = st.columns([1, 2, 1])

    with an_col1:
        st.markdown(
            f"""
            <div style="padding: 16px 20px; background: var(--bg-card);
                 border: 1px solid var(--border); border-left: 3px solid {rec_color};
                 border-radius: 8px; text-align: center;">
                <div class="dim-text" style="font-size: 0.7rem;
                     text-transform: uppercase; letter-spacing: 0.1em;">
                    Recomendação ({num_analysts} analistas)
                </div>
                <div style="font-family: var(--font-serif); font-size: 1.8rem;
                     color: {rec_color}; margin-top: 6px;">
                    {rec_label}
                </div>
                <div class="dim-text" style="font-size: 0.78rem; margin-top: 4px;">
                    Score: {rec_mean:.2f}/5 {'(menor = melhor)' if rec_mean else ''}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with an_col2:
        # Price targets vs current
        if target_mean and price:
            upside = (target_mean / price - 1) * 100
            upside_color = COLORS["gain"] if upside > 0 else COLORS["loss"]

            fig = go.Figure()
            # Range bar
            fig.add_trace(go.Bar(
                y=["Target"], x=[target_high - target_low],
                base=[target_low], orientation="h",
                marker_color="rgba(77,166,255,0.2)",
                showlegend=False, hoverinfo="skip",
            ))
            # Markers
            fig.add_trace(go.Scatter(
                x=[target_low], y=["Target"], mode="markers+text",
                marker=dict(color=COLORS["loss"], size=14, symbol="line-ns",
                           line=dict(width=2)),
                text=[f"Low {target_low:.0f}"],
                textposition="bottom center",
                textfont=dict(size=10, color=COLORS["text_dim"]),
                showlegend=False,
            ))
            fig.add_trace(go.Scatter(
                x=[target_high], y=["Target"], mode="markers+text",
                marker=dict(color=COLORS["gain"], size=14, symbol="line-ns",
                           line=dict(width=2)),
                text=[f"High {target_high:.0f}"],
                textposition="bottom center",
                textfont=dict(size=10, color=COLORS["text_dim"]),
                showlegend=False,
            ))
            fig.add_trace(go.Scatter(
                x=[target_mean], y=["Target"], mode="markers+text",
                marker=dict(color=COLORS["accent"], size=16, symbol="diamond"),
                text=[f"<b>Mean {target_mean:.0f}</b>"],
                textposition="top center",
                textfont=dict(size=11, color=COLORS["accent"]),
                showlegend=False,
            ))
            # Current price
            fig.add_trace(go.Scatter(
                x=[price], y=["Target"], mode="markers+text",
                marker=dict(color=COLORS["warn"], size=16, symbol="x",
                           line=dict(width=2)),
                text=[f"<b>Atual {price:.0f}</b>"],
                textposition="top center",
                textfont=dict(size=11, color=COLORS["warn"]),
                showlegend=False,
            ))
            fig.update_layout(
                **PLOTLY_DARK_LAYOUT,
                height=180,
                xaxis_title=f"Preço ({currency})",
                title=dict(text=f"Price Target · Upside: {upside:+.1f}%",
                           font=dict(size=12, color=upside_color), x=0.02),
            )
            fig.update_layout(margin=dict(l=20, r=20, t=40, b=40))
            fig.update_yaxes(visible=False)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with an_col3:
        if target_mean and price:
            upside = (target_mean / price - 1) * 100
            upside_color = COLORS["gain"] if upside > 0 else COLORS["loss"]
            st.markdown(
                f"""
                <div style="padding: 16px 20px; background: var(--bg-card);
                     border: 1px solid var(--border); border-radius: 8px;
                     text-align: center;">
                    <div class="dim-text" style="font-size: 0.7rem;
                         text-transform: uppercase; letter-spacing: 0.1em;">
                        Upside vs Target
                    </div>
                    <div style="font-family: var(--font-mono); font-size: 1.8rem;
                         color: {upside_color}; margin-top: 6px;">
                        {upside:+.1f}%
                    </div>
                    <div class="dim-text" style="font-size: 0.78rem; margin-top: 4px;">
                        Target: {currency} {target_mean:.2f}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
else:
    st.caption("Sem cobertura de analistas ou dados indisponíveis.")

# Recent recommendation changes
recs = fetch_analyst_recommendations(ticker)
if recs is not None and not recs.empty:
    st.markdown("### Histórico de Recomendações (4m)")
    # recs has columns: period, strongBuy, buy, hold, sell, strongSell
    if "period" in recs.columns:
        recs_display = recs.copy().head(4)
        # Transform to stacked bar
        fig = go.Figure()
        categories = [
            ("strongBuy", "Strong Buy", COLORS["gain"]),
            ("buy", "Buy", "#7cdb9a"),
            ("hold", "Hold", COLORS["warn"]),
            ("sell", "Sell", "#ff9e7d"),
            ("strongSell", "Strong Sell", COLORS["loss"]),
        ]
        for col_name, label, color in categories:
            if col_name in recs_display.columns:
                fig.add_trace(go.Bar(
                    y=recs_display["period"], x=recs_display[col_name],
                    name=label, orientation="h",
                    marker_color=color,
                ))
        fig.update_layout(
            **PLOTLY_DARK_LAYOUT,
            height=220, barmode="stack",
            legend=dict(orientation="h", y=1.15, x=0),
            xaxis_title="Número de analistas",
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ============================================================
# Earnings calendar
# ============================================================
cal = fetch_earnings_calendar(ticker)
next_earnings = cal.get("next_earnings")

if next_earnings:
    st.markdown("## Próximos Earnings")
    # next_earnings can be list of datetimes, single datetime, or string
    if isinstance(next_earnings, list) and next_earnings:
        next_date = next_earnings[0]
    else:
        next_date = next_earnings

    try:
        if isinstance(next_date, (datetime, pd.Timestamp)):
            next_dt = pd.to_datetime(next_date)
            days_until = (next_dt - pd.Timestamp.now()).days
        else:
            next_dt = pd.to_datetime(str(next_date))
            days_until = (next_dt - pd.Timestamp.now()).days

        color = COLORS["warn"] if days_until < 14 else COLORS["accent"]
        eps_est = cal.get("eps_estimate")
        rev_est = cal.get("revenue_estimate")

        st.markdown(
            f"""
            <div style="padding: 16px 20px; background: var(--bg-card);
                 border: 1px solid var(--border); border-left: 3px solid {color};
                 border-radius: 8px; display: grid;
                 grid-template-columns: repeat(3, 1fr); gap: 14px;">
                <div>
                    <div class="dim-text" style="font-size: 0.7rem;
                         text-transform: uppercase; letter-spacing: 0.1em;">
                        Data Prevista
                    </div>
                    <div style="font-family: var(--font-mono); font-size: 1.1rem;
                         margin-top: 4px;">
                        {next_dt.strftime('%d/%m/%Y')}
                    </div>
                    <div style="color: {color}; font-size: 0.82rem; margin-top: 2px;">
                        em {days_until} dias
                    </div>
                </div>
                <div>
                    <div class="dim-text" style="font-size: 0.7rem;
                         text-transform: uppercase; letter-spacing: 0.1em;">
                        EPS Estimado
                    </div>
                    <div style="font-family: var(--font-mono); font-size: 1.1rem;
                         margin-top: 4px;">
                        {f'${eps_est:.2f}' if eps_est else '—'}
                    </div>
                </div>
                <div>
                    <div class="dim-text" style="font-size: 0.7rem;
                         text-transform: uppercase; letter-spacing: 0.1em;">
                        Revenue Estimado
                    </div>
                    <div style="font-family: var(--font-mono); font-size: 1.1rem;
                         margin-top: 4px;">
                        {format_large_number(rev_est, '$') if rev_est else '—'}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        st.caption(f"Próximos earnings: {next_earnings}")

# ============================================================
# Dividends (if applicable)
# ============================================================
div_yield = info.get("dividend_yield")
if div_yield and div_yield > 0:
    st.markdown("## Dividendos")
    d_cols = st.columns(4)
    d_cols[0].metric("Yield", format_percent(div_yield))
    d_cols[1].metric("Rate (anual)", f"${info.get('dividend_rate', 0):.2f}"
                     if info.get("dividend_rate") else "—")
    d_cols[2].metric("Payout Ratio", format_percent(info.get("payout_ratio")))
    ex_div = info.get("ex_dividend_date")
    if ex_div:
        try:
            ex_date = pd.to_datetime(ex_div, unit="s") if isinstance(ex_div, (int, float)) else pd.to_datetime(ex_div)
            d_cols[3].metric("Ex-Dividend", ex_date.strftime("%d/%m/%Y"))
        except Exception:
            pass

# ============================================================
# Ownership
# ============================================================
st.markdown("## Detentores & Ownership")
own_col1, own_col2 = st.columns([1, 2])

with own_col1:
    held_ins = info.get("held_insiders")
    held_inst = info.get("held_institutions")
    short_pct = info.get("short_percent")
    st.metric("Insiders", format_percent(held_ins))
    st.metric("Instituições", format_percent(held_inst))
    if short_pct:
        st.metric("Short % of Float", format_percent(short_pct))

with own_col2:
    inst = fetch_institutional_holders(ticker)
    if inst is not None and not inst.empty:
        st.markdown("**Top Institutional Holders**")
        display_inst = inst.head(8).copy()
        # Rename columns to PT
        rename_map = {
            "Holder": "Detentor",
            "Shares": "Ações",
            "Date Reported": "Data",
            "% Out": "% Total",
            "pctHeld": "% Total",
            "Value": "Valor ($)",
        }
        display_inst = display_inst.rename(columns=rename_map)
        st.dataframe(display_inst, hide_index=True, use_container_width=True)
    else:
        st.caption("Sem dados institucionais.")

# ============================================================
# Price history
# ============================================================
st.markdown("## Evolução do Preço")
period = st.radio("Período", ["1mo", "6mo", "1y", "2y", "5y", "max"],
                  index=2, horizontal=True)
with st.spinner("A carregar histórico..."):
    hist = fetch_historical((ticker,), period=period)

if not hist.empty:
    prices = hist.iloc[:, 0].dropna()
    pct_change_period = ((prices.iloc[-1] / prices.iloc[0]) - 1) * 100
    period_color = COLORS["gain"] if pct_change_period >= 0 else COLORS["loss"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=prices.index, y=prices.values,
        line=dict(color=COLORS["gain"], width=2),
        fill="tozeroy", fillcolor="rgba(0,212,170,0.06)",
        name=ticker,
    ))
    # 52w high/low
    high_52w = info.get("52w_high")
    low_52w = info.get("52w_low")
    if high_52w:
        fig.add_hline(y=high_52w, line_dash="dot", line_color=COLORS["gain"],
                      annotation_text=f"52w High {high_52w:.0f}",
                      annotation_position="right",
                      annotation_font=dict(size=9, color=COLORS["gain"]))
    if low_52w:
        fig.add_hline(y=low_52w, line_dash="dot", line_color=COLORS["loss"],
                      annotation_text=f"52w Low {low_52w:.0f}",
                      annotation_position="right",
                      annotation_font=dict(size=9, color=COLORS["loss"]))
    # Moving averages
    ma50 = info.get("50d_avg")
    ma200 = info.get("200d_avg")
    if ma50:
        fig.add_hline(y=ma50, line_dash="dash", line_color=COLORS["warn"],
                      opacity=0.5,
                      annotation_text="MA50", annotation_position="left",
                      annotation_font=dict(size=9, color=COLORS["warn"]))
    if ma200:
        fig.add_hline(y=ma200, line_dash="dash", line_color=COLORS["accent"],
                      opacity=0.5,
                      annotation_text="MA200", annotation_position="left",
                      annotation_font=dict(size=9, color=COLORS["accent"]))

    fig.update_layout(
        **PLOTLY_DARK_LAYOUT,
        height=400,
        title=dict(
            text=f"{ticker} — {period} · {pct_change_period:+.2f}%",
            font=dict(size=12, color=period_color),
            x=0.02, xanchor="left",
        ),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

st.markdown("---")
st.caption(
    f"Dados via Yahoo Finance · Cache de 6h para fundamentais · "
    f"Última consulta: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
)
