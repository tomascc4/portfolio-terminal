"""Portfolio risk and performance metrics."""
import numpy as np
import pandas as pd

TRADING_DAYS = 252


def daily_returns(prices: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Calculate daily simple returns."""
    return prices.pct_change().dropna(how="all")


def annualized_return(returns: pd.Series) -> float:
    """Annualized return from a daily return series."""
    if len(returns) == 0:
        return 0.0
    cumulative = (1 + returns).prod()
    years = len(returns) / TRADING_DAYS
    if years <= 0:
        return 0.0
    return cumulative ** (1 / years) - 1


def annualized_volatility(returns: pd.Series) -> float:
    """Annualized volatility from daily returns."""
    return float(returns.std() * np.sqrt(TRADING_DAYS))


def sharpe_ratio(returns: pd.Series, risk_free: float = 0.025) -> float:
    """Sharpe ratio (annualized)."""
    ann_ret = annualized_return(returns)
    vol = annualized_volatility(returns)
    return (ann_ret - risk_free) / vol if vol > 0 else 0.0


def sortino_ratio(returns: pd.Series, risk_free: float = 0.025) -> float:
    """Sortino ratio using downside deviation."""
    ann_ret = annualized_return(returns)
    downside = returns[returns < 0]
    if len(downside) == 0:
        return 0.0
    downside_vol = float(downside.std() * np.sqrt(TRADING_DAYS))
    return (ann_ret - risk_free) / downside_vol if downside_vol > 0 else 0.0


def max_drawdown(prices: pd.Series) -> float:
    """Maximum drawdown from a price series."""
    if len(prices) == 0:
        return 0.0
    running_max = prices.cummax()
    drawdown = (prices - running_max) / running_max
    return float(drawdown.min())


def beta(asset_returns: pd.Series, market_returns: pd.Series) -> float:
    """Beta of asset relative to market."""
    aligned = pd.concat([asset_returns, market_returns], axis=1).dropna()
    if len(aligned) < 2:
        return 1.0
    cov = aligned.cov().iloc[0, 1]
    var = aligned.iloc[:, 1].var()
    return float(cov / var) if var > 0 else 1.0


def alpha_capm(asset_returns: pd.Series, market_returns: pd.Series, risk_free: float = 0.025) -> float:
    """Jensen's alpha (CAPM) — annualized."""
    b = beta(asset_returns, market_returns)
    ann_asset = annualized_return(asset_returns)
    ann_market = annualized_return(market_returns)
    return ann_asset - (risk_free + b * (ann_market - risk_free))


def r_squared(asset_returns: pd.Series, market_returns: pd.Series) -> float:
    """R² between asset and market returns."""
    aligned = pd.concat([asset_returns, market_returns], axis=1).dropna()
    if len(aligned) < 2:
        return 0.0
    corr = aligned.corr().iloc[0, 1]
    return float(corr ** 2)


def portfolio_returns(price_data: pd.DataFrame, weights: dict) -> pd.Series:
    """
    Calculate portfolio daily returns given historical prices and weights.
    weights: dict of {ticker: weight_fraction}
    """
    rets = daily_returns(price_data)
    available = [t for t in weights if t in rets.columns]
    w = np.array([weights[t] for t in available])
    w = w / w.sum() if w.sum() > 0 else w  # normalize
    return (rets[available] * w).sum(axis=1)


def herfindahl_index(weights: np.ndarray | pd.Series) -> float:
    """Concentration index. <0.15 well diversified, >0.25 concentrated."""
    w = np.array(weights) / np.array(weights).sum()
    return float(np.sum(w ** 2))


def interpret_hhi(hhi: float) -> str:
    if hhi < 0.10:
        return "Muito diversificado"
    if hhi < 0.18:
        return "Bem diversificado"
    if hhi < 0.25:
        return "Moderadamente concentrado"
    return "Muito concentrado"


def full_risk_suite(
    portfolio_rets: pd.Series,
    benchmark_rets: pd.Series,
    risk_free: float = 0.025,
) -> dict:
    """Compute the full risk metrics suite for display."""
    cum_prices = (1 + portfolio_rets).cumprod()
    return {
        "annualized_return": annualized_return(portfolio_rets),
        "volatility": annualized_volatility(portfolio_rets),
        "sharpe": sharpe_ratio(portfolio_rets, risk_free),
        "sortino": sortino_ratio(portfolio_rets, risk_free),
        "beta": beta(portfolio_rets, benchmark_rets),
        "alpha": alpha_capm(portfolio_rets, benchmark_rets, risk_free),
        "r_squared": r_squared(portfolio_rets, benchmark_rets),
        "max_drawdown": max_drawdown(cum_prices),
    }
