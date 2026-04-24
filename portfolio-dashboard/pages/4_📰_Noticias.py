"""Notícias — feed automático via Yahoo Finance por ticker."""
from datetime import datetime

import streamlit as st

from utils.data import fetch_news, load_portfolio
from utils.styling import COLORS, apply_custom_css

st.set_page_config(page_title="Notícias", page_icon="📰", layout="wide")
apply_custom_css()

st.markdown("# Notícias")
st.caption("Feed de notícias recentes via Yahoo Finance, agrupadas por ticker.")

portfolio_data = load_portfolio()
holdings_tickers = [p["ticker"] for p in portfolio_data["positions"]]
watchlist_tickers = [w["ticker"] for w in portfolio_data.get("watchlist", [])]
all_tickers = sorted(set(holdings_tickers + watchlist_tickers))

# ---------- Filters ----------
c1, c2 = st.columns([2, 1])
with c1:
    selected = st.multiselect(
        "Filtrar tickers",
        all_tickers,
        default=all_tickers[:8],
        help="Seleciona os tickers para ver notícias (limitado aos principais para não sobrecarregar)",
    )
with c2:
    per_ticker = st.slider("Notícias por ticker", 1, 10, 4)

if not selected:
    st.info("Escolhe pelo menos um ticker.")
    st.stop()

# ---------- Fetch and render ----------
with st.spinner("A buscar notícias..."):
    all_news = []
    for t in selected:
        news_items = fetch_news(t, limit=per_ticker)
        for item in news_items:
            item["ticker"] = t
            all_news.append(item)

# Sort by date (if available)
def parse_date(d):
    try:
        if isinstance(d, str) and len(d) >= 10:
            # Try common formats
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ"):
                try:
                    return datetime.strptime(d[:16], fmt)
                except ValueError:
                    continue
    except Exception:
        pass
    return datetime.min

all_news.sort(key=lambda x: parse_date(x.get("published", "")), reverse=True)

if not all_news:
    st.warning(
        "Não foi possível obter notícias neste momento. "
        "Yahoo Finance pode estar com rate-limit. Tenta recarregar daqui a alguns minutos."
    )
else:
    # Group visually but show chronologically
    tabs = st.tabs(["📰 Todas"] + [f"📌 {t}" for t in selected])

    with tabs[0]:
        st.caption(f"{len(all_news)} artigos — ordenados por data")
        for item in all_news:
            pub = item.get("published", "")
            title = item.get("title", "—")
            publisher = item.get("publisher", "—")
            link = item.get("link", "#")
            ticker = item.get("ticker", "")
            summary = item.get("summary", "")
            summary_html = (
                f'<div style="color: var(--text-dim); font-size:0.85rem; '
                f'margin-top:6px; line-height:1.5;">{summary[:200]}'
                f'{"..." if len(summary) > 200 else ""}</div>'
            ) if summary else ""

            st.markdown(
                f"""
                <a href="{link}" target="_blank" style="text-decoration:none; color:inherit;">
                <div style="
                    background: var(--bg-card);
                    border: 1px solid var(--border);
                    border-left: 3px solid {COLORS['accent']};
                    border-radius: 8px;
                    padding: 12px 16px;
                    margin-bottom: 8px;
                    transition: border-color 0.2s;
                    cursor: pointer;
                " onmouseover="this.style.borderColor='#2a3651'"
                  onmouseout="this.style.borderColor='#1f2a3d'">
                  <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                    <span class="badge badge-etf" style="font-family: var(--font-mono);">{ticker}</span>
                    <span class="dim-text" style="font-size:0.72rem;">
                        {publisher} · {pub}
                    </span>
                  </div>
                  <div style="font-size:0.95rem; font-weight:500; color: var(--text);">
                    {title}
                  </div>
                  {summary_html}
                </div>
                </a>
                """,
                unsafe_allow_html=True,
            )

    # Per-ticker tabs
    for i, ticker in enumerate(selected):
        with tabs[i + 1]:
            ticker_news = [n for n in all_news if n.get("ticker") == ticker]
            if not ticker_news:
                st.info(f"Sem notícias recentes para {ticker}")
                continue
            for item in ticker_news:
                pub = item.get("published", "")
                title = item.get("title", "—")
                publisher = item.get("publisher", "—")
                link = item.get("link", "#")
                summary = item.get("summary", "")
                summary_html = (
                    f'<div style="color: var(--text-dim); font-size:0.85rem; '
                    f'margin-top:6px; line-height:1.5;">{summary[:300]}'
                    f'{"..." if len(summary) > 300 else ""}</div>'
                ) if summary else ""

                st.markdown(
                    f"""
                    <a href="{link}" target="_blank" style="text-decoration:none; color:inherit;">
                    <div style="
                        background: var(--bg-card);
                        border: 1px solid var(--border);
                        border-radius: 8px;
                        padding: 14px 18px;
                        margin-bottom: 8px;
                    ">
                      <div class="dim-text" style="font-size:0.72rem; margin-bottom:4px;">
                          {publisher} · {pub}
                      </div>
                      <div style="font-size:1rem; font-weight:500; color: var(--text);">
                        {title}
                      </div>
                      {summary_html}
                    </div>
                    </a>
                    """,
                    unsafe_allow_html=True,
                )

st.caption(
    "Fonte: Yahoo Finance (feed público). Cache de 30 min para não sobrecarregar. "
    "Clica num artigo para abrir no browser."
)
