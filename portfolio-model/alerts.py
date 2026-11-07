"""Weekly Difference alerts.

Turns the Difference-signal trades into fixed rules (config.json "alerts"),
then, from the weekly coefficient table:
* fires this week's alerts (Difference of the latest week vs each rule's bar),
* logs every week a rule would have fired, with the next week's result.

Weeks before ``live_from`` are a backtest of rules chosen on that same data,
so their win rates flatter the rules. Weeks from ``live_from`` on are the
live record: the rules were fixed before those outcomes were known.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def fires(rule: dict, diff, vix=None):
    """True where the Difference meets the rule: at or above ``min_difference``,
    or at or below ``max_difference`` for a rule on a falling-VIX week. A rule
    with ``min_vix`` also needs the week's VIX close at or above that level."""
    mx = rule.get("max_difference")
    if mx is not None and np.isfinite(float(mx)):
        hit = diff <= float(mx)
    else:
        hit = diff >= float(rule["min_difference"])
    mv = rule.get("min_vix")
    if mv is not None and np.isfinite(float(mv)):
        hit = hit & (vix >= float(mv)) if vix is not None else hit & False
    return hit


def trigger_text(rule: dict) -> str:
    if isinstance(rule.get("trigger_text"), str):
        return rule["trigger_text"]
    mx = rule.get("max_difference")
    if mx is not None and np.isfinite(float(mx)):
        return f"Weekly Difference of {float(mx):+g} points or less"
    return f"Weekly Difference of {rule['min_difference']:+g} points or more"


def build(wkly: dict, cfg: dict, prices: pd.DataFrame | None = None) -> dict:
    ac = cfg["alerts"]
    live_from = pd.Timestamp(ac["live_from"])
    sym = cfg["vix"]["weekly"]["series"]
    tbl = wkly["table"]
    d = tbl["Difference"]
    vclose = tbl["VIX Close"]
    weeks = tbl.index

    log = []
    def weekly_change(rule):
        if "series" in rule:
            return rule["series"], sym.get(rule["series"], rule["series"]), tbl[rule["series"]]
        # A tradable instrument outside the workbook's series: Friday-to-Friday % change.
        p = prices[rule["symbol"]].resample("W-FRI").last().pct_change(fill_method=None).reindex(weeks)
        return rule["symbol"], rule["symbol"], p

    for rule in ac["rules"]:
        sg = 1 if rule["side"] == "Long" else -1
        s, symbol, chg = weekly_change(rule)
        nxt = chg.shift(-1)
        for t in weeks[fires(rule, d, vclose)]:
            res = nxt.get(t)
            res = None if res is None or not np.isfinite(res) else float(sg * res)
            log.append({"week": t.date().isoformat(), "difference": float(d[t]), "rule_id": rule["id"],
                        "rule": rule["name"], "status": rule["status"], "series": s, "symbol": symbol,
                        "side": rule["side"], "result": res,
                        "outcome": "open" if res is None else ("won" if res > 0 else "lost"),
                        "record": "live" if t >= live_from else "backtest",
                        "key": f"{t.date().isoformat()}|{rule['id']}"})
    log = pd.DataFrame(log).sort_values(["week", "rule_id"], ascending=[False, True]) if log else pd.DataFrame()

    rules = []
    for rule in ac["rules"]:
        g = log[log["rule_id"] == rule["id"]] if len(log) else pd.DataFrame()
        bt = g[(g["record"] == "backtest") & (g["outcome"] != "open")] if len(g) else g
        lv = g[(g["record"] == "live") & (g["outcome"] != "open")] if len(g) else g
        rules.append({"rule_id": rule["id"], "rule": rule["name"], "status": rule["status"],
                      "trigger": trigger_text(rule),
                      "min_difference": float(rule.get("min_difference", np.nan)),
                      "max_difference": float(rule.get("max_difference", np.nan)),
                      "min_vix": float(rule.get("min_vix", np.nan)), "trigger_text": rule.get("trigger_text"),
                      "symbol": rule.get("symbol") or sym.get(rule["series"], rule["series"]), "side": rule["side"], "how": rule["how"],
                      "backtest_signals": int(len(bt)), "backtest_win_rate": float((bt["result"] > 0).mean()) if len(bt) else None,
                      "backtest_avg_result": float(bt["result"].mean()) if len(bt) else None,
                      "live_signals": int(len(lv)), "live_wins": int((lv["result"] > 0).sum()) if len(lv) else 0})

    last = weeks[-1]
    fired = [r for r in ac["rules"] if fires(r, d.iloc[-1], vclose.iloc[-1])]
    now = {"week": last.date().isoformat(), "difference": float(d.iloc[-1]),
           "vix_close": float(vclose.iloc[-1]), "fired": len(fired), "fired_trades": sum(r["status"] == "trade" for r in fired),
           "headline": ("No alert this week: Difference inside every rule's bar." if not fired else
                        "Alert: " + "; ".join(f"{r['name']} ({r['status']})" for r in fired) + "."),
           "live_from": ac["live_from"]}
    # Orders for this week's trades: entry at this Friday's close, exit by next Friday's close.
    orders = []
    for r in fired:
        if r["status"] != "trade" or "symbol" not in r or prices is None or r["symbol"] not in prices.columns:
            continue
        s = prices[r["symbol"]].dropna()
        s = s[s.index <= last]
        if not len(s):
            continue
        entry = float(s.iloc[-1])
        tp = r.get("take_profit")
        orders.append({"rule_id": r["id"], "symbol": r["symbol"], "entry_date": s.index[-1].date().isoformat(),
                       "entry_price": entry, "exit_by": (last + pd.Timedelta(days=7)).date().isoformat(),
                       "take_profit": float(tp) if tp else None,
                       "target_price": entry * (1 + float(tp)) if tp else None,
                       "take_profit_optional": bool(r.get("take_profit_optional", False)),
                       "take_profit_note": r.get("take_profit_note", ""),
                       # Hold-to-target: a loss at the planned exit is held until +1% or the cap.
                       "hold_target_price": entry * (1 + float(ac.get("hold_to_target", 0.01))) if r.get("extend_cap_days") else None,
                       "hold_until": (s.index[-1] + pd.offsets.BDay(int(r["extend_cap_days"]))).date().isoformat()
                                     if r.get("extend_cap_days") else None,
                       "no_extend_note": r.get("no_extend_note", "")})
    now["orders"] = orders
    prev = weeks[-2] if len(weeks) > 1 else None
    prev_rows = log[log["week"] == prev.date().isoformat()] if prev is not None and len(log) else pd.DataFrame()
    now["last_week"] = prev.date().isoformat() if prev is not None else None
    now["last_week_result"] = ("No alerts fired last week." if not len(prev_rows) else
                               "; ".join(f"{r['rule']}: {r['outcome']} ({r['result']:+.2%})" for _, r in prev_rows.iterrows()) + ".")
    return {"now": now, "rules": pd.DataFrame(rules), "log": log}


def message(al: dict) -> str:
    n = al["now"]
    lines = [f"VIX Difference alert for the week ending {n['week']}: Difference {n['difference']:+.2f} pts.", n["headline"]]
    for _, r in al["rules"].iterrows():
        if fires(r, n["difference"], n.get("vix_close")):
            wr = r["backtest_win_rate"]
            lines.append(f"- {r['rule']} [{r['status']}]: {r['how']} Backtest won "
                         f"{wr:.0%} of {r['backtest_signals']} signals." if wr is not None else f"- {r['rule']}")
    if n.get("orders"):
        lines.append("Orders (buy at the Friday close, at about these prices):")
        for o in n["orders"]:
            line = f"- {o['symbol']}: buy at about ${o['entry_price']:.2f}."
            if o["target_price"]:
                kind = "Optional take profit" if o["take_profit_optional"] else "Take profit"
                line += (f" {kind}: sell if it closes at or above ${o['target_price']:.2f} (+{o['take_profit']:.1%})"
                         f" before {o['exit_by']}; otherwise sell at the {o['exit_by']} close.")
                if o["take_profit_note"]:
                    line += " " + o["take_profit_note"]
            else:
                line += f" Sell at the {o['exit_by']} close."
            if o.get("hold_target_price"):
                line += (f" If it is below your buy price at that close, keep holding until it closes at or above"
                         f" ${o['hold_target_price']:.2f} (+1%), or sell at the close on {o['hold_until']} at the latest.")
            elif o.get("no_extend_note"):
                line += " " + o["no_extend_note"]
            lines.append(line)
    lines.append(f"Last week ({n['last_week']}): {n['last_week_result']}")
    return "\n".join(lines)


def sco_exit_plan(wkly: dict, cfg: dict, prices: pd.DataFrame, entry_price: float | None) -> dict:
    """Exit levels for the buy-SCO alert from how past alert trades played out.

    Each past alert: buy at that Friday's close, then check the next week's
    daily closes. Rules compared: hold to Friday, take profit at a daily close
    up by the target, stop at a daily close down by the stop, and both.
    """
    rule = next((r for r in cfg["alerts"]["rules"] if r["id"] == "sco-long"), None)
    ex = cfg["alerts"].get("sco_exit", {})
    if rule is None or "SCO" not in prices.columns:
        return {}
    tbl = wkly["table"]
    d = tbl["Difference"]
    daily = prices["SCO"].dropna()
    trades = []
    for t in tbl.index[d >= float(rule["min_difference"])]:
        e = daily[daily.index <= t]
        w = daily[(daily.index > t) & (daily.index <= t + pd.Timedelta(days=7))]
        if len(e) and len(w) and w.index[-1] >= t + pd.Timedelta(days=6):
            trades.append(w.values / e.iloc[-1] - 1)

    def run(target, stop):
        out = []
        for path in trades:
            res = path[-1]
            for rr in path:
                if target is not None and rr >= target:
                    res = rr
                    break
                if stop is not None and rr <= -stop:
                    res = rr
                    break
            out.append(res)
        out = np.array(out)
        return {"trades": int(len(out)), "win_rate": float((out > 0).mean()) if len(out) else None,
                "avg": float(out.mean()) if len(out) else None, "worst": float(out.min()) if len(out) else None}

    rules = [("Hold to Friday close", None, None)]
    rules += [(f"Take profit at +{t:.0%}", t, None) for t in ex.get("compare_targets", [])]
    rules += [(f"Stop at -{s:.0%}", None, s) for s in ex.get("compare_stops", [])]
    tp, st = ex.get("take_profit"), ex.get("optional_stop")
    if tp and st:
        rules.append((f"Take profit +{tp:.0%} and stop -{st:.0%}", tp, st))
    comparison = [{"exit_rule": n, **run(t, s), "key": n} for n, t, s in rules]

    fri = np.array([p[-1] for p in trades])
    q = np.percentile(fri, [10, 50, 90]) if len(fri) else [np.nan] * 3
    plan = {"take_profit": tp, "optional_stop": st}
    if entry_price:
        plan.update({"target_price": entry_price * (1 + tp) if tp else None,
                     "stop_price": entry_price * (1 - st) if st else None,
                     "median_price": entry_price * (1 + q[1]), "p10_price": entry_price * (1 + q[0]),
                     "p90_price": entry_price * (1 + q[2])})
    return {"plan": plan, "comparison": pd.DataFrame(comparison)}


def exit_message(plan: dict, entry_week: str | None, exit_by: str | None, entry_price: float | None) -> str:
    p = plan.get("plan", {}) if plan else {}
    if not entry_price or not p.get("target_price"):
        return ""
    cmp_ = plan["comparison"].set_index("exit_rule")
    tp_rule = f"Take profit at +{p['take_profit']:.0%}"
    hold = cmp_.loc["Hold to Friday close"]
    tpr = cmp_.loc[tp_rule] if tp_rule in cmp_.index else None
    lines = [f"SCO exit plan (bought {entry_week} close at ${entry_price:.2f}):",
             f"- Take profit: sell if SCO closes at or above ${p['target_price']:.2f} (+{p['take_profit']:.0%}) before {exit_by}.",
             f"- Otherwise sell at the {exit_by} close. Typical result ${p['median_price']:.2f}; 1-in-10 bad week ${p['p10_price']:.2f}.",
             (f"- Optional risk limit: stop at ${p['stop_price']:.2f} (-{p['optional_stop']:.0%}); in the backtest stops lowered the average."
              if p.get("stop_price") else "")]
    if tpr is not None:
        lines.append(f"- Backtest: take-profit won {tpr['win_rate']:.0%} (avg {tpr['avg']:+.2%}) vs hold-to-Friday "
                     f"{hold['win_rate']:.0%} (avg {hold['avg']:+.2%}) over {int(hold['trades'])} trades.")
    return "\n".join(l for l in lines if l)
