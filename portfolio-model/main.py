"""Entry point.

Base model:  data -> moments -> optimisation -> frontier -> Monte Carlo
VIX model:   VIX regimes -> regime risk -> crisis-constrained portfolio ->
             regime-switching Monte Carlo -> stress test -> VIX rule backtests ->
             VIXY hedge sizing -> signal tests -> weekly coefficient table
Output:      one Excel workbook, VIX Dashboard first.

Usage:  venv/bin/python main.py [--config config.json] [--refresh]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import alerts
import dashboard_data
import margin
import data_loader
import exporter
import optimizer as opt
import vix_model as vm

BASE = Path(__file__).resolve().parent
log = logging.getLogger("portfolio_model")


def load_config(path: Path) -> dict:
    with open(path) as f:
        cfg = json.load(f)
    for section in ("data", "model", "optimization", "frictions", "monte_carlo", "vix", "output"):
        if section not in cfg:
            raise KeyError(f"config is missing section '{section}'")
    if not cfg.get("tickers") or len(cfg["tickers"]) < 2:
        raise ValueError("config.tickers must list at least 2 symbols")
    return cfg


def run_mc(p, mu, cov, mc_cfg, fr_cfg, regime=None):
    net = opt.simulate(p.weights.values, mu, cov, mc_cfg, fr_cfg, True, regime)
    gross = opt.simulate(p.weights.values, mu, cov, mc_cfg, fr_cfg, False, regime)
    metrics = opt.risk_metrics(net, gross, mc_cfg)
    if regime is not None:
        for k, lab in enumerate(regime.labels):
            metrics[f"Avg share of months in {lab}"] = float(net.regime_share[:, k].mean())
    bands, reps = opt.percentile_paths(net, mc_cfg["percentiles"])
    return metrics, bands, reps


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=str(BASE / "config.json"))
    ap.add_argument("--refresh", action="store_true", help="ignore the price cache")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s",
                        datefmt="%H:%M:%S")
    for noisy in ("yfinance", "peewee", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.CRITICAL)
    t0 = time.time()
    cfg = load_config(Path(args.config))
    if args.refresh:
        cfg["data"]["force_refresh"] = True   # download fresh, then update the cache
    m, fr_cfg, mc_cfg, vc = cfg["model"], cfg["frictions"], cfg["monte_carlo"], cfg["vix"]
    periods = int(m["trading_days_per_year"])
    rf = float(m["risk_free_rate"])

    # 1. Base data ---------------------------------------------------------
    prices, returns, report = data_loader.load_data(cfg["tickers"], cfg["data"], BASE)
    log.info("Base data: %d rows, %s to %s, tickers %s", report["clean_rows"],
             report["start"], report["end"], report["tickers"])
    if report["dropped_tickers"]:
        log.warning("Dropped tickers: %s", report["dropped_tickers"])

    # 2. Moments -----------------------------------------------------------
    mu = opt.expected_returns(returns, periods, m["expected_return_method"])
    cov, shrink = opt.covariance_matrix(returns, periods, m["covariance_method"])
    corr = cov / np.outer(np.sqrt(np.diag(cov)), np.sqrt(np.diag(cov)))
    stats = opt.asset_statistics(prices, returns, mu, cov, rf, periods)

    # 3. VIX data and regimes ---------------------------------------------
    vd = vm.load(cfg, list(mu.index), BASE)
    missing = sorted(set(mu.index) - set(vd.asset_returns.columns))
    if missing:
        raise data_loader.DataError(
            f"{missing} lack {vc['regime_lookback_years']}y of clean history for the regime "
            "model; shorten vix.regime_lookback_years or change the tickers")
    rm = vm.fit_regimes(vd, cfg)
    rm_raw = rm
    if vc.get("regime_calibrate_to_base", True):
        rm = vm.calibrate_to_base(rm, cov)
    state = vm.current_state(vd, rm)
    log.info("VIX %.2f on %s: %s regime, %s", state["VIX close"], state["As of"],
             state["Current regime"], state["Term structure"])

    # 4. Optimisation ------------------------------------------------------
    friction = opt.FrictionModel(mu.values, cov.values, fr_cfg["expense_ratio"],
                                 fr_cfg["capital_gains_tax_rate"], fr_cfg["rebalance_frequency"],
                                 int(fr_cfg.get("friction_draws", 4000)), int(fr_cfg.get("seed", 7)))
    engine = opt.MeanVarianceOptimizer(mu, cov, rf, friction, m["weight_bounds"],
                                       cfg["optimization"]["n_random_starts"],
                                       cfg["optimization"]["seed"])
    tick = list(mu.index)
    crisis_cov = rm.cov[rm.labels[-1]].loc[tick, tick].values
    mix_cov = sum(rm.stationary[k] * rm.cov[lab].loc[tick, tick].values
                  for k, lab in enumerate(rm.labels))
    portfolios = [engine.max_sharpe(), engine.min_variance(),
                  engine.max_sharpe_constrained("VIX Crisis-Constrained", cov.values, crisis_cov,
                                                float(vc["crisis_vol_cap"]))]
    for p in portfolios:
        if not np.isclose(p.weights.sum(), 1.0) or (p.weights < -1e-9).any():
            raise AssertionError(f"{p.name}: weights violate constraints")
        p.extra["crisis_vol"] = float(np.sqrt(p.weights.values @ crisis_cov @ p.weights.values))
        p.extra["regime_mix_vol"] = float(np.sqrt(p.weights.values @ mix_cov @ p.weights.values))
    frontier = engine.efficient_frontier(cfg["optimization"]["frontier_points"],
                                         portfolios[1].weights.values)

    # 5. Monte Carlo: stationary and regime-switching ----------------------
    proc = vm.regime_process(rm, mu, cfg)
    mc, mc_regime = {}, {}
    for p in portfolios:
        tm = time.time()
        mc[p.name] = run_mc(p, mu.values, cov.values, mc_cfg, fr_cfg)
        mc_regime[p.name] = run_mc(p, mu.values, cov.values, mc_cfg, fr_cfg, proc)
        log.info("Monte Carlo %s (stationary + regime): %.1fs", p.name, time.time() - tm)

    # 6. VIX analytics ------------------------------------------------------
    stress = vm.stress_test(portfolios, rm, float(mc_cfg["initial_capital"]), state["Current regime"])
    bt, curves = vm.backtest_overlays(vd, rm, portfolios, cfg)
    hedge = vm.hedge_sizing(vd, rm, portfolios[0], engine, cfg)
    sig = vm.signal_tests(vd, rm)
    wkly = vm.weekly_coefficients(vd, cfg)
    notes = vm.findings(state, rm, bt, hedge, sig, wkly, vd, vc["hedge_asset"])
    diff = vm.difference_study(cfg, BASE)
    dsig = vm.difference_signal(wkly, cfg)
    notes += vm.difference_signal_findings(dsig)
    al = alerts.build(wkly, cfg, vd.weekly_close)
    mg = margin.build(wkly, cfg, vd.weekly_close)
    _open = al["log"][(al["log"]["rule_id"] == "sco-long") & (al["log"]["outcome"] == "open")] if len(al["log"]) else al["log"]
    _entry = float(vd.weekly_close["SCO"].dropna()[lambda s: s.index <= pd.Timestamp(_open.iloc[0]["week"])].iloc[-1]) if len(_open) else None
    sco_exit = alerts.sco_exit_plan(wkly, cfg, vd.weekly_close, _entry)
    notes += vm.difference_findings(diff)

    # NaN guard on everything the model computed.
    for name, (md, _, _) in list(mc.items()) + list(mc_regime.items()):
        bad = [k for k, v in md.items() if not np.isfinite(v)]
        if bad:
            raise ValueError(f"Non-finite Monte Carlo metrics for {name}: {bad}")
    for label, df in (("frontier", frontier), ("stress test", stress), ("backtest", bt),
                      ("hedge sizing", hedge)):
        num = df.select_dtypes("number")
        if not np.isfinite(num.values).all():
            raise ValueError(f"Non-finite values in {label}")

    # 7. Export ---------------------------------------------------------------
    out = BASE / cfg["output"]["excel_file"]
    exporter.export(out, cfg=cfg, data_report=report, asset_stats=stats, corr=corr, cov=cov,
                    shrinkage=shrink, portfolios=portfolios, frontier=frontier, mc=mc,
                    mc_regime=mc_regime,
                    vix=dict(state=state, regimes=vm.regime_table(vd, rm_raw),
                             trans_1d=vm.transition_table(rm, 1), trans_1m=vm.transition_table(rm, 21, empirical=True),
                             trans_1m_markov=vm.transition_table(rm, 21),
                             stress=stress, backtest=bt, curves=curves, hedge=hedge, signals=sig,
                             weekly=wkly, iv_hv=vm.iv_hv(vd), difference=diff, diff_signal=dsig, alerts=al, margin=mg, findings=notes, vix=vd.vix, vix3m=vd.vix3m,
                             labels=rm.labels, thresholds=rm.thresholds))

    vix_bundle = dict(state=state, regimes=vm.regime_table(vd, rm_raw), stress=stress, labels=rm.labels,
                      vix=vd.vix, vix3m=vd.vix3m, difference=diff, diff_signal=dsig, alerts=al, margin=mg, sco_exit=sco_exit, weekly=wkly, iv_hv=vm.iv_hv(vd), prices=vd.weekly_close,
                      findings=notes)
    dash_file = dashboard_data.write(BASE / "dashboard_data" / "vix_model_data.json", portfolios=portfolios,
                                     mc_regime=mc_regime, vix=vix_bundle, cfg=cfg)
    log.info("Dashboard data: %s (%.0f KB)", dash_file.name, dash_file.stat().st_size / 1024)
    _ent = None
    if len(_open):
        _wk = pd.Timestamp(_open.iloc[0]["week"])
        _ent = (_wk.date().isoformat(), (_wk + pd.Timedelta(days=7)).date().isoformat())
    exit_text = alerts.exit_message(sco_exit, _ent[0] if _ent else None, _ent[1] if _ent else None, _entry)
    _lw = al["now"].get("last_week")
    _held = al["log"][(al["log"]["rule_id"] == "sco-long") & (al["log"]["week"] == _lw)] if (_lw and len(al["log"])) else []
    if len(_held):
        exit_text = (f"EXIT TODAY: if you still hold the SCO bought at the {_lw} close, sell it at today's close "
                     f"(unless it already hit its take-profit).\n" + exit_text).strip()
    alert_text = alerts.message(al) + "\n" + margin.message(mg) + ("\n" + exit_text if exit_text else "")
    (BASE / "dashboard_data" / "alert.txt").write_text(alert_text + "\n")

    # 8. Console summary ------------------------------------------------------
    w = 20
    names = [p.name for p in portfolios]
    print("\n" + "=" * (30 + w * len(names)))
    print("VIX DASHBOARD")
    for n_ in notes:
        print(" - " + n_)
    print("-" * (30 + w * len(names)))
    print(f"{'':30s}" + "".join(f"{n[:w - 2]:>{w}s}" for n in names))
    for label, attr in [("Net expected return", "net_return"), ("Volatility (base)", "volatility")]:
        print(f"{label:30s}" + "".join(f"{getattr(p, attr):>{w}.2%}" for p in portfolios))
    print(f"{'Volatility in Crisis regime':30s}" + "".join(f"{p.extra['crisis_vol']:>{w}.2%}" for p in portfolios))
    print(f"{'Net Sharpe':30s}" + "".join(f"{p.sharpe_net:>{w}.3f}" for p in portfolios))
    for t in tick:
        print(f"  weight {t:21s}" + "".join(f"{p.weights[t]:>{w}.2%}" for p in portfolios))
    for k in ["P10 Terminal Wealth", "P50 Terminal Wealth", "P90 Terminal Wealth"]:
        print(f"{k + ' (static)':30s}" + "".join(f"{mc[n][0][k]:>{w},.0f}" for n in names))
        print(f"{k + ' (VIX regime)':30s}" + "".join(f"{mc_regime[n][0][k]:>{w},.0f}" for n in names))
    print("=" * (30 + w * len(names)))
    print("\nALERT\n" + alert_text)
    print(f"Wrote {out.name} in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logging.getLogger("portfolio_model").exception("Pipeline failed")
        sys.exit(1)
