"""Data fetching and portfolio mutation utilities."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf

PORTFOLIO_PATH = Path(__file__).parent.parent / "data" / "portfolio.json"


# ==================== File I/O ====================

def load_portfolio() -> dict:
    """Load portfolio JSON (not cached — mutations must be seen immediately)."""
    with open(PORTFOLIO_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_portfolio(data: dict) -> None:
    """Write portfolio JSON back to disk and clear caches."""
    with open(PORTFOLIO_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    st.cache_data.clear()


# ==================== Currency helpers ====================

def _rate_to_eur(currency: str, eurusd: float) -> float:
    """Return multiplier so that value * rate = value in EUR.
    For USD: 1/eurusd (since 1 EUR = eurusd USD)
    For GBP: uses GBP/EUR rate (fetched separately)
    """
    if currency == "EUR":
        return 1.0
    if currency == "USD":
        return 1.0 / eurusd if eurusd else 0
    # For GBP and others we fall back in _cross_convert
    return 1.0


def _cross_convert(value: float | None, from_ccy: str, to_ccy: str,
                   eurusd: float, gbpeur: float | None = None) -> float | None:
    """Convert a value from one currency to another via EUR."""
    if value is None:
        return None
    if from_ccy == to_ccy:
        return value
    # Step 1: convert from_ccy → EUR
    if from_ccy == "EUR":
        in_eur = value
    elif from_ccy == "USD":
        in_eur = value / eurusd if eurusd else 0
    elif from_ccy == "GBP" and gbpeur:
        in_eur = value * gbpeur
    else:
        in_eur = value  # fallback
    # Step 2: convert EUR → to_ccy
    if to_ccy == "EUR":
        return in_eur
    if to_ccy == "USD":
        return in_eur * eurusd
    if to_ccy == "GBP" and gbpeur:
        return in_eur / gbpeur
    return in_eur


# ==================== Market data (cached) ====================

@st.cache_data(ttl=300)
def fetch_current_prices(tickers: tuple) -> dict:
    """Latest close + daily change for a list of tickers."""
    results = {}
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period="5d", auto_adjust=False)
            if hist.empty:
                results[ticker] = {"price": None, "change_pct": 0.0}
                continue
            last = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[-2] if len(hist) >= 2 else last
            change_pct = ((last / prev) - 1) * 100 if prev else 0.0
            results[ticker] = {"price": float(last), "change_pct": float(change_pct)}
        except Exception as exc:
            print(f"[warn] fetch_current_prices {ticker}: {exc}")
            results[ticker] = {"price": None, "change_pct": 0.0}
    return results


@st.cache_data(ttl=3600)
def fetch_historical(tickers: tuple, period: str = "1y") -> pd.DataFrame:
    """Historical adjusted closes."""
    if not tickers:
        return pd.DataFrame()
    data = yf.download(
        list(tickers), period=period, progress=False,
        auto_adjust=True, group_by="ticker",
    )
    if len(tickers) == 1:
        if "Close" in data.columns:
            return data[["Close"]].rename(columns={"Close": tickers[0]})
        return data
    closes = pd.DataFrame()
    for t in tickers:
        try:
            closes[t] = data[t]["Close"]
        except (KeyError, TypeError):
            continue
    return closes.dropna(how="all")


@st.cache_data(ttl=3600)
def fetch_sparkline_data(tickers: tuple, days: int = 30) -> dict:
    """Return {ticker: [list of closes]} for sparklines."""
    hist = fetch_historical(tickers, period=f"{max(days, 5)+10}d")
    if hist.empty:
        return {t: [] for t in tickers}
    return {
        t: hist[t].dropna().tail(days).tolist() if t in hist.columns else []
        for t in tickers
    }


@st.cache_data(ttl=3600)
def fetch_eurusd() -> float:
    """Current EUR/USD (1 EUR = X USD). Fallback 1.17."""
    try:
        hist = yf.Ticker("EURUSD=X").history(period="5d")
        return float(hist["Close"].iloc[-1]) if not hist.empty else 1.17
    except Exception:
        return 1.17


@st.cache_data(ttl=3600)
def fetch_gbpeur() -> float:
    """Current GBP/EUR (1 GBP = X EUR). Fallback 1.15."""
    try:
        hist = yf.Ticker("GBPEUR=X").history(period="5d")
        return float(hist["Close"].iloc[-1]) if not hist.empty else 1.15
    except Exception:
        return 1.15


@st.cache_data(ttl=86400)
def detect_quote_currency(ticker: str) -> str:
    """Auto-detect the currency yfinance returns for a ticker via .info."""
    try:
        info = yf.Ticker(ticker).info
        curr = (info.get("currency") or "").upper()
        if curr in ("USD", "EUR", "GBP", "CHF", "JPY", "GBX"):
            return "GBP" if curr == "GBX" else curr
    except Exception:
        pass
    # Heuristic fallbacks based on suffix
    if ticker.endswith(".L"):
        return "USD"  # LSE UCITS ETFs often trade in USD (EXUS.L, VUAA.L, CSPX.L)
    if ticker.endswith((".DE", ".AS", ".MI", ".PA")):
        return "EUR"
    return "USD"


@st.cache_data(ttl=3600)
def fetch_macro_indicators() -> dict:
    """VIX, FX, commodities, indices."""
    tickers = {
        "VIX": "^VIX",
        "EUR/USD": "EURUSD=X",
        "Ouro (XAU/USD)": "GC=F",
        "Brent (BNO)": "BNO",
        "DXY (UUP)": "UUP",
        "S&P 500": "^GSPC",
        "NASDAQ 100": "^NDX",
        "STOXX 600": "^STOXX",
    }
    results = {}
    for label, tk in tickers.items():
        try:
            hist = yf.Ticker(tk).history(period="5d")
            if hist.empty or len(hist) < 2:
                continue
            last = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[-2]
            results[label] = {
                "price": float(last),
                "change_pct": float(((last / prev) - 1) * 100),
            }
        except Exception:
            continue
    return results


@st.cache_data(ttl=1800)
def fetch_news(ticker: str, limit: int = 8) -> list[dict]:
    """Fetch recent news via yfinance."""
    try:
        raw = yf.Ticker(ticker).news or []
    except Exception as exc:
        print(f"[warn] fetch_news {ticker}: {exc}")
        return []

    results = []
    for item in raw[:limit]:
        content = item.get("content", item)
        title = content.get("title") or item.get("title") or "—"
        publisher = (
            content.get("provider", {}).get("displayName")
            if isinstance(content.get("provider"), dict)
            else content.get("publisher") or item.get("publisher") or ""
        )
        link = (
            content.get("canonicalUrl", {}).get("url")
            if isinstance(content.get("canonicalUrl"), dict)
            else content.get("link") or item.get("link") or ""
        )
        pub_date = (
            content.get("pubDate")
            or content.get("providerPublishTime")
            or item.get("providerPublishTime")
        )
        if isinstance(pub_date, (int, float)):
            pub_date = datetime.fromtimestamp(pub_date).strftime("%Y-%m-%d %H:%M")
        elif isinstance(pub_date, str) and "T" in pub_date:
            pub_date = pub_date.replace("T", " ").split(".")[0][:16]
        summary = content.get("summary") or ""
        results.append({
            "title": title, "publisher": publisher or "—",
            "link": link, "published": pub_date or "", "summary": summary,
        })
    return results


# ==================== Portfolio enrichment ====================

def enrich_portfolio(portfolio_data: dict) -> pd.DataFrame:
    """
    Enrich positions with live data, handling the distinction between:
    - currency: the currency of the avg_price (what the user paid in)
    - quote_currency: the currency yfinance returns (can differ for UCITS ETFs)

    Example: EXUS.L has currency="EUR" (user paid in EUR) but quote_currency="USD"
    (yfinance returns USD quote). PM is in EUR so no FX applied to cost.
    Current price in USD is converted to EUR before value calc.
    """
    df = pd.DataFrame(portfolio_data["positions"])
    if df.empty:
        return df

    # Ensure optional columns exist
    for col in ("stop", "take_profit", "quote_currency"):
        if col not in df.columns:
            df[col] = None
    # Default quote_currency = currency if not specified
    df["quote_currency"] = df.apply(
        lambda r: r["quote_currency"] if pd.notna(r.get("quote_currency"))
                  and r.get("quote_currency") else r["currency"],
        axis=1,
    )

    tickers = tuple(df["ticker"].tolist())
    prices = fetch_current_prices(tickers)
    eurusd = fetch_eurusd()
    gbpeur = fetch_gbpeur()

    df["current_price"] = df["ticker"].map(lambda t: prices.get(t, {}).get("price"))
    df["change_pct"] = df["ticker"].map(lambda t: prices.get(t, {}).get("change_pct", 0.0))

    # --- Convert everything to EUR independently ---
    # Current price arrives in QUOTE_CURRENCY → convert to EUR
    df["price_eur"] = df.apply(
        lambda r: _cross_convert(r["current_price"], r["quote_currency"], "EUR", eurusd, gbpeur),
        axis=1,
    )
    # Avg price is in user's CURRENCY (PM currency) → convert to EUR
    df["avg_price_eur"] = df.apply(
        lambda r: _cross_convert(r["avg_price"], r["currency"], "EUR", eurusd, gbpeur),
        axis=1,
    )
    # For display parity with user's spreadsheet: show current price
    # in the PM currency (user's mental model)
    df["current_price_display"] = df.apply(
        lambda r: _cross_convert(r["current_price"], r["quote_currency"], r["currency"],
                                 eurusd, gbpeur),
        axis=1,
    )

    df["value_eur"] = df["qty"] * df["price_eur"]
    df["cost_eur"] = df["qty"] * df["avg_price_eur"]
    df["pl_eur"] = df["value_eur"] - df["cost_eur"]
    df["pl_pct"] = (df["pl_eur"] / df["cost_eur"]) * 100

    total = df["value_eur"].sum()
    df["weight"] = (df["value_eur"] / total) * 100 if total else 0

    # Stop/TP distances (in quote currency — that's what user watches on the platform)
    def pct_distance(current, target):
        if current is None or target is None or pd.isna(target):
            return None
        return ((target / current) - 1) * 100

    df["dist_stop_pct"] = df.apply(
        lambda r: pct_distance(r["current_price"], r["stop"]), axis=1,
    )
    df["dist_tp_pct"] = df.apply(
        lambda r: pct_distance(r["current_price"], r["take_profit"]), axis=1,
    )
    return df


# ==================== Watchlist ====================

def compute_signal(price, entry_lo, entry_hi, stop, tp1) -> str:
    if price is None:
        return "—"
    if price <= stop:
        return "Stop atingido"
    if price < entry_lo:
        return "Abaixo entry"
    if entry_lo <= price <= entry_hi:
        return "Zona de compra"
    if entry_hi < price < tp1:
        return "Monitorizar"
    return "Já correu"


def enrich_watchlist(portfolio_data: dict) -> pd.DataFrame:
    wl = portfolio_data.get("watchlist", [])
    if not wl:
        return pd.DataFrame()
    df = pd.DataFrame(wl)
    tickers = tuple(df["ticker"].tolist())
    prices = fetch_current_prices(tickers)
    df["price"] = df["ticker"].map(lambda t: prices.get(t, {}).get("price"))
    df["change_pct"] = df["ticker"].map(lambda t: prices.get(t, {}).get("change_pct", 0.0))

    def dist(curr, target):
        if curr is None or target is None:
            return None
        return ((target / curr) - 1) * 100

    df["dist_stop"] = df.apply(lambda r: dist(r["price"], r["stop"]), axis=1)
    df["dist_tp1"] = df.apply(lambda r: dist(r["price"], r["tp1"]), axis=1)
    df["dist_tp2"] = df.apply(lambda r: dist(r["price"], r["tp2"]), axis=1)
    df["signal"] = df.apply(
        lambda r: compute_signal(r["price"], r["entry_lo"], r["entry_hi"],
                                 r["stop"], r["tp1"]),
        axis=1,
    )
    return df


# ==================== Transactions ====================

def add_transaction(
    ticker: str, action: str, qty: float, price: float,
    currency: str, date: str, name: str = "", sector: str = "",
    classification: str = "Core",
    stop: float | None = None, take_profit: float | None = None,
    quote_currency: str | None = None,
) -> str:
    """Record a buy/sell and update the position.
    For a new BUY, quote_currency auto-detected if not passed.
    """
    data = load_portfolio()
    action = action.upper()

    tx = {
        "date": date, "ticker": ticker, "action": action,
        "qty": float(qty), "price": float(price), "currency": currency,
    }
    data.setdefault("transactions", []).append(tx)

    positions = data["positions"]
    existing_idx = next(
        (i for i, p in enumerate(positions) if p["ticker"] == ticker), None,
    )

    if action == "BUY":
        if existing_idx is not None:
            pos = positions[existing_idx]
            new_qty = pos["qty"] + qty
            new_avg = (pos["qty"] * pos["avg_price"] + qty * price) / new_qty
            pos["qty"] = round(new_qty, 6)
            pos["avg_price"] = round(new_avg, 4)
            if stop is not None:
                pos["stop"] = float(stop)
            if take_profit is not None:
                pos["take_profit"] = float(take_profit)
            msg = (f"Compra aplicada. Nova qtd: {new_qty:.4f} | "
                   f"Novo PM: {new_avg:.2f} {currency}")
        else:
            qc = quote_currency or detect_quote_currency(ticker)
            new_pos = {
                "ticker": ticker, "name": name or ticker,
                "qty": float(qty), "avg_price": float(price),
                "class": classification, "sector": sector or "—",
                "currency": currency,
                "stop": float(stop) if stop is not None else None,
                "take_profit": float(take_profit) if take_profit is not None else None,
            }
            if qc != currency:
                new_pos["quote_currency"] = qc
            positions.append(new_pos)
            auto = f" (quote auto-detectada: {qc})" if qc != currency else ""
            msg = f"Nova posição: {ticker} × {qty}{auto}"

    elif action == "SELL":
        if existing_idx is None:
            return f"❌ Não tens posição em {ticker}."
        pos = positions[existing_idx]
        if qty > pos["qty"] + 1e-6:
            return f"❌ Só tens {pos['qty']:.4f} de {ticker}."
        new_qty = pos["qty"] - qty
        if new_qty < 1e-6:
            positions.pop(existing_idx)
            msg = f"Posição fechada: {ticker}."
        else:
            pos["qty"] = round(new_qty, 6)
            msg = f"Venda parcial: {ticker} → {new_qty:.4f}."
    else:
        return f"❌ Acção desconhecida: {action}"

    save_portfolio(data)
    return "✅ " + msg


def add_to_watchlist(item: dict) -> str:
    data = load_portfolio()
    data.setdefault("watchlist", []).append(item)
    save_portfolio(data)
    return f"✅ {item['ticker']} adicionado à watchlist."


def remove_from_watchlist(ticker: str) -> str:
    data = load_portfolio()
    wl = data.get("watchlist", [])
    new_wl = [w for w in wl if w["ticker"] != ticker]
    if len(new_wl) == len(wl):
        return f"❌ {ticker} não estava na watchlist."
    data["watchlist"] = new_wl
    save_portfolio(data)
    return f"✅ {ticker} removido da watchlist."


# ==================== Company fundamentals ====================

@st.cache_data(ttl=21600)  # 6 hours — info changes slowly
def fetch_company_info(ticker: str) -> dict:
    """Fetch comprehensive company info from yfinance."""
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
    except Exception as exc:
        print(f"[warn] fetch_company_info {ticker}: {exc}")
        return {}

    def g(key, default=None):
        return info.get(key, default)

    return {
        # Identity
        "name": g("longName") or g("shortName") or ticker,
        "symbol": g("symbol", ticker),
        "summary": g("longBusinessSummary", ""),
        "industry": g("industry", ""),
        "sector": g("sector", ""),
        "country": g("country", ""),
        "city": g("city", ""),
        "state": g("state", ""),
        "address": g("address1", ""),
        "website": g("website", ""),
        "employees": g("fullTimeEmployees"),
        "exchange": g("exchange", ""),
        "currency": g("currency", ""),
        "officers": g("companyOfficers", []) or [],

        # Valuation
        "market_cap": g("marketCap"),
        "enterprise_value": g("enterpriseValue"),
        "trailing_pe": g("trailingPE"),
        "forward_pe": g("forwardPE"),
        "peg_ratio": g("pegRatio") or g("trailingPegRatio"),
        "price_to_book": g("priceToBook"),
        "price_to_sales": g("priceToSalesTrailing12Months"),
        "ev_revenue": g("enterpriseToRevenue"),
        "ev_ebitda": g("enterpriseToEbitda"),

        # Profitability & margins
        "gross_margin": g("grossMargins"),
        "operating_margin": g("operatingMargins"),
        "profit_margin": g("profitMargins"),
        "roe": g("returnOnEquity"),
        "roa": g("returnOnAssets"),

        # Balance sheet health
        "debt_to_equity": g("debtToEquity"),
        "current_ratio": g("currentRatio"),
        "quick_ratio": g("quickRatio"),
        "total_cash": g("totalCash"),
        "total_debt": g("totalDebt"),

        # Growth
        "revenue_growth": g("revenueGrowth"),
        "earnings_growth": g("earningsGrowth"),
        "earnings_qoq": g("earningsQuarterlyGrowth"),
        "revenue_ttm": g("totalRevenue"),
        "ebitda": g("ebitda"),
        "free_cashflow": g("freeCashflow"),
        "operating_cashflow": g("operatingCashflow"),

        # Per share
        "eps_trailing": g("trailingEps"),
        "eps_forward": g("forwardEps"),
        "book_value": g("bookValue"),
        "shares_outstanding": g("sharesOutstanding"),
        "float_shares": g("floatShares"),

        # Dividends
        "dividend_yield": g("dividendYield"),
        "dividend_rate": g("dividendRate"),
        "payout_ratio": g("payoutRatio"),
        "ex_dividend_date": g("exDividendDate"),

        # Analyst
        "recommendation": g("recommendationKey", ""),
        "recommendation_mean": g("recommendationMean"),
        "num_analysts": g("numberOfAnalystOpinions"),
        "target_mean": g("targetMeanPrice"),
        "target_high": g("targetHighPrice"),
        "target_low": g("targetLowPrice"),
        "target_median": g("targetMedianPrice"),

        # Technical
        "beta": g("beta"),
        "52w_high": g("fiftyTwoWeekHigh"),
        "52w_low": g("fiftyTwoWeekLow"),
        "50d_avg": g("fiftyDayAverage"),
        "200d_avg": g("twoHundredDayAverage"),
        "short_ratio": g("shortRatio"),
        "short_percent": g("shortPercentOfFloat"),
        "held_insiders": g("heldPercentInsiders"),
        "held_institutions": g("heldPercentInstitutions"),

        # Price (for convenience)
        "current_price": g("currentPrice") or g("regularMarketPrice"),
        "previous_close": g("previousClose"),
    }


@st.cache_data(ttl=21600)
def fetch_financials_history(ticker: str) -> dict:
    """
    Fetch quarterly and annual income statement history.
    Returns DataFrames for key growth/margin analysis.
    """
    try:
        t = yf.Ticker(ticker)
        return {
            "quarterly_income": t.quarterly_income_stmt,
            "annual_income": t.income_stmt,
            "quarterly_cashflow": t.quarterly_cashflow,
            "quarterly_balance": t.quarterly_balance_sheet,
        }
    except Exception as exc:
        print(f"[warn] fetch_financials_history {ticker}: {exc}")
        return {}


@st.cache_data(ttl=21600)
def fetch_earnings_calendar(ticker: str) -> dict:
    """Fetch upcoming earnings date + recent history of surprises."""
    try:
        t = yf.Ticker(ticker)
        cal = t.calendar
        result = {"next_earnings": None, "surprises": None}
        if isinstance(cal, dict):
            result["next_earnings"] = cal.get("Earnings Date")
            result["eps_estimate"] = cal.get("Earnings Average")
            result["revenue_estimate"] = cal.get("Revenue Average")
        try:
            result["surprises"] = t.earnings_history
        except Exception:
            pass
        return result
    except Exception as exc:
        print(f"[warn] fetch_earnings_calendar {ticker}: {exc}")
        return {}


@st.cache_data(ttl=21600)
def fetch_analyst_recommendations(ticker: str) -> pd.DataFrame | None:
    """Recent analyst recommendation history."""
    try:
        t = yf.Ticker(ticker)
        recs = t.recommendations
        if recs is None or (hasattr(recs, "empty") and recs.empty):
            return None
        return recs
    except Exception as exc:
        print(f"[warn] fetch_analyst_recommendations {ticker}: {exc}")
        return None


@st.cache_data(ttl=21600)
def fetch_institutional_holders(ticker: str) -> pd.DataFrame | None:
    """Top institutional holders."""
    try:
        t = yf.Ticker(ticker)
        holders = t.institutional_holders
        if holders is None or (hasattr(holders, "empty") and holders.empty):
            return None
        return holders
    except Exception as exc:
        print(f"[warn] fetch_institutional_holders {ticker}: {exc}")
        return None


def format_large_number(n: float | int | None, currency: str = "$") -> str:
    """Format big numbers as 1.2T / 450.3B / 2.1M / 5.4K."""
    if n is None or pd.isna(n):
        return "—"
    n = float(n)
    sign = "-" if n < 0 else ""
    n = abs(n)
    if n >= 1e12:
        return f"{sign}{currency}{n/1e12:.2f}T"
    if n >= 1e9:
        return f"{sign}{currency}{n/1e9:.2f}B"
    if n >= 1e6:
        return f"{sign}{currency}{n/1e6:.2f}M"
    if n >= 1e3:
        return f"{sign}{currency}{n/1e3:.2f}K"
    return f"{sign}{currency}{n:.2f}"


def format_percent(n: float | None, decimals: int = 2) -> str:
    """Format a fraction as percentage."""
    if n is None or pd.isna(n):
        return "—"
    return f"{n*100:.{decimals}f}%"


def format_ratio(n: float | None, decimals: int = 2) -> str:
    if n is None or pd.isna(n):
        return "—"
    return f"{n:.{decimals}f}"


def recommendation_label(key: str) -> tuple[str, str]:
    """Return (label_PT, color) for recommendation key."""
    mapping = {
        "strong_buy": ("Strong Buy", "#00d4aa"),
        "buy": ("Buy", "#7cdb9a"),
        "hold": ("Hold", "#ffb74d"),
        "sell": ("Sell", "#ff9e7d"),
        "strong_sell": ("Strong Sell", "#ff5c7a"),
        "underperform": ("Underperform", "#ff9e7d"),
        "outperform": ("Outperform", "#7cdb9a"),
        "none": ("—", "#8892a6"),
    }
    return mapping.get((key or "").lower(), ((key or "—").title(), "#8892a6"))
