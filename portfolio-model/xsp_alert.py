"""Morning XSP check: a same-day bull put spread sold at 50 delta.

Run at about 9:20 AM ET on weekdays. The trade it checks: sell the XSP put at
the strike nearest the live price (50 delta), buy the put 2 or 3 strikes lower,
both expiring today, sold about 9:35 to 9:40 AM ET and held to the close
(XSP settles in cash on the 4:00 PM S&P 500 close).

The script does not see option prices. It says:

* SKIP, with the reason, on days the history says the trade makes no sense:
  VIX closed 30 or higher, SPY is 0.5% or more below yesterday's close in
  premarket, or VIX fell 3+ points (close minus open) yesterday. On those days
  the break-even credit rose to $83 to $100 for a $2 spread, above what the
  market usually pays.
* Otherwise LOOK, with the minimum credit to accept for each width: the average
  payout since 2010 on days like today, scaled to today's XSP level, plus fees
  and a safety margin. Below that credit, do not place it.
* A rough fair credit from yesterday's VIX1D, as a guide to whether the minimum
  is reachable.

History uses SPY open to close (a tradable open; the S&P 500 index open print
is partly stale and flatters gap days). Settings: config.json under "xsp".
Writes dashboard_data/xsp_alert.txt and dashboard_data/xsp_alert.json.

    venv/bin/python xsp_alert.py
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import norm

BASE = Path(__file__).resolve().parent
ET = ZoneInfo("America/New_York")
BUCKETS = [(0, 15, "under 15"), (15, 20, "15 to 20"), (20, 30, "20 to 30"), (30, 999, "30 or higher")]


def _col(df, field, sym):
    return df[field][sym] if isinstance(df.columns, pd.MultiIndex) else df[field]


def _put_spread_bs(S, K, w, sig, T=1 / 252):
    def put(k):
        d1 = (math.log(S / k) + 0.5 * sig ** 2 * T) / (sig * math.sqrt(T))
        d2 = d1 - sig * math.sqrt(T)
        return k * norm.cdf(-d2) - S * norm.cdf(-d1)
    return (put(K) - put(K - w)) * 100


def build(cfg: dict) -> dict:
    xc = cfg["xsp"]
    sk = xc["skip_rules"]
    now = datetime.now(ET)
    today = pd.Timestamp(now.date())

    d = yf.download(["SPY", "^VIX", "^VIX1D", "^XSP"], start=xc["history_start"],
                    auto_adjust=False, actions=True, progress=False)
    spy = pd.DataFrame({k: _col(d, k, "SPY") for k in ["Open", "Close", "Dividends"]}).dropna(subset=["Open", "Close"])
    vix_c, vix_o = _col(d, "Close", "^VIX").dropna(), _col(d, "Open", "^VIX").dropna()
    v1d = _col(d, "Close", "^VIX1D").dropna()
    xsp = _col(d, "Close", "^XSP").dropna()

    # Completed sessions only (a row for today can appear before the open).
    spy_done = spy[spy.index.tz_localize(None) < today] if spy.index.tz is not None else spy[spy.index < today]
    prev_day = spy_done.index[-1]
    prev_close = float(spy_done.Close.iloc[-1])
    vprev = vix_c[vix_c.index <= prev_day]
    vix_prev = float(vprev.iloc[-1])
    vix_chg = float(vprev.iloc[-1] - vix_o.reindex(vprev.index).iloc[-1])
    v1d_prev = float(v1d[v1d.index <= prev_day].iloc[-1]) if len(v1d) else float("nan")
    xsp_prev = float(xsp[xsp.index <= prev_day].iloc[-1]) if len(xsp) else prev_close

    # Premarket SPY.
    m = yf.download("SPY", period="1d", interval="5m", prepost=True, auto_adjust=False, progress=False)
    pm_price, pm_time = None, None
    if len(m):
        m.index = m.index.tz_convert(ET)
        pre = m[(m.index.date == now.date()) & ((m.index.hour * 100 + m.index.minute) < 930)]
        if len(pre):
            pm_price = float(_col(pre, "Close", "SPY").iloc[-1])
            pm_time = pre.index[-1].strftime("%H:%M")
    market_open_today = pm_price is not None and now.weekday() < 5
    gap = (pm_price / prev_close - 1) * 100 if pm_price else float("nan")
    xsp_est = xsp_prev * (1 + (gap / 100 if math.isfinite(gap) else 0))
    short_k = round(xsp_est)

    # History: SPY open to close since history_start, excluding ex-dividend days.
    h = spy[(spy.index >= xc["history_start"]) & (spy.Dividends == 0)].copy()
    h["r"] = h.Close / h.Open - 1
    h["vix_prev"] = vix_c.shift().reindex(h.index)
    h = h.dropna(subset=["vix_prev"])
    lo, hi, label = next(b for b in BUCKETS if b[0] <= vix_prev < b[1])
    like = h[(h.vix_prev >= lo) & (h.vix_prev < hi)]

    reasons = []
    if vix_prev >= sk["max_vix"]:
        reasons.append(f"VIX closed {vix_prev:.2f}, at or above {sk['max_vix']}: the index swings too far for a 50-delta spread (full loss on 41% of days, break-even near $88 for $2 wide)")
    if math.isfinite(gap) and gap <= sk["min_premarket_gap_pct"]:
        reasons.append(f"SPY is {gap:+.2f}% versus yesterday's close in premarket: after gaps down of 0.5% or more the $2 break-even rose to $82 to $88")
    if vix_chg <= sk["min_prior_vix_change"]:
        reasons.append(f"VIX fell {vix_chg:+.2f} points yesterday (close minus open): the next day the $2 break-even was about $100 and the spread was kept 47% of the time")
    if not market_open_today:
        status = "NO DATA"
    else:
        status = "SKIP" if reasons else "LOOK"

    rows = []
    for w in xc["widths"]:
        pay = np.clip(-like.r.values * xsp_est, 0, w) * 100
        be = float(pay.mean())
        min_credit = math.ceil(be + xc["fees_per_spread"] + xc["safety_margin"])
        fair = _put_spread_bs(xsp_est, short_k, w, v1d_prev / 100) if math.isfinite(v1d_prev) else float("nan")
        rows.append({
            "width": w, "short_strike": short_k, "long_strike": short_k - w,
            "keep_pct": round(float((pay == 0).mean() * 100), 1),
            "full_loss_pct": round(float((pay >= w * 100 - 1e-9).mean() * 100), 1),
            "break_even": round(be, 2), "min_credit": min_credit,
            "vix1d_fair_credit": None if not math.isfinite(fair) else round(fair, 2),
            "max_loss": round(w * 100 - min_credit, 2),
        })

    return {
        "run_at": now.strftime("%Y-%m-%d %H:%M ET"), "date": str(now.date()), "status": status, "reasons": reasons,
        "prev_day": str(prev_day.date()), "spy_prev_close": round(prev_close, 2),
        "spy_premarket": pm_price, "premarket_time": pm_time, "premarket_gap_pct": None if not math.isfinite(gap) else round(gap, 2),
        "vix_prev": round(vix_prev, 2), "vix_prev_change": round(vix_chg, 2), "vix_bucket": label,
        "vix1d_prev": None if not math.isfinite(v1d_prev) else round(v1d_prev, 2),
        "xsp_prev_close": round(xsp_prev, 2), "xsp_estimate": round(xsp_est, 2),
        "history_days": int(len(like)), "spreads": rows, "entry_window": xc["entry_window"],
    }


def message(a: dict) -> str:
    if a["status"] == "NO DATA":
        return (f"XSP {a['date']}: NO DATA. No premarket SPY price for today (market holiday or data delay). "
                "No spread check today.")
    gap = f"{a['premarket_gap_pct']:+.2f}%" if a["premarket_gap_pct"] is not None else "n/a"
    head = (f"XSP {a['date']}: {a['status']}. 50-delta bull put spread, expires today.\n"
            f"SPY premarket {a['spy_premarket']:.2f} at {a['premarket_time']} ET ({gap} vs {a['spy_prev_close']:.2f} close). "
            f"VIX {a['vix_prev']:.2f} (yesterday {a['vix_prev_change']:+.2f} points close minus open). "
            + (f"VIX1D {a['vix1d_prev']:.2f}. " if a["vix1d_prev"] is not None else "")
            + f"XSP about {a['xsp_estimate']:.2f}.")
    if a["status"] == "SKIP":
        lines = [head, "Makes no sense today:"] + [f"- {r}" for r in a["reasons"]]
        lines.append("Do not sell the spread today.")
        return "\n".join(lines)
    lines = [head, f"Sell {a['entry_window']}. Short strike is the one nearest the live XSP price (about {a['spreads'][0]['short_strike']}); adjust if XSP has moved.",
             f"Days like today since 2010 (VIX {a['vix_bucket']}, {a['history_days']} days):"]
    for s in a["spreads"]:
        fair = f"; fair credit from VIX1D about ${s['vix1d_fair_credit']:.0f}" if s["vix1d_fair_credit"] is not None else ""
        lines.append(f"- ${s['width']} wide, sell {s['short_strike']}P / buy {s['long_strike']}P: accept only a credit of ${s['min_credit']} or more "
                     f"(break-even ${s['break_even']:.0f}). Kept in full {s['keep_pct']:.0f}% of days, full loss {s['full_loss_pct']:.0f}%, "
                     f"most you can lose about ${s['max_loss']:.0f}{fair}.")
    lows = [s for s in a["spreads"] if s["vix1d_fair_credit"] is not None and s["vix1d_fair_credit"] < s["min_credit"]]
    if lows:
        lines.append("Fair credit is below the minimum for " + ", ".join(f"${s['width']} wide" for s in lows)
                     + ": likely no edge there today unless the market pays more than the minimum.")
    lines.append("If the mid price is below the minimum credit, it makes no sense: skip it. Needs spread approval; a cash account usually cannot sell spreads. Statistical pattern, not investment advice.")
    return "\n".join(lines)


def main():
    cfg = json.loads((BASE / "config.json").read_text())
    a = build(cfg)
    txt = message(a)
    out = BASE / "dashboard_data"
    out.mkdir(exist_ok=True)
    (out / "xsp_alert.txt").write_text(txt + "\n")
    (out / "xsp_alert.json").write_text(json.dumps({"xsp_now": [a], "generated": datetime.now(timezone.utc).isoformat()}, indent=1, default=str))
    print(txt)


if __name__ == "__main__":
    main()
