#!/usr/bin/env python3
"""
Orchestrateur du système de trading multi-agents.
Chaque agent = un appel claude -p qui lit et écrit des fichiers Markdown.

Flux :
  0. Python  : fetch_data.py          → data/market/YYYY-MM-DD.md
  1. Claude  : briefing agent         → data/briefing/YYYY-MM-DD.md
  2. Claude  : momentum trader        ┐ (en parallèle)
  3. Claude  : value trader           ┘ → data/traders/{style}/YYYY-MM-DD.md
  4. Claude  : broker agent           → data/broker/positions.md + data/broker/YYYY-MM-DD.md
  5. Claude  : performance agent      → data/performance/YYYY-MM-DD.md
"""
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler

# ── Chemins ────────────────────────────────────────────────────────────────────
PROJECT_DIR = Path(__file__).parent.resolve()
CLAUDE_BIN  = shutil.which("claude") or str(Path.home() / ".local/bin/claude")
TODAY       = date.today().isoformat()


# ── Utilitaire : appel claude -p ───────────────────────────────────────────────
def run_claude(
    agent_name: str,
    system_prompt_file: str,
    user_message: str,
    allowed_tools: str = "Read,Write",
) -> bool:
    system_prompt = (PROJECT_DIR / "prompts" / system_prompt_file).read_text(encoding="utf-8")

    cmd = [
        CLAUDE_BIN,
        "--print",
        "--system-prompt", system_prompt,
        "--allowedTools", allowed_tools,
        "--permission-mode", "acceptEdits",
        user_message,
    ]

    print(f"  → Lancement de {agent_name}...")
    result = subprocess.run(cmd, cwd=str(PROJECT_DIR), capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  ❌ {agent_name} — erreur (code {result.returncode})")
        if result.stderr:
            print(f"     {result.stderr[:300]}")
        return False

    print(f"  ✅ {agent_name} terminé")
    return True


# ── Étape 0 : fetch des données marché (Python pur) ───────────────────────────
def step_fetch_data(today: str) -> bool:
    market_file = PROJECT_DIR / "data" / "market" / f"{today}.md"
    if market_file.exists():
        print(f"  ✅ Données marché déjà présentes : {market_file.name}")
        return True

    result = subprocess.run(
        [sys.executable, str(PROJECT_DIR / "fetch_data.py")],
        cwd=str(PROJECT_DIR),
        capture_output=False,   # laisse les prints s'afficher
    )
    return result.returncode == 0


# ── Étape 1 : Briefing ─────────────────────────────────────────────────────────
def step_briefing(today: str) -> bool:
    return run_claude(
        agent_name="Agent 1 — Briefing",
        system_prompt_file="briefing.md",
        user_message=(
            f"Lis le fichier data/market/{today}.md qui contient toutes les données de marché du jour.\n"
            f"Rédige un briefing complet selon le format demandé et écris-le dans data/briefing/{today}.md."
        ),
    )


# ── Étape 2 & 3 : Traders (en parallèle) ─────────────────────────────────────
def step_momentum_trader(today: str) -> bool:
    return run_claude(
        agent_name="Agent 2 — Momentum Trader",
        system_prompt_file="momentum.md",
        user_message=(
            f"Lis ces fichiers pour préparer ton analyse :\n"
            f"- data/briefing/{today}.md (contexte marché du jour)\n"
            f"- data/market/{today}.md (données brutes, section Candidats Momentum)\n"
            f"- data/broker/positions.md (ton portefeuille actuel, section Momentum Trader)\n\n"
            f"Analyse les opportunités momentum d'aujourd'hui et écris tes décisions "
            f"dans data/traders/momentum/{today}.md selon le format demandé."
        ),
    )


def step_value_trader(today: str) -> bool:
    return run_claude(
        agent_name="Agent 3 — Value Trader",
        system_prompt_file="value.md",
        user_message=(
            f"Lis ces fichiers pour préparer ton analyse :\n"
            f"- data/briefing/{today}.md (contexte marché du jour)\n"
            f"- data/market/{today}.md (données brutes, section Candidats Value)\n"
            f"- data/broker/positions.md (ton portefeuille actuel, section Value Trader)\n\n"
            f"Analyse les opportunités value d'aujourd'hui et écris tes décisions "
            f"dans data/traders/value/{today}.md selon le format demandé."
        ),
    )


def step_traders_parallel(today: str) -> bool:
    print("  → Lancement des traders en parallèle...")
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(step_momentum_trader, today): "Momentum",
            executor.submit(step_value_trader, today): "Value",
        }
        results = {}
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as e:
                print(f"  ❌ {name} trader — exception : {e}")
                results[name] = False
    return all(results.values())


# ── Étape 4 : Broker ──────────────────────────────────────────────────────────
def step_broker(today: str) -> bool:
    return run_claude(
        agent_name="Agent 4 — Broker",
        system_prompt_file="broker.md",
        user_message=(
            f"Exécute les ordres du jour en lisant ces fichiers :\n"
            f"- data/traders/momentum/{today}.md (ordres du Momentum Trader)\n"
            f"- data/traders/value/{today}.md (ordres du Value Trader)\n"
            f"- data/broker/positions.md (état actuel du portefeuille)\n"
            f"- data/market/{today}.md (prix du jour pour validation des ordres)\n\n"
            f"1. Mets à jour data/broker/positions.md (portefeuille complet après exécution)\n"
            f"2. Écris le log d'exécution dans data/broker/{today}.md"
        ),
    )


# ── Étape 5 : Performance ─────────────────────────────────────────────────────
def step_performance(today: str) -> bool:
    return run_claude(
        agent_name="Agent 5 — Performance Tracker",
        system_prompt_file="performance.md",
        user_message=(
            f"Génère le rapport de performance du jour en lisant ces fichiers :\n"
            f"- data/briefing/{today}.md\n"
            f"- data/traders/momentum/{today}.md\n"
            f"- data/traders/value/{today}.md\n"
            f"- data/broker/{today}.md (log d'exécution)\n"
            f"- data/broker/positions.md (portefeuille mis à jour)\n"
            f"- data/market/{today}.md (données de marché du jour)\n\n"
            f"Écris le rapport complet dans data/performance/{today}.md"
        ),
    )


# ── Cycle journalier complet ──────────────────────────────────────────────────
def run_daily_cycle():
    today = date.today().isoformat()
    sep = "=" * 60

    print(f"\n{sep}")
    print(f"  CYCLE TRADING — {today}")
    print(f"{sep}")

    steps = [
        ("Étape 0 — Données marché",   lambda: step_fetch_data(today)),
        ("Étape 1 — Briefing",         lambda: step_briefing(today)),
        ("Étapes 2&3 — Traders",       lambda: step_traders_parallel(today)),
        ("Étape 4 — Broker",           lambda: step_broker(today)),
        ("Étape 5 — Performance",      lambda: step_performance(today)),
    ]

    for label, fn in steps:
        print(f"\n[{label}]")
        ok = fn()
        if not ok:
            print(f"\n⚠️  Cycle interrompu à : {label}")
            return

    print(f"\n{sep}")
    print(f"  CYCLE TERMINÉ — rapports dans data/")
    print(f"  Performance : data/performance/{today}.md")
    print(f"{sep}\n")


# ── Point d'entrée ────────────────────────────────────────────────────────────
def main():
    if "--now" in sys.argv:
        print("⚡ Mode --now : lancement immédiat")
        run_daily_cycle()
        return

    print(f"⏰ Scheduler actif — déclenchement chaque jour ouvré à 10h30 ET")
    print(f"   (passe --now pour un lancement immédiat)")
    print(f"   Claude bin : {CLAUDE_BIN}")

    scheduler = BlockingScheduler(timezone="America/New_York")
    scheduler.add_job(
        run_daily_cycle,
        trigger="cron",
        day_of_week="mon-fri",
        hour=10,
        minute=30,
        id="daily_cycle",
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Scheduler arrêté.")


if __name__ == "__main__":
    main()
