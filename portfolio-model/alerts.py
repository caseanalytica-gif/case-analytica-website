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


def build(wkly: dict, cfg: dict) -> dict:
    ac = cfg["alerts"]
    live_from = pd.Timestamp(ac["live_from"])
    sym = cfg["vix"]["weekly"]["series"]
    tbl = wkly["table"]
    d = tbl["Difference"]
    weeks = tbl.index

    log = []
    for rule in ac["rules"]:
        s, sg = rule["series"], (1 if rule["side"] == "Long" else -1)
        nxt = tbl[s].shift(-1)
        for t in weeks[d >= float(rule["min_difference"])]:
            res = nxt.get(t)
            res = None if res is None or not np.isfinite(res) else float(sg * res)
            log.append({"week": t.date().isoformat(), "difference": float(d[t]), "rule_id": rule["id"],
                        "rule": rule["name"], "status": rule["status"], "series": s, "symbol": sym.get(s, s),
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
                      "trigger": f"Weekly Difference of {rule['min_difference']:+g} points or more",
                      "min_difference": float(rule["min_difference"]),
                      "symbol": sym.get(rule["series"], rule["series"]), "side": rule["side"], "how": rule["how"],
                      "backtest_signals": int(len(bt)), "backtest_win_rate": float((bt["result"] > 0).mean()) if len(bt) else None,
                      "backtest_avg_result": float(bt["result"].mean()) if len(bt) else None,
                      "live_signals": int(len(lv)), "live_wins": int((lv["result"] > 0).sum()) if len(lv) else 0})

    last = weeks[-1]
    fired = [r for r in ac["rules"] if d.iloc[-1] >= float(r["min_difference"])]
    now = {"week": last.date().isoformat(), "difference": float(d.iloc[-1]),
           "fired": len(fired), "fired_trades": sum(r["status"] == "trade" for r in fired),
           "headline": ("No alert this week: Difference below every rule's bar." if not fired else
                        "Alert: " + "; ".join(f"{r['name']} ({r['status']})" for r in fired) + "."),
           "live_from": ac["live_from"]}
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
        if n["difference"] >= r["min_difference"]:
            wr = r["backtest_win_rate"]
            lines.append(f"- {r['rule']} [{r['status']}]: {r['how']} Backtest won "
                         f"{wr:.0%} of {r['backtest_signals']} signals." if wr is not None else f"- {r['rule']}")
    lines.append(f"Last week ({n['last_week']}): {n['last_week_result']}")
    return "\n".join(lines)
