# Quantitative Portfolio Optimization and Risk Model

A modular Python pipeline. It downloads five years of daily prices, estimates
risk and return, solves for the Maximum Sharpe and Minimum Variance long-only
portfolios on returns net of fees and taxes, traces the efficient frontier, and
runs a 10,000-trial, 20-year Monte Carlo of each portfolio. Results go to a
formatted, multi-tab Excel workbook.

```
portfolio-model/
├── config.json        all parameters (tickers, lookback, risk-free rate, frictions, MC)
├── data_loader.py     download, cache, clean, quality-screen, returns
├── optimizer.py       moments, friction model, MVO, frontier, Monte Carlo, risk metrics
├── exporter.py        Excel workbook with formatting and native charts
├── main.py            orchestration and console summary
└── portfolio_model_output.xlsx   generated output
```

## How to run

```bash
cd portfolio-model
python3 -m venv venv
venv/bin/pip install pandas numpy yfinance scipy openpyxl
venv/bin/python main.py
```

Options:

| Flag | Effect |
|---|---|
| `--config path.json` | use another config file |
| `--refresh` | ignore the 24-hour price cache and download fresh data |

The script exits with code 0 on success and 1 on any failure, logging the full
stack trace either way. A full run takes about 5 seconds.

Network note: yfinance needs `query1.finance.yahoo.com`,
`query2.finance.yahoo.com` and `fc.yahoo.com`. In a restricted sandbox, allow
those hosts.

## Changing the assets

Edit the `tickers` list in `config.json`:

```json
"tickers": ["SPY", "QQQ", "GLD", "TLT", "ARKK"]
```

Any Yahoo Finance symbol works (ETFs, stocks, `^VIX`-style indices, `BTC-USD`).
You need at least two. Nothing else has to change, because every module reads
the ticker list from the cleaned data. The cache key includes the tickers, so a
new list triggers a fresh download.

The original spec named BIOM as the high-volatility asset. Its Yahoo series is
unusable: a 1-for-20,000 reverse split in April 2026, quotes jumping between
quantized values ($2.00, $0.20, $2.00), and 68% of trading days unchanged. Fed
to the optimizer, it produced an "expected return" of +1,870% a year. The data
quality screen (below) now drops it automatically with a logged reason, and
ARKK replaces it as a liquid asset with roughly 50% volatility.

## Configuration reference

| Key | Default | Meaning |
|---|---|---|
| `data.lookback_years` | 5 | history window |
| `data.min_coverage` | 0.90 | drop a ticker with prices on fewer than 90% of dates |
| `data.max_ffill_days` | 5 | longest gap filled with the last price |
| `data.max_stale_fraction` | 0.25 | drop a ticker unchanged on more than 25% of days |
| `data.max_abs_daily_return` | 0.75 | drop a ticker with any one-day move above 75% |
| `model.risk_free_rate` | 0.04 | annual, used for Sharpe ratios |
| `model.expected_return_method` | arithmetic | `arithmetic` or `geometric` |
| `model.covariance_method` | ledoit_wolf | `ledoit_wolf` or `sample` |
| `model.weight_bounds` | [0, 1] | per-asset min and max weight |
| `frictions.expense_ratio` | 0.0007 | 0.07% annual management drag |
| `frictions.capital_gains_tax_rate` | 0.15 | tax on net realized rebalancing gains |
| `frictions.rebalance_frequency` | annual | `annual`, `semiannual`, `quarterly`, `monthly` |
| `frictions.tax_loss_carryforward` | true | carry net realized losses into later years |
| `monte_carlo.n_trials` | 10000 | simulated paths |
| `monte_carlo.horizon_years` | 20 | forecast length |
| `monte_carlo.steps_per_year` | 12 | monthly time steps |
| `monte_carlo.distribution` | normal | `normal` or `student_t` (fat tails) |
| `monte_carlo.initial_capital` | 1000000 | starting wealth |

## Methodology

### 1. Data cleaning (`data_loader.py`)

1. Download split- and dividend-adjusted closes (`auto_adjust=True`), retrying
   with exponential backoff (2, 4, 8, 16 s).
2. Coerce to numeric. Set non-positive and infinite prices to NaN.
3. Drop tickers below `min_coverage`.
4. **Quality screen.** Drop tickers whose share of zero-return days exceeds
   `max_stale_fraction` (untraded or halted shells) or that show any one-day
   move above `max_abs_daily_return` (bad split adjustments). One corrupt series
   distorts every covariance term it touches, so dropping it costs less than
   keeping it.
5. Forward-fill gaps of up to `max_ffill_days` (holidays, an incomplete bar for
   today). Then trim to rows where every asset has a price.
6. Simple daily returns r_t = P_t / P_{t-1} - 1. The pipeline stops if any NaN
   survives.

### 2. Moment estimation

Expected returns, annualized with 252 trading days:

    mu_i = 252 * mean(r_i)

Covariance uses **Ledoit-Wolf shrinkage on the correlation matrix**. Returns
are standardized and the LW (2004) optimal intensity delta shrinks the sample
correlation C toward the identity:

    C* = delta * I + (1 - delta) * C
    Sigma = D C* D,   D = diag(annualized sample volatilities)

Shrinking correlations instead of the raw covariance keeps each asset's own
variance exact. That matters when one asset is far more volatile than the rest,
because shrinking toward a scaled identity would inflate the variance of the
calm assets. The intensity used is written to the workbook.

### 3. Friction model

Net expected return of a weight vector w:

    mu_net(w) = w' mu - ER - TaxDrag(w)

* **ER** = 0.07% a year, a flat drag.
* **TaxDrag(w)** is the expected annual tax on rebalancing gains. It uses 4,000
  fixed joint lognormal draws of one-period asset returns R. For each draw, the
  drifted holding w_i(1+R_i) is compared with its target w_i(1+R_p). Overweight
  assets are sold back to target. The realized gain on a sale is
  sell_i * R_i / (1+R_i), taking basis as the start-of-period value. Gains and
  losses net within the period, and the 15% rate applies to the positive net:

      TaxDrag(w) = tau * f * E[ max(0, sum_i sell_i * R_i/(1+R_i)) ]

  f is rebalances per year. The draws are fixed, so the function is
  deterministic and continuous for the optimizer.

The tax term rewards weights that drift less and penalizes pairs of
uncorrelated assets with very different returns, which have to be trimmed
every year. This proxy is used only in the optimizer. The Monte Carlo tracks
true cost basis (section 6), so the leakage it reports is the authoritative
figure.

### 4. Optimization (`optimizer.py`)

All problems are solved with SLSQP under sum(w) = 1 and 0 <= w_i <= 1.

* **Minimum Variance:** minimize w' Sigma w, with an analytic gradient. This
  is a convex QP with one solution.
* **Maximum Sharpe:** maximize (mu_net(w) - r_f) / sqrt(w' Sigma w). The tax
  term makes this non-convex, so it runs from 1 + N + 20 starting points (equal
  weight, each asset tilted, random Dirichlet draws) and keeps the best result.
* **Efficient frontier:** 40 net-return targets, evenly spaced from the Minimum
  Variance return to the highest achievable net return. For each target,
  minimize w' Sigma w subject to mu_net(w) = target, warm-started from the
  previous point. A point counts only if it converges and hits its target to
  within 1e-6.

### 5. Monte Carlo simulation

Each of the 10,000 trials runs 240 monthly steps. Asset log-returns are
correlated, with GBM drift:

    ln(S_{t+dt}/S_t) = (mu - sigma^2/2) dt + L z,   where L L' = Sigma dt

z is standard normal. With `distribution: student_t`, z is multivariate
Student-t with `student_t_df` degrees of freedom, rescaled to unit variance, so
the tails are fatter at the same volatility.

At each step:

1. Holdings grow by their simulated returns.
2. The expense ratio accrues: holdings *= (1 - ER)^dt.
3. On each rebalance date, overweight positions are sold back to target.
   Realized gains use the **average-cost method**, gain = (sold / held) *
   (value - basis), and basis is updated on both sells and buys. Net gains plus
   any loss carryforward are taxed at 15%. The tax is paid pro rata, so weights
   stay at target.

The gross run (no fees, no tax) and the net run reuse the same random seed.
Every trial therefore sees the same market in both, and their difference is
pure friction leakage with no sampling noise mixed in. Both portfolios also
face identical scenarios.

**Percentile paths.** The workbook gives two views:
* *Bands:* the cross-sectional 10th, 50th and 90th percentile of wealth at each
  year. This is the standard fan chart.
* *Representative paths:* the actual simulated trial whose terminal wealth
  ranks at the 10th, 50th or 90th percentile, year by year. A real path
  includes drawdowns that the smooth bands average away.

**Risk metrics:** terminal wealth percentiles (P5 to P95), CAGR percentiles,
probability of loss and of doubling, 1-year VaR and CVaR at 95%, 20-year VaR
and CVaR of dollar loss versus initial capital (a negative value means even the
5% tail ends above the starting capital), the distribution of maximum drawdown
on the monthly path, median fees and taxes paid, and median friction leakage
in dollars and as a share of gross wealth.

### 6. Validation performed

* With monthly rebalancing and no frictions, the simulated median terminal
  wealth of the Minimum Variance portfolio (2,399,427) matches the closed-form
  continuous-rebalancing value exp((w'mu - w'Sigma w / 2) T) (2,391,401) to
  within 0.3%.
* With annual rebalancing the simulated median is higher (2,664,591). That
  gap is real. Between rebalances the portfolio drifts toward its
  faster-growing assets, which is worth about (1/2) * sum_i w_i (mu_i - mu_p)^2,
  or roughly 0.58% a year when GLD (+17.5%) and TLT (-7.3%) are both held.
* Weights are asserted to sum to 1 and be non-negative. Every metric is
  checked for NaN or infinity before export.

## Output workbook (`portfolio_model_output.xlsx`)

| Tab | Contents |
|---|---|
| Summary | gross and net return, drag breakdown, volatility, Sharpe, weights, headline MC results |
| Optimal Weights | weights per portfolio |
| Efficient Frontier | 40 points (net and gross return, volatility, Sharpe, weights) and a chart with both optimal portfolios marked |
| Monte Carlo Metrics | full risk metric table for both portfolios |
| Wealth Paths MaxSharpe / MinVar | P10, P50, P90 bands and representative paths by year, with a chart |
| Asset Statistics | return, CAGR, volatility, Sharpe, max drawdown, skew, kurtosis per asset |
| Correlation & Covariance | shrunk correlation and annualized covariance |
| Assumptions | every config value and the data-cleaning report |

## Limitations

* Expected returns are trailing five-year sample means, which carry large
  estimation error. GLD's +17.5% reflects one strong gold run, and the Max
  Sharpe portfolio leans on it heavily. Treat the weights as a function of that
  window, not a forecast. Shorten or lengthen `lookback_years` to see how
  sensitive they are.
* Returns are nominal, and parameters are held constant over 20 years. The
  model has no regime switching or volatility clustering. `student_t` covers
  fat tails only.
* The tax model applies one rate to all realized gains. It does not split
  short-term from long-term gains, model wash sales, or tax distributions
  inside the funds.
