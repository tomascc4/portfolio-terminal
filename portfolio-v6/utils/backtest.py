"""Backtesting engine — simulações retroativas de estratégias de investimento."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    strategy_name: str
    dates: pd.DatetimeIndex
    portfolio_value: pd.Series  # Total value over time
    invested_cumulative: pd.Series  # Cumulative cash invested
    final_value: float
    total_invested: float
    profit: float
    irr_annual: float  # Internal rate of return (annualized)
    max_drawdown: float
    sharpe_ratio: float
    n_purchases: int


def _annualized_irr(values: pd.Series, invested: pd.Series) -> float:
    """Approximation of IRR via CAGR using time-weighted average."""
    if values.empty or invested.iloc[-1] <= 0:
        return 0.0
    final = values.iloc[-1]
    # Use weighted average of investment timing
    days = (values.index[-1] - values.index[0]).days
    years = max(days / 365.25, 0.01)
    avg_invested = invested.mean()
    if avg_invested <= 0:
        return 0.0
    # CAGR-style: ((final / avg_invested) ^ (1/years)) - 1
    ratio = max(final / avg_invested, 0.001)
    return ratio ** (1 / years) - 1


def _max_drawdown(values: pd.Series) -> float:
    if values.empty:
        return 0.0
    running_max = values.cummax()
    dd = (values - running_max) / running_max.replace(0, np.nan)
    return float(dd.min()) if not dd.empty else 0.0


def _sharpe(values: pd.Series, risk_free: float = 0.025) -> float:
    if len(values) < 30:
        return 0.0
    rets = values.pct_change().dropna()
    if rets.std() == 0:
        return 0.0
    annual_return = (1 + rets.mean()) ** 252 - 1
    annual_vol = rets.std() * np.sqrt(252)
    return (annual_return - risk_free) / annual_vol if annual_vol > 0 else 0.0


def backtest_dca(
    prices: pd.DataFrame,
    weights: dict[str, float],
    monthly_contribution: float,
    initial_capital: float = 0.0,
    frequency_days: int = 21,  # ~3 weeks (matches user's DCA)
) -> BacktestResult:
    """
    Backtest a Dollar-Cost Averaging strategy.

    prices: DataFrame with daily prices, columns = tickers
    weights: dict {ticker: weight_fraction} — must sum to ~1.0
    monthly_contribution: cash invested per period (scaled to frequency)
    frequency_days: trading days between purchases (21 ~ monthly, 14 ~ biweekly)
    """
    if prices.empty:
        raise ValueError("Sem dados de preços.")

    # Normalize weights
    total_w = sum(weights.values())
    weights = {k: v / total_w for k, v in weights.items()}

    # Per-period contribution (scaled from monthly to chosen freq)
    contribution_per_period = monthly_contribution * (frequency_days / 21)

    # Simulate
    holdings = {t: 0.0 for t in weights}  # qty per ticker
    portfolio_value = []
    invested_cumulative = []
    cumulative = initial_capital
    n_purchases = 0

    # Allocate initial capital at first day
    if initial_capital > 0:
        first_prices = prices.iloc[0]
        for t, w in weights.items():
            if t in first_prices and first_prices[t] > 0:
                holdings[t] += (initial_capital * w) / first_prices[t]

    last_purchase_idx = -frequency_days  # Force first purchase

    for i, (dt, row) in enumerate(prices.iterrows()):
        # Time to buy?
        if i - last_purchase_idx >= frequency_days:
            for t, w in weights.items():
                if t in row and not pd.isna(row[t]) and row[t] > 0:
                    cash_for_ticker = contribution_per_period * w
                    holdings[t] += cash_for_ticker / row[t]
            cumulative += contribution_per_period
            last_purchase_idx = i
            n_purchases += 1

        # Mark to market
        value = sum(
            holdings[t] * row[t] for t in holdings
            if t in row and not pd.isna(row[t])
        )
        portfolio_value.append(value)
        invested_cumulative.append(cumulative)

    pv = pd.Series(portfolio_value, index=prices.index)
    ic = pd.Series(invested_cumulative, index=prices.index)

    return BacktestResult(
        strategy_name="DCA",
        dates=prices.index,
        portfolio_value=pv,
        invested_cumulative=ic,
        final_value=pv.iloc[-1],
        total_invested=ic.iloc[-1],
        profit=pv.iloc[-1] - ic.iloc[-1],
        irr_annual=_annualized_irr(pv, ic),
        max_drawdown=_max_drawdown(pv),
        sharpe_ratio=_sharpe(pv),
        n_purchases=n_purchases,
    )


def backtest_lump_sum(
    prices: pd.DataFrame,
    weights: dict[str, float],
    capital: float,
) -> BacktestResult:
    """Backtest investing all capital at the start."""
    if prices.empty:
        raise ValueError("Sem dados de preços.")

    total_w = sum(weights.values())
    weights = {k: v / total_w for k, v in weights.items()}

    first_prices = prices.iloc[0]
    holdings = {}
    for t, w in weights.items():
        if t in first_prices and first_prices[t] > 0:
            holdings[t] = (capital * w) / first_prices[t]
        else:
            holdings[t] = 0

    portfolio_value = []
    invested_cumulative = []
    for _, row in prices.iterrows():
        value = sum(
            holdings[t] * row[t] for t in holdings
            if t in row and not pd.isna(row[t])
        )
        portfolio_value.append(value)
        invested_cumulative.append(capital)

    pv = pd.Series(portfolio_value, index=prices.index)
    ic = pd.Series(invested_cumulative, index=prices.index)

    return BacktestResult(
        strategy_name="Lump Sum",
        dates=prices.index,
        portfolio_value=pv,
        invested_cumulative=ic,
        final_value=pv.iloc[-1],
        total_invested=capital,
        profit=pv.iloc[-1] - capital,
        irr_annual=_annualized_irr(pv, ic),
        max_drawdown=_max_drawdown(pv),
        sharpe_ratio=_sharpe(pv),
        n_purchases=1,
    )


def backtest_buy_the_dip(
    prices: pd.DataFrame,
    weights: dict[str, float],
    monthly_contribution: float,
    drawdown_threshold: float = -0.10,  # Buy when index drops 10% from recent high
    cash_drag_rate: float = 0.02,  # Annual yield on cash held while waiting
) -> BacktestResult:
    """
    Buy-the-dip strategy: accumulate cash and only deploy when there's a drawdown.
    Uses the equally-weighted basket as proxy for "the index".
    """
    if prices.empty:
        raise ValueError("Sem dados de preços.")

    total_w = sum(weights.values())
    weights = {k: v / total_w for k, v in weights.items()}

    # Equal-weighted basket as drawdown signal
    basket = (prices * pd.Series(weights)).sum(axis=1)
    basket_max = basket.expanding().max()
    drawdown = (basket - basket_max) / basket_max

    holdings = {t: 0.0 for t in weights}
    cash = 0.0
    portfolio_value = []
    invested_cumulative = []
    cumulative = 0.0
    n_purchases = 0

    daily_cash_yield = (1 + cash_drag_rate) ** (1 / 252) - 1

    # Add monthly contribution every ~21 days
    last_contrib_idx = -21
    for i, (dt, row) in enumerate(prices.iterrows()):
        # Add cash monthly
        if i - last_contrib_idx >= 21:
            cash += monthly_contribution
            cumulative += monthly_contribution
            last_contrib_idx = i

        # Yield on cash
        cash *= (1 + daily_cash_yield)

        # If in drawdown, deploy cash
        if drawdown.iloc[i] <= drawdown_threshold and cash > monthly_contribution * 0.5:
            for t, w in weights.items():
                if t in row and not pd.isna(row[t]) and row[t] > 0:
                    cash_for_ticker = cash * w
                    holdings[t] += cash_for_ticker / row[t]
            cash = 0
            n_purchases += 1

        value = cash + sum(
            holdings[t] * row[t] for t in holdings
            if t in row and not pd.isna(row[t])
        )
        portfolio_value.append(value)
        invested_cumulative.append(cumulative)

    pv = pd.Series(portfolio_value, index=prices.index)
    ic = pd.Series(invested_cumulative, index=prices.index)

    return BacktestResult(
        strategy_name=f"Buy-the-Dip ({drawdown_threshold*100:.0f}%)",
        dates=prices.index,
        portfolio_value=pv,
        invested_cumulative=ic,
        final_value=pv.iloc[-1],
        total_invested=ic.iloc[-1],
        profit=pv.iloc[-1] - ic.iloc[-1],
        irr_annual=_annualized_irr(pv, ic),
        max_drawdown=_max_drawdown(pv),
        sharpe_ratio=_sharpe(pv),
        n_purchases=n_purchases,
    )


# ==================== Rolling returns ====================

def rolling_returns(prices: pd.Series, window_years: int = 3) -> pd.Series:
    """All overlapping N-year returns from a price series."""
    if len(prices) < window_years * 252:
        return pd.Series(dtype=float)
    window = window_years * 252
    rolling = (prices / prices.shift(window)) ** (1 / window_years) - 1
    return rolling.dropna()


# ==================== Stress tests ====================

# Known crisis periods for stress testing
CRISIS_PERIODS = {
    "COVID Crash (Fev-Mar 2020)": ("2020-02-19", "2020-03-23"),
    "Bear Market 2022 (Jan-Out 2022)": ("2022-01-03", "2022-10-12"),
    "Lehman / GFC (Set-Nov 2008)": ("2008-09-15", "2008-11-20"),
    "Dot-com Bottom (Mar 2000-Out 2002)": ("2000-03-24", "2002-10-09"),
    "Volmageddon (Fev 2018)": ("2018-01-26", "2018-02-08"),
    "China Devaluation (Ago 2015)": ("2015-08-17", "2015-08-25"),
    "Brexit (Jun 2016)": ("2016-06-23", "2016-06-27"),
}


def stress_test(prices: pd.DataFrame, weights: dict[str, float],
                start: str, end: str) -> dict:
    """Calculate portfolio drawdown during a specific period."""
    try:
        period_prices = prices[start:end]
    except (KeyError, IndexError):
        return {"available": False}
    if period_prices.empty or len(period_prices) < 2:
        return {"available": False}

    # Equal-weighted portfolio value (normalized to 100)
    total_w = sum(weights.values())
    norm_weights = {k: v / total_w for k, v in weights.items()}
    available_tickers = [t for t in norm_weights if t in period_prices.columns]

    if not available_tickers:
        return {"available": False}

    # Re-normalize weights to available tickers
    avail_weight_sum = sum(norm_weights[t] for t in available_tickers)
    re_norm = {t: norm_weights[t] / avail_weight_sum for t in available_tickers}

    # Calculate per-asset returns and weighted portfolio
    rets = period_prices[available_tickers].pct_change().fillna(0)
    portfolio_rets = (rets * pd.Series(re_norm)).sum(axis=1)
    portfolio_value = (1 + portfolio_rets).cumprod() * 100

    peak = portfolio_value.iloc[0]
    trough = portfolio_value.min()
    final = portfolio_value.iloc[-1]
    drawdown = (trough / peak - 1) * 100

    return {
        "available": True,
        "start_value": peak,
        "trough_value": trough,
        "final_value": final,
        "max_drawdown_pct": drawdown,
        "total_return_pct": (final / peak - 1) * 100,
        "n_days": len(portfolio_value),
        "tickers_available": len(available_tickers),
        "tickers_total": len(weights),
    }
