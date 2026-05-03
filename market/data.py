import json
import os
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

from config import STOCK_UNIVERSE

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache")
CLAUDE_BIN = shutil.which("claude") or str(Path.home() / ".local/bin/claude")

_SECTORS = {
    "XLK": "Technology", "XLF": "Financials", "XLV": "Healthcare",
    "XLY": "Consumer Disc.", "XLP": "Consumer Staples", "XLE": "Energy",
    "XLI": "Industrials", "XLB": "Materials", "XLRE": "Real Estate",
    "XLU": "Utilities", "XLC": "Communication",
}


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


def _claude(prompt: str, timeout: int = 180) -> object:
    """Call Claude CLI with WebSearch and return parsed JSON."""
    cmd = [
        CLAUDE_BIN, "--print",
        "--allowedTools", "WebSearch",
        "--permission-mode", "acceptEdits",
        prompt,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"claude exit {proc.returncode}: {proc.stderr[:300]}")

    text = proc.stdout.strip()
    # Strip markdown code fences if present
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        text = match.group(1)
    return json.loads(text)


def get_market_overview() -> dict:
    cached = _load_cache("overview")
    if cached:
        return cached

    data = _claude(
        "Search for today's latest prices for SPY, QQQ, DIA, IWM, and VIX (^VIX). "
        "For each, find the current price and today's percentage change. "
        'Return ONLY this JSON (fill in real values): '
        '{"S&P 500": {"ticker": "SPY", "price": 0.0, "change_pct": 0.0}, '
        '"Nasdaq 100": {"ticker": "QQQ", "price": 0.0, "change_pct": 0.0}, '
        '"Dow Jones": {"ticker": "DIA", "price": 0.0, "change_pct": 0.0}, '
        '"Russell 2000": {"ticker": "IWM", "price": 0.0, "change_pct": 0.0}, '
        '"VIX": {"ticker": "^VIX", "price": 0.0, "change_pct": 0.0}}'
    )
    _save_cache("overview", data)
    return data


def get_sector_performance() -> dict:
    cached = _load_cache("sectors")
    if cached:
        return cached

    tickers = list(_SECTORS.keys())
    data = _claude(
        f"Search for today's price changes for these sector ETFs: {', '.join(tickers)}. "
        "For each ETF, find today's percentage change. "
        f"Sector name mapping: {json.dumps(_SECTORS)}. "
        'Return ONLY JSON where keys are sector names, values have "ticker" and "change_pct". '
        'Example: {"Technology": {"ticker": "XLK", "change_pct": 1.2}, '
        '"Financials": {"ticker": "XLF", "change_pct": -0.3}, ...}'
    )
    _save_cache("sectors", data)
    return data


def get_stock_quote(symbol: str) -> dict:
    data = _claude(
        f"Search for the current stock price and today's change for {symbol}. "
        f'Return ONLY JSON: {{"symbol": "{symbol}", "price": 0.0, "change_pct": 0.0, "volume": 0}}'
    )
    return data


def get_stock_fundamentals(symbol: str) -> dict:
    data = _claude(
        f"Search for fundamental financial data for {symbol}: "
        "sector, trailing P/E ratio, forward P/E, price-to-book ratio, "
        "net profit margin (as decimal), EV/EBITDA, dividend yield (as decimal), "
        "revenue growth YoY (as decimal), debt-to-equity ratio, market cap in billions. "
        f'Return ONLY JSON: {{"symbol": "{symbol}", "sector": "", "pe_ratio": null, '
        '"forward_pe": null, "pb_ratio": null, "ev_ebitda": null, '
        '"profit_margin": null, "revenue_growth_yoy": null, '
        '"debt_to_equity": null, "dividend_yield": null, "market_cap_B": null, "description": ""}}'
    )
    return data


def get_momentum_candidates(top_n: int = 15) -> list[dict]:
    cached = _load_cache("momentum")
    if cached:
        return cached[:top_n]

    print("Screening momentum candidates via web search (can take 2-3 min)...")

    # Fetch SPY 3m performance first for alpha calculation
    spy_data = _claude(
        "Search for SPY ETF's 3-month percentage return and current price and 1-month return. "
        'Return ONLY JSON: {"price": 0.0, "perf_1m_pct": 0.0, "perf_3m_pct": 0.0}'
    )
    spy_3m = spy_data.get("perf_3m_pct", 0.0)

    universe_str = ", ".join(STOCK_UNIVERSE)
    data = _claude(
        f"Search for 1-month and 3-month price performance for these stocks: {universe_str}. "
        "Also find each stock's current price and 52-week high. "
        "Rank them by 3-month return minus SPY's 3-month return (alpha), best first. "
        f"SPY 3-month return is {spy_3m:.1f}%. "
        "Return ONLY a JSON array of the top 20, each with: "
        'symbol, price, perf_1m_pct, perf_3m_pct, alpha_vs_spy_3m, pct_from_52w_high. '
        'Example: [{"symbol": "AMD", "price": 150.0, "perf_1m_pct": 10.5, '
        '"perf_3m_pct": 35.2, "alpha_vs_spy_3m": 28.1, "pct_from_52w_high": -2.3}, ...]',
        timeout=300,
    )
    _save_cache("momentum", data)
    return data[:top_n]


def get_value_candidates(top_n: int = 15) -> list[dict]:
    cached = _load_cache("value")
    if cached:
        return cached[:top_n]

    print("Screening value candidates via web search (can take 2-3 min)...")
    universe_str = ", ".join(STOCK_UNIVERSE)
    data = _claude(
        f"Search for value investing metrics for these stocks: {universe_str}. "
        "Find stocks that meet ALL of these criteria: "
        "P/E ratio between 5 and 20, price-to-book below 3, net profit margin above 5%. "
        "For qualifying stocks find: current price, P/E, P/B, profit margin %, "
        "EV/EBITDA, dividend yield %, sector. "
        "Rank by P/E ascending. Return up to 20 results. "
        "Return ONLY a JSON array: "
        '[{"symbol": "WFC", "price": 0.0, "pe_ratio": 0.0, "pb_ratio": 0.0, '
        '"profit_margin_pct": 0.0, "ev_ebitda": null, "dividend_yield_pct": 0.0, '
        '"sector": ""}, ...]',
        timeout=300,
    )
    _save_cache("value", data)
    return data[:top_n]


def get_bulk_quotes(symbols: list[str]) -> dict[str, float]:
    """Fetch current prices for multiple symbols."""
    data = _claude(
        f"Search for current stock prices for: {', '.join(symbols)}. "
        'Return ONLY a JSON object with symbol as key and price as float value. '
        'Example: {"AAPL": 150.25, "MSFT": 305.10}'
    )
    return {k: float(v) for k, v in data.items()}
