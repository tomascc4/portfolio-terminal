"""Teses — editor de teses de investimento por posição.
Não usa LLM — só guarda e organiza. Quando quiseres análise, copias para o Claude."""
from datetime import datetime

import streamlit as st

from utils.data import load_portfolio, save_portfolio
from utils.styling import COLORS, apply_custom_css

st.set_page_config(page_title="Teses", page_icon="📜", layout="wide")
apply_custom_css()

st.markdown("# Teses de Investimento")
st.caption(
    "Documenta porque entraste em cada posição, que catalysts esperas, e o que te "
    "faria sair. Útil para te manteres honesto e para análise periódica com Claude."
)

portfolio_data = load_portfolio()
holdings = [p["ticker"] for p in portfolio_data["positions"]]

if "theses" not in portfolio_data:
    portfolio_data["theses"] = {}

# ============================================================
# Summary: which positions have theses?
# ============================================================
themed = set(portfolio_data["theses"].keys())
without = [t for t in holdings if t not in themed]

c1, c2, c3 = st.columns(3)
c1.metric("Posições", f"{len(holdings)}")
c2.metric("Com tese", f"{len(themed)}", f"{len(themed)/max(1,len(holdings))*100:.0f}%")
c3.metric("Sem tese", f"{len(without)}")

if without:
    st.markdown(
        f"""
        <div style="padding: 10px 14px; background: var(--bg-card);
             border-left: 3px solid {COLORS['warn']}; border-radius: 6px;
             font-size: 0.85rem;">
        ⚠️ Posições sem tese documentada: <b>{', '.join(without)}</b>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# Editor
# ============================================================
st.markdown("## Editor")

if not holdings:
    st.info("Sem posições para anotar.")
    st.stop()

ticker = st.selectbox("Posição", holdings, key="tese_ticker")

current = portfolio_data["theses"].get(ticker, {})
existing_text = current.get("text", "")
existing_date = current.get("date", "")

if existing_date:
    st.caption(f"Última actualização: **{existing_date}**")

new_text = st.text_area(
    "Tese de investimento",
    value=existing_text,
    height=320,
    placeholder=(
        "Estrutura sugerida:\n\n"
        "## Por que entrei\n"
        "...\n\n"
        "## Catalysts esperados (próximos 6-12 meses)\n"
        "- ...\n- ...\n\n"
        "## Riscos principais\n"
        "- ...\n- ...\n\n"
        "## Sair se...\n"
        "- (ex: revenue growth cair abaixo de 20% YoY)\n"
        "- (ex: margem operacional comprimir abaixo de 25%)\n"
        "- (ex: stop a $X)\n\n"
        "## Notas adicionais\n"
        "..."
    ),
)

c1, c2, c3 = st.columns([1, 1, 4])
with c1:
    if st.button("💾 Guardar", type="primary", use_container_width=True):
        if not new_text.strip():
            st.error("Escreve algo antes de guardar.")
        else:
            portfolio_data.setdefault("theses", {})[ticker] = {
                "text": new_text,
                "date": datetime.now().isoformat(timespec="minutes"),
            }
            save_portfolio(portfolio_data)
            st.success(f"✅ Tese de {ticker} guardada.")
            st.rerun()

with c2:
    if existing_text and st.button("🗑️ Apagar", use_container_width=True):
        portfolio_data["theses"].pop(ticker, None)
        save_portfolio(portfolio_data)
        st.success(f"Tese de {ticker} apagada.")
        st.rerun()

# ============================================================
# Export-for-Claude block
# ============================================================
if existing_text:
    st.markdown("## Para análise externa")
    st.caption(
        "Copia este bloco para o Claude (ou outro LLM) quando quiseres uma "
        "segunda opinião sobre a tese. Inclui dados actuais da empresa."
    )

    from utils.data import enrich_portfolio, fetch_company_info, fetch_news

    with st.spinner("A reunir contexto..."):
        df = enrich_portfolio(portfolio_data)
        position_row = df[df["ticker"] == ticker]
        info = fetch_company_info(ticker)
        news = fetch_news(ticker, limit=5)

    if not position_row.empty and info:
        r = position_row.iloc[0]
        price = info.get("current_price")
        target = info.get("target_mean")
        upside_str = ""
        if target and price:
            upside_str = f" ({((target/price-1)*100):+.1f}% upside)"

        news_lines = "\n".join([
            f"  - [{n.get('published','?')}] {n['title']}"
            for n in news[:5]
        ])

        export_block = f"""Avalia se a minha tese de investimento sobre {ticker} se está a sustentar, dados estes inputs.

# Tese original (escrita em {existing_date})
{new_text}

# Estado actual da empresa ({info.get('name', ticker)})
- Preço: {price} {info.get('currency', 'USD')}
- Market Cap: ${(info.get('market_cap') or 0)/1e9:.1f}B
- P/E trailing: {info.get('trailing_pe')}
- P/E forward: {info.get('forward_pe')}
- PEG: {info.get('peg_ratio')}
- Revenue Growth YoY: {(info.get('revenue_growth') or 0)*100:.1f}%
- Earnings Growth YoY: {(info.get('earnings_growth') or 0)*100:.1f}%
- Gross Margin: {(info.get('gross_margin') or 0)*100:.1f}%
- Operating Margin: {(info.get('operating_margin') or 0)*100:.1f}%
- Analyst target médio: {target}{upside_str}
- Recomendação: {info.get('recommendation', '—')} ({info.get('num_analysts', 0)} analistas)
- 52w range: {info.get('52w_low')} – {info.get('52w_high')}
- Beta: {info.get('beta')}

# A minha posição
- Quantidade: {r['qty']:.4f}
- PM: {r['avg_price']:.2f} {r['currency']}
- P/L atual: €{r['pl_eur']:.2f} ({r['pl_pct']:+.2f}%)
- Peso na carteira: {r['weight']:.2f}%
- Stop: {r['stop'] or 'sem stop'}
- TP: {r['take_profit'] or 'sem TP'}

# Notícias recentes
{news_lines}

Responde:
1. Veredicto (a sustentar-se / sinais mistos / a partir-se) com racional curto
2. O que está a favor (bullets com números)
3. O que está contra (bullets com números)
4. Sugestão de acção (manter / rever / reduzir / sair / aumentar)"""

        st.code(export_block, language="markdown")

# ============================================================
# Visão geral de todas as teses
# ============================================================
if portfolio_data["theses"]:
    st.markdown("## Todas as Teses")
    st.caption("Vista rápida de todas as teses guardadas, ordenadas por data.")

    sorted_theses = sorted(
        portfolio_data["theses"].items(),
        key=lambda x: x[1].get("date", ""),
        reverse=True,
    )
    for tk, t in sorted_theses:
        with st.expander(f"**{tk}** — actualizada em {t.get('date', '?')}"):
            st.markdown(t.get("text", ""))
