"""Scanner engine — aplica filtros ao universo e devolve tickers qualificados."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from utils.data import fetch_company_info

UNIVERSE_PATH = Path(__file__).parent.parent / "data" / "scanner_universe.json"


@dataclass
class FilterConfig:
    """Configurable filter thresholds for the scanner."""
    # Valuation
    max_trailing_pe: float | None = 50.0
    max_forward_pe: float | None = 35.0
    max_peg: float | None = 1.5
    max_price_to_sales: float | None = 15.0

    # Growth
    min_revenue_growth: float | None = 0.12  # 12% YoY
    min_earnings_growth: float | None = 0.10  # 10% YoY

    # Profitability
    min_gross_margin: float | None = 0.30  # 30%
    min_operating_margin: float | None = 0.05  # positive and not tiny

    # Size & liquidity
    min_market_cap: float | None = 2e9  # $2B
    max_market_cap: float | None = None

    # Analyst sentiment
    min_analyst_upside: float | None = 0.15  # 15% to target mean
    min_num_analysts: int | None = 5
    max_recommendation_mean: float | None = 2.5  # <= 2.5 (closer to buy)

    # Risk
    max_beta: float | None = 2.0
    min_beta: float | None = 0.5

    # Balance sheet
    max_debt_to_equity: float | None = 200.0


@dataclass
class ScanResult:
    """Output of a scan for a single ticker."""
    ticker: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    info: dict = field(default_factory=dict)
    score: float = 0.0


def load_universe() -> list[str]:
    with open(UNIVERSE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    # dedupe while preserving order
    seen = set()
    result = []
    for t in data["tickers"]:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def _check(val: Any, op: str, threshold: Any) -> tuple[bool, str]:
    """Apply a filter. Returns (passed, failure_reason_if_failed)."""
    if threshold is None:
        return True, ""
    if val is None or pd.isna(val):
        return False, "dados em falta"
    if op == ">=" and val < threshold:
        return False, f"{val:.2f} < {threshold}"
    if op == "<=" and val > threshold:
        return False, f"{val:.2f} > {threshold}"
    return True, ""


def apply_filters(info: dict, cfg: FilterConfig) -> ScanResult:
    """Run all filters against a single company's info dict."""
    ticker = info.get("symbol", "?")
    failures = []

    # Valuation
    ok, why = _check(info.get("trailing_pe"), "<=", cfg.max_trailing_pe)
    if not ok:
        failures.append(f"P/E trailing: {why}")
    ok, why = _check(info.get("forward_pe"), "<=", cfg.max_forward_pe)
    if not ok:
        failures.append(f"P/E forward: {why}")
    ok, why = _check(info.get("peg_ratio"), "<=", cfg.max_peg)
    if not ok:
        failures.append(f"PEG: {why}")
    ok, why = _check(info.get("price_to_sales"), "<=", cfg.max_price_to_sales)
    if not ok:
        failures.append(f"P/S: {why}")

    # Growth
    ok, why = _check(info.get("revenue_growth"), ">=", cfg.min_revenue_growth)
    if not ok:
        failures.append(f"Rev growth: {why}")
    ok, why = _check(info.get("earnings_growth"), ">=", cfg.min_earnings_growth)
    if not ok:
        failures.append(f"EPS growth: {why}")

    # Profitability
    ok, why = _check(info.get("gross_margin"), ">=", cfg.min_gross_margin)
    if not ok:
        failures.append(f"Gross margin: {why}")
    ok, why = _check(info.get("operating_margin"), ">=", cfg.min_operating_margin)
    if not ok:
        failures.append(f"Op margin: {why}")

    # Size
    ok, why = _check(info.get("market_cap"), ">=", cfg.min_market_cap)
    if not ok:
        failures.append(f"Market cap: {why}")
    if cfg.max_market_cap is not None:
        ok, why = _check(info.get("market_cap"), "<=", cfg.max_market_cap)
        if not ok:
            failures.append(f"Market cap: {why}")

    # Analyst
    target_mean = info.get("target_mean")
    price = info.get("current_price")
    if target_mean and price:
        upside = (target_mean / price) - 1
        ok, why = _check(upside, ">=", cfg.min_analyst_upside)
        if not ok:
            failures.append(f"Upside: {upside*100:.1f}% < {cfg.min_analyst_upside*100:.0f}%")
    else:
        if cfg.min_analyst_upside is not None:
            failures.append("Upside: sem target de analistas")

    ok, why = _check(info.get("num_analysts"), ">=", cfg.min_num_analysts)
    if not ok:
        failures.append(f"Nº analistas: {why}")
    ok, why = _check(info.get("recommendation_mean"), "<=", cfg.max_recommendation_mean)
    if not ok:
        failures.append(f"Rec score: {why}")

    # Risk
    ok, why = _check(info.get("beta"), "<=", cfg.max_beta)
    if not ok:
        failures.append(f"Beta: {why}")
    ok, why = _check(info.get("beta"), ">=", cfg.min_beta)
    if not ok:
        failures.append(f"Beta: {why}")

    # Balance sheet
    ok, why = _check(info.get("debt_to_equity"), "<=", cfg.max_debt_to_equity)
    if not ok:
        failures.append(f"D/E: {why}")

    passed = len(failures) == 0
    # Simple score: average of key metrics
    score = _compute_score(info)

    return ScanResult(
        ticker=ticker, passed=passed, failures=failures,
        info=info, score=score,
    )


def _compute_score(info: dict) -> float:
    """Simple 0-100 composite score from key metrics."""
    components = []

    # Growth weight (0-30)
    rg = info.get("revenue_growth") or 0
    components.append(min(30, max(0, rg * 100)))

    # Upside weight (0-25)
    target = info.get("target_mean")
    price = info.get("current_price")
    if target and price:
        upside = (target / price - 1) * 100
        components.append(min(25, max(0, upside)))

    # Margin weight (0-20)
    op_m = info.get("operating_margin") or 0
    components.append(min(20, max(0, op_m * 50)))

    # PEG weight inverse (0-15)
    peg = info.get("peg_ratio")
    if peg and peg > 0:
        components.append(max(0, 15 - peg * 5))

    # Analyst rec (0-10, inverted — lower = better)
    rec = info.get("recommendation_mean")
    if rec:
        components.append(max(0, 10 - (rec - 1) * 3))

    return sum(components)


def run_scan(
    tickers: list[str],
    cfg: FilterConfig,
    progress_callback=None,
    limit: int | None = None,
) -> list[ScanResult]:
    """Run the scanner on a list of tickers. Respects cache from fetch_company_info."""
    results = []
    tickers_to_scan = tickers[:limit] if limit else tickers
    total = len(tickers_to_scan)

    for i, ticker in enumerate(tickers_to_scan):
        try:
            info = fetch_company_info(ticker)
            if info and info.get("name"):
                result = apply_filters(info, cfg)
                results.append(result)
        except Exception as exc:
            print(f"[scan error] {ticker}: {exc}")
            continue

        if progress_callback:
            progress_callback(i + 1, total, ticker)

    return results


def filter_passed(results: list[ScanResult]) -> list[ScanResult]:
    return [r for r in results if r.passed]


def close_to_passing(results: list[ScanResult], max_failures: int = 2) -> list[ScanResult]:
    """Return candidates that failed by a small margin — useful for watchlist."""
    return [r for r in results if not r.passed and 0 < len(r.failures) <= max_failures]


def results_to_dataframe(results: list[ScanResult]) -> pd.DataFrame:
    """Transform scan results into a DataFrame for UI display."""
    rows = []
    for r in results:
        info = r.info
        price = info.get("current_price")
        target = info.get("target_mean")
        upside = ((target / price - 1) * 100) if target and price else None
        rows.append({
            "Ticker": r.ticker,
            "Nome": info.get("name", ""),
            "Sector": info.get("sector", ""),
            "Preço": price,
            "Market Cap": info.get("market_cap"),
            "P/E fwd": info.get("forward_pe"),
            "PEG": info.get("peg_ratio"),
            "P/S": info.get("price_to_sales"),
            "Rev Growth": info.get("revenue_growth"),
            "EPS Growth": info.get("earnings_growth"),
            "Op Margin": info.get("operating_margin"),
            "ROE": info.get("roe"),
            "Upside %": upside / 100 if upside is not None else None,
            "Rec Score": info.get("recommendation_mean"),
            "Nº Analistas": info.get("num_analysts"),
            "Beta": info.get("beta"),
            "Score": r.score,
            "Falhas": len(r.failures),
            "Razões": "; ".join(r.failures[:3]) if r.failures else "",
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Score", ascending=False)
    return df
