"""VIX-centred risk engine.

The VIX is the market's 30-day implied volatility for the S&P 500. It is not
investable (only futures-based products such as VIXY are), so this module uses
it in the three places where it carries real information:

1. Regime model. Each day is labelled Calm / Normal / Elevated / Crisis by the
   VIX close. Per-regime covariance matrices and a Markov transition matrix
   turn one static risk model into a state-dependent one.
2. Forward-looking risk. Today's regime, term structure (VIX vs VIX3M) and the
   Markov chain give the probability of reaching Crisis over 1, 3, 12 months
   and each portfolio's risk under current conditions.
3. Signals, tested rather than assumed. Every timing rule is backtested with a
   one-day lag (no look-ahead), and the weekly cross-asset "coefficient"
   workbook is automated and checked for predictive power.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

import data_loader
import optimizer as opt

log = logging.getLogger(__name__)
DAYS = 252


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
@dataclass
class VixData:
    vix_open: pd.Series
    vix: pd.Series            # VIX close
    vix3m: pd.Series
    tbill: pd.Series          # daily simple return of 13-week T-bills
    asset_prices: pd.DataFrame
    asset_returns: pd.DataFrame
    weekly_close: pd.DataFrame
    weekly_report: dict


def load(cfg: dict, tickers: list[str], base_dir: Path) -> VixData:
    vc, dc = cfg["vix"], cfg["data"]
    years = vc["regime_lookback_years"]
    idx = fetch = data_loader.fetch_panel(
        [vc["symbol"], vc["term_symbol"], vc["tbill_symbol"]], years, dc, base_dir,
        fields=("Open", "Close"), tag="vix")
    close = fetch["Close"].copy()
    close.index = pd.to_datetime(close.index).tz_localize(None)
    opn = idx["Open"].copy()
    opn.index = pd.to_datetime(opn.index).tz_localize(None)

    # Asset panel over the (longer) regime window, cleaned exactly like the
    # base model's.
    rcfg = dict(dc, lookback_years=years)
    prices, rets, rep = data_loader.load_data(tickers, rcfg, base_dir)
    if rep["dropped_tickers"]:
        log.warning("Regime window dropped %s", rep["dropped_tickers"])

    dates = rets.index
    vix = close[vc["symbol"]].reindex(dates).ffill()
    vix3m = close[vc["term_symbol"]].reindex(dates).ffill()
    vopen = opn[vc["symbol"]].reindex(dates).ffill()
    irx = close[vc["tbill_symbol"]].reindex(dates).ffill().bfill()
    tbill = (irx / 100.0) / DAYS                 # annual yield -> daily accrual
    if vix.isna().any():
        raise data_loader.DataError("VIX series has gaps that cannot be filled")

    # Weekly cross-asset panel (the "Coefficient Table" workbook).
    ws = vc["weekly"]["series"]
    extra = [s for s in cfg.get("alerts", {}).get("instruments", []) if s not in ws.values()]
    wk = data_loader.fetch_panel(list(ws.values()) + ["SPY"] + extra, years, dc, base_dir,
                                 fields=("Close",), tag="weekly")["Close"]
    wk.index = pd.to_datetime(wk.index).tz_localize(None)
    wk = wk.mask(wk <= 0)                        # WTI settled negative in Apr 2020
    missing = [s for s in ws.values() if s not in wk.columns or wk[s].dropna().empty]
    report = {"missing": missing}
    if missing:
        log.warning("Weekly series unavailable: %s", missing)

    return VixData(vopen, vix, vix3m, tbill, prices, rets, wk, report)


# --------------------------------------------------------------------------
# Regimes
# --------------------------------------------------------------------------
@dataclass
class RegimeModel:
    labels: list
    thresholds: list
    states: pd.Series          # int regime per day (contemporaneous VIX close)
    P_day: np.ndarray
    stationary: np.ndarray
    mu: dict                   # label -> annual mean (Series), raw per regime
    cov: dict                  # label -> annual covariance (DataFrame)
    counts: dict
    shrink: dict               # label -> Ledoit-Wolf intensity

    @property
    def K(self):
        return len(self.labels)

    def P(self, days: int) -> np.ndarray:
        """Daily chain compounded ``days`` times. Memoryless, so it understates
        persistence at multi-week horizons; used only for first-passage odds."""
        return np.linalg.matrix_power(self.P_day, int(days))

    def P_h(self, h: int) -> np.ndarray:
        """Empirical h-day-ahead transition matrix: counts of (state_t,
        state_{t+h}) over all overlapping pairs. This keeps the persistence the
        daily chain loses and is what the monthly Monte Carlo step uses."""
        s = self.states.values
        E = np.zeros((self.K, self.K))
        np.add.at(E, (s[:-h], s[h:]), 1)
        for k in range(self.K):
            if E[k].sum() == 0:
                E[k, k] = 1
        return E / E.sum(axis=1, keepdims=True)

    def P_months(self, months: int, h: int = 21) -> np.ndarray:
        return np.linalg.matrix_power(self.P_h(h), int(months))

    def mixture_cov(self) -> np.ndarray:
        return sum(self.stationary[k] * self.cov[l].values for k, l in enumerate(self.labels))

    def hit_probability(self, start: int, target: int, days: int) -> float:
        """P(reach ``target`` at least once within ``days`` | start)."""
        if start == target:
            return 1.0
        A = self.P_day.copy()
        A[target] = 0.0
        A[target, target] = 1.0                  # make target absorbing
        return float(np.linalg.matrix_power(A, int(days))[start, target])


def classify(vix: pd.Series, thresholds, labels) -> pd.Series:
    bins = [-np.inf] + list(thresholds) + [np.inf]
    return pd.Series(pd.cut(vix, bins, labels=False, right=False), index=vix.index).astype(int)


def fit_regimes(vd: VixData, cfg: dict) -> RegimeModel:
    vc = cfg["vix"]
    labels, thr = vc["regime_labels"], vc["regime_thresholds"]
    if len(labels) != len(thr) + 1:
        raise ValueError("vix.regime_labels must have one more entry than regime_thresholds")
    states = classify(vd.vix, thr, labels)
    K = len(labels)

    T = np.zeros((K, K))
    s = states.values
    np.add.at(T, (s[:-1], s[1:]), 1)
    for k in range(K):                           # unseen regime: stay put
        if T[k].sum() == 0:
            T[k, k] = 1
    P = T / T.sum(axis=1, keepdims=True)
    evals, evecs = np.linalg.eig(P.T)
    pi = np.real(evecs[:, np.argmin(np.abs(evals - 1))])
    pi = pi / pi.sum()

    mu, cov, counts, shrink = {}, {}, {}, {}
    min_obs = int(vc.get("min_regime_days", 60))
    full_cov, _ = opt.covariance_matrix(vd.asset_returns, DAYS, cfg["model"]["covariance_method"])
    for k, lab in enumerate(labels):
        r = vd.asset_returns[states == k]
        counts[lab] = len(r)
        if len(r) < min_obs:
            log.warning("Regime %s has only %d days; using full-sample covariance", lab, len(r))
            cov[lab], shrink[lab] = full_cov, float("nan")
            mu[lab] = vd.asset_returns.mean() * DAYS
            continue
        mu[lab] = r.mean() * DAYS
        cov[lab], shrink[lab] = opt.covariance_matrix(r, DAYS, cfg["model"]["covariance_method"])
    return RegimeModel(labels, thr, states, P, pi, mu, cov, counts, shrink)


def calibrate_to_base(rm: RegimeModel, cov_base: pd.DataFrame) -> RegimeModel:
    """Rescale every regime covariance by D = diag(sigma_base / sigma_mix) so
    the stationary mixture has exactly the base model's asset volatilities.
    Regime correlations and the vol ratios between regimes are unchanged, so
    any difference from the static model comes from VIX dynamics (clustering,
    crisis correlations), not from the longer estimation window."""
    tick = list(cov_base.index)
    mix = sum(rm.stationary[k] * rm.cov[l].loc[tick, tick].values for k, l in enumerate(rm.labels))
    D = np.sqrt(np.diag(cov_base.values) / np.diag(mix))
    cov = {l: pd.DataFrame(rm.cov[l].loc[tick, tick].values * np.outer(D, D), tick, tick)
           for l in rm.labels}
    return RegimeModel(rm.labels, rm.thresholds, rm.states, rm.P_day, rm.stationary,
                       rm.mu, cov, rm.counts, rm.shrink)


def regime_process(rm: RegimeModel, mu_base: pd.Series, cfg: dict) -> opt.RegimeProcess:
    """Per-step regime process for the Monte Carlo.

    Regime means are shrunk toward the base model's expected returns by
    ``regime_mean_shrinkage`` (1.0 = every regime earns the base mean, so the
    regimes change risk only). The Signal Tests tab shows why: forward returns
    by regime are not statistically distinguishable.
    """
    spy = int(cfg["monte_carlo"]["steps_per_year"])
    s = float(cfg["vix"]["regime_mean_shrinkage"])
    tick = list(mu_base.index)
    drift, chol = [], []
    for lab in rm.labels:
        m = s * mu_base.values + (1 - s) * rm.mu[lab][tick].values
        C = rm.cov[lab].loc[tick, tick].values
        drift.append((m - 0.5 * np.diag(C)) / spy)
        chol.append(np.linalg.cholesky(C / spy))
    start = int(rm.states.iloc[-1])
    return opt.RegimeProcess(np.array(drift), np.array(chol), rm.P_h(DAYS // spy), start, rm.labels)


# --------------------------------------------------------------------------
# Current state / dashboard
# --------------------------------------------------------------------------
def current_state(vd: VixData, rm: RegimeModel) -> dict:
    v, v3 = vd.vix, vd.vix3m
    k = int(rm.states.iloc[-1])
    run = int((rm.states[::-1] != k).values.argmax()) or len(rm.states)
    spy = vd.asset_returns["SPY"] if "SPY" in vd.asset_returns else vd.asset_returns.iloc[:, 0]
    rv21 = float(spy.iloc[-21:].std() * np.sqrt(DAYS) * 100)
    crisis = rm.K - 1
    ratio = float(v.iloc[-1] / v3.iloc[-1])
    out = {
        "As of": rm.states.index[-1].date().isoformat(),
        "VIX close": float(v.iloc[-1]),
        "VIX 1 week ago": float(v.iloc[-6]),
        "VIX3M close": float(v3.iloc[-1]),
        "VIX / VIX3M ratio": ratio,
        "Term structure": "Backwardation (inverted, stress)" if ratio > 1 else "Contango (normal)",
        "Current regime": rm.labels[k],
        "Consecutive days in regime": run,
        "Expected days remaining in regime": float(1 / max(1 - rm.P_day[k, k], 1e-9)),
        "VIX percentile (regime window)": float((v <= v.iloc[-1]).mean()),
        "VIX mean (regime window)": float(v.mean()),
        "VIX median (regime window)": float(v.median()),
        "SPY realized vol, last 21 days (pts)": rv21,
        "Implied minus realized vol (pts)": float(v.iloc[-1] - rv21),
    }
    # Model (Markov) vs history: of all past days in the current regime, the
    # share followed by at least one Crisis close within the horizon. The
    # first-order chain has no memory, so VIX flickering around a threshold
    # inflates its estimate; the empirical column is the check on it.
    s = rm.states.values
    is_c = (s == crisis).astype(int)
    csum = np.concatenate([[0], np.cumsum(is_c)])
    for days, lab in ((21, "1 month"), (63, "3 months"), (252, "12 months")):
        out[f"P(reach {rm.labels[crisis]} within {lab}), Markov model"] = rm.hit_probability(k, crisis, days)
        starts = np.where(s[: len(s) - days] == k)[0]
        hits = (csum[starts + days + 1] - csum[starts + 1]) > 0 if len(starts) else np.array([])
        out[f"P(reach {rm.labels[crisis]} within {lab}), historical"] = (
            float(hits.mean()) if len(hits) else float("nan"))
    for months, lab in ((1, "1 month"), (12, "12 months")):
        row = rm.P_months(months)[k]
        for j, l in enumerate(rm.labels):
            out[f"P(in {l} in {lab})"] = float(row[j])
    return out


def regime_table(vd: VixData, rm: RegimeModel) -> pd.DataFrame:
    rows = []
    for k, lab in enumerate(rm.labels):
        m = rm.states == k
        lo = "-inf" if k == 0 else rm.thresholds[k - 1]
        hi = "inf" if k == rm.K - 1 else rm.thresholds[k]
        row = {"Regime": lab, "VIX range": f"[{lo}, {hi})", "Days": int(m.sum()),
               "Share of time": float(m.mean()), "Stationary prob.": float(rm.stationary[k]),
               "Avg spell (days)": float(1 / max(1 - rm.P_day[k, k], 1e-9)),
               "Mean VIX": float(vd.vix[m].mean()) if m.any() else np.nan,
               "LW shrinkage": rm.shrink[rm.labels[k]]}
        for t in vd.asset_returns.columns:
            row[f"{t} ann. return"] = float(rm.mu[lab][t])
            row[f"{t} ann. vol"] = float(np.sqrt(rm.cov[lab].loc[t, t]))
        if "SPY" in vd.asset_returns.columns:
            c = rm.cov[lab]
            sd = np.sqrt(np.diag(c.values))
            corr = pd.DataFrame(c.values / np.outer(sd, sd), c.index, c.columns)
            for t in vd.asset_returns.columns:
                if t != "SPY":
                    row[f"corr({t}, SPY)"] = float(corr.loc[t, "SPY"])
        rows.append(row)
    return pd.DataFrame(rows)


def transition_table(rm: RegimeModel, days: int, empirical: bool = False) -> pd.DataFrame:
    M = rm.P_h(days) if empirical else rm.P(days)
    return pd.DataFrame(M, index=[f"from {l}" for l in rm.labels],
                        columns=[f"to {l}" for l in rm.labels])


def stress_test(portfolios, rm: RegimeModel, capital: float, now_regime: str) -> pd.DataFrame:
    """Portfolio return, volatility and 1-month parametric VaR in each regime,
    using the raw (contemporaneous) regime means: what each portfolio did
    while the VIX sat in that band."""
    rows = []
    for p in portfolios:
        w = p.weights
        for lab in rm.labels + ["Stationary mix"]:
            if lab == "Stationary mix":
                C = rm.mixture_cov()
                m = sum(rm.stationary[k] * rm.mu[l][w.index].values for k, l in enumerate(rm.labels))
            else:
                C = rm.cov[lab].loc[w.index, w.index].values
                m = rm.mu[lab][w.index].values
            vol = float(np.sqrt(w.values @ C @ w.values))
            mret = float(w.values @ m)
            var_m = -(mret / 12 - 1.645 * vol / np.sqrt(12))
            rows.append({"Portfolio": p.name, "Regime": lab + (" (current)" if lab == now_regime else ""),
                         "Ann. return in regime": mret, "Ann. volatility in regime": vol,
                         "1-month VaR 95% (return)": var_m,
                         "1-month VaR 95% ($)": var_m * capital})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Backtests
# --------------------------------------------------------------------------
def _sleeve_returns(rets: pd.DataFrame, w: pd.Series, cost_bps: float) -> tuple[pd.Series, float]:
    """Daily returns of a portfolio rebalanced to ``w`` at each month end,
    drifting in between, net of rebalancing cost. Returns (series, turnover/yr)."""
    R = rets[w.index].values
    target = w.values.astype(float)
    hold = target.copy()
    month = rets.index.month
    out = np.empty(len(R))
    turnover = 0.0
    for t in range(len(R)):
        rp = hold @ R[t]
        hold = hold * (1 + R[t]) / (1 + rp)
        cost = 0.0
        if t == len(R) - 1 or month[t + 1] != month[t]:
            tv = 0.5 * np.abs(hold - target).sum()
            turnover += tv
            cost = tv * cost_bps / 1e4
            hold = target.copy()
        out[t] = rp - cost
    return pd.Series(out, index=rets.index), turnover / (len(R) / DAYS)


def _metrics(r: pd.Series, cash: pd.Series, exposure: pd.Series | None,
             windows: dict) -> dict:
    eq = (1 + r).cumprod()
    yrs = len(r) / DAYS
    vol = r.std() * np.sqrt(DAYS)
    ex = (r - cash).mean() * DAYS
    dd = (eq / eq.cummax() - 1).min()
    monthly = (1 + r).resample("ME").prod() - 1
    out = {"CAGR": eq.iloc[-1] ** (1 / yrs) - 1, "Volatility": vol,
           "Sharpe (vs T-bills)": ex / vol if vol > 0 else np.nan,
           "Max drawdown": dd, "Calmar": (eq.iloc[-1] ** (1 / yrs) - 1) / abs(dd) if dd < 0 else np.nan,
           "Worst month": monthly.min(), "Best month": monthly.max(),
           "Avg exposure": float(exposure.mean()) if exposure is not None else 1.0,
           "Days de-risked": float((exposure < 0.999).mean()) if exposure is not None else 0.0}
    for name, (a, b) in windows.items():
        seg = r[(r.index >= a) & (r.index <= b)]
        out[f"Return: {name}"] = (1 + seg).prod() - 1 if len(seg) else np.nan
    return out


def overlay_exposures(vd: VixData, rm: RegimeModel, cfg: dict) -> dict:
    """Exposure series for each VIX rule. All use the previous day's close."""
    oc = cfg["vix"]["overlay"]
    mx = float(oc["max_exposure"])
    v_lag = vd.vix.shift(1)
    med = vd.vix.rolling(DAYS, min_periods=60).median().shift(1)
    ratio_lag = (vd.vix / vd.vix3m).shift(1)
    reg_lag = rm.states.shift(1)
    emap = np.array([oc["regime_exposure"][l] for l in rm.labels], float)
    ex = {
        "VIX vol-target": (med / v_lag).clip(0, mx),
        "Term-structure switch": pd.Series(np.where(ratio_lag > 1, oc["backwardation_exposure"], 1.0),
                                           index=vd.vix.index),
        "Regime map": pd.Series(emap[reg_lag.fillna(0).astype(int).values], index=vd.vix.index),
    }
    return {k: s.fillna(1.0).clip(0, mx) for k, s in ex.items()}


def backtest_overlays(vd: VixData, rm: RegimeModel, portfolios, cfg: dict):
    """Static vs VIX-managed versions of each portfolio, plus SPY alone."""
    oc = cfg["vix"]["overlay"]
    cost = float(oc["cost_bps"])
    windows = {k: tuple(pd.Timestamp(x) for x in v) for k, v in cfg["vix"]["stress_windows"].items()}
    exposures = overlay_exposures(vd, rm, cfg)
    cash = vd.tbill
    rows, curves = [], {}
    books = [(p.name, p.weights) for p in portfolios]
    if "SPY" in vd.asset_returns.columns:
        books.append(("SPY only", pd.Series({"SPY": 1.0})))
    for name, w in books:
        w = w[w > 0]
        sleeve, tvr = _sleeve_returns(vd.asset_returns, w, cost)
        r = sleeve
        m = _metrics(r, cash, None, windows)
        rows.append({"Portfolio": name, "Strategy": "Static (monthly rebalance)",
                     "Sleeve turnover / yr": tvr, **m})
        curves[f"{name} | Static"] = (1 + r).cumprod()
        for sname, e in exposures.items():
            de = e.diff().abs().fillna(0)
            r2 = e * sleeve + (1 - e) * cash - de * cost / 1e4
            m2 = _metrics(r2, cash, e, windows)
            rows.append({"Portfolio": name, "Strategy": sname,
                         "Sleeve turnover / yr": tvr, **m2})
            curves[f"{name} | {sname}"] = (1 + r2).cumprod()
    return pd.DataFrame(rows), pd.DataFrame(curves)


def hedge_sizing(vd: VixData, rm: RegimeModel, base, engine, cfg: dict) -> pd.DataFrame:
    """Blend a VIXY sleeve into a portfolio: cost in expected return versus
    protection in the Crisis regime and in historical stress windows."""
    hedge = cfg["vix"]["hedge_asset"]
    if hedge not in base.weights.index:
        return pd.DataFrame()
    windows = {k: tuple(pd.Timestamp(x) for x in v) for k, v in cfg["vix"]["stress_windows"].items()}
    crisis = rm.cov[rm.labels[-1]].loc[base.weights.index, base.weights.index].values
    rows = []
    core = base.weights.copy()
    core[hedge] = 0.0
    core = core / core.sum()
    for h in cfg["vix"]["hedge_sizes"]:
        w = core * (1 - h)
        w[hedge] += h
        wv = w.values
        sleeve, _ = _sleeve_returns(vd.asset_returns, w[w > 0], float(cfg["vix"]["overlay"]["cost_bps"]))
        m = _metrics(sleeve, vd.tbill, None, windows)
        rows.append({"VIXY weight": h, "Expected net return (model)": engine.net(wv),
                     "Volatility (model)": engine.vol(wv),
                     "Net Sharpe (model)": (engine.net(wv) - engine.rf) / engine.vol(wv),
                     "Crisis-regime volatility": float(np.sqrt(wv @ crisis @ wv)),
                     **{f"Backtest {k}": v for k, v in m.items()
                        if k not in ("Avg exposure", "Days de-risked")}})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Signal tests
# --------------------------------------------------------------------------
def _tstat(x: pd.Series) -> float:
    x = x.dropna()
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 and x.std() > 0 else np.nan


def signal_tests(vd: VixData, rm: RegimeModel) -> dict:
    spy = vd.asset_returns["SPY"]
    h = 21
    fwd_ret = (1 + spy).rolling(h).apply(np.prod, raw=True).shift(-h) - 1
    fwd_vol = spy.rolling(h).std().shift(-h) * np.sqrt(DAYS) * 100
    df = pd.DataFrame({"vix": vd.vix, "ratio": vd.vix / vd.vix3m, "state": rm.states,
                       "fwd_ret": fwd_ret, "fwd_vol": fwd_vol}).dropna()
    sample = df.iloc[::h]                       # non-overlapping months for t-stats

    fc = {"Days tested": len(df),
          "Corr(VIX, next-21d realized SPY vol)": float(df["vix"].corr(df["fwd_vol"])),
          "Mean VIX": float(df["vix"].mean()),
          "Mean next-21d realized vol": float(df["fwd_vol"].mean()),
          "Share of days VIX > realized": float((df["vix"] > df["fwd_vol"]).mean()),
          "Regression slope (realized on VIX)": float(np.polyfit(df["vix"], df["fwd_vol"], 1)[0])}

    rows = []
    for k, lab in enumerate(rm.labels):
        s = sample[sample["state"] == k]
        rows.append({"Signal state": f"Regime: {lab}", "Months (non-overlapping)": len(s),
                     "Mean next-month SPY return": s["fwd_ret"].mean(),
                     "t-stat": _tstat(s["fwd_ret"]), "Share positive": (s["fwd_ret"] > 0).mean(),
                     "Mean next-month realized vol": s["fwd_vol"].mean()})
    for lab, mask in (("Contango (VIX < VIX3M)", sample["ratio"] <= 1),
                      ("Backwardation (VIX > VIX3M)", sample["ratio"] > 1)):
        s = sample[mask]
        rows.append({"Signal state": f"Term structure: {lab}", "Months (non-overlapping)": len(s),
                     "Mean next-month SPY return": s["fwd_ret"].mean(), "t-stat": _tstat(s["fwd_ret"]),
                     "Share positive": (s["fwd_ret"] > 0).mean(),
                     "Mean next-month realized vol": s["fwd_vol"].mean()})
    return {"forecast": fc, "by_state": pd.DataFrame(rows)}


# --------------------------------------------------------------------------
# Weekly cross-asset coefficient table (automates the VIX Algo workbook)
# --------------------------------------------------------------------------
def weekly_coefficients(vd: VixData, cfg: dict) -> dict:
    wc = cfg["vix"]["weekly"]
    series = {k: v for k, v in wc["series"].items() if v in vd.weekly_close.columns}
    vix_name = next(k for k, v in series.items() if v == cfg["vix"]["symbol"])
    close = vd.weekly_close[list(series.values())].resample("W-FRI").last()
    chg = close.pct_change(fill_method=None)
    chg.columns = list(series.keys())
    vix_d = pd.DataFrame({"o": vd.vix_open, "c": vd.vix})
    wk_o = vix_d["o"].resample("W-FRI").first()
    wk_c = vix_d["c"].resample("W-FRI").last()

    table = chg.copy()
    # Workbook formulas (algo_with_chart.xlsx): Spread Total = sum of the six
    # % changes, Average = Spread Total / 6.
    table["Spread Total"] = chg.sum(axis=1, min_count=1)
    table["Average"] = table["Spread Total"] / chg.notna().sum(axis=1).replace(0, np.nan)
    table["VIX Open"] = wk_o
    table["VIX Close"] = wk_c
    table["Difference"] = wk_c - wk_o
    table["STD (open, close)"] = (wk_c - wk_o).abs() / np.sqrt(2)   # = STDEV(open, close)
    table = table.dropna(subset=[vix_name]).iloc[1:]

    # Coefficients: correlation and beta of each series to VIX weekly change,
    # winsorised at 1% / 99% so single outliers (Apr 2020 oil) do not dominate.
    def wins(x):
        return x.clip(x.quantile(0.01), x.quantile(0.99))

    others = [c for c in chg.columns if c != vix_name]
    coef_rows = []
    n_recent = int(wc["history_weeks"])
    for c in others:
        row = {"Series": c, "Yahoo symbol": series[c]}
        for lab, sub in (("full window", table), (f"last {n_recent} weeks", table.iloc[-n_recent:])):
            pair = sub[[c, vix_name]].dropna()
            a, b = wins(pair[c]), wins(pair[vix_name])
            row[f"Corr to VIX ({lab})"] = float(a.corr(b))
            row[f"Beta to VIX ({lab})"] = float(np.cov(a, b)[0, 1] / b.var()) if b.var() > 0 else np.nan
        coef_rows.append(row)

    # Does the Spread Total predict next week's SPY return or VIX change?
    spy_wk = vd.weekly_close["SPY"].resample("W-FRI").last().pct_change(fill_method=None)
    test = pd.DataFrame({"spread": table["Average"], "vix_next": table[vix_name].shift(-1),
                         "spy_next": spy_wk.reindex(table.index).shift(-1)}).dropna()
    n = len(test)

    def corr_t(x, y):
        r = float(x.corr(y))
        return r, r * np.sqrt((n - 2) / max(1 - r * r, 1e-12))

    r1, t1 = corr_t(test["spread"], test["spy_next"])
    r2, t2 = corr_t(test["spread"], test["vix_next"])
    pred = {"Weeks tested": n,
            "Corr(Spread Total, next-week SPY return)": r1, "t-stat (SPY)": t1,
            "Corr(Spread Total, next-week VIX change)": r2, "t-stat (VIX)": t2,
            "Hit rate: sign(spread) = sign(next VIX change)":
                float((np.sign(test["spread"]) == np.sign(test["vix_next"])).mean()),
            "Hit rate: sign(spread) = sign(next SPY return)":
                float((np.sign(test["spread"]) == np.sign(test["spy_next"])).mean())}
    # Stability check: a real signal should hold in both halves of the sample.
    half = n // 2
    for lab, sub in (("first half", test.iloc[:half]), ("second half", test.iloc[half:])):
        pred[f"Corr(Spread Total, next-week SPY return), {lab} ({sub.index[0].year}-{sub.index[-1].year})"] = \
            float(sub["spread"].corr(sub["spy_next"]))
    # Benchmark: VIX weekly change alone, the dominant term in the average.
    pred["Corr(VIX weekly change alone, next-week SPY return)"] = \
        float(table[vix_name].reindex(test.index).corr(test["spy_next"]))
    # Full cross-correlation matrices (the workbook's Sheet1), weekly and daily.
    def corr_matrix(x):
        x = x.apply(lambda c: c.clip(c.quantile(0.01), c.quantile(0.99)))
        m = x.corr()
        m.index.name = "Correlation"
        return m

    daily_close = vd.weekly_close[list(series.values())]
    dchg = daily_close.pct_change(fill_method=None)
    dchg.columns = list(series.keys())
    dchg = dchg.dropna(how="all").iloc[1:]
    daily = dchg.copy()
    daily["Spread Total"] = dchg.sum(axis=1, min_count=1)
    daily["Average"] = daily["Spread Total"] / dchg.notna().sum(axis=1).replace(0, np.nan)
    daily["VIX Open"] = vd.vix_open.reindex(daily.index)
    daily["VIX Close"] = vd.vix.reindex(daily.index)
    daily["Difference"] = daily["VIX Close"] - daily["VIX Open"]
    daily["STD (open, close)"] = daily["Difference"].abs() / np.sqrt(2)
    return {"table": table, "daily": daily.dropna(subset=[vix_name]),
            "coefficients": pd.DataFrame(coef_rows), "predictive": pred,
            "corr_weekly": corr_matrix(chg.iloc[1:]), "corr_daily": corr_matrix(dchg),
            "vix_name": vix_name}


def iv_hv(vd: VixData, window: int = 21, rank_days: int = 252) -> pd.DataFrame:
    """Implied vs historical volatility with 52-week ranks (the workbook's
    Sheet2). IV = VIX / 100 (30-day implied vol of the S&P 500); HV = SPY
    realized vol over ``window`` days, annualised. Rank = position of today's
    value within its trailing 52-week range, 0 to 100."""
    spy = vd.asset_returns["SPY"]
    iv = vd.vix / 100.0
    hv = spy.rolling(window).std() * np.sqrt(DAYS)

    def rank(x):
        lo, hi = x.rolling(rank_days).min(), x.rolling(rank_days).max()
        return 100 * (x - lo) / (hi - lo)

    out = pd.DataFrame({"Implied Volatility": iv, "IV Rank": rank(iv),
                        "Historical Volatility": hv, "HV Rank": rank(hv)})
    out["IV minus HV"] = out["Implied Volatility"] - out["Historical Volatility"]
    out.index.name = "Date"
    return out.dropna()


def findings(state: dict, rm: RegimeModel, bt: pd.DataFrame, hedge: pd.DataFrame,
             sig: dict, wkly: dict, vd: VixData, hedge_asset: str) -> list[str]:
    """Plain-language conclusions generated from the numbers."""
    out = []
    out.append(f"VIX closed at {state['VIX close']:.2f} on {state['As of']}: {state['Current regime']} regime, "
               f"{state['Term structure'].split(' (')[0].lower()} "
               f"(VIX / VIX3M = {state['VIX / VIX3M ratio']:.3f}).")
    crisis = rm.labels[-1]
    out.append(f"Markov chain from today: {state[f'P(reach {crisis} within 1 month), Markov model']:.0%} chance of a "
               f"{crisis} day within 1 month, {state[f'P(reach {crisis} within 12 months), Markov model']:.0%} within 12 "
               f"(historical frequency from this regime: {state[f'P(reach {crisis} within 1 month), historical']:.0%} and "
               f"{state[f'P(reach {crisis} within 12 months), historical']:.0%}).")
    fc = sig["forecast"]
    out.append(f"VIX forecasts risk: correlation with next-month realized SPY vol is {fc['Corr(VIX, next-21d realized SPY vol)']:.2f}; "
               f"VIX exceeded subsequent realized vol on {fc['Share of days VIX > realized']:.0%} of days "
               f"(the volatility risk premium).")
    bs = sig["by_state"]
    cr = bs[bs["Signal state"] == f"Regime: {crisis}"]
    if len(cr) and np.isfinite(cr["t-stat"].iloc[0]):
        out.append(f"VIX does not reliably forecast direction: after {crisis} closes, next-month SPY averaged "
                   f"{cr['Mean next-month SPY return'].iloc[0]:+.1%} (t = {cr['t-stat'].iloc[0]:.2f}, "
                   f"{int(cr['Months (non-overlapping)'].iloc[0])} months). Selling on VIX spikes tends to sell near lows.")
    if hedge_asset in vd.asset_prices.columns:
        p = vd.asset_prices[hedge_asset]
        out.append(f"{hedge_asset} (long VIX futures) returned {p.iloc[-1] / p.iloc[0] - 1:.1%} over the regime "
                   f"window: futures roll decay makes a permanent VIX hedge expensive.")
    if len(hedge) > 1:
        h0, hk = hedge.iloc[0], hedge.iloc[min(2, len(hedge) - 1)]
        out.append(f"A {hk['VIXY weight']:.0%} {hedge_asset} sleeve on Max Sharpe cuts Crisis-regime vol from "
                   f"{h0['Crisis-regime volatility']:.1%} to {hk['Crisis-regime volatility']:.1%} and costs "
                   f"{h0['Expected net return (model)'] - hk['Expected net return (model)']:.2%} a year in expected return.")
    st = bt[bt["Strategy"] != "Static (monthly rebalance)"]
    for pname in bt["Portfolio"].unique():
        base = bt[(bt["Portfolio"] == pname) & (bt["Strategy"].str.startswith("Static"))].iloc[0]
        best = st[st["Portfolio"] == pname].sort_values("Sharpe (vs T-bills)").iloc[-1]
        verdict = "improved" if best["Sharpe (vs T-bills)"] > base["Sharpe (vs T-bills)"] else "did not improve"
        out.append(f"{pname}: best VIX rule ({best['Strategy']}) {verdict} Sharpe "
                   f"({base['Sharpe (vs T-bills)']:.2f} static vs {best['Sharpe (vs T-bills)']:.2f}); "
                   f"max drawdown {base['Max drawdown']:.1%} vs {best['Max drawdown']:.1%}.")
    pr = wkly["predictive"]
    halves = [v for k, v in pr.items() if k.startswith("Corr(Spread Total, next-week SPY return), ")]
    r_spy, t_spy = pr["Corr(Spread Total, next-week SPY return)"], pr["t-stat (SPY)"]
    stable = len(halves) == 2 and np.sign(halves[0]) == np.sign(halves[1]) == np.sign(r_spy)
    if abs(t_spy) >= 2 and stable:
        verdict = (f"a weak but stable link (same sign in both halves: {halves[0]:+.3f}, {halves[1]:+.3f}); "
                   f"it explains about {r_spy ** 2:.1%} of next-week SPY variance")
    elif abs(t_spy) >= 2:
        verdict = "significant in the full sample but not stable across halves, so likely noise"
    else:
        verdict = "no reliable signal"
    out.append(f"Workbook Spread Total vs next-week SPY return: correlation {r_spy:+.3f} (t = {t_spy:.2f}, "
               f"{pr['Weeks tested']} weeks), {verdict}. VIX change alone shows "
               f"{pr['Corr(VIX weekly change alone, next-week SPY return)']:+.3f}, so any signal comes from the "
               f"commodity and yield legs. Against next-week VIX change: {pr['Corr(Spread Total, next-week VIX change)']:+.3f} "
               f"(t = {pr['t-stat (VIX)']:.2f}).")
    return out


# --------------------------------------------------------------------------
# Difference study: what happens after VIX rises vs falls within a period
# --------------------------------------------------------------------------
def _welch_t(a: pd.Series, b: pd.Series) -> float:
    a, b = a.dropna(), b.dropna()
    if len(a) < 3 or len(b) < 3:
        return np.nan
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return float((a.mean() - b.mean()) / se) if se > 0 else np.nan


def difference_study(cfg: dict, base_dir: Path) -> dict:
    """Event study on the workbook's Difference column (VIX close - VIX open).

    For each period (day, and week Monday-open to Friday-close) the VIX
    either rose (Difference > 0) or fell. We measure (a) what the VIX did
    next, and (b) how non-VIX instruments behaved next, versus all other
    periods. Then the strongest candidates are backtested with thresholds
    computed from trailing data only.
    """
    vc = cfg["vix"]
    ds = vc["difference_study"]
    start = pd.Timestamp(ds["start_date"])
    years = (pd.Timestamp.now() - start).days / 365.25 + 0.1
    inst = list(ds["instruments"])
    panel = data_loader.fetch_panel([vc["symbol"], vc["tbill_symbol"]] + inst, round(years, 1),
                                    cfg["data"], base_dir, fields=("Open", "Close"), tag="diffstudy")
    close = panel["Close"].copy()
    opn = panel["Open"].copy()
    for df in (close, opn):
        df.index = pd.to_datetime(df.index).tz_localize(None)
    close, opn = close[close.index >= start], opn[opn.index >= start]
    v, vo = close[vc["symbol"]], opn[vc["symbol"]]
    ok = v.notna() & vo.notna() & (vo > 0)
    v, vo = v[ok], vo[ok]
    px = close[inst].reindex(v.index).ffill(limit=3)
    cash_d = (close[vc["tbill_symbol"]].reindex(v.index).ffill() / 100) / DAYS
    q = float(ds["big_quantile"])
    cost = float(ds["cost_bps"]) / 1e4

    frames = {}
    # Daily: signal at close t, outcome from close t to close t+1.
    d = pd.DataFrame({"diff": v - vo, "pct": (v - vo) / vo, "vix": v})
    d["vix_next"] = v.shift(-1) / v - 1
    d["same_SPY"] = px["SPY"].pct_change(fill_method=None) if "SPY" in px else np.nan
    fwd_d = px.shift(-1) / px - 1
    frames["Daily"] = (d, fwd_d, int(ds["daily_threshold_window"]))
    # Weekly: Monday open to Friday close; outcome is the following week.
    wo, wc = vo.resample("W-FRI").first(), v.resample("W-FRI").last()
    w = pd.DataFrame({"diff": wc - wo, "pct": (wc - wo) / wo, "vix": wc}).dropna()
    w["vix_next"] = wc.shift(-1).reindex(w.index) / w["vix"] - 1
    wpx = px.resample("W-FRI").last().reindex(w.index)
    w["same_SPY"] = wpx["SPY"].pct_change(fill_method=None) if "SPY" in wpx else np.nan
    fwd_w = wpx.shift(-1) / wpx - 1
    frames["Weekly"] = (w, fwd_w, int(ds["weekly_threshold_window"]))

    vix_rows, inst_rows, strat_rows = [], [], []
    for freq, (df, fwd, win) in frames.items():
        df = df.dropna(subset=["pct"])
        hi, lo = df["pct"].quantile(q), df["pct"].quantile(1 - q)
        buckets = {f"Big rise (top {1 - q:.0%})": df["pct"] >= hi, "VIX rose (Difference > 0)": df["diff"] > 0,
                   "VIX fell (Difference < 0)": df["diff"] < 0, f"Big fall (bottom {1 - q:.0%})": df["pct"] <= lo,
                   "All periods": df["diff"].notna()}
        for lab, m in buckets.items():
            s = df[m]
            nxt = s["vix_next"].dropna()
            vix_rows.append({"Frequency": freq, "Bucket": lab, "Periods": len(s),
                             "Mean Difference (pts)": s["diff"].mean(), "Mean VIX move in period": s["pct"].mean(),
                             "SPY return in same period": s["same_SPY"].mean(),
                             "Next-period VIX change, mean": nxt.mean(),
                             "Next-period VIX change, median": nxt.median(),
                             "Share of times VIX lower next period": float((nxt < 0).mean())})
        half = df.index[len(df) // 2]
        for k in inst:
            f = fwd[k].reindex(df.index)
            base = f.mean()
            for lab in list(buckets)[:4]:
                m = buckets[lab]
                a, b = f[m], f[~m]
                e1 = f[m & (df.index < half)].mean() - f[~m & (df.index < half)].mean()
                e2 = f[m & (df.index >= half)].mean() - f[~m & (df.index >= half)].mean()
                inst_rows.append({"Frequency": freq, "Instrument": k, "Bucket": lab, "Periods": int(a.count()),
                                  "Next-period return after bucket": a.mean(), "Next-period return, all periods": base,
                                  "Excess vs other periods": a.mean() - b.mean(), "t-stat (Welch)": _welch_t(a, b),
                                  "Share positive": float((a.dropna() > 0).mean()),
                                  f"Excess, {df.index[0].year}-{half.year - 1}": e1,
                                  f"Excess, {half.year}-{df.index[-1].year}": e2,
                                  "Same sign both halves": bool(np.sign(e1) == np.sign(e2) != 0)})

        # Strategy: trade only after a big VIX rise, threshold from trailing window.
        thr = df["pct"].rolling(win, min_periods=win // 2).quantile(q).shift(1)
        sig = (df["pct"] >= thr) & thr.notna()
        per_year = DAYS if freq == "Daily" else 52
        cash = (cash_d.reindex(df.index).fillna(0) if freq == "Daily"
                else ((1 + cash_d).resample("W-FRI").prod() - 1).reindex(df.index).fillna(0))
        cash_next = cash.shift(-1).fillna(0)
        key = "daily_strategies" if freq == "Daily" else "weekly_strategies"
        for st in ds[key]:
            k, side = st["symbol"], int(st["side"])
            f = fwd[k].reindex(df.index)
            valid = f.notna() & thr.notna()
            trade = side * f - 2 * cost                    # round trip each signal
            strat = np.where(sig, trade, cash_next)
            strat = pd.Series(strat, index=df.index)[valid]
            bh = (side * f)[valid]
            trades = (side * f)[sig & valid] - 2 * cost
            yrs = valid.sum() / per_year

            def ann(x):
                eq = (1 + x).prod()
                return eq ** (1 / yrs) - 1 if yrs > 0 else np.nan

            def shp(x, c):
                ex = x - c[x.index]
                return float(ex.mean() / ex.std() * np.sqrt(per_year)) if ex.std() > 0 else np.nan

            strat_rows.append({
                "Frequency": freq, "Instrument": k, "Side": "Long" if side > 0 else "Short",
                "Rule": f"{'Long' if side > 0 else 'Short'} {k} for the next {'day' if freq == 'Daily' else 'week'} "
                        f"after the VIX rises more than its trailing {win}-period {q:.0%} percentile; otherwise T-bills",
                "Trades": int(len(trades)), "Trades per year": len(trades) / yrs if yrs else np.nan,
                "Avg net return per trade": trades.mean(),
                "Avg return, all periods (same side)": bh.mean(),
                "Excess per trade vs all periods": trades.mean() + 2 * cost - bh.mean(),
                "t-stat (trade vs other periods)": _welch_t(trades + 2 * cost, (side * f)[~sig & valid]),
                "Hit rate": float((trades > 0).mean()) if len(trades) else np.nan,
                "Time in market": float(sig[valid].mean()),
                "Strategy CAGR": ann(strat), "Strategy Sharpe (vs T-bills)": shp(strat, cash_next),
                "Buy-and-hold CAGR": ann(bh), "Buy-and-hold Sharpe (vs T-bills)": shp(bh, cash_next)})

    return {"vix": pd.DataFrame(vix_rows), "instruments": pd.DataFrame(inst_rows),
            "strategies": pd.DataFrame(strat_rows), "start": df.index[0].date().isoformat() if len(df) else "",
            "big_quantile": q}


def difference_findings(dsr: dict) -> list[str]:
    out = []
    vx = dsr["vix"]
    for freq in ("Daily", "Weekly"):
        sub = vx[vx["Frequency"] == freq].set_index("Bucket")
        big = [b for b in sub.index if b.startswith("Big rise")][0]
        out.append(f"{freq}, since {dsr['start'][:4]}: after the VIX rose (Difference > 0) it was lower the next period "
                   f"{sub.loc['VIX rose (Difference > 0)', 'Share of times VIX lower next period']:.0%} of the time "
                   f"({sub.loc[big, 'Share of times VIX lower next period']:.0%} after a {big.split('(')[0].strip().lower()}, "
                   f"median {sub.loc[big, 'Next-period VIX change, median']:+.1%}); after it fell, "
                   f"{sub.loc['VIX fell (Difference < 0)', 'Share of times VIX lower next period']:.0%}. Rises revert, falls do not.")
    ins = dsr["instruments"]
    robust = ins[(ins["t-stat (Welch)"].abs() >= 2) & ins["Same sign both halves"]
                 & ins["Bucket"].str.startswith("Big rise")].sort_values("t-stat (Welch)", key=abs, ascending=False)
    if len(robust):
        out.append("Non-VIX instruments with a significant (|t| >= 2) and stable response after big VIX rises: " +
                   "; ".join(f"{r.Instrument} {r.Frequency.lower()} {r['Excess vs other periods']:+.2%} vs other periods "
                             f"(t = {r['t-stat (Welch)']:.1f})" for _, r in robust.head(5).iterrows()) + ".")
    else:
        out.append("No non-VIX instrument shows a significant and stable response after big VIX rises.")
    for _, r in dsr["strategies"].iterrows():
        better = r["Strategy Sharpe (vs T-bills)"] > r["Buy-and-hold Sharpe (vs T-bills)"]
        out.append(f"{r['Frequency']} {r['Side'].lower()} {r['Instrument']} after big VIX rises: {r['Trades']} trades, "
                   f"{r['Avg net return per trade']:+.2%} per trade net of costs (vs {r['Avg return, all periods (same side)']:+.2%} on an average period, "
                   f"t = {r['t-stat (trade vs other periods)']:.1f}), hit rate {r['Hit rate']:.0%}, in market "
                   f"{r['Time in market']:.0%} of the time; Sharpe {r['Strategy Sharpe (vs T-bills)']:.2f} vs "
                   f"{r['Buy-and-hold Sharpe (vs T-bills)']:.2f} {'buy-and-hold' if r['Side'] == 'Long' else 'always short'}"
                   f"{' (better)' if better else ''}.")
    return out


# --------------------------------------------------------------------------
# Difference signal on the workbook's own series (weekly table)
# --------------------------------------------------------------------------
def difference_signal(wkly: dict, cfg: dict) -> dict:
    """Bucket each week of the weekly coefficient table by its Difference
    (VIX close minus VIX open, in points) and measure what each of the
    workbook's series did the following week. Win rates are compared with
    all weeks (binomial test), and checked in both halves of the window."""
    from scipy.stats import binomtest

    wc = cfg["vix"]["weekly"]
    edges = list(wc.get("difference_buckets", [-3, -1, 0, 1, 3]))
    extreme = float(wc.get("difference_extreme", 5))
    sym = wc["series"]
    tbl = wkly["table"]
    names = [k for k in sym if k in tbl.columns]
    nxt = tbl[names].shift(-1)
    d = tbl["Difference"]

    def lab(lo, hi):
        f = lambda v: f"{v:+g}" if v else "0"
        if lo is None:
            return f"Below {f(hi)}"
        if hi is None:
            return f"{f(lo)} and up"
        return f"{f(lo)} to {f(hi)}"

    bounds = [(None, edges[0])] + list(zip(edges[:-1], edges[1:])) + [(edges[-1], None)]
    labels = [lab(lo, hi) for lo, hi in bounds]
    bucket = pd.Series(pd.cut(d, [-np.inf] + edges + [np.inf], labels=labels, right=False), index=d.index)
    half = tbl.index[len(tbl) // 2]
    scopes = [(l, bucket == l) for l in labels] + [(f"{extreme:+g} and up (extreme)", d >= extreme)]

    rows, trades = [], []
    for order, (scope, mask) in enumerate(scopes):
        for name in names:
            x = nxt[name][mask].dropna()
            allx = nxt[name].dropna()
            if not len(x):
                continue
            up, base_up = float((x > 0).mean()), float((allx > 0).mean())
            for side, sg in (("Long", 1), ("Short", -1)):
                y = sg * x
                base = float((sg * allx > 0).mean())
                p = float(binomtest(int((y > 0).sum()), len(y), base, alternative="greater").pvalue) if len(y) >= 5 else np.nan
                h1, h2 = y[y.index < half], y[y.index >= half]
                w1, w2 = (float((h1 > 0).mean()) if len(h1) else np.nan), (float((h2 > 0).mean()) if len(h2) else np.nan)
                trades.append({"scope": scope, "order": order, "series": name, "symbol": sym[name], "side": side,
                               "weeks": len(y), "win": float((y > 0).mean()), "normal_win": base,
                               "edge": float((y > 0).mean()) - base, "mean_next": float(y.mean()), "p_value": p,
                               "win_first_half": w1, "win_second_half": w2,
                               "holds_both_halves": bool(np.isfinite(w1) and np.isfinite(w2) and w1 > base and w2 > base),
                               "key": f"{scope}|{side} {name}"})
            rows.append({"bucket": scope, "order": order, "series": name, "symbol": sym[name], "weeks": len(x),
                         "p_up_next": up, "p_up_all": base_up, "mean_next": float(x.mean()),
                         "key": f"{scope}|{name}"})
    trades = pd.DataFrame(trades)
    cur_val = float(d.iloc[-1])
    cur_bucket = str(bucket.iloc[-1])
    current = {"week": tbl.index[-1].date().isoformat(), "difference": cur_val, "bucket": cur_bucket,
               "extreme": bool(cur_val >= extreme), "first_week": tbl.index[0].date().isoformat(),
               "split_week": half.date().isoformat(), "weeks_total": len(tbl)}
    in_scope = [cur_bucket] + ([f"{extreme:+g} and up (extreme)"] if cur_val >= extreme else [])
    ranked = (trades[trades["scope"].isin(in_scope)]
              .sort_values(["order", "win"], ascending=[True, False]))
    return {"buckets": pd.DataFrame(rows), "trades": trades, "now": ranked, "current": current, "labels": labels}


def difference_signal_findings(ds: dict) -> list[str]:
    c = ds["current"]
    out = [f"Latest week ({c['week']}): Difference {c['difference']:+.2f} pts, bucket '{c['bucket']}'."]
    now = ds["now"]
    for scope in now["scope"].unique():
        s = now[now["scope"] == scope]
        vix = s[(s["series"] == "VIX") & (s["side"] == "Short")]
        if len(vix):
            v = vix.iloc[0]
            out.append(f"After Difference {scope.lower()}, VIX was lower the next week {v['win']:.0%} of the time "
                       f"({int(v['weeks'])} weeks; normal week {v['normal_win']:.0%}; halves {v['win_first_half']:.0%} / "
                       f"{v['win_second_half']:.0%}).")
        other = s[(s["series"] != "VIX")].sort_values("win", ascending=False)
        good = other[(other["p_value"] < 0.05) & other["holds_both_halves"]]
        if len(good):
            out.append(f"In that bucket, workbook series with a significant and stable edge: " + "; ".join(
                f"{r['side'].lower()} {r['series']} ({r['symbol']}) won {r['win']:.0%} vs {r['normal_win']:.0%} normally"
                for _, r in good.iterrows()) + ".")
        else:
            b = other.iloc[0]
            out.append(f"No non-VIX workbook series has a significant and stable edge there; the best is "
                       f"{b['side'].lower()} {b['series']} at {b['win']:.0%} vs {b['normal_win']:.0%} normally (p = {b['p_value']:.2f}).")
    return out
