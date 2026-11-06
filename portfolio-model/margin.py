"""Margin alert: does this week's Difference sit at a level where the next
week has cleared a profit margin?

For each long-only instrument, every threshold rule "Difference >= t" (t >= 0)
and "Difference <= t" (t < 0) is scored on the weeks it covers: next-week
result net of a round-trip cost, win rate, average and t-stat. A rule
qualifies when it has enough weeks, wins often enough and averages at least
the margin. The best qualifying rule (highest t-stat) is the instrument's
current rule.

Picking the best of many thresholds on the same data overstates the edge, so
the same selection is replayed walk-forward: each week the rule is chosen
from earlier weeks only and the alert is scored on the week that follows.
The alert fires only when this week's Difference triggers the current rule
AND the walk-forward record also clears the margin.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _grid(mc):
    a, b, s = mc["up_thresholds"]
    up = [(">=", round(float(t), 4)) for t in np.arange(a, b + s / 2, s)]
    a, b, s = mc["down_thresholds"]
    down = [("<=", round(float(t), 4)) for t in np.arange(a, b + s / 2, s)]
    return up + down


def _score(dvals, rets, grid, mc):
    rows = []
    for op, t in grid:
        m = (dvals >= t) if op == ">=" else (dvals <= t)
        y = rets[m]
        y = y[np.isfinite(y)]
        n = len(y)
        if n == 0:
            rows.append((op, t, 0, np.nan, np.nan, np.nan, False))
            continue
        win, avg = float((y > 0).mean()), float(y.mean())
        sd = float(y.std(ddof=1)) if n > 1 else np.nan
        ts = avg / (sd / np.sqrt(n)) if n > 1 and sd > 0 else np.nan
        ok = n >= mc["min_weeks"] and win >= mc["min_win"] and avg >= mc["margin"]
        rows.append((op, t, n, win, avg, ts, ok))
    return rows


def _best(rows):
    ok = [r for r in rows if r[6] and np.isfinite(r[5])]
    return max(ok, key=lambda r: r[5]) if ok else None


def build(wkly: dict, cfg: dict, prices: pd.DataFrame) -> dict:
    mc = cfg["alerts"]["margin"]
    tbl = wkly["table"]
    weeks = tbl.index
    d = tbl["Difference"].values
    grid = _grid(mc)
    cost = float(mc["cost_round_trip"])
    cur = float(d[-1])

    summary, curve = [], []
    for sym in mc["instruments"]:
        if sym not in prices.columns:
            continue
        p = prices[sym].resample("W-FRI").last()
        r = (p.shift(-1) / p - 1).reindex(weeks).values - cost   # next-week result, net
        rows = _score(d, r, grid, mc)
        for op, t, n, win, avg, ts, ok in rows:
            curve.append({"instrument": sym, "rule": f"Difference {op} {t:+g}", "op": op, "threshold": t,
                          "weeks": n, "win_rate": win, "avg_result": avg, "t_stat": ts, "clears_margin": bool(ok),
                          "key": f"{sym}|{op}{t:+g}"})
        best = _best(rows)

        # Walk-forward: at week i, choose from weeks j < i (their outcome closed by week i's close).
        rec = []
        for i in range(int(mc["warmup_weeks"]), len(weeks) - 1):
            b = _best(_score(d[:i], r[:i], grid, mc))
            if b is None or not np.isfinite(r[i]):
                continue
            fire = d[i] >= b[1] if b[0] == ">=" else d[i] <= b[1]
            if fire:
                rec.append(r[i])
        rec = np.array(rec)
        wf_n = len(rec)
        wf_win = float((rec > 0).mean()) if wf_n else None
        wf_avg = float(rec.mean()) if wf_n else None
        confirmed = bool(wf_n >= mc["min_live_signals"] and wf_win is not None
                         and wf_win >= mc["min_win"] and wf_avg >= mc["margin"])
        triggers = bool(best is not None and (cur >= best[1] if best[0] == ">=" else cur <= best[1]))
        allw = r[np.isfinite(r)]
        summary.append({
            "instrument": sym,
            "rule": f"Difference {best[0]} {best[1]:+g}" if best else "No rule clears the margin",
            "weeks": best[2] if best else 0, "win_rate": best[3] if best else None,
            "avg_result": best[4] if best else None, "t_stat": best[5] if best else None,
            "normal_win": float((allw > 0).mean()), "normal_avg": float(allw.mean()),
            "wf_signals": wf_n, "wf_win_rate": wf_win, "wf_avg_result": wf_avg,
            "confirmed": "yes" if confirmed else "no",
            "triggers_now": "yes" if triggers else "no",
            "alert": "MARGIN ALERT" if (triggers and confirmed) else
                     ("triggered, not confirmed" if triggers else "no"),
        })

    summary = pd.DataFrame(summary)
    fired = summary[summary["alert"] == "MARGIN ALERT"] if len(summary) else summary
    unconfirmed = summary[summary["alert"] == "triggered, not confirmed"] if len(summary) else summary
    if len(fired):
        head = "Margin alert: " + "; ".join(f"buy {r.instrument} next week ({r.rule})" for r in fired.itertuples()) + "."
    else:
        head = (f"No margin alert: at Difference {cur:+.2f}, no instrument has a rule that clears the "
                f"{mc['margin']:.1%} weekly margin both in-sample and walk-forward.")
    now = {"week": weeks[-1].date().isoformat(), "difference": cur, "fired": int(len(fired)),
           "headline": head, "margin": float(mc["margin"]), "min_win": float(mc["min_win"]),
           "unconfirmed": ", ".join(f"{r.instrument} ({r.rule})" for r in unconfirmed.itertuples()) or "none"}
    return {"now": now, "summary": summary, "curve": pd.DataFrame(curve)}


def message(mg: dict) -> str:
    n = mg["now"]
    lines = [n["headline"]]
    if n["unconfirmed"] != "none":
        lines.append(f"Triggered in-sample but not confirmed walk-forward (not alerts): {n['unconfirmed']}.")
    return "\n".join(lines)
