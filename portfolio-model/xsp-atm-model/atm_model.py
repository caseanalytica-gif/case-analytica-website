"""XSP same-day ATM call and put check, run at 10:00 and 11:00 ET.

Separate from the VIX model: own settings (config.json here), own output
(output/), touches nothing else.

What it does at run time:
1. Live XSP and live VIX1D (1-minute prices). Hours left to the 4:00 PM close.
2. Market price, from the video's formulas with T in trading hours:
     M (expected move, 1 std dev) = S x IV x sqrt(hours left / 1638)
     ATM call ~ ATM put ~ 0.4 x M, straddle ~ 0.8 x M (break-even move)
   and Black-Scholes at the nearest $1 strike with the same IV, plus greeks.
3. Fair price: the average payout the option would have had on past days,
   using how far the index actually moved to the close per unit of VIX1D-implied
   move (2 years of hourly data, 10:30 and 11:30 entries), in the same bucket
   (VIX above or below 20, market up or down since the open), scaled to today.
4. Verdict per option: UPSIDE only if fair beats the market price by the
   minimum edge plus fees. Otherwise NO UPSIDE. No upside is the normal answer.

    ../venv/bin/python atm_model.py            # live run
    ../venv/bin/python atm_model.py --backtest # walk-forward test of the verdict
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import norm

BASE = Path(__file__).resolve().parent
ET = ZoneInfo("America/New_York")
CFG = json.loads((BASE / "config.json").read_text())
HPY = CFG["trading_hours_per_year"]


def _dl(sym, **kw):
    d = yf.download(sym, auto_adjust=False, progress=False, **kw)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    if d.index.tz is not None:
        d.index = d.index.tz_convert(ET)
    return d


def bs(S, K, sig, h):
    """Black-Scholes (r = 0) for h trading hours left. Prices per share of XSP."""
    T = h / HPY
    st = sig * math.sqrt(T)
    d1 = (math.log(S / K) + 0.5 * st ** 2) / st
    d2 = d1 - st
    call = S * norm.cdf(d1) - K * norm.cdf(d2)
    put = K * norm.cdf(-d2) - S * norm.cdf(-d1)
    pdf = norm.pdf(d1)
    theta_hr = -S * pdf * sig / (2 * math.sqrt(T)) / HPY
    return {
        "call": call, "put": put,
        "call_delta": norm.cdf(d1), "put_delta": norm.cdf(d1) - 1,
        "gamma": pdf / (S * st), "vega_per_pt": S * pdf * math.sqrt(T) / 100,
        "theta_per_hour": theta_hr,
    }


def history() -> pd.DataFrame:
    """Past days: move to close per unit of live VIX1D-implied move, at 10:30 and 11:30."""
    s = _dl("^GSPC", period=CFG["history_period"], interval="1h")
    v = _dl("^VIX1D", period=CFG["history_period"], interval="1h")
    d = _dl("^VIX", start="2022-06-01")
    d.index = pd.to_datetime(d.index).date
    vix_close = d["Close"]
    rows = []
    for day, g in s.groupby(s.index.date):
        if g.index[-1].hour < 15:
            continue
        prev = vix_close[vix_close.index < day]
        if not len(prev):
            continue
        gv = v[v.index.date == day]
        op, cl = float(g.Open.iloc[0]), float(g.Close.iloc[-1])
        for hh in (10, 11):
            t = pd.Timestamp(day).tz_localize(ET) + pd.Timedelta(hours=hh, minutes=30)
            if t not in g.index or t not in gv.index:
                continue
            S = float(g.Open[t])
            h = 15.5 - hh
            sig = float(gv.Open[t]) / 100 * math.sqrt(h / HPY)
            rows.append({"day": day, "hour": hh, "z": (cl / S - 1) / sig, "sig": sig,
                         "vix_prev": float(prev.iloc[-1]), "morning_up": S >= op})
    return pd.DataFrame(rows)


def bucket(hist: pd.DataFrame, vix_prev: float, morning_up: bool):
    hi = vix_prev >= CFG["split_vix"]
    b = hist[((hist.vix_prev >= CFG["split_vix"]) == hi) & (hist.morning_up == morning_up)]
    label = f"VIX {'20+' if hi else 'under 20'}, market {'up' if morning_up else 'down'} since open"
    if len(b) < CFG["min_bucket_days"]:
        return hist, "all days (bucket too small)"
    return b, label


def fair(z, S, K, sig):
    end = S * (1 + sig * z)
    cp, pp = np.maximum(end - K, 0), np.maximum(K - end, 0)
    return float(cp.mean()), float(pp.mean()), end


def verdict(fair_px, mkt_px):
    fee = CFG["fees_per_contract"] / 100
    need = mkt_px * (1 + CFG["min_edge_pct"] / 100) + fee
    return ("UPSIDE" if fair_px >= need else "NO UPSIDE"), fair_px - fee


def live() -> dict:
    now = datetime.now(ET)
    x = _dl("^XSP", period="1d", interval="1m")
    v = _dl("^VIX1D", period="1d", interval="1m")
    x = x[x.index.date == now.date()]
    v = v[v.index.date == now.date()]
    if not len(x) or not len(v) or now.weekday() >= 5:
        return {"run_at": now.strftime("%Y-%m-%d %H:%M ET"), "status": "NO DATA"}
    S, t_px = float(x.Close.iloc[-1]), x.index[-1]
    op = float(x.Open.iloc[0])
    iv = float(v.Close.iloc[-1])
    close_hr = CFG.get("early_close_hour", {}).get(str(now.date()), 16)
    h = max((pd.Timestamp(now.date()).tz_localize(ET) + pd.Timedelta(hours=close_hr) - t_px).total_seconds() / 3600, 0.25)
    d = _dl("^VIX", period="10d")
    d.index = pd.to_datetime(d.index).date
    vix_prev = float(d.Close[d.index < now.date()].iloc[-1])

    sig = iv / 100 * math.sqrt(h / HPY)
    M = S * sig
    K = round(S)
    g = bs(S, K, iv / 100, h)
    hist = history()
    b, label = bucket(hist, vix_prev, S >= op)
    fc, fp, end = fair(b.z.values, S, K, sig)
    cv, cmax = verdict(fc, g["call"])
    pv, pmax = verdict(fp, g["put"])
    return {
        "run_at": now.strftime("%Y-%m-%d %H:%M ET"), "status": "OK",
        "xsp": round(S, 2), "price_time": t_px.strftime("%H:%M"), "xsp_open": round(op, 2),
        "vix1d": round(iv, 2), "vix_prev": round(vix_prev, 2), "hours_left": round(h, 2),
        "expected_move": round(M, 2), "video_atm": round(0.4 * M, 2), "video_straddle": round(0.8 * M, 2),
        "strike": K, "greeks": {k: round(val, 4) for k, val in g.items()},
        "bucket": label, "bucket_days": int(len(b)),
        "realized_vs_implied": round(float(np.abs(b.z).mean() / math.sqrt(2 / math.pi)), 2),
        "up_share": round(float((b.z > 0).mean() * 100), 1),
        "call": {"market": round(g["call"], 2), "fair": round(fc, 2), "max_pay": round(cmax, 2), "verdict": cv,
                 "prob_profit": round(float((np.maximum(end - K, 0) > g["call"]).mean() * 100), 1),
                 "breakeven": round(K + g["call"], 2)},
        "put": {"market": round(g["put"], 2), "fair": round(fp, 2), "max_pay": round(pmax, 2), "verdict": pv,
                "prob_profit": round(float((np.maximum(K - end, 0) > g["put"]).mean() * 100), 1),
                "breakeven": round(K - g["put"], 2)},
    }


def message(a: dict) -> str:
    if a["status"] != "OK":
        return f"XSP ATM {a['run_at']}: NO DATA (market closed or no live price)."
    c, p, gk = a["call"], a["put"], a["greeks"]
    any_up = [n for n, o in (("CALL", c), ("PUT", p)) if o["verdict"] == "UPSIDE"]
    head = f"XSP ATM {a['run_at']}: " + (f"UPSIDE in {' and '.join(any_up)}" if any_up else "NO UPSIDE in either")
    return "\n".join([
        head,
        f"XSP {a['xsp']:.2f} at {a['price_time']} (open {a['xsp_open']:.2f}). VIX1D {a['vix1d']:.2f}, VIX yesterday {a['vix_prev']:.2f}. {a['hours_left']:.1f} hours to the close.",
        f"Expected move to the close: {a['expected_move']:.2f} points (1 std dev). Video formula: ATM call or put about ${a['video_atm']:.2f}, straddle about ${a['video_straddle']:.2f}.",
        f"Strike {a['strike']}. Delta call {gk['call_delta']:.2f} / put {gk['put_delta']:.2f}, gamma {gk['gamma']:.3f}, vega ${gk['vega_per_pt']*100:.0f} per VIX1D point, time decay about ${-gk['theta_per_hour']*100:.0f} per hour per contract.",
        f"- {a['strike']} call: market about ${c['market']:.2f} (${c['market']*100:.0f}), fair ${c['fair']:.2f}. {c['verdict']}. Pay at most ${c['max_pay']:.2f}. Profit on {c['prob_profit']:.0f}% of similar days, break-even {c['breakeven']:.2f}.",
        f"- {a['strike']} put: market about ${p['market']:.2f} (${p['market']*100:.0f}), fair ${p['fair']:.2f}. {p['verdict']}. Pay at most ${p['max_pay']:.2f}. Profit on {p['prob_profit']:.0f}% of similar days, break-even {p['breakeven']:.2f}.",
        f"Fair is from {a['bucket_days']} past entries ({a['bucket']}): real moves were {a['realized_vs_implied']:.0%} of what VIX1D implied, index higher at the close {a['up_share']:.0f}% of the time.",
        "If your broker's ask is at or below the 'pay at most' price, the option is cheap. Market price here is estimated from VIX1D, not a live option quote. Statistical pattern, not investment advice.",
    ])


def backtest():
    """Walk-forward: each day's fair price uses only earlier days. Report flagged trades."""
    hist = history().sort_values("day").reset_index(drop=True)
    res = []
    for i, r in hist.iterrows():
        past = hist[hist.day < r.day]
        if len(past) < 200:
            continue
        b, _ = bucket(past, r.vix_prev, r.morning_up)
        S, K, sig = 100.0, 100.0, r.sig
        mk = bs(S, K, sig / math.sqrt((15.5 - r.hour) / HPY), 15.5 - r.hour)
        fc, fp, _ = fair(b.z.values, S, K, sig)
        end = S * (1 + sig * r.z)
        for side, f, m, pay in (("call", fc, mk["call"], max(end - K, 0)), ("put", fp, mk["put"], max(K - end, 0))):
            v, _ = verdict(f / S * 713, m / S * 713)
            res.append({"day": r.day, "hour": r.hour, "side": side, "flag": v == "UPSIDE", "ret": pay / m - 1})
    df = pd.DataFrame(res)
    print(f"Walk-forward entries: {len(df)} ({df.day.min()} to {df.day.max()})")
    for side in ("call", "put"):
        g = df[df.side == side]
        f = g[g.flag]
        print(f"{side}: all avg {g.ret.mean()*100:+.0f}% won {(g.ret>0).mean()*100:.0f}% | flagged UPSIDE {len(f)} "
              + (f"avg {f.ret.mean()*100:+.0f}% won {(f.ret>0).mean()*100:.0f}%" if len(f) else ""))


def main():
    if "--backtest" in sys.argv:
        return backtest()
    a = live()
    txt = message(a)
    out = BASE / "output"
    out.mkdir(exist_ok=True)
    (out / "atm_alert.txt").write_text(txt + "\n")
    (out / "atm_alert.json").write_text(json.dumps({"atm_now": [a], "generated": datetime.now(timezone.utc).isoformat()}, indent=1, default=str))
    print(txt)


if __name__ == "__main__":
    main()
