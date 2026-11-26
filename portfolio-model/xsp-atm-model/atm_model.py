"""XSP same-day ATM call and put check, run at 10:00 and 11:00 ET.

Separate from the VIX model: own settings (config.json here), own output
(output/), touches nothing else.

What it does at run time:
1. Live XSP and VIX1D (1-minute prices) and the real bid/ask for today's XSP
   expiry at the strike nearest XSP, from Yahoo (about 15 minutes delayed, so
   everything is priced as of that moment). Hours left to the close.
2. If the chain is unavailable, the price falls back to the video's formulas:
     M (expected move, 1 std dev) = S x IV x sqrt(hours left / 1638)
     ATM call ~ ATM put ~ 0.4 x M, straddle ~ 0.8 x M (break-even move)
   and Black-Scholes at the nearest $1 strike with the same IV, plus greeks.
3. Fair price: the average payout the option would have had on past days,
   using how far the index actually moved to the close per unit of VIX1D-implied
   move (2 years of hourly data, 10:30 and 11:30 entries), in the same bucket
   (VIX above or below 20, market up or down since the open), scaled to today.
4. Verdict per option: UPSIDE only if fair beats the market price by the
   minimum edge plus fees, judged against the ask (what you would pay).
   Otherwise NO UPSIDE. No upside is the normal answer.

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


def implied_vol(px, S, K, h, call=True):
    """Volatility that makes Black-Scholes match an option price (None if it cannot)."""
    from scipy.optimize import brentq
    intrinsic = max(S - K, 0) if call else max(K - S, 0)
    if not px or px <= intrinsic + 1e-6:
        return None
    f = lambda s: bs(S, K, s, h)["call" if call else "put"] - px
    try:
        return brentq(f, 0.01, 5.0)
    except ValueError:
        return None


def chain_quotes(day, K):
    """Bid and ask for today's XSP expiry at strike K, from Yahoo (about 15 minutes delayed)."""
    import time
    try:
        exp, opts = str(day), ()
        for attempt in range(3):  # Yahoo returns an empty list when it rate-limits
            t = yf.Ticker("^XSP")
            opts = t.options
            if opts:
                break
            time.sleep(20)
        if not opts:
            return None, "Yahoo option chain unavailable (rate limit or outage)"
        if exp not in opts:
            return None, f"no XSP expiry listed for {exp}"
        ch = t.option_chain(exp)
        out = {}
        for side, df in (("call", ch.calls), ("put", ch.puts)):
            row = df[df.strike == K]
            if not len(row):
                return None, f"strike {K} not in the chain"
            bid, ask = float(row.bid.iloc[0] or 0), float(row.ask.iloc[0] or 0)
            if ask <= 0 or bid < 0 or ask < bid:
                return None, f"no valid {side} bid/ask (bid {bid}, ask {ask})"
            out[side] = {"bid": bid, "ask": ask, "mid": (bid + ask) / 2}
        return out, None
    except Exception as e:  # rate limits, network
        return None, f"chain download failed: {e}"


def live() -> dict:
    now = datetime.now(ET)
    x = _dl("^XSP", period="1d", interval="1m")
    v = _dl("^VIX1D", period="1d", interval="1m")
    x = x[x.index.date == now.date()]
    v = v[v.index.date == now.date()]
    if not len(x) or not len(v) or now.weekday() >= 5:
        return {"run_at": now.strftime("%Y-%m-%d %H:%M ET"), "status": "NO DATA"}
    op = float(x.Open.iloc[0])
    S_now, iv_now = float(x.Close.iloc[-1]), float(v.Close.iloc[-1])
    # Option quotes run about 15 minutes behind: price everything at that moment.
    t_ref = x.index[-1] - pd.Timedelta(minutes=CFG["quote_delay_min"])
    xr, vr = x[x.index <= t_ref], v[v.index <= t_ref]
    if not len(xr) or not len(vr):
        xr, vr = x.iloc[:1], v.iloc[:1]
    S, t_px, iv = float(xr.Close.iloc[-1]), xr.index[-1], float(vr.Close.iloc[-1])
    close_hr = CFG.get("early_close_hour", {}).get(str(now.date()), 16)
    h = max((pd.Timestamp(now.date()).tz_localize(ET) + pd.Timedelta(hours=close_hr) - t_px).total_seconds() / 3600, 0.25)
    d = _dl("^VIX", period="10d")
    d.index = pd.to_datetime(d.index).date
    vix_prev = float(d.Close[d.index < now.date()].iloc[-1])

    sig = iv / 100 * math.sqrt(h / HPY)
    M = S * sig
    K = round(S)
    est = bs(S, K, iv / 100, h)
    q, q_err = chain_quotes(now.date(), K)
    hist = history()
    b, label = bucket(hist, vix_prev, S >= op)
    fc, fp, end = fair(b.z.values, S, K, sig)

    sides = {}
    for side, f in (("call", fc), ("put", fp)):
        if q:
            pay, src = q[side]["ask"], "ask"
            opt_iv = implied_vol(q[side]["mid"], S, K, h, side == "call")
        else:
            pay, src, opt_iv = est[side], "VIX1D estimate", None
        vd, mx = verdict(f, pay)
        lo, hi = CFG["quote_iv_sanity"]
        if q and vd == "UPSIDE" and (opt_iv is None or not lo <= opt_iv * 100 / iv <= hi):
            vd = "CHECK QUOTE (implied vol far from VIX1D, quote may be stale)"
        payoff = np.maximum(end - K, 0) if side == "call" else np.maximum(K - end, 0)
        sides[side] = {
            "bid": q[side]["bid"] if q else None, "ask": q[side]["ask"] if q else None,
            "price_used": round(pay, 2), "price_source": src, "vix1d_estimate": round(est[side], 2),
            "option_iv": None if opt_iv is None else round(opt_iv * 100, 1),
            "fair": round(f, 2), "max_pay": round(mx, 2), "verdict": vd,
            "edge_pct": round((f / pay - 1) * 100, 0),
            "prob_profit": round(float((payoff > pay).mean() * 100), 1),
            "breakeven": round(K + pay if side == "call" else K - pay, 2),
        }
    giv = sides["call"]["option_iv"] or iv
    g = bs(S, K, giv / 100, h)
    return {
        "run_at": now.strftime("%Y-%m-%d %H:%M ET"), "status": "OK",
        "quotes": "Yahoo chain" if q else f"VIX1D estimate ({q_err})",
        "xsp_now": round(S_now, 2), "xsp": round(S, 2), "price_time": t_px.strftime("%H:%M"), "xsp_open": round(op, 2),
        "vix1d_now": round(iv_now, 2), "vix1d": round(iv, 2), "vix_prev": round(vix_prev, 2), "hours_left": round(h, 2),
        "expected_move": round(M, 2), "video_atm": round(0.4 * M, 2), "video_straddle": round(0.8 * M, 2),
        "strike": K, "greeks": {k: round(val, 4) for k, val in g.items()},
        "bucket": label, "bucket_days": int(len(b)),
        "realized_vs_implied": round(float(np.abs(b.z).mean() / math.sqrt(2 / math.pi)), 2),
        "up_share": round(float((b.z > 0).mean() * 100), 1),
        "call": sides["call"], "put": sides["put"],
    }


def message(a: dict) -> str:
    if a["status"] != "OK":
        return f"XSP ATM {a['run_at']}: NO DATA (market closed or no live price)."
    c, p, gk = a["call"], a["put"], a["greeks"]
    any_up = [n for n, o in (("CALL", c), ("PUT", p)) if o["verdict"] == "UPSIDE"]
    chk = [n for n, o in (("CALL", c), ("PUT", p)) if o["verdict"].startswith("CHECK")]
    head = f"XSP ATM {a['run_at']}: " + (f"UPSIDE in {' and '.join(any_up)}" if any_up else
                                         f"CHECK QUOTE on {' and '.join(chk)}" if chk else "NO UPSIDE in either")

    def line(name, o):
        if o["ask"] is not None:
            q = f"bid ${o['bid']:.2f} / ask ${o['ask']:.2f} (${o['ask']*100:.0f})" + (f", IV {o['option_iv']:.0f}%" if o["option_iv"] else "")
        else:
            q = f"estimated ${o['price_used']:.2f} (${o['price_used']*100:.0f})"
        return (f"- {a['strike']} {name}: {q}, fair ${o['fair']:.2f} ({o['edge_pct']:+.0f}% vs price). {o['verdict']}. "
                f"Pay at most ${o['max_pay']:.2f}. Profit on {o['prob_profit']:.0f}% of similar days, break-even {o['breakeven']:.2f}.")

    return "\n".join([
        head,
        f"Quotes: {a['quotes']}, about {CFG['quote_delay_min']} minutes delayed, so prices are as of {a['price_time']}: XSP {a['xsp']:.2f}, VIX1D {a['vix1d']:.2f} (now {a['xsp_now']:.2f} and {a['vix1d_now']:.2f}). Open {a['xsp_open']:.2f}, VIX yesterday {a['vix_prev']:.2f}, {a['hours_left']:.1f} hours to the close.",
        f"Expected move to the close: {a['expected_move']:.2f} points (1 std dev). Video formula: ATM call or put about ${a['video_atm']:.2f}, straddle about ${a['video_straddle']:.2f}.",
        f"Greeks at {a['strike']}: delta call {gk['call_delta']:.2f} / put {gk['put_delta']:.2f}, gamma {gk['gamma']:.3f}, vega ${gk['vega_per_pt']*100:.0f} per vol point, time decay about ${-gk['theta_per_hour']*100:.0f} per hour per contract.",
        line("call", c),
        line("put", p),
        f"Fair is from {a['bucket_days']} past entries ({a['bucket']}): real moves were {a['realized_vs_implied']:.0%} of what VIX1D implied, index higher at the close {a['up_share']:.0f}% of the time.",
        "Check your broker's live ask before acting: buy only at or below 'pay at most'. Statistical pattern, not investment advice.",
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
