"""Cálculos fiscais portugueses para investimentos.

Regras 2026 (Código IRS, Categoria E e G):

CATEGORIA E (Rendimentos de Capitais — dividendos, juros)
- Tributação liberatória: 28% (taxa única)
- OU englobamento opcional: somam aos restantes rendimentos, taxa marginal IRS
- Englobamento normalmente só compensa se rendimento global é baixo (<~€20k)
- Dividendos de empresas EUA têm retenção na fonte de 15% (com W-8BEN)
- Esses 15% dão direito a crédito de imposto em PT (Anexo J, código E11)

CATEGORIA G (Mais-Valias — ganhos de capital em valores mobiliários)
- Tributação liberatória: 28% sobre ganho líquido (mais-valias - menos-valias do ano)
- OU englobamento opcional
- A partir de 2023: para activos detidos > 1 ano, é OBRIGATÓRIO englobamento se
  rendimento colectável > €78.834 (último escalão IRS)
- Método FIFO obrigatório (First In, First Out) para cálculo da mais-valia
- Câmbio à data da operação (compra e venda separadamente)
- Despesas associadas (corretagem) são deduzíveis

ANEXO J — Rendimentos obtidos no estrangeiro
- Obrigatório para Revolut (broker irlandês mas custódia internacional)
- Código E11: dividendos de fonte estrangeira
- Código G01: mais-valias de valores mobiliários
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

import pandas as pd


# Tax rates 2026
LIBERATORY_RATE = 0.28
US_DIVIDEND_WITHHOLDING_W8BEN = 0.15
US_DIVIDEND_WITHHOLDING_NO_W8BEN = 0.30

# IRS marginal rates 2026 (escalões aproximados, ajustar quando OE 2026 for publicado)
IRS_BRACKETS_2026 = [
    # (limit, rate)
    (8059, 0.1325),
    (12160, 0.18),
    (17233, 0.23),
    (22306, 0.26),
    (28400, 0.3275),
    (41629, 0.37),
    (44987, 0.4350),
    (83696, 0.4500),
    (float("inf"), 0.4800),
]


@dataclass
class TaxConfig:
    """User's fiscal configuration."""
    use_aggregation: bool = False  # Englobamento
    has_w8ben: bool = True  # Reduces US withholding to 15%
    other_taxable_income: float = 0.0  # Income from other sources (salary, etc.)
    realized_losses_carryforward: float = 0.0  # Prejuízos a recuperar


@dataclass
class Lot:
    """A single buy lot for FIFO tracking."""
    date: date
    qty: float
    price_eur: float  # Already in EUR at the date of purchase

    @property
    def cost(self) -> float:
        return self.qty * self.price_eur


@dataclass
class SaleResult:
    """Output of simulating a sale."""
    ticker: str
    qty_sold: float
    sale_price_eur: float
    gross_proceeds: float  # qty * price
    cost_basis: float  # FIFO cost
    gain: float  # gross - cost
    tax_due: float
    net_proceeds: float  # gross - tax
    tax_rate_effective: float
    method: str  # "liberatory" or "aggregation"
    holding_period_days: int  # average weighted
    lots_consumed: list[tuple[Lot, float]]  # (lot, qty_taken)


# ==================== Helpers ====================

def marginal_irs_rate(income: float) -> float:
    """Marginal rate for the LAST euro of income at this level."""
    for limit, rate in IRS_BRACKETS_2026:
        if income <= limit:
            return rate
    return IRS_BRACKETS_2026[-1][1]


def total_irs_on_income(income: float) -> float:
    """Calculate total IRS due via aggregation (progressive brackets)."""
    if income <= 0:
        return 0.0
    tax = 0.0
    prev_limit = 0.0
    for limit, rate in IRS_BRACKETS_2026:
        slice_income = min(income, limit) - prev_limit
        if slice_income <= 0:
            break
        tax += slice_income * rate
        prev_limit = limit
        if income <= limit:
            break
    return tax


# ==================== FIFO Lot Builder ====================

def build_lots_from_transactions(
    transactions: list[dict],
    ticker: str,
    eurusd_at_date: dict | None = None,
) -> list[Lot]:
    """
    Build a FIFO lot list from the transactions log for a given ticker.
    eurusd_at_date: optional {date_str: rate} for historical FX. If None,
    assumes price already in EUR (which it is for our portfolio.json).
    """
    lots: list[Lot] = []
    for tx in transactions:
        if tx.get("ticker") != ticker:
            continue

        tx_date_raw = tx.get("date", "")
        try:
            tx_date = pd.to_datetime(tx_date_raw).date()
        except Exception:
            tx_date = date.today()

        qty = float(tx.get("qty", 0))
        price = float(tx.get("price", 0))
        currency = tx.get("currency", "EUR")

        # Convert to EUR if needed
        if currency != "EUR" and eurusd_at_date:
            rate = eurusd_at_date.get(tx_date_raw[:10], 1.10)
            price_eur = price / rate if currency == "USD" else price
        else:
            price_eur = price  # Assume already EUR

        action = tx.get("action", "BUY").upper()

        if action == "BUY":
            lots.append(Lot(date=tx_date, qty=qty, price_eur=price_eur))
        elif action == "SELL":
            # Consume FIFO
            remaining = qty
            new_lots = []
            for lot in lots:
                if remaining <= 0:
                    new_lots.append(lot)
                    continue
                take = min(lot.qty, remaining)
                if lot.qty - take > 1e-9:
                    new_lots.append(Lot(date=lot.date, qty=lot.qty - take,
                                        price_eur=lot.price_eur))
                remaining -= take
            lots = new_lots

    return lots


def lots_from_position(position: dict) -> list[Lot]:
    """
    Fallback: when there are no granular transactions, treat the position as
    a single lot with the avg_price.
    """
    avg_price = float(position.get("avg_price", 0))
    qty = float(position.get("qty", 0))
    currency = position.get("currency", "EUR")

    # Assume PM is in EUR (which is what user stores)
    if currency == "EUR":
        price_eur = avg_price
    else:
        # Conservative assumption — we don't have the historical FX so use current
        # User can override by using the transactions log for accurate tracking
        price_eur = avg_price  # caller should warn

    # Use today as date (lacking better info)
    return [Lot(date=date.today(), qty=qty, price_eur=price_eur)]


# ==================== Sale Simulation ====================

def simulate_sale(
    ticker: str,
    qty_to_sell: float,
    sale_price_eur: float,
    lots: list[Lot],
    cfg: TaxConfig,
    annual_realized_gains: float = 0.0,
) -> SaleResult:
    """Simulate selling qty units at sale_price_eur, using FIFO."""
    if not lots:
        raise ValueError("Sem lotes disponíveis para venda.")

    total_qty_available = sum(lot.qty for lot in lots)
    if qty_to_sell > total_qty_available + 1e-6:
        raise ValueError(
            f"Quantidade pedida ({qty_to_sell}) excede disponível ({total_qty_available})."
        )

    # FIFO consumption
    remaining = qty_to_sell
    consumed: list[tuple[Lot, float]] = []
    cost_basis = 0.0
    weighted_holding_days = 0.0
    today = date.today()

    for lot in lots:
        if remaining <= 0:
            break
        take = min(lot.qty, remaining)
        consumed.append((lot, take))
        cost_basis += take * lot.price_eur
        weighted_holding_days += take * (today - lot.date).days
        remaining -= take

    avg_holding = (weighted_holding_days / qty_to_sell) if qty_to_sell > 0 else 0
    gross = qty_to_sell * sale_price_eur
    gain = gross - cost_basis

    # Apply year-to-date offset (losses in same year reduce gain)
    taxable_gain = max(0, gain + min(0, annual_realized_gains))

    if cfg.use_aggregation:
        # Aggregation: gain joins other income at progressive rates
        new_total_income = cfg.other_taxable_income + taxable_gain
        old_tax = total_irs_on_income(cfg.other_taxable_income)
        new_tax = total_irs_on_income(new_total_income)
        tax_due = new_tax - old_tax
        method = "aggregation"
    else:
        tax_due = max(0, taxable_gain) * LIBERATORY_RATE
        method = "liberatory"

    # Carryforward losses can offset gains
    if gain < 0:
        tax_due = 0  # losses don't generate tax

    effective_rate = (tax_due / gain) if gain > 0 else 0

    return SaleResult(
        ticker=ticker,
        qty_sold=qty_to_sell,
        sale_price_eur=sale_price_eur,
        gross_proceeds=gross,
        cost_basis=cost_basis,
        gain=gain,
        tax_due=tax_due,
        net_proceeds=gross - tax_due,
        tax_rate_effective=effective_rate,
        method=method,
        holding_period_days=int(avg_holding),
        lots_consumed=consumed,
    )


# ==================== Dividend tax ====================

@dataclass
class DividendTax:
    gross_eur: float
    us_withholding: float  # already withheld at source
    pt_tax_due: float  # additional PT tax after foreign credit
    net_eur: float
    foreign_credit: float


def compute_dividend_tax(
    gross_dividend_eur: float,
    cfg: TaxConfig,
    source_country: Literal["US", "EU", "UK"] = "US",
) -> DividendTax:
    """
    Compute tax on a dividend received from foreign source.
    Assumes the gross amount is BEFORE any withholding (i.e. the actual dividend
    declared by the company, not what landed in your account).
    """
    # Step 1: foreign withholding
    if source_country == "US":
        wh_rate = (US_DIVIDEND_WITHHOLDING_W8BEN if cfg.has_w8ben
                   else US_DIVIDEND_WITHHOLDING_NO_W8BEN)
    elif source_country == "UK":
        wh_rate = 0.0  # UK doesn't withhold on most dividends
    else:
        wh_rate = 0.0  # depends, conservative

    foreign_wh = gross_dividend_eur * wh_rate

    # Step 2: PT tax @ 28%, BUT we get credit for foreign withholding (DTT)
    pt_tax_rate = LIBERATORY_RATE
    pt_tax_gross = gross_dividend_eur * pt_tax_rate

    # Foreign tax credit limited to what PT would have charged
    foreign_credit = min(foreign_wh, pt_tax_gross)
    pt_tax_due = max(0, pt_tax_gross - foreign_credit)

    net = gross_dividend_eur - foreign_wh - pt_tax_due

    return DividendTax(
        gross_eur=gross_dividend_eur,
        us_withholding=foreign_wh,
        pt_tax_due=pt_tax_due,
        net_eur=net,
        foreign_credit=foreign_credit,
    )


# ==================== Tax-loss harvesting ====================

def find_harvest_candidates(positions_df: pd.DataFrame,
                             min_loss_eur: float = 50.0,
                             min_loss_pct: float = -5.0) -> pd.DataFrame:
    """
    Identify positions in loss that could be sold to offset realized gains.
    """
    candidates = positions_df[
        (positions_df["pl_eur"] < -min_loss_eur)
        & (positions_df["pl_pct"] < min_loss_pct)
    ].copy()
    candidates = candidates.sort_values("pl_eur")
    return candidates


# ==================== Annual summary ====================

def yearly_summary(transactions: list[dict], year: int,
                   eurusd_today: float = 1.17) -> dict:
    """
    Compute realized gains/losses + activity for a calendar year.
    Returns dict with summary stats. Uses FIFO across the full history.
    """
    by_ticker: dict[str, list[dict]] = {}
    for tx in transactions:
        by_ticker.setdefault(tx["ticker"], []).append(tx)

    realized_total = 0.0
    sales_in_year: list[dict] = []

    for ticker, txs in by_ticker.items():
        # Sort by date
        txs_sorted = sorted(txs, key=lambda x: x.get("date", ""))
        lots: list[Lot] = []

        for tx in txs_sorted:
            tx_date = pd.to_datetime(tx.get("date", "")).date()
            qty = float(tx.get("qty", 0))
            price = float(tx.get("price", 0))
            currency = tx.get("currency", "EUR")

            # Convert to EUR (rough — using current fx as fallback)
            price_eur = price if currency == "EUR" else price / eurusd_today

            if tx.get("action", "BUY").upper() == "BUY":
                lots.append(Lot(date=tx_date, qty=qty, price_eur=price_eur))
            else:  # SELL
                remaining = qty
                cost = 0.0
                while remaining > 0 and lots:
                    lot = lots[0]
                    take = min(lot.qty, remaining)
                    cost += take * lot.price_eur
                    if lot.qty - take > 1e-9:
                        lots[0] = Lot(date=lot.date, qty=lot.qty - take,
                                      price_eur=lot.price_eur)
                    else:
                        lots.pop(0)
                    remaining -= take

                gross = qty * price_eur
                gain = gross - cost

                if tx_date.year == year:
                    realized_total += gain
                    sales_in_year.append({
                        "date": tx_date.isoformat(),
                        "ticker": ticker,
                        "qty": qty,
                        "price_eur": price_eur,
                        "cost_basis": cost,
                        "gain": gain,
                    })

    return {
        "year": year,
        "realized_total": realized_total,
        "tax_estimate_28pct": max(0, realized_total) * LIBERATORY_RATE,
        "n_sales": len(sales_in_year),
        "sales": sales_in_year,
    }
