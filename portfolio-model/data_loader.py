"""Historical price acquisition and cleaning.

Responsibilities
----------------
* Download adjusted daily closes from Yahoo Finance (via yfinance) with retries.
* Cache the raw download locally so repeated runs are fast and reproducible.
* Clean the panel: drop tickers with insufficient history, forward-fill short
  gaps (holidays, halts), trim to a common date range, and reject non-positive
  prices.
* Produce simple daily returns, guaranteed free of NaN / inf.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


class DataError(RuntimeError):
    """Raised when usable price data cannot be produced."""


def _download(tickers: list[str], start: datetime, end: datetime,
              interval: str, retries: int) -> pd.DataFrame:
    import yfinance as yf

    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            raw = yf.download(
                tickers, start=start.strftime("%Y-%m-%d"),
                end=(end + timedelta(days=1)).strftime("%Y-%m-%d"),
                interval=interval, auto_adjust=True, progress=False,
                group_by="column", threads=True,
            )
            if raw is None or raw.empty:
                raise DataError("yfinance returned an empty frame")
            close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
            if isinstance(close, pd.Series):
                close = close.to_frame()
            if close.shape[1] == 1 and len(tickers) == 1:
                close.columns = tickers
            if close.dropna(how="all").empty:
                raise DataError("all downloaded prices are NaN")
            return close
        except Exception as exc:  # network / parsing failures
            last_exc = exc
            wait = 2 ** (attempt + 1)
            if attempt < retries:
                log.warning("Download attempt %d failed (%s); retrying in %ds",
                            attempt + 1, exc, wait)
                time.sleep(wait)
    raise DataError(f"Price download failed after {retries + 1} attempts: {last_exc}")


def fetch_prices(tickers: list[str], data_cfg: dict, base_dir: Path) -> pd.DataFrame:
    """Return a raw (uncleaned) adjusted-close panel, using the cache if fresh."""
    tickers = [t.strip().upper() for t in tickers]
    if len(set(tickers)) != len(tickers):
        raise DataError(f"Duplicate tickers in config: {tickers}")

    end = datetime.now()
    start = end - timedelta(days=int(round(365.25 * data_cfg["lookback_years"])))

    cache_dir = base_dir / data_cfg.get("cache_dir", "data_cache")
    key = "_".join(sorted(tickers)) + f"_{data_cfg['lookback_years']}y_{data_cfg['interval']}"
    cache_file = cache_dir / f"prices_{key}.csv"

    if data_cfg.get("use_cache", True) and cache_file.exists():
        age_h = (time.time() - cache_file.stat().st_mtime) / 3600
        if age_h <= data_cfg.get("cache_max_age_hours", 24):
            log.info("Loading prices from cache %s (%.1fh old)", cache_file.name, age_h)
            cached = pd.read_csv(cache_file, index_col=0, parse_dates=True)
            return cached[[t for t in tickers if t in cached.columns]]

    log.info("Downloading %s from %s to %s", tickers, start.date(), end.date())
    prices = _download(tickers, start, end, data_cfg["interval"],
                       int(data_cfg.get("download_retries", 4)))
    prices = prices.reindex(columns=[t for t in tickers if t in prices.columns])

    if data_cfg.get("use_cache", True):
        cache_dir.mkdir(parents=True, exist_ok=True)
        prices.to_csv(cache_file)
    return prices


def clean_prices(prices: pd.DataFrame, data_cfg: dict) -> tuple[pd.DataFrame, dict]:
    """Clean a raw price panel. Returns (clean_prices, report)."""
    report: dict = {"raw_rows": len(prices), "dropped_tickers": {}, "ffilled_cells": 0}

    prices = prices.copy()
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    prices = prices[~prices.index.duplicated(keep="last")].sort_index()
    prices = prices.apply(pd.to_numeric, errors="coerce")
    prices = prices.replace([np.inf, -np.inf], np.nan)
    prices = prices.mask(prices <= 0)  # non-positive prices are data errors

    # Drop calendar rows where no ticker traded.
    prices = prices.dropna(how="all")
    if prices.empty:
        raise DataError("No price rows after removing empty dates")

    # Coverage filter: a ticker missing too much of the window is unusable.
    min_cov = float(data_cfg.get("min_coverage", 0.9))
    coverage = prices.notna().mean()
    for t, cov in coverage.items():
        if cov < min_cov:
            report["dropped_tickers"][t] = f"coverage {cov:.1%} < {min_cov:.0%}"
            log.warning("Dropping %s: only %.1f%% of dates have prices", t, cov * 100)
    prices = prices.loc[:, coverage >= min_cov]
    if prices.shape[1] < 2:
        raise DataError(f"Need at least 2 usable tickers, have {list(prices.columns)}")

    # Quality screen: stale quotes and impossible one-day moves indicate an
    # untraded shell or a mis-adjusted split, either of which corrupts the
    # moment estimates far more than dropping the asset does.
    max_stale = float(data_cfg.get("max_stale_fraction", 0.25))
    max_move = float(data_cfg.get("max_abs_daily_return", 0.75))
    for t in list(prices.columns):
        s = prices[t].dropna()
        r = s.pct_change().dropna()
        stale = float((r == 0).mean()) if len(r) else 1.0
        worst = float(r.abs().max()) if len(r) else 0.0
        reason = None
        if stale > max_stale:
            reason = f"stale prices: {stale:.0%} of days unchanged (> {max_stale:.0%})"
        elif worst > max_move:
            reason = f"implausible one-day move of {worst:.0%} (> {max_move:.0%}); likely split/data error"
        if reason:
            report["dropped_tickers"][t] = reason
            log.warning("Dropping %s: %s", t, reason)
            prices = prices.drop(columns=t)
    if prices.shape[1] < 2:
        raise DataError(f"Need at least 2 usable tickers after quality screen, have {list(prices.columns)}")

    # Forward-fill short gaps only (a stale price for > N days is not a price).
    limit = int(data_cfg.get("max_ffill_days", 5))
    before = prices.isna().sum().sum()
    prices = prices.ffill(limit=limit)
    report["ffilled_cells"] = int(before - prices.isna().sum().sum())

    # Trim to the window where every asset has a price (leading NaNs from late
    # listings, trailing NaNs from today's incomplete bar, long gaps).
    n_before = len(prices)
    prices = prices.dropna(how="any")
    report["dropped_rows"] = int(n_before - len(prices))
    if len(prices) < 252:
        raise DataError(f"Only {len(prices)} complete rows remain; need >= 252")

    report["clean_rows"] = len(prices)
    report["start"] = prices.index.min().date().isoformat()
    report["end"] = prices.index.max().date().isoformat()
    report["tickers"] = list(prices.columns)
    return prices, report


def compute_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Simple daily returns with NaN/inf guaranteed absent."""
    rets = prices.pct_change().iloc[1:]
    rets = rets.replace([np.inf, -np.inf], np.nan)
    if rets.isna().any().any():
        bad = rets.isna().sum()
        raise DataError(f"NaN returns after cleaning: {bad[bad > 0].to_dict()}")
    return rets


def load_data(tickers: list[str], data_cfg: dict, base_dir: Path):
    """Full pipeline: fetch -> clean -> returns."""
    raw = fetch_prices(tickers, data_cfg, base_dir)
    missing = sorted(set(t.upper() for t in tickers) - set(raw.columns))
    prices, report = clean_prices(raw, data_cfg)
    for t in missing:
        report["dropped_tickers"][t] = "no data returned by Yahoo Finance"
    returns = compute_returns(prices)
    return prices, returns, report
