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

import alerts as weekly_alerts

BASE = Path(__file__).resolve().parent
ET = ZoneInfo("America/New_York")
COST = 0.0004  # round trip, as in the weekly rules


def _fires(rule: dict, d: float) -> bool:
    return d >= rule["min_difference"] if "min_difference" in rule else d <= rule["max_difference"]


def _num(v):
    v = float(v)
    return None if not math.isfinite(v) else round(v, 6)


def _held_positions(cfg, drules, wrules, close, opn, days, diff) -> list[dict]:
    """Trades at a loss on their planned exit, held until they close at +1% or hit the cap.

    Weekly rules: signal on a week's last trading day, planned exit the next
    week's last trading day. Daily rules: planned exit hold_days later. The cap
    counts trading days from the entry. SCO is never held past plan.
    """
    target = float(cfg["alerts"].get("hold_to_target", 0.01))
    i_t = len(days) - 1
    vc, vo = close["^VIX"].reindex(days), opn["^VIX"].reindex(days)
    pos = pd.Series(range(len(days)), index=days)
    wk = pos.groupby(pd.Grouper(freq="W-FRI"))
    lw = list(zip(wk.min().dropna().astype(int).values, wk.max().dropna().astype(int).values))
    entries = []  # (rule label, symbol, entry index, planned exit index, cap)
    for k, (f, l) in enumerate(lw[:-1]):
        if l < i_t - 200:
            continue
        d, v = float(vc.iloc[l] - vo.iloc[f]), float(vc.iloc[l])
        for r in wrules:
            if weekly_alerts.fires(r, d, v):
                entries.append((r["name"], r["symbol"], l, lw[k + 1][1], int(r["extend_cap_days"])))
    for r in drules:
        if r.get("extend_cap_days"):
            h = int(r["hold_days"])
            for i in range(max(0, i_t - 130), i_t + 1):
                if _fires(r, float(diff.iloc[i])):
                    entries.append((f"Daily {r['symbol']}", r["symbol"], i, i + h, int(r["extend_cap_days"])))
    out = []
    for label, sym, i_e, i_x, cap in entries:
        cap_i = i_e + cap
        if i_x > i_t or i_t > cap_i:
            continue
        s = close[sym].reindex(days).ffill()
        ep = float(s.iloc[i_e])
        if not math.isfinite(ep) or float(s.iloc[i_x]) / ep - 1 - COST >= 0:
            continue  # closed at a profit on plan
        tgt = ep * (1 + target)
        hit = next((j for j in range(i_x + 1, min(cap_i, i_t) + 1) if float(s.iloc[j]) >= tgt), None)
        if hit is not None and hit < i_t:
            continue  # already sold at the target
        cp = float(s.iloc[i_t])
        cap_day = (days[cap_i] if cap_i < len(days) else days[i_e] + pd.offsets.BDay(cap)).date().isoformat()
        base = {"key": f"{days[i_e].date().isoformat()}|{sym}|{label}", "rule": label, "symbol": sym,
                "entry_date": days[i_e].date().isoformat(), "entry_price": _num(ep),
                "planned_exit": days[i_x].date().isoformat(), "target_price": _num(tgt), "hold_until": cap_day,
                "price_now": _num(cp), "change": _num(cp / ep - 1), "days_held": int(i_t - i_e)}
        if hit == i_t:
            out.append({**base, "action": "SELL", "reason": "Reached the +1% target",
                        "text": f"SELL {sym} at today's close: it reached the +1% target (${tgt:.2f}). Bought "
                                f"{base['entry_date']} at about ${ep:.2f} ({label}), now ${cp:.2f} ({cp / ep - 1:+.2%})."})
        elif i_t == cap_i:
            out.append({**base, "action": "SELL", "reason": "Hold limit reached",
                        "text": f"SELL {sym} at today's close: the hold limit is reached without the +1% target. Bought "
                                f"{base['entry_date']} at about ${ep:.2f} ({label}), now ${cp:.2f} ({cp / ep - 1:+.2%})."})
        else:
            out.append({**base, "action": "HOLD", "reason": "Below +1% after the planned exit",
                        "text": f"HOLD {sym}: bought {base['entry_date']} at about ${ep:.2f} ({label}), now ${cp:.2f} "
                                f"({cp / ep - 1:+.2%}). Sell when it closes at or above ${tgt:.2f} (+1%), or at the close "
                                f"on {cap_day} at the latest."})
    out.sort(key=lambda x: (x["action"] != "SELL", x["entry_date"]))
    return out


def build(cfg: dict | None = None) -> dict:
    cfg = cfg or json.loads((BASE / "config.json").read_text())
    dc = cfg["daily"]
    rules = dc["rules"]
    wrules = [r for r in cfg["alerts"]["rules"] if r.get("extend_cap_days") and r.get("symbol")]
    syms = sorted({r["symbol"] for r in rules} | {r["symbol"] for r in wrules} | {"^VIX"})
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
            if r.get("extend_cap_days") and cp / ep - 1 - COST < 0:
                continue  # at a loss on the planned exit: held to target, see held positions
            orders.append({"key": f"SELL|{r['symbol']}", "action": "SELL", "symbol": r["symbol"],
                           "price": _num(cp), "entry_date": entry_day.date().isoformat(),
                           "sell_on": today.date().isoformat(), "change": _num(cp / ep - 1),
                           "note": f"Bought {entry_day.date().isoformat()} at about ${ep:.2f} "
                                   f"(VIX Difference {float(diff.loc[entry_day]):+.2f})."})

    held = _held_positions(cfg, rules, wrules, close, opn, days, diff)
    buys = [o["symbol"] for o in orders if o["action"] == "BUY"]
    sells = [o["symbol"] for o in orders if o["action"] == "SELL"]
    sells += [h["symbol"] for h in held if h["action"] == "SELL"]
    holds = [h["symbol"] for h in held if h["action"] == "HOLD"]
    if buys or sells:
        headline = "; ".join(p for p in (("Buy " + ", ".join(buys) + " at today's close") if buys else "",
                                          ("Sell " + ", ".join(sells) + " at today's close") if sells else "") if p) + "."
    else:
        headline = f"No daily signal: VIX moved less than {dc['threshold']:g} points today and nothing is due to sell."
    if holds:
        headline += " Holding past plan for the +1% target: " + ", ".join(holds) + "."
    daily_now = [{"date": today.date().isoformat(), "vix_open": _num(vix_o), "vix_close": _num(vix_c),
                  "difference": _num(d0), "headline": headline, "buys": len(buys), "sells": len(sells), "holds": len(holds),
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
            hold = ""
            if r.get("extend_cap_days"):
                hold = (f" If it is below your buy price at that close, keep holding until it closes at or above "
                        f"${o['price'] * (1 + dc.get('hold_to_target', 0.01)):.2f} (+1%), or sell at the close on "
                        f"{(today + pd.offsets.BDay(int(r['extend_cap_days']))).date().isoformat()} at the latest.")
            lines.append(f"BUY {o['symbol']} at today's close (about ${o['price']:.2f}); sell at the close on "
                         f"{o['sell_on']}.{hold} {r['note']}")
        else:
            lines.append(f"SELL {o['symbol']} at today's close: {o['note']} Now ${o['price']:.2f} ({o['change']:+.2%}).")
    for h in held:
        lines.append(h["text"])
    if not orders and not held:
        lines.append(headline)
    lines.append("Cash only: buy with settled funds, and do not reuse today's sale proceeds for a trade you sell before they settle.")

    return {"text": "\n".join(lines),
            "tables": {"daily_now": daily_now, "daily_orders": orders, "daily_rules": rule_rows, "daily_log": log,
                       "daily_held": [{k: v for k, v in h.items() if k != "text"} for h in held]}}


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
