import json
import os
from datetime import date, datetime

import pandas as pd
import yfinance as yf

from config import STOCK_UNIVERSE

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache")


def _cache_path(name: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{date.today().isoformat()}_{name}.json")


def _load_cache(name: str):
    path = _cache_path(name)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def _save_cache(name: str, data):
    with open(_cache_path(name), "w") as f:
        json.dump(data, f)


def get_market_overview() -> dict:
    tickers = {"SPY": "S&P 500", "QQQ": "Nasdaq 100", "DIA": "Dow Jones", "IWM": "Russell 2000", "^VIX": "VIX"}
    result = {}
    for ticker, label in tickers.items():
        try:
            hist = yf.Ticker(ticker).history(period="2d")
            if len(hist) >= 2:
                prev, curr = hist["Close"].iloc[-2], hist["Close"].iloc[-1]
                result[label] = {
                    "ticker": ticker,
                    "price": round(curr, 2),
                    "change_pct": round((curr - prev) / prev * 100, 2),
                }
        except Exception as e:
            result[label] = {"error": str(e)}
    return result


def get_sector_performance() -> dict:
    sectors = {
        "XLK": "Technology", "XLF": "Financials", "XLV": "Healthcare",
        "XLY": "Consumer Disc.", "XLP": "Consumer Staples", "XLE": "Energy",
        "XLI": "Industrials", "XLB": "Materials", "XLRE": "Real Estate",
        "XLU": "Utilities", "XLC": "Communication",
    }
    result = {}
    for ticker, name in sectors.items():
        try:
            hist = yf.Ticker(ticker).history(period="2d")
            if len(hist) >= 2:
                prev, curr = hist["Close"].iloc[-2], hist["Close"].iloc[-1]
                result[name] = {"ticker": ticker, "change_pct": round((curr - prev) / prev * 100, 2)}
        except Exception:
            pass
    return result


def get_stock_quote(symbol: str) -> dict:
    try:
        hist = yf.Ticker(symbol).history(period="2d")
        if len(hist) >= 2:
            prev, curr = hist["Close"].iloc[-2], hist["Close"].iloc[-1]
            return {
                "symbol": symbol,
                "price": round(curr, 2),
                "change_pct": round((curr - prev) / prev * 100, 2),
                "volume": int(hist["Volume"].iloc[-1]),
            }
        elif len(hist) == 1:
            curr = hist["Close"].iloc[-1]
            return {"symbol": symbol, "price": round(curr, 2), "change_pct": None, "volume": int(hist["Volume"].iloc[-1])}
    except Exception as e:
        return {"error": str(e)}
    return {"error": "no data"}


def get_stock_fundamentals(symbol: str) -> dict:
    try:
        info = yf.Ticker(symbol).info
        return {
            "symbol": symbol,
            "sector": info.get("sector"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "pb_ratio": info.get("priceToBook"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "profit_margin": round(info.get("profitMargins", 0) * 100, 1) if info.get("profitMargins") else None,
            "revenue_growth_yoy": round(info.get("revenueGrowth", 0) * 100, 1) if info.get("revenueGrowth") else None,
            "debt_to_equity": info.get("debtToEquity"),
            "dividend_yield": round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else 0,
            "market_cap_B": round(info.get("marketCap", 0) / 1e9, 1) if info.get("marketCap") else None,
            "description": (info.get("longBusinessSummary") or "")[:400],
        }
    except Exception as e:
        return {"error": str(e)}


def get_momentum_candidates(top_n: int = 15) -> list[dict]:
    cached = _load_cache("momentum")
    if cached:
        return cached[:top_n]

    print("Screening momentum candidates (can take 1-2 min)...")
    spy_hist = yf.Ticker("SPY").history(period="6mo")
    spy_3m = (spy_hist["Close"].iloc[-1] / spy_hist["Close"].iloc[-63] - 1) * 100 if len(spy_hist) > 63 else 0

    results = []
    for symbol in STOCK_UNIVERSE:
        try:
            hist = yf.Ticker(symbol).history(period="6mo")
            if len(hist) < 63:
                continue
            curr = hist["Close"].iloc[-1]
            high_52w = hist["Close"].max()
            perf_1m = (curr / hist["Close"].iloc[-21] - 1) * 100
            perf_3m = (curr / hist["Close"].iloc[-63] - 1) * 100
            results.append({
                "symbol": symbol,
                "price": round(curr, 2),
                "perf_1m_pct": round(perf_1m, 1),
                "perf_3m_pct": round(perf_3m, 1),
                "alpha_vs_spy_3m": round(perf_3m - spy_3m, 1),
                "pct_from_52w_high": round((curr / high_52w - 1) * 100, 1),
            })
        except Exception:
            continue

    results.sort(key=lambda x: x["alpha_vs_spy_3m"], reverse=True)
    _save_cache("momentum", results)
    return results[:top_n]


def get_value_candidates(top_n: int = 15) -> list[dict]:
    cached = _load_cache("value")
    if cached:
        return cached[:top_n]

    print("Screening value candidates (can take 2-3 min)...")
    results = []
    for symbol in STOCK_UNIVERSE:
        try:
            info = yf.Ticker(symbol).info
            pe = info.get("trailingPE")
            pb = info.get("priceToBook")
            margin = info.get("profitMargins", 0) or 0
            if pe and 0 < pe < 20 and pb and pb < 3 and margin > 0.05:
                hist = yf.Ticker(symbol).history(period="2d")
                curr = hist["Close"].iloc[-1] if len(hist) > 0 else info.get("currentPrice", 0)
                results.append({
                    "symbol": symbol,
                    "price": round(float(curr), 2),
                    "pe_ratio": round(pe, 1),
                    "pb_ratio": round(pb, 2),
                    "profit_margin_pct": round(margin * 100, 1),
                    "ev_ebitda": info.get("enterpriseToEbitda"),
                    "dividend_yield_pct": round((info.get("dividendYield") or 0) * 100, 2),
                    "sector": info.get("sector", ""),
                })
        except Exception:
            continue

    results.sort(key=lambda x: x["pe_ratio"])
    _save_cache("value", results)
    return results[:top_n]


def get_bulk_quotes(symbols: list[str]) -> dict[str, float]:
    """Fetch current prices for multiple symbols efficiently."""
    try:
        data = yf.download(symbols, period="1d", auto_adjust=True, progress=False)
        prices = {}
        if isinstance(data.columns, pd.MultiIndex):
            close = data["Close"]
            for sym in symbols:
                if sym in close.columns and not close[sym].empty:
                    prices[sym] = round(float(close[sym].iloc[-1]), 2)
        else:
            if not data.empty:
                prices[symbols[0]] = round(float(data["Close"].iloc[-1]), 2)
        return prices
    except Exception:
        return {}
