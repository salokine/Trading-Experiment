#!/usr/bin/env python3
"""
Étape 0 — Collecte des données de marché (pur Python, pas d'IA).
Écrit data/market/YYYY-MM-DD.md avec toutes les données dont les agents auront besoin.
"""
import sys
from datetime import date

from market.data import (
    get_market_overview,
    get_momentum_candidates,
    get_sector_performance,
    get_value_candidates,
)

OUTPUT_DIR = "data/market"


def fmt_change(val):
    if val is None:
        return "N/A"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.2f}%"


def build_report(today: str) -> str:
    lines = [f"# Données de Marché — {today}\n"]

    # ── Indices ──────────────────────────────────────────────
    print("  Fetching indices...")
    overview = get_market_overview()
    lines.append("## Indices Majeurs\n")
    lines.append("| Indice | Prix | Variation Jour |")
    lines.append("|--------|------|----------------|")
    for name, d in overview.items():
        if "error" not in d:
            lines.append(f"| {name} | ${d['price']:,.2f} | {fmt_change(d['change_pct'])} |")
    lines.append("")

    # ── Secteurs ─────────────────────────────────────────────
    print("  Fetching sectors...")
    sectors = get_sector_performance()
    lines.append("## Performance Sectorielle\n")
    lines.append("| Secteur | ETF | Variation Jour |")
    lines.append("|---------|-----|----------------|")
    for name, d in sorted(sectors.items(), key=lambda x: x[1].get("change_pct", 0), reverse=True):
        lines.append(f"| {name} | {d['ticker']} | {fmt_change(d.get('change_pct'))} |")
    lines.append("")

    # ── Momentum ─────────────────────────────────────────────
    print("  Screening momentum candidates (can take ~2 min)...")
    momentum = get_momentum_candidates(top_n=20)
    lines.append("## Candidats Momentum — Top 20\n")
    lines.append("| # | Symbole | Prix | Perf 1M | Perf 3M | Alpha vs SPY | % du 52S High |")
    lines.append("|---|---------|------|---------|---------|--------------|---------------|")
    for i, s in enumerate(momentum, 1):
        lines.append(
            f"| {i} | **{s['symbol']}** | ${s['price']:,.2f} | {fmt_change(s['perf_1m_pct'])} "
            f"| {fmt_change(s['perf_3m_pct'])} | {fmt_change(s['alpha_vs_spy_3m'])} "
            f"| {s['pct_from_52w_high']:.1f}% |"
        )
    lines.append("")

    # ── Value ─────────────────────────────────────────────────
    print("  Screening value candidates (can take ~3 min)...")
    value = get_value_candidates(top_n=20)
    lines.append("## Candidats Value — Top 20\n")
    lines.append("| # | Symbole | Prix | P/E | P/B | Marge Nette | EV/EBITDA | Div Yield | Secteur |")
    lines.append("|---|---------|------|-----|-----|-------------|-----------|-----------|---------|")
    for i, s in enumerate(value, 1):
        ev = f"{s['ev_ebitda']:.1f}x" if s.get("ev_ebitda") else "N/A"
        lines.append(
            f"| {i} | **{s['symbol']}** | ${s['price']:,.2f} | {s['pe_ratio']}x | {s['pb_ratio']}x "
            f"| {s['profit_margin_pct']}% | {ev} | {s['dividend_yield_pct']}% | {s['sector']} |"
        )
    lines.append("")

    lines.append("---")
    lines.append(f"*Données collectées le {today} via yfinance (cours différés de 15 min)*")

    return "\n".join(lines)


def main():
    today = date.today().isoformat()
    output_path = f"{OUTPUT_DIR}/{today}.md"

    print(f"📊 Collecte des données de marché pour le {today}...")
    report = build_report(today)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✅ Données écrites dans {output_path}")
    return output_path


if __name__ == "__main__":
    main()
