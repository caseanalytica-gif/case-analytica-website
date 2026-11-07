"""Daily VIX alert: the intraday Difference (today's VIX close minus today's open).

Run during the session (about 3:37 PM ET) so a buy can be placed before the
close. Rules and their backtests live in config.json under "daily":

* VIX up 3+ points on the day: buy QQQ at the close, sell at the next close.
* VIX down 3+ points on the day: buy GLD at the close, sell 5 trading days later.

It also reminds the user to sell positions opened by earlier daily alerts.
Writes dashboard_data/daily_alert.txt and prints the same text.

    venv/bin/python daily_alert.py
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

BASE = Path(__file__).resolve().parent
ET = ZoneInfo("America/New_York")


def main() -> str:
    cfg = json.loads((BASE / "config.json").read_text())["daily"]
    rules = cfg["rules"]
    syms = sorted({r["symbol"] for r in rules} | {"^VIX"})
    raw = yf.download(syms, period="3mo", auto_adjust=True, progress=False)
    close, opn = raw["Close"].dropna(how="all"), raw["Open"].dropna(how="all")
    if close.empty or close["^VIX"].dropna().empty:
        raise SystemExit("No VIX data from Yahoo Finance.")
    days = close["^VIX"].dropna().index
    today = days[-1]
    now = datetime.now(ET)
    diff = (close["^VIX"] - opn["^VIX"]).reindex(days)

    def fired(rule, d):
        return d >= rule["min_difference"] if "min_difference" in rule else d <= rule["max_difference"]

    d0 = float(diff.iloc[-1])
    vix_o, vix_c = float(opn["^VIX"].loc[today]), float(close["^VIX"].loc[today])
    prelim = today.date() == now.date() and now.hour < 16
    lines = [f"Daily VIX alert for {today.date().isoformat()}"
             f"{' (preliminary, VIX as of ' + now.strftime('%-I:%M %p') + ' ET)' if prelim else ''}: "
             f"VIX open {vix_o:.2f}, now {vix_c:.2f}, Difference {d0:+.2f} pts."]

    buys = [r for r in rules if fired(r, d0)]
    for r in buys:
        px = float(close[r["symbol"]].dropna().iloc[-1])
        lines.append(f"BUY {r['symbol']} at today's close (about ${px:.2f}); sell at the close "
                     f"{'tomorrow' if r['hold_days'] == 1 else str(r['hold_days']) + ' trading days from today'}. "
                     f"{r['note']}")

    # Exits due today: positions opened hold_days trading days ago.
    exits = []
    for r in rules:
        h = int(r["hold_days"])
        if len(days) > h:
            entry_day = days[-1 - h]
            d_then = float(diff.loc[entry_day])
            if fired(r, d_then):
                s = close[r["symbol"]].dropna()
                ep, cp = float(s.loc[:entry_day].iloc[-1]), float(s.iloc[-1])
                exits.append(f"SELL {r['symbol']} at today's close: bought {entry_day.date().isoformat()} "
                             f"at about ${ep:.2f} (VIX Difference {d_then:+.2f}), now ${cp:.2f} ({cp / ep - 1:+.2%}).")
    lines += exits

    if not buys and not exits:
        lines.append(f"No daily signal: Difference inside +/-{cfg['threshold']:g} points and no position to sell today.")
    lines.append("Cash only: buy with settled funds, and do not reuse today's sale proceeds for a trade you sell before they settle.")
    text = "\n".join(lines)
    out = BASE / "dashboard_data" / "daily_alert.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n")
    return text


if __name__ == "__main__":
    print(main())
