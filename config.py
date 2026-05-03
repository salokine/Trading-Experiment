INITIAL_CAPITAL = 100_000.0  # $100k per trader
MAX_POSITION_SIZE = 0.10     # 10% of capital max per position
MODEL = "claude-sonnet-4-6"

TRADERS = {
    "momentum": "Momentum Trader",
    "value": "Value Trader",
}

STOCK_UNIVERSE = [
    # Tech
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "AMD", "AVGO", "CRM", "ORCL",
    # Finance
    "JPM", "BAC", "GS", "MS", "V", "MA", "WFC", "AXP", "BLK", "C",
    # Healthcare
    "LLY", "UNH", "JNJ", "ABBV", "MRK", "PFE", "TMO", "ABT", "ISRG", "CVS",
    # Consumer
    "TSLA", "HD", "MCD", "NKE", "SBUX", "TGT", "COST", "WMT", "LOW", "TJX",
    # Energy
    "XOM", "CVX", "COP", "SLB", "OXY", "PSX", "VLO", "EOG", "MPC", "HES",
    # Industrials
    "CAT", "HON", "UPS", "RTX", "BA", "GE", "MMM", "DE", "LMT", "NOC",
    # Materials & Utilities
    "LIN", "APD", "ECL", "NEM", "FCX", "NEE", "DUK", "SO", "AEP", "EXC",
]
