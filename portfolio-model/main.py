"""Entry point: data -> moments -> optimisation -> frontier -> Monte Carlo -> Excel.

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

import data_loader
import exporter
import optimizer as opt

BASE = Path(__file__).resolve().parent
log = logging.getLogger("portfolio_model")


def load_config(path: Path) -> dict:
    with open(path) as f:
        cfg = json.load(f)
    for section in ("data", "model", "optimization", "frictions", "monte_carlo", "output"):
        if section not in cfg:
            raise KeyError(f"config is missing section '{section}'")
    if not cfg.get("tickers") or len(cfg["tickers"]) < 2:
        raise ValueError("config.tickers must list at least 2 symbols")
    return cfg


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=str(BASE / "config.json"))
    ap.add_argument("--refresh", action="store_true", help="ignore the price cache")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s",
                        datefmt="%H:%M:%S")
    t0 = time.time()
    cfg = load_config(Path(args.config))
    if args.refresh:
        cfg["data"]["use_cache"] = False
    m, fr_cfg, mc_cfg = cfg["model"], cfg["frictions"], cfg["monte_carlo"]
    periods = int(m["trading_days_per_year"])
    rf = float(m["risk_free_rate"])

    # 1. Data --------------------------------------------------------------
    prices, returns, report = data_loader.load_data(cfg["tickers"], cfg["data"], BASE)
    log.info("Clean data: %d rows, %s to %s, tickers %s (ffilled %d cells, dropped %d rows)",
             report["clean_rows"], report["start"], report["end"], report["tickers"],
             report["ffilled_cells"], report["dropped_rows"])
    if report["dropped_tickers"]:
        log.warning("Dropped tickers: %s", report["dropped_tickers"])

    # 2. Moments -----------------------------------------------------------
    mu = opt.expected_returns(returns, periods, m["expected_return_method"])
    cov, shrink = opt.covariance_matrix(returns, periods, m["covariance_method"])
    corr = cov / np.outer(np.sqrt(np.diag(cov)), np.sqrt(np.diag(cov)))
    stats = opt.asset_statistics(prices, returns, mu, cov, rf, periods)
    log.info("Covariance method %s (shrinkage %.3f)", m["covariance_method"], shrink)

    # 3. Optimisation --------------------------------------------------------
    friction = opt.FrictionModel(mu.values, cov.values, fr_cfg["expense_ratio"],
                                 fr_cfg["capital_gains_tax_rate"], fr_cfg["rebalance_frequency"],
                                 int(fr_cfg.get("friction_draws", 4000)), int(fr_cfg.get("seed", 7)))
    engine = opt.MeanVarianceOptimizer(mu, cov, rf, friction, m["weight_bounds"],
                                       cfg["optimization"]["n_random_starts"],
                                       cfg["optimization"]["seed"])
    max_sharpe = engine.max_sharpe()
    min_var = engine.min_variance()
    portfolios = [max_sharpe, min_var]
    for p in portfolios:
        if not np.isclose(p.weights.sum(), 1.0) or (p.weights < -1e-9).any():
            raise AssertionError(f"{p.name}: weights violate constraints")
        if not p.converged:
            log.warning("%s: optimiser reported '%s'", p.name, p.message)

    frontier = engine.efficient_frontier(cfg["optimization"]["frontier_points"],
                                         min_var.weights.values)

    # 4. Monte Carlo ---------------------------------------------------------
    mc_metrics, bands, reps = {}, {}, {}
    for p in portfolios:
        tm = time.time()
        net = opt.simulate(p.weights.values, mu.values, cov.values, mc_cfg, fr_cfg, True)
        gross = opt.simulate(p.weights.values, mu.values, cov.values, mc_cfg, fr_cfg, False)
        mc_metrics[p.name] = opt.risk_metrics(net, gross, mc_cfg)
        bands[p.name], reps[p.name] = opt.percentile_paths(net, mc_cfg["percentiles"])
        log.info("Monte Carlo %s: %d trials x %d yrs in %.1fs", p.name, mc_cfg["n_trials"],
                 mc_cfg["horizon_years"], time.time() - tm)

    # Final NaN guard before anything is written.
    for name, md in mc_metrics.items():
        bad = [k for k, v in md.items() if not np.isfinite(v)]
        if bad:
            raise ValueError(f"Non-finite Monte Carlo metrics for {name}: {bad}")
    if frontier.isna().any().any():
        raise ValueError("NaN in efficient frontier")

    # 5. Export --------------------------------------------------------------
    out = BASE / cfg["output"]["excel_file"]
    exporter.export(out, cfg=cfg, data_report=report, asset_stats=stats, corr=corr, cov=cov,
                    shrinkage=shrink, portfolios=portfolios, frontier=frontier,
                    mc_metrics=mc_metrics, bands=bands, rep_paths=reps)

    # 6. Console summary -----------------------------------------------------
    print("\n" + "=" * 78)
    print(f"{'':28s}{'Max Sharpe':>18s}{'Min Variance':>18s}")
    for label, attr in [("Gross expected return", "gross_return"), ("Tax drag (est.)", "tax_drag"),
                        ("Net expected return", "net_return"), ("Volatility", "volatility")]:
        print(f"{label:28s}{getattr(max_sharpe, attr):>18.2%}{getattr(min_var, attr):>18.2%}")
    print(f"{'Net Sharpe':28s}{max_sharpe.sharpe_net:>18.3f}{min_var.sharpe_net:>18.3f}")
    for t in mu.index:
        print(f"  weight {t:19s}{max_sharpe.weights[t]:>18.2%}{min_var.weights[t]:>18.2%}")
    for k in ["P10 Terminal Wealth", "P50 Terminal Wealth", "P90 Terminal Wealth",
              "Probability of Loss (Terminal < Initial)", "Median Friction Leakage ($)"]:
        a, b = mc_metrics[max_sharpe.name][k], mc_metrics[min_var.name][k]
        fmt = "{:>18.2%}" if "Probability" in k else "{:>18,.0f}"
        print(f"{k[:28]:28s}" + fmt.format(a) + fmt.format(b))
    print("=" * 78)
    print(f"Wrote {out.name} in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logging.getLogger("portfolio_model").exception("Pipeline failed")
        sys.exit(1)
