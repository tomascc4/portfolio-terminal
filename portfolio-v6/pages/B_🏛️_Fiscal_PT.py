"""Fiscal PT — calculadora de mais-valias, simulador, harvesting, resumo anual."""
from datetime import date, datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data import enrich_portfolio, load_portfolio
from utils.styling import COLORS, PLOTLY_DARK_LAYOUT, apply_custom_css
from utils.tax_pt import (
    LIBERATORY_RATE,
    TaxConfig,
    build_lots_from_transactions,
    compute_dividend_tax,
    find_harvest_candidates,
    lots_from_position,
    marginal_irs_rate,
    simulate_sale,
    total_irs_on_income,
    yearly_summary,
)

st.set_page_config(page_title="Fiscal PT", page_icon="🏛️", layout="wide")
apply_custom_css()

st.markdown("# Fiscal PT")
st.caption(
    "Cálculo de mais-valias e dividendos segundo o Código IRS português. "
    "Não substitui um contabilista — é uma estimativa baseada nas regras 2026."
)

portfolio_data = load_portfolio()

# ============================================================
# Configuração fiscal (sidebar)
# ============================================================
with st.sidebar:
    st.markdown("---")
    st.markdown("### Config Fiscal")
    use_agg = st.checkbox(
        "Englobamento", value=False,
        help="Junta as mais-valias aos restantes rendimentos. Só compensa se "
             "rendimento global for baixo (~<€20k).",
    )
    has_w8ben = st.checkbox(
        "W-8BEN preenchido", value=True,
        help="No Revolut Metal está activo por defeito. Reduz retenção EUA "
             "de 30% para 15% em dividendos.",
    )
    other_income = st.number_input(
        "Outros rendimentos taxáveis (€/ano)",
        value=0.0, step=1000.0,
        help="Salário e outros rendimentos para cálculo do englobamento.",
    )

cfg = TaxConfig(
    use_aggregation=use_agg,
    has_w8ben=has_w8ben,
    other_taxable_income=other_income,
)

# ============================================================
# Tabs
# ============================================================
tab_sim, tab_whatif, tab_harvest, tab_div, tab_year = st.tabs([
    "💰 Simulador de Venda",
    "🎯 What-if (preciso de €X)",
    "🌾 Tax-Loss Harvesting",
    "💸 Dividendos",
    "📅 Resumo Anual",
])

# Common: enriched portfolio
with st.spinner("A carregar carteira..."):
    df = enrich_portfolio(portfolio_data).dropna(subset=["current_price"])

transactions = portfolio_data.get("transactions", [])

# ============================================================
# TAB 1 — Simulador de Venda
# ============================================================
with tab_sim:
    st.markdown("### Simular venda parcial ou total")
    st.caption(
        "Escolhe a posição, indica quanto queres vender e a que preço. "
        "Vê o impacto fiscal em ambos os métodos (28% liberatório vs englobamento)."
    )

    if df.empty:
        st.info("Sem posições.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            sim_ticker = st.selectbox("Posição", df["ticker"].tolist(), key="sim_ticker")
        position = df[df["ticker"] == sim_ticker].iloc[0]
        max_qty = float(position["qty"])
        with c2:
            sim_qty = st.number_input(
                "Quantidade a vender", min_value=0.0, max_value=max_qty,
                value=max_qty, step=max_qty / 20, format="%.4f",
            )
        with c3:
            default_price = float(position["price_eur"])
            sim_price = st.number_input(
                f"Preço de venda (€)", min_value=0.0,
                value=default_price, step=0.01, format="%.2f",
            )

        # Build lots
        ticker_txs = [t for t in transactions if t.get("ticker") == sim_ticker]
        if ticker_txs:
            lots = build_lots_from_transactions(transactions, sim_ticker)
            lots_source = f"{len(ticker_txs)} transacções registadas"
        else:
            lots = lots_from_position(position.to_dict())
            lots_source = "Posição agregada (sem histórico de transacções — usa-se o PM)"

        st.caption(f"📋 Origem dos lotes: {lots_source}")

        if sim_qty > 0:
            try:
                # Run both methods for comparison
                cfg_lib = TaxConfig(use_aggregation=False, has_w8ben=cfg.has_w8ben,
                                    other_taxable_income=cfg.other_taxable_income)
                cfg_agg = TaxConfig(use_aggregation=True, has_w8ben=cfg.has_w8ben,
                                    other_taxable_income=cfg.other_taxable_income)
                r_lib = simulate_sale(sim_ticker, sim_qty, sim_price, lots, cfg_lib)
                r_agg = simulate_sale(sim_ticker, sim_qty, sim_price, lots, cfg_agg)

                # Headline: best method
                best = r_lib if r_lib.tax_due <= r_agg.tax_due else r_agg
                worst = r_agg if best == r_lib else r_lib
                savings = worst.tax_due - best.tax_due

                # Hero
                gain_color = COLORS["gain"] if best.gain >= 0 else COLORS["loss"]
                st.markdown(
                    f"""
                    <div style="display:grid; grid-template-columns: repeat(4, 1fr);
                         gap: 14px; margin: 16px 0;">
                        <div style="padding: 14px 18px; background: var(--bg-card);
                             border: 1px solid var(--border); border-radius: 10px;">
                            <div class="dim-text" style="font-size: 0.7rem;
                                 text-transform: uppercase; letter-spacing: 0.1em;">
                                Receita bruta
                            </div>
                            <div style="font-family: var(--font-mono); font-size: 1.3rem;
                                 margin-top: 4px;">€ {best.gross_proceeds:,.2f}</div>
                        </div>
                        <div style="padding: 14px 18px; background: var(--bg-card);
                             border: 1px solid var(--border); border-radius: 10px;">
                            <div class="dim-text" style="font-size: 0.7rem;
                                 text-transform: uppercase; letter-spacing: 0.1em;">
                                Custo (FIFO)
                            </div>
                            <div style="font-family: var(--font-mono); font-size: 1.3rem;
                                 margin-top: 4px;">€ {best.cost_basis:,.2f}</div>
                        </div>
                        <div style="padding: 14px 18px; background: var(--bg-card);
                             border: 1px solid var(--border); border-left: 3px solid {gain_color};
                             border-radius: 10px;">
                            <div class="dim-text" style="font-size: 0.7rem;
                                 text-transform: uppercase; letter-spacing: 0.1em;">
                                Mais/menos-valia
                            </div>
                            <div style="font-family: var(--font-mono); font-size: 1.3rem;
                                 color: {gain_color}; margin-top: 4px;">
                                € {best.gain:+,.2f}
                            </div>
                        </div>
                        <div style="padding: 14px 18px; background: var(--bg-card);
                             border: 1px solid var(--border); border-left: 3px solid {COLORS['accent']};
                             border-radius: 10px;">
                            <div class="dim-text" style="font-size: 0.7rem;
                                 text-transform: uppercase; letter-spacing: 0.1em;">
                                Líquido para ti
                            </div>
                            <div style="font-family: var(--font-mono); font-size: 1.3rem;
                                 color: {COLORS['accent']}; margin-top: 4px;">
                                € {best.net_proceeds:,.2f}
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Method comparison
                st.markdown("#### Comparação de Métodos")
                method_cols = st.columns(2)
                for col, r, label in [
                    (method_cols[0], r_lib, "🔵 Liberatório (28%)"),
                    (method_cols[1], r_agg, "🟣 Englobamento"),
                ]:
                    is_best = (r.tax_due == best.tax_due)
                    border = COLORS["gain"] if is_best else COLORS["border"]
                    badge = ' <span style="background:rgba(0,212,170,0.15); color:#00d4aa; font-size:0.7rem; padding:2px 6px; border-radius:4px; margin-left:6px;">MELHOR</span>' if is_best else ""
                    with col:
                        st.markdown(
                            f"""
                            <div style="padding: 14px 18px; background: var(--bg-card);
                                 border: 1px solid var(--border); border-left: 3px solid {border};
                                 border-radius: 10px;">
                                <div style="font-weight: 600; margin-bottom: 8px;">
                                    {label}{badge}
                                </div>
                                <div style="font-family: var(--font-mono); font-size: 0.85rem;
                                     line-height: 1.7; color: var(--text-dim);">
                                    Imposto: <span style="color: var(--text);">€ {r.tax_due:,.2f}</span><br>
                                    Taxa efectiva: <span style="color: var(--text);">{r.tax_rate_effective*100:.2f}%</span><br>
                                    Líquido: <span style="color: var(--text);">€ {r.net_proceeds:,.2f}</span>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                if savings > 0.50:
                    st.info(
                        f"💡 Escolher **{('Liberatório' if best == r_lib else 'Englobamento')}** "
                        f"poupa-te **€ {savings:.2f}** vs a outra opção."
                    )

                # Holding period
                st.markdown("#### Detalhes")
                d1, d2, d3 = st.columns(3)
                d1.metric("Dias detidos (média ponderada)", f"{best.holding_period_days}")
                long_term = best.holding_period_days >= 365
                d2.metric(
                    "Tratamento", "Longo prazo" if long_term else "Curto prazo",
                    help="Em PT, ambos têm a mesma taxa (28%) — não há benefício "
                         "fiscal de longo prazo como nos EUA.",
                )
                d3.metric("Lotes consumidos (FIFO)", f"{len(best.lots_consumed)}")

                if best.lots_consumed:
                    with st.expander("Ver detalhe dos lotes consumidos"):
                        lot_rows = []
                        for lot, taken in best.lots_consumed:
                            lot_rows.append({
                                "Data compra": lot.date.isoformat(),
                                "PM (€)": lot.price_eur,
                                "Qtd consumida": taken,
                                "Custo (€)": taken * lot.price_eur,
                                "Dias detidos": (date.today() - lot.date).days,
                            })
                        st.dataframe(pd.DataFrame(lot_rows), hide_index=True,
                                     use_container_width=True)
            except Exception as e:
                st.error(f"Erro: {e}")

# ============================================================
# TAB 2 — What-if "preciso de €X"
# ============================================================
with tab_whatif:
    st.markdown("### Preciso de €X líquido — qual a melhor posição para vender?")
    st.caption(
        "Indica o valor líquido que precisas. A app calcula, para cada posição, "
        "quanto terias de vender e qual o impacto fiscal."
    )

    if df.empty:
        st.info("Sem posições.")
    else:
        target = st.number_input(
            "Quanto precisas (€ líquido após imposto)",
            min_value=0.0, value=1000.0, step=100.0,
        )

        if target > 0:
            results = []
            for _, pos in df.iterrows():
                tk = pos["ticker"]
                ticker_txs = [t for t in transactions if t.get("ticker") == tk]
                lots = (build_lots_from_transactions(transactions, tk) if ticker_txs
                        else lots_from_position(pos.to_dict()))
                if not lots:
                    continue

                # Iterative: estimate qty needed
                # Cost basis avg
                total_cost = sum(l.qty * l.price_eur for l in lots)
                total_q = sum(l.qty for l in lots)
                avg_cost_per_unit = total_cost / total_q if total_q else 0
                price_eur = pos["price_eur"]

                # Estimate gain rate per unit sold: (price - cost)
                gain_per_unit = max(0, price_eur - avg_cost_per_unit)
                tax_per_unit = gain_per_unit * LIBERATORY_RATE
                net_per_unit = price_eur - tax_per_unit

                if net_per_unit <= 0:
                    continue

                qty_needed = target / net_per_unit

                if qty_needed > pos["qty"]:
                    # Cannot fulfill from this position alone
                    max_net = pos["qty"] * net_per_unit
                    results.append({
                        "Ticker": tk,
                        "Nome": pos["name"],
                        "Qtd necessária": pos["qty"],
                        "Disponível": pos["qty"],
                        "Líquido obtido": max_net,
                        "Imposto estimado": pos["qty"] * tax_per_unit,
                        "Cobre objectivo": False,
                        "Eficiência fiscal": net_per_unit / price_eur if price_eur else 0,
                    })
                else:
                    try:
                        r = simulate_sale(tk, qty_needed, price_eur, lots, cfg)
                        # Refine: if the simulation gives different net, adjust
                        if r.net_proceeds < target * 0.99:
                            # Need slightly more
                            qty_needed = qty_needed * (target / max(r.net_proceeds, 0.01))
                            qty_needed = min(qty_needed, pos["qty"])
                            r = simulate_sale(tk, qty_needed, price_eur, lots, cfg)
                        results.append({
                            "Ticker": tk,
                            "Nome": pos["name"],
                            "Qtd necessária": qty_needed,
                            "Disponível": pos["qty"],
                            "Líquido obtido": r.net_proceeds,
                            "Imposto estimado": r.tax_due,
                            "Cobre objectivo": True,
                            "Eficiência fiscal": r.net_proceeds / r.gross_proceeds if r.gross_proceeds else 0,
                        })
                    except Exception:
                        continue

            if results:
                results_df = pd.DataFrame(results)
                results_df = results_df.sort_values(
                    ["Cobre objectivo", "Imposto estimado"],
                    ascending=[False, True],
                )
                st.markdown("#### Opções (ordenadas: cobre primeiro, depois menor imposto)")
                st.dataframe(
                    results_df, use_container_width=True, hide_index=True,
                    column_config={
                        "Qtd necessária": st.column_config.NumberColumn(format="%.4f"),
                        "Disponível": st.column_config.NumberColumn(format="%.4f"),
                        "Líquido obtido": st.column_config.NumberColumn(format="€ %.2f"),
                        "Imposto estimado": st.column_config.NumberColumn(format="€ %.2f"),
                        "Eficiência fiscal": st.column_config.ProgressColumn(
                            format="%.1f%%", min_value=0, max_value=1,
                            help="Líquido / Bruto. Quanto maior, menos perdes para impostos.",
                        ),
                    },
                )
                st.caption(
                    "💡 Vender posições com menor mais-valia % é fiscalmente mais eficiente. "
                    "Se nenhuma cobre o objectivo, considera vender de várias posições combinadas."
                )

# ============================================================
# TAB 3 — Tax-Loss Harvesting
# ============================================================
with tab_harvest:
    st.markdown("### Tax-Loss Harvesting")
    st.caption(
        "Identifica posições em prejuízo que podes vender para compensar mais-valias "
        "realizadas no mesmo ano. Em PT, prejuízos podem ser deduzidos a ganhos do mesmo "
        "ano (mesma categoria) ou reportados 5 anos."
    )

    candidates = find_harvest_candidates(df, min_loss_eur=20.0, min_loss_pct=-3.0)

    if candidates.empty:
        st.success("✅ Sem posições em prejuízo significativo. Nada para colher.")
    else:
        st.warning(
            f"📉 Encontradas **{len(candidates)}** posições em prejuízo material."
        )

        total_loss = candidates["pl_eur"].sum()
        potential_offset = abs(total_loss) * LIBERATORY_RATE

        c1, c2 = st.columns(2)
        c1.metric("Prejuízo total realizável", f"€ {total_loss:,.2f}")
        c2.metric("Compensação fiscal potencial",
                  f"€ {potential_offset:,.2f}",
                  help="Se tiveres mais-valias realizadas no ano, este montante "
                       "pode neutralizar o imposto correspondente.",
                  )

        st.markdown("#### Candidatas")
        display = candidates[[
            "ticker", "name", "qty", "avg_price", "current_price",
            "pl_eur", "pl_pct", "weight",
        ]].rename(columns={
            "ticker": "Ticker", "name": "Nome", "qty": "Qtd",
            "avg_price": "PM", "current_price": "Preço",
            "pl_eur": "Prejuízo €", "pl_pct": "Prejuízo %", "weight": "% Cart.",
        })
        st.dataframe(
            display, use_container_width=True, hide_index=True,
            column_config={
                "Qtd": st.column_config.NumberColumn(format="%.4f"),
                "PM": st.column_config.NumberColumn(format="%.2f"),
                "Preço": st.column_config.NumberColumn(format="%.2f"),
                "Prejuízo €": st.column_config.NumberColumn(format="€ %.2f"),
                "Prejuízo %": st.column_config.NumberColumn(format="%.2f%%"),
                "% Cart.": st.column_config.NumberColumn(format="%.2f%%"),
            },
        )
        st.caption(
            "⚠️ **Atenção:** vender só por motivos fiscais pode ser fiscalmente "
            "racional mas estrategicamente mau. Revê a tese da posição antes."
        )

# ============================================================
# TAB 4 — Dividendos
# ============================================================
with tab_div:
    st.markdown("### Calculadora de Dividendos")
    st.caption(
        "Calcula o líquido que recebes de um dividendo, com retenção EUA e IRS PT."
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        div_gross = st.number_input("Dividendo bruto (€)", min_value=0.0,
                                     value=100.0, step=10.0)
    with c2:
        div_country = st.selectbox("País da fonte", ["US", "EU", "UK"])
    with c3:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        st.metric("W-8BEN activo?", "Sim" if cfg.has_w8ben else "Não",
                  help="Configurar na sidebar.")

    if div_gross > 0:
        dt = compute_dividend_tax(div_gross, cfg, source_country=div_country)

        st.markdown("#### Decomposição")
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Bruto declarado", f"€ {dt.gross_eur:.2f}")
        d2.metric("Retenção origem", f"€ {dt.us_withholding:.2f}",
                  f"{(dt.us_withholding/dt.gross_eur*100 if dt.gross_eur else 0):.0f}%")
        d3.metric("IRS adicional PT", f"€ {dt.pt_tax_due:.2f}",
                  help=f"Crédito fiscal aplicado: € {dt.foreign_credit:.2f}")
        d4.metric("Líquido para ti", f"€ {dt.net_eur:.2f}",
                  f"{dt.net_eur/dt.gross_eur*100:.1f}% do bruto")

        # Visual breakdown
        fig = go.Figure(go.Bar(
            x=["Bruto", "Retenção origem", "IRS PT adicional", "Líquido"],
            y=[dt.gross_eur, -dt.us_withholding, -dt.pt_tax_due, dt.net_eur],
            marker_color=[COLORS["accent"], COLORS["loss"], COLORS["loss"], COLORS["gain"]],
            text=[f"€ {v:.2f}" for v in [dt.gross_eur, -dt.us_withholding,
                                          -dt.pt_tax_due, dt.net_eur]],
            textposition="outside",
            textfont=dict(family="JetBrains Mono"),
        ))
        fig.update_layout(**PLOTLY_DARK_LAYOUT, height=280, showlegend=False)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        st.caption(
            f"💡 Para o **Anexo J** do IRS, declara €{dt.gross_eur:.2f} no código "
            f"E11 (dividendos estrangeiros) e €{dt.us_withholding:.2f} como imposto "
            f"pago no estrangeiro (campo 8)."
        )

# ============================================================
# TAB 5 — Resumo Anual
# ============================================================
with tab_year:
    st.markdown("### Resumo Anual")
    st.caption(
        "Mais-valias realizadas no ano civil. Útil para preparar o IRS em Maio/Junho."
    )

    current_year = datetime.now().year
    year = st.selectbox("Ano fiscal", list(range(current_year, current_year - 5, -1)))

    summary = yearly_summary(transactions, year)

    c1, c2, c3 = st.columns(3)
    c1.metric("Mais-valias realizadas", f"€ {summary['realized_total']:,.2f}",
              delta="Tributável" if summary["realized_total"] > 0 else "Sem imposto")
    c2.metric("IRS estimado (28% liberatório)",
              f"€ {summary['tax_estimate_28pct']:,.2f}")
    c3.metric("Nº de vendas", summary["n_sales"])

    if summary["sales"]:
        st.markdown("#### Vendas no ano")
        sales_df = pd.DataFrame(summary["sales"])
        sales_df = sales_df.rename(columns={
            "date": "Data", "ticker": "Ticker", "qty": "Qtd",
            "price_eur": "Preço €", "cost_basis": "Custo €", "gain": "Ganho €",
        })
        st.dataframe(
            sales_df, use_container_width=True, hide_index=True,
            column_config={
                "Qtd": st.column_config.NumberColumn(format="%.4f"),
                "Preço €": st.column_config.NumberColumn(format="€ %.2f"),
                "Custo €": st.column_config.NumberColumn(format="€ %.2f"),
                "Ganho €": st.column_config.NumberColumn(format="€ %.2f"),
            },
        )

        # Anexo J helper
        st.markdown("#### Pré-preenchimento Anexo J (Modelo 3)")
        st.caption(
            "Resumo dos campos para o Anexo J. Confirma sempre com um contabilista "
            "antes de submeter."
        )
        st.code(
            f"""ANEXO J — Rendimentos obtidos no estrangeiro

Quadro 9 — Mais-Valias (código G01)
  País: 840 (EUA) [confirmar consoante origem]
  Valor de realização: € {sum(s['qty']*s['price_eur'] for s in summary['sales']):,.2f}
  Valor de aquisição: € {sum(s['cost_basis'] for s in summary['sales']):,.2f}
  Saldo: € {summary['realized_total']:,.2f}
  Imposto pago no estrangeiro: € 0.00 (mais-valias geralmente não retidas)

Opção tributação: {'Englobamento (Q11)' if cfg.use_aggregation else 'Liberatória 28%'}
""",
            language="text",
        )
    else:
        st.info(f"Sem vendas registadas em {year}. Tudo o que tens está em aberto.")

# ============================================================
# Footer
# ============================================================
st.markdown("---")
st.caption(
    "🏛️ Estimativas baseadas no Código IRS (regras 2026). "
    "Não substitui aconselhamento fiscal profissional. "
    f"Configuração actual: {'Englobamento' if cfg.use_aggregation else 'Liberatório 28%'} · "
    f"W-8BEN: {'✓' if cfg.has_w8ben else '✗'}"
)
