"""Daily VIX alert: the intraday Difference (today's VIX close minus today's open).

Run during the session (about 3:37 PM ET) so a buy can be placed before the
close. Rules live in config.json under "daily":

* VIX up 3+ points on the day: buy QQQ at the close, sell at the next close.
* VIX down 3+ points on the day: buy GLD at the close, sell 5 trading days later.

It also reminds the user to sell positions opened by earlier daily alerts.
Writes dashboard_data/daily_alert.txt (the alert text) and
dashboard_data/daily_alert.json (the dashboard's daily tables), and prints the
text. main.py also folds the same tables into vix_model_data.json.

    venv/bin/python daily_alert.py
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

BASE = Path(__file__).resolve().parent
ET = ZoneInfo("America/New_York")
COST = 0.0004  # round trip, as in the weekly rules


def _fires(rule: dict, d: float) -> bool:
    return d >= rule["min_difference"] if "min_difference" in rule else d <= rule["max_difference"]


def _num(v):
    v = float(v)
    return None if not math.isfinite(v) else round(v, 6)


def build(cfg: dict | None = None) -> dict:
    cfg = cfg or json.loads((BASE / "config.json").read_text())
    dc = cfg["daily"]
    rules = dc["rules"]
    syms = sorted({r["symbol"] for r in rules} | {"^VIX"})
    raw = yf.download(syms, start=dc.get("history_start", "2010-01-01"), auto_adjust=True, progress=False)
    close, opn = raw["Close"].dropna(how="all"), raw["Open"].dropna(how="all")
    if close.empty or close["^VIX"].dropna().empty:
        raise SystemExit("No VIX data from Yahoo Finance.")
    days = close["^VIX"].dropna().index
    diff = (close["^VIX"] - opn["^VIX"]).reindex(days)
    today = days[-1]
    now = datetime.now(ET)
    prelim = today.date() == now.date() and now.hour < 16
    d0 = float(diff.iloc[-1])
    vix_o, vix_c = float(opn["^VIX"].loc[today]), float(close["^VIX"].loc[today])
    l3 = today - pd.DateOffset(years=3)

    orders, log, rule_rows = [], [], []
    for r in rules:
        s = close[r["symbol"]].dropna().reindex(days).ffill()
        h = int(r["hold_days"])
        fwd = s.shift(-h) / s - 1 - COST          # buy this close, sell h trading days later
        hit = diff.apply(lambda x: _fires(r, x))
        res, base = fwd[hit].dropna(), fwd.dropna()
        last3 = res[res.index > l3]
        rule_rows.append({
            "rule_id": r["id"], "symbol": r["symbol"], "trigger": r["trigger_text"],
            "hold": "Next trading day's close" if h == 1 else f"{h} trading days",
            "signals": int(len(res)), "win_rate": _num((res > 0).mean()) if len(res) else None,
            "avg_result": _num(res.mean()) if len(res) else None,
            "normal_win": _num((base > 0).mean()), "normal_avg": _num(base.mean()),
            "last3y_signals": int(len(last3)), "last3y_win_rate": _num((last3 > 0).mean()) if len(last3) else None,
            "last3y_avg": _num(last3.mean()) if len(last3) else None})
        # Log: every signal in the last 3 years, open ones included.
        for t in days[hit & (days > l3)]:
            i = days.get_loc(t)
            done = i + h < len(days)
            rv = float(fwd.loc[t]) if done else None
            log.append({"key": f"{t.date().isoformat()}|{r['symbol']}", "date": t.date().isoformat(),
                        "difference": _num(diff.loc[t]), "symbol": r["symbol"],
                        "entry_price": _num(s.loc[t]),
                        "exit_date": days[i + h].date().isoformat() if done else None,
                        "result": _num(rv) if rv is not None else None,
                        "outcome": "open" if rv is None else ("won" if rv > 0 else "lost")})
        if _fires(r, d0):
            px = float(s.iloc[-1])
            orders.append({"key": f"BUY|{r['symbol']}", "action": "BUY", "symbol": r["symbol"],
                           "price": _num(px), "entry_date": today.date().isoformat(),
                           "sell_on": (today + pd.offsets.BDay(h)).date().isoformat(),
                           "change": None, "note": r["note"]})
        if len(days) > h and _fires(r, float(diff.iloc[-1 - h])):
            entry_day = days[-1 - h]
            ep, cp = float(s.loc[entry_day]), float(s.iloc[-1])
            orders.append({"key": f"SELL|{r['symbol']}", "action": "SELL", "symbol": r["symbol"],
                           "price": _num(cp), "entry_date": entry_day.date().isoformat(),
                           "sell_on": today.date().isoformat(), "change": _num(cp / ep - 1),
                           "note": f"Bought {entry_day.date().isoformat()} at about ${ep:.2f} "
                                   f"(VIX Difference {float(diff.loc[entry_day]):+.2f})."})

    buys = [o["symbol"] for o in orders if o["action"] == "BUY"]
    sells = [o["symbol"] for o in orders if o["action"] == "SELL"]
    if buys or sells:
        headline = "; ".join(p for p in (("Buy " + ", ".join(buys) + " at today's close") if buys else "",
                                          ("Sell " + ", ".join(sells) + " at today's close") if sells else "") if p) + "."
    else:
        headline = f"No daily signal: VIX moved less than {dc['threshold']:g} points today and nothing is due to sell."
    daily_now = [{"date": today.date().isoformat(), "vix_open": _num(vix_o), "vix_close": _num(vix_c),
                  "difference": _num(d0), "headline": headline, "buys": len(buys), "sells": len(sells),
                  "status": "preliminary" if prelim else "final",
                  "as_of": now.strftime("%-I:%M %p ET, %b %-d"),
                  "threshold": dc["threshold"]}]
    log.sort(key=lambda x: (x["date"], x["symbol"]), reverse=True)

    # Alert text
    lines = [f"Daily VIX alert for {today.date().isoformat()}"
             f"{' (preliminary, VIX as of ' + now.strftime('%-I:%M %p') + ' ET)' if prelim else ''}: "
             f"VIX open {vix_o:.2f}, now {vix_c:.2f}, Difference {d0:+.2f} pts."]
    for o in orders:
        if o["action"] == "BUY":
            r = next(x for x in rules if x["symbol"] == o["symbol"])
            lines.append(f"BUY {o['symbol']} at today's close (about ${o['price']:.2f}); sell at the close on "
                         f"{o['sell_on']}. {r['note']}")
        else:
            lines.append(f"SELL {o['symbol']} at today's close: {o['note']} Now ${o['price']:.2f} ({o['change']:+.2%}).")
    if not orders:
        lines.append(headline)
    lines.append("Cash only: buy with settled funds, and do not reuse today's sale proceeds for a trade you sell before they settle.")

    return {"text": "\n".join(lines),
            "tables": {"daily_now": daily_now, "daily_orders": orders, "daily_rules": rule_rows, "daily_log": log}}


def main() -> str:
    out = build()
    dd = BASE / "dashboard_data"
    dd.mkdir(parents=True, exist_ok=True)
    (dd / "daily_alert.txt").write_text(out["text"] + "\n")
    payload = {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **out["tables"]}
    (dd / "daily_alert.json").write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False))
    return out["text"]


if __name__ == "__main__":
    print(main())
