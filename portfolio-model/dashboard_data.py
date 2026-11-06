"""Write the model's results as one JSON file for the online VIX dashboard.

The dashboard reads every table from this single file, so refreshing the
dashboard means re-running main.py and replacing the file in the dashboard's
Sources panel.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


def _clean(v):
    if isinstance(v, (np.floating, float)):
        v = float(v)
        return None if not math.isfinite(v) else round(v, 6)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.strftime("%Y-%m-%d")
    return v


def _rows(df: pd.DataFrame, rename: dict | None = None) -> list[dict]:
    df = df.rename(columns=rename or {})
    return [{k: _clean(v) for k, v in r.items()} for r in df.to_dict("records")]


def write(path: Path, *, portfolios, mc_regime, vix: dict, cfg: dict) -> Path:
    st = vix["state"]
    crisis = vix["labels"][-1]
    state = [{
        "as_of": st["As of"], "vix": st["VIX close"], "vix_1w_ago": st["VIX 1 week ago"],
        "vix3m": st["VIX3M close"], "ratio": st["VIX / VIX3M ratio"],
        "term_structure": "Backwardation" if st["VIX / VIX3M ratio"] > 1 else "Contango",
        "regime": st["Current regime"], "days_in_regime": st["Consecutive days in regime"],
        "vix_percentile": st["VIX percentile (regime window)"], "vix_median": st["VIX median (regime window)"],
        "spy_realized_vol": st["SPY realized vol, last 21 days (pts)"],
        "implied_minus_realized": st["Implied minus realized vol (pts)"],
        **{f"p_crisis_{h}_{src}": st[f"P(reach {crisis} within {lab}), {name}"]
           for h, lab in (("1m", "1 month"), ("3m", "3 months"), ("12m", "12 months"))
           for src, name in (("model", "Markov model"), ("hist", "historical"))},
    }]
    odds = [{"horizon": lab, "regime": l, "probability": st[f"P(in {l} in {lab})"]}
            for lab in ("1 month", "12 months") for l in vix["labels"]]

    hist = pd.DataFrame({"vix": vix["vix"], "vix3m": vix["vix3m"]}).resample("W-FRI").last().dropna()
    hist = hist.reset_index().rename(columns={"index": "week", "Date": "week"})
    hist.columns = ["week", "vix", "vix3m"]

    stress = vix["stress"]
    prow = []
    for p in portfolios:
        cur = stress[(stress["Portfolio"] == p.name) & stress["Regime"].str.endswith("(current)")].iloc[0]
        m = mc_regime[p.name][0]
        prow.append({"portfolio": p.name, "net_return": p.net_return, "volatility": p.volatility,
                     "crisis_vol": p.extra["crisis_vol"], "current_regime_vol": cur["Ann. volatility in regime"],
                     "sharpe": p.sharpe_net, "var_1m_now": cur["1-month VaR 95% ($)"],
                     "p10": m["P10 Terminal Wealth"], "p50": m["P50 Terminal Wealth"],
                     "p90": m["P90 Terminal Wealth"], "cvar_1y": m["1-Year CVaR 95% (return)"]})
    weights = [{"portfolio": p.name, "ticker": t, "weight": float(w)}
               for p in portfolios for t, w in p.weights.items()]

    rg = vix["regimes"]
    regimes = [{"regime": r["Regime"], "vix_range": r["VIX range"], "days": r["Days"],
                "share": r["Share of time"], "avg_spell_days": r["Avg spell (days)"],
                "spy_vol": r.get("SPY ann. vol"), "corr_tlt_spy": r.get("corr(TLT, SPY)"),
                "corr_gld_spy": r.get("corr(GLD, SPY)")} for _, r in rg.iterrows()]

    d = vix["difference"]
    diff_vix = _rows(d["vix"], {"Frequency": "frequency", "Bucket": "bucket", "Periods": "periods",
                                "Mean Difference (pts)": "mean_difference",
                                "Mean VIX move in period": "vix_move",
                                "SPY return in same period": "spy_same_period",
                                "Next-period VIX change, mean": "vix_next_mean",
                                "Next-period VIX change, median": "vix_next_median",
                                "Share of times VIX lower next period": "share_vix_lower"})
    for r in diff_vix:
        r["key"] = f"{r['frequency']}|{r['bucket']}"
    inst = d["instruments"].copy()
    half_cols = [c for c in inst.columns if c.startswith("Excess, ")]
    inst = inst.rename(columns={half_cols[0]: "excess_first_half", half_cols[1]: "excess_second_half"})
    diff_inst = _rows(inst, {"Frequency": "frequency", "Instrument": "instrument", "Bucket": "bucket",
                             "Periods": "periods", "Next-period return after bucket": "return_after",
                             "Next-period return, all periods": "return_all",
                             "Excess vs other periods": "excess", "t-stat (Welch)": "t_stat",
                             "Share positive": "share_positive", "Same sign both halves": "stable"})
    for r in diff_inst:
        r["key"] = f"{r['frequency']}|{r['instrument']}|{r['bucket']}"
    strat = d["strategies"].drop(columns=["Rule"])
    diff_strat = _rows(strat, {"Frequency": "frequency", "Instrument": "instrument", "Side": "side",
                               "Trades": "trades", "Trades per year": "trades_per_year",
                               "Avg net return per trade": "avg_trade",
                               "Avg return, all periods (same side)": "avg_all",
                               "Excess per trade vs all periods": "excess_per_trade",
                               "t-stat (trade vs other periods)": "t_stat", "Hit rate": "hit_rate",
                               "Time in market": "time_in_market", "Strategy CAGR": "cagr",
                               "Strategy Sharpe (vs T-bills)": "sharpe",
                               "Buy-and-hold CAGR": "bh_cagr",
                               "Buy-and-hold Sharpe (vs T-bills)": "bh_sharpe"})
    for r in diff_strat:
        r["key"] = f"{r['frequency']}|{r['side']} {r['instrument']}"

    wk = vix["weekly"]["table"].copy()
    wk["next_week_vix"] = wk[vix["weekly"]["vix_name"]].shift(-1)
    wk = wk.iloc[-52:].iloc[::-1].reset_index()
    wk.columns = ["week", "vix", "natgas", "ten_year", "gold", "oil", "dj_commodity", "spread_total",
                  "average", "vix_open", "vix_close", "difference", "std", "next_week_vix"]
    ivhv = vix["iv_hv"].iloc[-252:].reset_index()
    ivhv.columns = ["date", "iv", "iv_rank", "hv", "hv_rank", "iv_minus_hv"]

    sig = vix["diff_signal"]
    cur = sig["current"]
    state[0].update({"diff_week": cur["week"], "diff_value": cur["difference"], "diff_bucket": cur["bucket"],
                     "diff_extreme": "yes" if cur["extreme"] else "no", "diff_first_week": cur["first_week"],
                     "diff_weeks": cur["weeks_total"]})
    diff_signal = _rows(sig["buckets"])
    diff_now = _rows(sig["now"])
    for r in diff_now:
        r["trade"] = f"{r['side']} {r['series']}"
        strong = r["p_value"] is not None and r["p_value"] < 0.05 and r["holds_both_halves"]
        r["verdict"] = "holds" if strong else ("weak" if r["holds_both_halves"] else "no edge")

    al = vix["alerts"]
    alert_now = [dict(al["now"])]
    alert_rules = _rows(al["rules"])
    alert_log = _rows(al["log"])

    # SCO: the long-only instrument for the oil-short alert, with crude for comparison.
    px = vix["prices"]
    sco_rows, sco_stats = [], []
    if "SCO" in px.columns:
        p = px[["SCO", "CL=F"]].copy()
        p.columns = ["sco", "crude"]
        p["crude"] = p["crude"].mask(p["crude"] <= 0)
        recent = p[p.index >= p.index.max() - pd.DateOffset(years=5)].dropna(subset=["sco"])
        recent = recent.reset_index()
        recent.columns = ["date", "sco", "crude"]
        sco_rows = _rows(recent)
        s = p["sco"].dropna()
        wkr = p.resample("W-FRI").last().pct_change(fill_method=None)
        yr = s[s.index >= s.index.max() - pd.DateOffset(years=1)]
        trades = al["log"][al["log"]["rule_id"] == "sco-long"] if len(al["log"]) else pd.DataFrame()
        done = trades[trades["outcome"] != "open"] if len(trades) else trades
        sco_stats = [{
            "as_of": s.index[-1].date().isoformat(), "last": float(s.iloc[-1]),
            "chg_1w": float(s.iloc[-1] / s.iloc[-6] - 1), "chg_1m": float(s.iloc[-1] / s.iloc[-22] - 1),
            "high_52w": float(yr.max()), "low_52w": float(yr.min()),
            "corr_weekly_crude": float(wkr["sco"].corr(wkr["crude"])),
            "alert_trades": int(len(done)),
            "alert_win_rate": float((done["result"] > 0).mean()) if len(done) else None,
            "alert_avg": float(done["result"].mean()) if len(done) else None,
            "alert_open": "yes" if len(trades) and (trades["outcome"] == "open").any() else "no",
        }]
        # The open SCO trade, if any: bought at that Friday's close, sold at the next Friday's close.
        open_t = trades[trades["outcome"] == "open"] if len(trades) else trades
        if len(open_t):
            buy_wk = pd.Timestamp(open_t.iloc[0]["week"])
            entry = s[s.index <= buy_wk]
            sco_stats[0].update({
                "entry_week": buy_wk.date().isoformat(), "entry_price": float(entry.iloc[-1]),
                "exit_by": (buy_wk + pd.Timedelta(days=7)).date().isoformat(),
                "entry_difference": float(open_t.iloc[0]["difference"]),
                "since_entry": float(s.iloc[-1] / entry.iloc[-1] - 1),
                "position": "Open: buy SCO at the entry close, sell at the exit-day close"})
        else:
            sco_stats[0].update({"entry_week": None, "entry_price": None, "exit_by": None,
                                 "entry_difference": None, "since_entry": None,
                                 "position": "No open SCO alert this week"})

    mg = vix["margin"]
    margin_now = [dict(mg["now"])]
    margin_summary = _rows(mg["summary"])
    margin_curve = _rows(mg["curve"])

    se = vix.get("sco_exit") or {}
    if sco_stats and se:
        pl = se.get("plan", {})
        sco_stats[0].update({k: pl.get(k) for k in ("take_profit", "optional_stop", "target_price", "stop_price",
                                                       "median_price", "p10_price", "p90_price")})
    sco_exit_rules = _rows(se["comparison"]) if se else []

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "state": state, "odds": odds, "history": _rows(hist), "portfolios": prow, "weights": weights,
        "regimes": regimes, "diff_vix": diff_vix, "diff_inst": diff_inst, "diff_strat": diff_strat,
        "weekly": _rows(wk), "ivhv": _rows(ivhv), "diff_signal": diff_signal, "diff_now": diff_now,
        "alert_now": alert_now, "alert_rules": alert_rules, "alert_log": alert_log,
        "sco": sco_rows, "sco_stats": sco_stats,
        "margin_now": margin_now, "margin_summary": margin_summary, "margin_curve": margin_curve,
        "sco_exit_rules": sco_exit_rules,
        "findings": [{"n": i + 1, "text": t} for i, t in enumerate(vix["findings"])],
    }
    payload = json.loads(json.dumps(payload, default=_clean))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False))
    return path
